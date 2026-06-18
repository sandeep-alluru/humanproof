"""Tests for InputTrajectory and InputSample."""

from __future__ import annotations

import pytest
from humanproof.trajectory import InputSample, InputTrajectory


def make_samples(n: int = 5, dx: float = 1.0, dy: float = 1.0, dt: float = 10.0) -> list[InputSample]:
    return [InputSample(dx=dx, dy=dy, dt=dt) for _ in range(n)]


def make_traj(n: int = 5, session_id: str = "", **kwargs) -> InputTrajectory:
    return InputTrajectory(samples=make_samples(n, **kwargs), session_id=session_id)


# InputSample tests
def test_input_sample_basic() -> None:
    s = InputSample(dx=1.0, dy=2.0, dt=10.0)
    assert s.dx == 1.0
    assert s.dy == 2.0
    assert s.dt == 10.0
    assert s.timestamp == 0.0


def test_input_sample_dt_zero_raises() -> None:
    with pytest.raises(ValueError, match="dt must be > 0"):
        InputSample(dx=1.0, dy=1.0, dt=0.0)


def test_input_sample_dt_negative_raises() -> None:
    with pytest.raises(ValueError, match="dt must be > 0"):
        InputSample(dx=1.0, dy=1.0, dt=-1.0)


def test_input_sample_timestamp() -> None:
    s = InputSample(dx=0.5, dy=0.5, dt=5.0, timestamp=1000.0)
    assert s.timestamp == 1000.0


# InputTrajectory construction tests
def test_trajectory_empty_raises() -> None:
    with pytest.raises(ValueError, match="samples must not be empty"):
        InputTrajectory(samples=[])


def test_trajectory_id_is_16_chars() -> None:
    traj = make_traj()
    assert len(traj.id) == 16


def test_trajectory_id_deterministic() -> None:
    t1 = make_traj(session_id="abc")
    t2 = make_traj(session_id="abc")
    assert t1.id == t2.id


def test_trajectory_id_differs_by_session() -> None:
    t1 = make_traj(session_id="abc")
    t2 = make_traj(session_id="xyz")
    assert t1.id != t2.id


# velocity_profile tests
def test_velocity_profile_length() -> None:
    traj = make_traj(5, dx=3.0, dy=4.0, dt=10.0)
    vp = traj.velocity_profile()
    assert len(vp) == 5


def test_velocity_profile_values() -> None:
    # speed = sqrt(3^2 + 4^2) / 10 = 5/10 = 0.5
    traj = make_traj(3, dx=3.0, dy=4.0, dt=10.0)
    vp = traj.velocity_profile()
    for v in vp:
        assert abs(v - 0.5) < 1e-9


# acceleration_profile tests
def test_acceleration_profile_length() -> None:
    traj = make_traj(5)
    ap = traj.acceleration_profile()
    assert len(ap) == 4


def test_acceleration_profile_uniform_is_zero() -> None:
    traj = make_traj(4, dx=1.0, dy=0.0, dt=5.0)
    for a in traj.acceleration_profile():
        assert abs(a) < 1e-9


# jerk_profile tests
def test_jerk_profile_length() -> None:
    traj = make_traj(5)
    jp = traj.jerk_profile()
    assert len(jp) == 3


def test_jerk_profile_uniform_is_zero() -> None:
    traj = make_traj(5, dx=1.0, dy=0.0, dt=5.0)
    for j in traj.jerk_profile():
        assert abs(j) < 1e-9


# correction_count tests
def test_correction_count_no_reversals() -> None:
    samples = [InputSample(dx=1.0, dy=1.0, dt=10.0) for _ in range(5)]
    traj = InputTrajectory(samples=samples)
    assert traj.correction_count() == 0


def test_correction_count_alternating_x() -> None:
    samples = [
        InputSample(dx=1.0, dy=1.0, dt=10.0),
        InputSample(dx=-1.0, dy=1.0, dt=10.0),
        InputSample(dx=1.0, dy=1.0, dt=10.0),
        InputSample(dx=-1.0, dy=1.0, dt=10.0),
    ]
    traj = InputTrajectory(samples=samples)
    assert traj.correction_count() >= 2


def test_correction_count_single_sample() -> None:
    traj = InputTrajectory(samples=[InputSample(dx=1.0, dy=0.0, dt=5.0)])
    assert traj.correction_count() == 0


# noise_ratio tests
def test_noise_ratio_uniform_zero() -> None:
    traj = make_traj(5, dx=1.0, dy=0.0, dt=5.0)
    assert traj.noise_ratio() == 0.0


def test_noise_ratio_nonzero_for_varied_speed() -> None:
    samples = [
        InputSample(dx=10.0, dy=0.0, dt=5.0),
        InputSample(dx=1.0, dy=0.0, dt=5.0),
        InputSample(dx=10.0, dy=0.0, dt=5.0),
        InputSample(dx=1.0, dy=0.0, dt=5.0),
    ]
    traj = InputTrajectory(samples=samples)
    assert traj.noise_ratio() > 0.0


def test_noise_ratio_zero_mean() -> None:
    samples = [InputSample(dx=0.0, dy=0.0, dt=5.0) for _ in range(3)]
    traj = InputTrajectory(samples=samples)
    assert traj.noise_ratio() == 0.0


# serialization tests
def test_to_dict_from_dict_roundtrip() -> None:
    original = make_traj(3, session_id="test123")
    d = original.to_dict()
    restored = InputTrajectory.from_dict(d)
    assert restored.id == original.id
    assert len(restored.samples) == len(original.samples)


def test_from_dict_preserves_timestamps() -> None:
    samples = [InputSample(dx=1.0, dy=2.0, dt=5.0, timestamp=100.0)]
    original = InputTrajectory(samples=samples, session_id="ts_test")
    d = original.to_dict()
    restored = InputTrajectory.from_dict(d)
    assert restored.samples[0].timestamp == 100.0
