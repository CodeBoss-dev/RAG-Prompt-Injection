"""Attack implementations for indirect prompt injection scenarios."""

from src.attacks.base import Attack
from src.attacks.exfiltration import ExfiltrationAttack
from src.attacks.phishing import PhishingAttack
from src.attacks.goal_hijacking import GoalHijackingAttack
from src.attacks.privilege_escalation import PrivilegeEscalationAttack

ALL_ATTACKS: list[type[Attack]] = [
    ExfiltrationAttack,
    PhishingAttack,
    GoalHijackingAttack,
    PrivilegeEscalationAttack,
]

__all__ = [
    "Attack",
    "ExfiltrationAttack",
    "PhishingAttack",
    "GoalHijackingAttack",
    "PrivilegeEscalationAttack",
    "ALL_ATTACKS",
]
