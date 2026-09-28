"""A reference-only acknowledgement flow; no model, repair, or warranty decisions."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from psycopg.types.json import Jsonb

from g0.database import connect


class ProbeState(TypedDict, total=False):
    run_id: str
    input_event_id: int
    phase: str


def await_input(state: ProbeState) -> dict:
    reference = interrupt(
        {"kind": "g0_acknowledgement_only", "run_id": state["run_id"]}
    )
    if not isinstance(reference, dict) or type(reference.get("event_id")) is not int:
        raise ValueError("Resume requires a stored input event reference")
    with connect() as conn:
        event = conn.execute(
            "SELECT id FROM g0_service.events WHERE id = %s AND run_id = %s AND kind = 'input_received'",
            (reference["event_id"], state["run_id"]),
        ).fetchone()
    if not event:
        raise ValueError("Resume event does not belong to this run")
    return {"input_event_id": event["id"], "phase": "INPUT_RECEIVED"}


def record_result(state: ProbeState) -> dict:
    with connect() as conn:
        event = conn.execute(
            "SELECT command_id, payload FROM g0_service.events WHERE id = %s AND run_id = %s AND kind = 'input_received'",
            (state["input_event_id"], state["run_id"]),
        ).fetchone()
        if not event:
            raise ValueError("Authoritative input is missing")
        conn.execute(
            """INSERT INTO g0_service.events (run_id, command_id, kind, payload)
               VALUES (%s, %s, 'probe_completed', %s)
               ON CONFLICT (command_id, kind) DO NOTHING""",
            (
                state["run_id"],
                event["command_id"],
                Jsonb(
                    {
                        "acknowledged": event["payload"]["acknowledged"],
                        "scope": "infrastructure_probe_only",
                    }
                ),
            ),
        )
        conn.execute(
            "UPDATE g0_service.runs SET status = 'COMPLETED' WHERE id = %s",
            (state["run_id"],),
        )
    return {"phase": "COMPLETED"}


def build_graph(checkpointer):
    return (
        StateGraph(ProbeState)
        .add_node("await_input", await_input)
        .add_node("record_result", record_result)
        .add_edge(START, "await_input")
        .add_edge("await_input", "record_result")
        .add_edge("record_result", END)
        .compile(checkpointer=checkpointer)
    )
