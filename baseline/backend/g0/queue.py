from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from procrastinate import App, PsycopgConnector, SyncPsycopgConnector
from psycopg.types.json import Jsonb

from g0.database import CHECKPOINT_SCHEMA, QUEUE_SCHEMA, connect, database_url
from g0.workflow import build_graph

TASK_NAME = "g0.advance"
QUEUE_NAME = "g0_interactive"
HEARTBEAT_SECONDS = 1.0
STALLED_SECONDS = 3.0


def advance(command_id: str) -> None:
    with connect(autocommit=True) as conn:
        command = conn.execute(
            "SELECT * FROM g0_service.commands WHERE id = %s", (command_id,)
        ).fetchone()
        if not command:
            raise ValueError("Unknown command")
        run_id = str(command["run_id"])
        lock_key = int.from_bytes(command["run_id"].bytes[:8], signed=True)
        # G0 serializes one run. Production generation fencing remains a separate gate.
        conn.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
        try:
            command = conn.execute(
                "SELECT * FROM g0_service.commands WHERE id = %s", (command_id,)
            ).fetchone()
            if command["processed"]:
                return
            with connect(schema=CHECKPOINT_SCHEMA, autocommit=True) as checkpoint_conn:
                graph = build_graph(PostgresSaver(checkpoint_conn))
                config = {"configurable": {"thread_id": run_id}}
                snapshot = graph.get_state(config)
                if command["kind"] == "start":
                    if not snapshot.values:
                        graph.invoke({"run_id": run_id, "phase": "PENDING"}, config)
                    snapshot = graph.get_state(config)
                    if snapshot.next != ("await_input",):
                        raise RuntimeError("Start must leave a waiting checkpoint")
                    with conn.transaction():
                        conn.execute(
                            "UPDATE g0_service.runs SET status = 'WAITING_INPUT' WHERE id = %s",
                            (run_id,),
                        )
                        conn.execute(
                            """INSERT INTO g0_service.events (run_id, command_id, kind, payload)
                               VALUES (%s, %s, 'waiting_input', %s)
                               ON CONFLICT (command_id, kind) DO NOTHING""",
                            (
                                run_id,
                                command_id,
                                Jsonb(
                                    {
                                        "checkpoint_id": snapshot.config[
                                            "configurable"
                                        ]["checkpoint_id"]
                                    }
                                ),
                            ),
                        )
                        conn.execute(
                            "UPDATE g0_service.commands SET processed = true WHERE id = %s",
                            (command_id,),
                        )
                else:
                    event = conn.execute(
                        "SELECT id FROM g0_service.events WHERE command_id = %s AND kind = 'input_received'",
                        (command_id,),
                    ).fetchone()
                    if not event or not snapshot.values:
                        raise RuntimeError(
                            "Resume requires an input event and saved checkpoint"
                        )
                    if snapshot.next:
                        graph.invoke(Command(resume={"event_id": event["id"]}), config)
                    completed = conn.execute(
                        "SELECT id FROM g0_service.events WHERE command_id = %s AND kind = 'probe_completed'",
                        (command_id,),
                    ).fetchone()
                    if not completed:
                        raise RuntimeError(
                            "Completion cannot be inferred from a checkpoint alone"
                        )
                    conn.execute(
                        "UPDATE g0_service.commands SET processed = true WHERE id = %s",
                        (command_id,),
                    )
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))


def make_queue(*, synchronous: bool = False) -> App:
    connector = SyncPsycopgConnector if synchronous else PsycopgConnector
    app = App(
        connector=connector(
            conninfo=database_url(),
            min_size=0,
            max_size=3,
            kwargs={"options": f"-c search_path={QUEUE_SCHEMA}", "connect_timeout": 5},
        )
    )
    app.task(name=TASK_NAME, queue=QUEUE_NAME, retry=False)(advance)
    return app


if __name__ == "__main__":
    make_queue().run_worker(
        queues=[QUEUE_NAME],
        concurrency=1,
        wait=False,
        update_heartbeat_interval=HEARTBEAT_SECONDS,
        stalled_worker_timeout=STALLED_SECONDS,
    )
