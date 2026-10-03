"""Who is asking: the per-run identity that tools use for permissions."""

from dataclasses import dataclass
from typing import Literal

Role = Literal["staff", "family", "unknown"]


@dataclass
class Context:
    """Identity of the caller, set per run and never read from the conversation.

    The defaults grant nothing: a run without an identity sees no records.
    """

    user_id: int = 0
    role: Role = "unknown"
