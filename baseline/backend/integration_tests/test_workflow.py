import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from g0.database import CHECKPOINT_SCHEMA, QUEUE_SCHEMA, connect, database_url
from g0.migrate import migrate
from g0.queue import STALLED_SECONDS, TASK_NAME, make_queue
from g0.workflow import build_graph


def start(api):
    run_id, command_id = uuid4(), uuid4()
    body = {"command_id": str(command_id), "prompt": "G0 acknowledgement fixture"}
    response = api.post(f"/g0/runs/{run_id}/start", json=body)
    assert response.status_code == 202, response.text
    return run_id, command_id, body, response.json()


def snapshot(run_id):
    with connect(schema=CHECKPOINT_SCHEMA, autocommit=True) as conn:
        return build_graph(PostgresSaver(conn)).get_state(
            {"configurable": {"thread_id": str(run_id)}}
        )


def job(job_id):
    with connect(schema=QUEUE_SCHEMA) as conn:
        return conn.execute(
            "SELECT status, attempts FROM procrastinate_jobs WHERE id = %s", (job_id,)
        ).fetchone()


@pytest.mark.parametrize(
    "env",
    [
        {"YIBU_G0_PROBE": "0"},
        {"DATABASE_URL": "postgresql://yibu_g0@localhost/yibu_g0_test"},
        {"DATABASE_URL": "postgresql://yibu_g0@db/customer_data"},
        {"DATABASE_URL": "postgresql://postgres@db/yibu_g0_test"},
        {"DATABASE_URL": "postgresql://yibu_g0@db:5433/yibu_g0_test"},
        {"DATABASE_URL": "postgresql://yibu_g0@db/yibu_g0_test?host=other"},
        {"LANGSMITH_TRACING": "true"},
        {"LANGCHAIN_TRACING_V2": "true"},
    ],
)
def test_refuses_unsafe_target(monkeypatch, env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        database_url()


def test_migration_idempotent_and_keeps_records(api):
    run_id, _, _, _ = start(api)
    first, second = migrate(), migrate()
    assert first == second
    assert api.get(f"/g0/runs/{run_id}").json()["status"] == "PENDING"
    with connect() as conn:
        schemas = conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'g0_%'"
        ).fetchall()
        assert {row["schema_name"] for row in schemas} == {
            "g0_service",
            "g0_checkpoints",
            "g0_jobs",
        }


def test_http_to_worker_pause_and_resume_in_new_process(api, worker, record_property):
    run_id, command_id, body, original = start(api)
    assert job(original["job_id"])["status"] == "todo"
    first_pid = worker()
    waiting = api.get(f"/g0/runs/{run_id}").json()
    assert waiting["status"] == "WAITING_INPUT"
    checkpoint = snapshot(run_id)
    assert checkpoint.next == ("await_input",)
    assert checkpoint.values["run_id"] == str(run_id)
    assert job(original["job_id"])["status"] == "succeeded"
    prior_job = job(original["job_id"])
    time.sleep(STALLED_SECONDS + 1)
    idle_pid = worker()
    assert job(original["job_id"]) == prior_job
    assert api.get(f"/g0/runs/{run_id}").json() == waiting
    replay = api.post(f"/g0/runs/{run_id}/start", json=body)
    assert replay.json() == {"job_id": original["job_id"], "duplicate": True}
    resume_id = uuid4()
    resume_body = {"command_id": str(resume_id), "acknowledged": False}
    queued = api.post(f"/g0/runs/{run_id}/resume", json=resume_body)
    assert queued.status_code == 202, queued.text
    second_pid = worker()
    final = api.get(f"/g0/runs/{run_id}").json()
    assert final["status"] == "COMPLETED"
    assert [event["kind"] for event in final["events"]] == [
        "intent_received",
        "waiting_input",
        "input_received",
        "probe_completed",
    ]
    assert final["events"][-1]["payload"] == {
        "acknowledged": False,
        "scope": "infrastructure_probe_only",
    }
    assert job(queued.json()["job_id"])["status"] == "succeeded"
    finished = snapshot(run_id)
    assert not finished.next
    assert (
        finished.config["configurable"]["checkpoint_id"]
        != checkpoint.config["configurable"]["checkpoint_id"]
    )
    queue = make_queue(synchronous=True)
    with queue.open():
        duplicate_job = queue.tasks[TASK_NAME].defer(command_id=str(resume_id))
    duplicate_pid = worker()
    assert job(duplicate_job)["status"] == "succeeded"
    assert api.get(f"/g0/runs/{run_id}").json() == final
    assert (
        api.post(f"/g0/runs/{run_id}/resume", json=resume_body).json()["duplicate"]
        is True
    )
    assert len({first_pid, idle_pid, second_pid, duplicate_pid}) == 4
    record_property("waiting_seconds", STALLED_SECONDS + 1)
    record_property(
        "worker_processes", [first_pid, idle_pid, second_pid, duplicate_pid]
    )
    record_property(
        "saved_checkpoint", checkpoint.config["configurable"]["checkpoint_id"]
    )
    record_property(
        "resumed_checkpoint", finished.config["configurable"]["checkpoint_id"]
    )
    record_property("original_command", str(command_id))


