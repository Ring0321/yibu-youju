"""Finite synthetic probe, not a physical device model or production verifier."""

from dataclasses import dataclass, replace
from itertools import combinations, product
from typing import Callable


@dataclass(frozen=True, order=True)
class World:
    visible_clear: bool
    seated_ok: bool
    other_ok: bool

    @property
    def function_ok(self) -> bool:
        return self.visible_clear and self.seated_ok and self.other_ok


UNIVERSE = frozenset(World(*values) for values in product((False, True), repeat=3))
FIELDS = frozenset({"visible_clear", "seated_ok", "other_ok"})
DEPENDENCIES = {name: frozenset({name}) for name in FIELDS}
DEPENDENCIES.update({"function_ok": FIELDS, "model": frozenset()})


def value(world: World, predicate: str) -> bool | str:
    if predicate == "model":
        return "SYNTHETIC_DEVICE"
    return getattr(world, predicate)


@dataclass(frozen=True)
class Evidence:
    event_id: str
    source_group: str
    device_id: str
    predicate: str
    observed_value: bool | str
    acquired_seq: int | None
    grade: str = "fixture_verified"


@dataclass(frozen=True)
class Action:
    event_id: str
    seq: int
    may_affect: frozenset[str]


class Verifier:
    def __init__(self, states=UNIVERSE, device_id="toy-1"):
        self.reachable = frozenset(states)
        self.device_id = device_id
        self.seq = 0
        self.evidence: dict[str, Evidence] = {}
        self.actions: dict[str, Action] = {}
        self.out_of_scope = False

    def add_evidence(self, evidence: Evidence) -> None:
        if evidence.predicate not in DEPENDENCIES:
            raise ValueError("Unknown predicate")
        if evidence.event_id in self.actions:
            raise ValueError("Event id already used by an action")
        existing = self.evidence.get(evidence.event_id)
        if existing is not None and existing != evidence:
            raise ValueError("Conflicting duplicate event id")
        self.evidence[evidence.event_id] = evidence

    def active(self) -> tuple[Evidence, ...]:
        result = []
        for evidence in self.evidence.values():
            if evidence.device_id != self.device_id:
                continue
            # This grade is an oracle fixture assumption, not VLM confidence.
            if evidence.grade != "fixture_verified":
                continue
            if evidence.acquired_seq is None or evidence.acquired_seq > self.seq:
                continue
            deps = DEPENDENCIES[evidence.predicate]
            if any(action.seq > evidence.acquired_seq and deps & action.may_affect
                   for action in self.actions.values()):
                continue
            result.append(evidence)
        return tuple(result)

    def belief(self) -> frozenset[World]:
        return frozenset(world for world in self.reachable
                         if all(value(world, item.predicate) == item.observed_value
                                for item in self.active()))

    def source_group_count(self) -> int:
        return len({item.source_group for item in self.active()})

    def record_action(self, event_id: str, may_affect: frozenset[str]) -> None:
        if not may_affect <= FIELDS:
            raise ValueError("Unknown action effect")
        if event_id in self.evidence:
            raise ValueError("Event id already used by evidence")
        existing = self.actions.get(event_id)
        if existing is not None:
            if existing.may_affect != may_affect:
                raise ValueError("Conflicting duplicate action id")
            return
        prior = self.belief()
        if not prior:
            raise ValueError("Resolve conflicting evidence before planning")
        # Preserve no execution, partial execution and full execution possibilities.
        names = sorted(may_affect)
        self.reachable = frozenset(
            replace(world, **dict(zip(names, outcomes)))
            for world in prior
            for outcomes in product((False, True), repeat=len(names))
        )
        self.seq += 1
        self.actions[event_id] = Action(event_id, self.seq, may_affect)

    def closure_grade(self) -> str:
        states = self.belief()
        if not states:
            return "CONFLICT"
        if self.out_of_scope:
            return "OUT_OF_SCOPE"
        # Component observations alone are not the functional-test contract.
        functional_test = any(item.predicate == "function_ok"
                              and item.observed_value is True for item in self.active())
        if functional_test and all(world.function_ok for world in states):
            return "MODEL_SUPPORTED_IN_FIXTURE"
        return "NOT_VERIFIED"


def opposite_pairs(states: frozenset[World]) -> frozenset[tuple[World, World]]:
    return frozenset((left, right) for left, right in combinations(sorted(states), 2)
                     if left.function_ok != right.function_ok)


@dataclass(frozen=True)
class Check:
    name: str
    cost: float
    outcomes: Callable[[World], frozenset[str]]
    available: bool = True
    mutates_state: bool = False


def next_check(states: frozenset[World], checks: tuple[Check, ...]) -> str | None:
    pair_count = len(opposite_pairs(states))
    best = None
    best_score = 0.0
    for check in sorted(checks, key=lambda item: item.name):
        if not check.available or check.mutates_state or check.cost <= 0:
            continue
        outcomes = {outcome for world in states for outcome in check.outcomes(world)}
        if not outcomes or any(not check.outcomes(world) for world in states):
            continue
        worst_remaining = max(
            len(opposite_pairs(frozenset(world for world in states
                                        if outcome in check.outcomes(world))))
            for outcome in outcomes
        )
        score = (pair_count - worst_remaining) / check.cost
        if score > best_score:
            best, best_score = check.name, score
    return best


def guard_counterexamples(requirements: dict[str, bool | str]) -> tuple[World, ...]:
    return tuple(world for world in sorted(UNIVERSE)
                 if all(value(world, name) == expected
                        for name, expected in requirements.items())
                 and not world.function_ok)


def deterministic_check(name: str, predicate: str, cost=1.0, available=True) -> Check:
    return Check(name, cost, lambda world: frozenset({str(value(world, predicate))}),
                 available=available)
