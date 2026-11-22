"""Who may do what. Nothing is allowed unless a registered rule says so."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.core.outcomes import Outcome, Refusal

Role = Literal["OWNER", "ADMIN", "USER"]


@dataclass(frozen=True)
class Actor:
    account_id: int
    name: str
    role: Role


Rule = Callable[[Actor, object | None], bool]

_rules: dict[str, Rule] = {}


def permission(action: str) -> Callable[[Rule], Rule]:
    """Register the rule for an action, e.g. ``@permission("reports.open")``.

    The rule receives the actor and the resource and returns True to allow.
    """

    def register(rule: Rule) -> Rule:
        if action in _rules:
            raise ValueError(f"permission registered twice: {action}")
        _rules[action] = rule
        return rule

    return register


def authorize(actor: Actor, action: str, resource: object | None = None) -> None:
    rule = _rules.get(action)
    if rule is None or rule(actor, resource) is not True:
        raise Refusal(Outcome.FORBIDDEN, "禁止存取", attempted=action)
