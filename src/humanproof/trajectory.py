"""Core data model for input trajectories."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InputSample:
    """A single mouse/aim input sample.

    Attributes:
        dx: X-axis delta (pixels).
        dy: Y-axis delta (pixels).
        dt: Time delta in milliseconds (must be > 0).
        timestamp: Absolute timestamp in milliseconds.
    """

    dx: float
    dy: float
    dt: float
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.dt <= 0:
            raise ValueError(f"dt must be > 0, got {self.dt}")


@dataclass
class InputTrajectory:
    """A sequence of input samples forming a trajectory.

    Attributes:
        samples: Ordered list of input samples.
        session_id: Optional session identifier string.
        id: SHA-256[:16] fingerprint computed from session_id, length, first/last sample.
    """

    samples: list[InputSample]
    session_id: str = ""
    id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("samples must not be empty")
        first = self.samples[0]
        last = self.samples[-1]
        payload = (
            f"{self.session_id}{len(self.samples)}"
            f"{first.dx}{first.dy}{first.dt}{first.timestamp}"
            f"{last.dx}{last.dy}{last.dt}{last.timestamp}"
        )
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def velocity_profile(self) -> list[float]:
        """Compute speed at each sample step (pixels/ms)."""
        return [
            math.sqrt(s.dx**2 + s.dy**2) / s.dt
            for s in self.samples
        ]

    def acceleration_profile(self) -> list[float]:
        """Compute acceleration at each step (pixels/ms^2). Length = n-1."""
        vp = self.velocity_profile()
        return [vp[i + 1] - vp[i] for i in range(len(vp) - 1)]

    def jerk_profile(self) -> list[float]:
        """Compute jerk at each step (pixels/ms^3). Length = n-2."""
        ap = self.acceleration_profile()
        return [ap[i + 1] - ap[i] for i in range(len(ap) - 1)]

    def correction_count(self) -> int:
        """Count direction reversals (velocity sign flips in x or y)."""
        count = 0
        for i in range(1, len(self.samples)):
            prev = self.samples[i - 1]
            curr = self.samples[i]
            x_flip = (prev.dx != 0 and curr.dx != 0 and
                      (prev.dx > 0) != (curr.dx > 0))
            y_flip = (prev.dy != 0 and curr.dy != 0 and
                      (prev.dy > 0) != (curr.dy > 0))
            if x_flip or y_flip:
                count += 1
        return count

    def noise_ratio(self) -> float:
        """Compute std(velocity) / mean(abs(velocity)). Returns 0.0 if mean is 0."""
        vp = self.velocity_profile()
        if not vp:
            return 0.0
        mean_v = sum(vp) / len(vp)
        if mean_v == 0:
            return 0.0
        variance = sum((v - mean_v) ** 2 for v in vp) / len(vp)
        std_v = math.sqrt(variance)
        return std_v / mean_v

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "session_id": self.session_id,
            "samples": [
                {"dx": s.dx, "dy": s.dy, "dt": s.dt, "timestamp": s.timestamp}
                for s in self.samples
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InputTrajectory:
        """Deserialize from a dict produced by to_dict()."""
        samples = [
            InputSample(
                dx=float(s["dx"]),
                dy=float(s["dy"]),
                dt=float(s["dt"]),
                timestamp=float(s.get("timestamp", 0.0)),
            )
            for s in d["samples"]
        ]
        return cls(samples=samples, session_id=d.get("session_id", ""))
