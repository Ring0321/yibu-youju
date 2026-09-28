from uuid import UUID

from psycopg.types.json import Jsonb

from g0.database import QUEUE_SCHEMA, connect
from g0.queue import TASK_NAME, make_queue


class ConflictError(ValueError):
    pass


def submit(run_id: UUID, command_id: UUID, kind: str, payload: dict) -> dict:
    if kind not in {"start", "resume"}:
        raise ValueError("Unexpected command kind")
    with connect(schema=QUEUE_SCHEMA) as conn:
        # Serialize submission keys before looking them up; same ID with new content is an error.
        conn.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (int.from_bytes(command_id.bytes[:8], signed=True),),
        )
        existing = conn.execute(
            "SELECT * FROM g0_service.commands WHERE id = %s", (command_id,)
        ).fetchone()
        if existing:
            if (
                existing["run_id"] != run_id
                or existing["kind"] != kind
                or existing["payload"] != payload
            ):
                raise ConflictError("Command ID already used with different content")
            return {"job_id": existing["job_id"], "duplicate": True}
        if kind == "start":
            inserted = conn.execute(
                "INSERT INTO g0_service.runs (id, prompt) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id",
                (run_id, payload["prompt"]),
            ).fetchone()
            if not inserted:
                raise ConflictError(
                    "Run already exists; replay the original command ID"
                )
        else:
            run = conn.execute(
                "SELECT status FROM g0_service.runs WHERE id = %s FOR UPDATE", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError("Run not found")
            if run["status"] != "WAITING_INPUT":
                raise ConflictError("Run is not waiting for input")
            if conn.execute(
                "SELECT id FROM g0_service.commands WHERE run_id = %s AND kind = 'resume'",
                (run_id,),
            ).fetchone():
                raise ConflictError("An input command is already queued")
        conn.execute(
            "INSERT INTO g0_service.commands (id, run_id, kind, payload) VALUES (%s, %s, %s, %s)",
            (command_id, run_id, kind, Jsonb(payload)),
        )
        conn.execute(
            "INSERT INTO g0_service.events (run_id, command_id, kind, payload) VALUES (%s, %s, %s, %s)",
            (
                run_id,
                command_id,
                "intent_received" if kind == "start" else "input_received",
                Jsonb(payload),
            ),
        )
        queue = make_queue(synchronous=True)
        with queue.open():
            job_id = (
                queue.tasks[TASK_NAME]
                .configure(connection=conn, lock=str(run_id))
                .defer(command_id=str(command_id))
            )
        conn.execute(
            "UPDATE g0_service.commands SET job_id = %s WHERE id = %s",
            (job_id, command_id),
        )
        return {"job_id": job_id, "duplicate": False}


def read_run(run_id: UUID) -> dict:
    with connect() as conn:
        run = conn.execute(
            "SELECT id, status FROM g0_service.runs WHERE id = %s", (run_id,)
        ).fetchone()
        if not run:
            raise KeyError("Run not found")
        events = conn.execute(
            "SELECT id, kind, payload FROM g0_service.events WHERE run_id = %s ORDER BY id",
            (run_id,),
        ).fetchall()
        return {
            "run_id": str(run["id"]),
            "status": run["status"],
            "events": events,
            "scope": "infrastructure_probe_only",
        }
