from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(slots=True)
class Locker:
    locker_id: str
    compartments: int = 0
    active_reservations: int = 0
    degraded_compartments: int = 0
    state_hash: str = ""

    def set_state_hash(self) -> str:
        """
        Compute a deterministic hash of the locker summary state and store it in `state_hash`.
        """
        payload = {
            "locker_id": self.locker_id,
            "compartments": self.compartments,
            "active_reservations": self.active_reservations,
            "degraded_compartments": self.degraded_compartments,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.state_hash = hashlib.sha256(raw).hexdigest()
        return self.state_hash


