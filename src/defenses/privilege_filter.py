"""Role-based access control defense.

Pre-filters retrieved nodes based on the requesting user's role and the
``access_level`` metadata on each node.

Role hierarchy::

    employee   -> public, internal
    manager    -> public, internal, confidential
    executive  -> public, internal, confidential, restricted
"""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core.schema import NodeWithScore

from src.defenses.base import BaseDefense

logger = logging.getLogger(__name__)

# Maps each role to the set of access levels it is allowed to view.
ROLE_ACCESS: dict[str, set[str]] = {
    "employee": {"public", "internal"},
    "manager": {"public", "internal", "confidential"},
    "executive": {"public", "internal", "confidential", "restricted"},
}


class PrivilegeFilter(BaseDefense):
    """Filters nodes by access level based on the user's role.

    If the user's role is not recognised, only ``public`` documents are
    allowed (fail-closed).
    """

    @property
    def name(self) -> str:
        return "PrivilegeFilter"

    def apply(
        self,
        nodes: list[NodeWithScore],
        query: str,
        user_context: dict[str, Any],
    ) -> list[NodeWithScore]:
        role = user_context.get("role", "employee")
        allowed = ROLE_ACCESS.get(role, {"public"})

        result: list[NodeWithScore] = []
        for node in nodes:
            access_level = node.node.metadata.get("access_level", "public")
            if access_level in allowed:
                result.append(node)
            else:
                logger.info(
                    "PrivilegeFilter: blocked node (access_level=%s, role=%s): %.80s…",
                    access_level,
                    role,
                    node.node.get_content(),
                )

        return result