def test_concurrent_duplicate_submission_only_one_job(api):
    run_id, command_id = uuid4(), uuid4()
    body = {"command_id": str(command_id), "prompt": "Concurrent fixture"}
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: api.post(f"/g0/runs/{run_id}/start", json=body), range(2)
            )
        )
    assert [r.status_code for r in responses] == [202, 202]
    assert len({r.json()["job_id"] for r in responses}) == 1
    assert sorted(r.json()["duplicate"] for r in responses) == [False, True]
    assert len(api.get(f"/g0/runs/{run_id}").json()["events"]) == 1


def test_key_reuse_with_different_content_conflicts(api):
    run_id, _, body, _ = start(api)
    response = api.post(
        f"/g0/runs/{run_id}/start", json={**body, "prompt": "Different"}
    )
    assert response.status_code == 409
    assert api.post(f"/g0/runs/{uuid4()}/start", json=body).status_code == 409


def test_unknown_run_early_resume_and_bad_input_are_rejected(api):
    body = {"command_id": str(uuid4()), "acknowledged": True}
    assert api.post(f"/g0/runs/{uuid4()}/resume", json=body).status_code == 404
    run_id, _, _, _ = start(api)
    assert api.post(f"/g0/runs/{run_id}/resume", json=body).status_code == 409
    assert (
        api.post(
            f"/g0/runs/{run_id}/resume", json={**body, "acknowledged": "true"}
        ).status_code
        == 422
    )
    assert (
        api.post(
            f"/g0/runs/{run_id}/resume", json={**body, "trusted": True}
        ).status_code
        == 422
    )


def test_authentication_is_required(api):
    with httpx.Client(base_url=str(api.base_url), timeout=5) as anonymous:
        assert anonymous.get(f"/g0/runs/{uuid4()}").status_code == 401
        assert (
            anonymous.post(
                f"/g0/runs/{uuid4()}/start",
                json={"command_id": str(uuid4()), "prompt": "anonymous"},
            ).status_code
            == 401
        )


def test_enqueue_rolls_back_with_business_write():
    run_id, command_id = uuid4(), uuid4()
    queue = make_queue(synchronous=True)
    with (
        pytest.raises(RuntimeError, match="intentional rollback"),
        queue.open(),
        connect(schema=QUEUE_SCHEMA) as conn,
    ):
        conn.execute(
            "INSERT INTO g0_service.runs (id, prompt) VALUES (%s, 'rollback fixture')",
            (run_id,),
        )
        job_id = (
            queue.tasks[TASK_NAME]
            .configure(connection=conn)
            .defer(command_id=str(command_id))
        )
        raise RuntimeError("intentional rollback")
    with connect() as conn:
        assert not conn.execute(
            "SELECT id FROM g0_service.runs WHERE id = %s", (run_id,)
        ).fetchone()
    assert job(job_id) is None


def test_resume_reference_from_other_run_is_not_accepted(api, worker):
    target, _, _, _ = start(api)
    other, _, _, _ = start(api)
    worker()
    assert (
        api.post(
            f"/g0/runs/{other}/resume",
            json={"command_id": str(uuid4()), "acknowledged": True},
        ).status_code
        == 202
    )
    event_id = api.get(f"/g0/runs/{other}").json()["events"][-1]["id"]
    with connect(schema=CHECKPOINT_SCHEMA, autocommit=True) as conn:
        graph = build_graph(PostgresSaver(conn))
        with pytest.raises(ValueError, match="does not belong"):
            graph.invoke(
                Command(resume={"event_id": event_id}),
                {"configurable": {"thread_id": str(target)}},
            )
    assert api.get(f"/g0/runs/{target}").json()["status"] == "WAITING_INPUT"
