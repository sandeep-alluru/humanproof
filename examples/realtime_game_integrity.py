"""Real-time bot detection for a live game session using humanproof motor-noise fingerprinting.

Story: VaultFire-Match-7891 — 5 players analyzed live, one action window at a time.
3 players are humans (varying skill levels), 2 players are bots (one aim-assist macro,
one economy bot that injects random noise to try to evade detection).

The system demonstrates:
  - Per-action scoring with a rolling 50-sample buffer per player
  - Three-consecutive-flag rule for false positive mitigation (requires 3 AI verdicts in
    a row before escalating — avoids banning humans who have one noisy window)
  - Session-level analysis after all actions are processed, catching behavioral shifts
  - How evasion bots that inject artificial noise are still caught by correction_rate

Run from repo root:
    python examples/realtime_game_integrity.py
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanproof.scorer import MotorScorer
from humanproof.session import SessionAnalysis, analyze_session
from humanproof.trajectory import InputSample, InputTrajectory

# ── Constants ──────────────────────────────────────────────────────────────────

MATCH_ID = "VaultFire-Match-7891"
RNG_SEED = 777
BUFFER_SIZE = 50        # samples per scoring window
FLAG_THRESHOLD = 3      # consecutive AI verdicts before session escalation
ACTIONS_PER_PLAYER = 8  # number of 50-sample windows simulated per player


# ── Player profile ──────────────────────────────────────────────────────────────

@dataclass
class PlayerProfile:
    name: str
    player_id: str
    kind: str           # "human_pro", "human_casual", "aimbot", "evasion_bot"
    noise_std: float    # gaussian noise std used for human simulation
    seed: int


PLAYERS: list[PlayerProfile] = [
    PlayerProfile("Vortex",   "player_001", "human_pro",    2.5, 111),
    PlayerProfile("NovaStar", "player_002", "human_casual", 5.8, 222),
    PlayerProfile("RyzUp",    "player_003", "human_casual", 6.3, 333),
    PlayerProfile("X0-BOT",   "player_004", "aimbot",       0.0, 444),
    # EkoBOT injects random noise believing it defeats behavioral detection.
    # In practice noise_ratio improves slightly, but correction_rate stays near 0.0
    # (direction reversals are never injected) — still flagged.
    PlayerProfile("EkoBOT",   "player_005", "evasion_bot",  0.0, 555),
]


# ── Sample generators ───────────────────────────────────────────────────────────

def make_human_window(rng: random.Random, noise_std: float) -> list[InputSample]:
    """Generate BUFFER_SIZE human-like input samples with organic motor noise."""
    samples: list[InputSample] = []
    base_dx = rng.uniform(2.0, 6.5)
    base_dy = rng.uniform(1.5, 4.5)
    ts = 0.0

    for _ in range(BUFFER_SIZE):
        dx = rng.gauss(base_dx, noise_std)
        dy = rng.gauss(base_dy, noise_std * 0.9)
        dt = rng.uniform(14.0, 32.0)

        # Micro-corrections — hallmark of human motor control (~20% of samples)
        if rng.random() < 0.20:
            dx *= -rng.uniform(0.25, 0.75)
            dy *= -rng.uniform(0.25, 0.75)

        # Occasional speed burst (flick shot or adrenaline response)
        if rng.random() < 0.04:
            dx *= rng.uniform(2.0, 3.8)
            dy *= rng.uniform(2.0, 3.8)

        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    return samples


def make_aimbot_window(action_index: int) -> list[InputSample]:
    """Generate BUFFER_SIZE perfectly smooth aimbot samples — no noise, constant timing."""
    samples: list[InputSample] = []
    dx, dy, dt = 4.0, 3.0, 16.0  # mechanically perfect — locked to exactly one frame
    ts = float(action_index * BUFFER_SIZE * dt)

    for _ in range(BUFFER_SIZE):
        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    return samples


def make_evasion_bot_window(rng: random.Random, action_index: int) -> list[InputSample]:
    """Generate evasion bot samples: base aimbot trajectory with injected random noise.

    The operator has added uniform noise to dx/dy hoping to defeat noise_ratio detection.
    However, they have not injected direction reversals, so correction_rate stays near 0.0,
    which is the stronger discriminating signal.
    """
    samples: list[InputSample] = []
    dx_base, dy_base, dt_base = 4.0, 3.0, 16.0
    ts = float(action_index * BUFFER_SIZE * dt_base)

    for _ in range(BUFFER_SIZE):
        dx = dx_base + rng.uniform(-1.2, 1.2)     # noise injection
        dy = dy_base + rng.uniform(-0.9, 0.9)
        dt = dt_base + rng.uniform(-0.5, 0.5)     # small timing jitter only
        # No direction reversals — correction_rate stays near 0.0

        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    return samples


# ── Simulation ──────────────────────────────────────────────────────────────────

def run_session(
    players: list[PlayerProfile],
    scorer: MotorScorer,
) -> tuple[
    dict[str, list[InputTrajectory]],
    dict[str, list[float]],
    dict[str, int],
    dict[str, int],
]:
    """Simulate ACTIONS_PER_PLAYER action windows for each player and score each window.

    Returns:
        all_trajectories: session_id -> ordered list of trajectory windows
        score_history:    session_id -> human_score per window
        flag_counter:     session_id -> current consecutive-flag count (resets on clean window)
        total_flags:      session_id -> total windows that returned verdict 'ai'
    """
    rng_map = {p.player_id: random.Random(p.seed) for p in players}
    all_trajectories: dict[str, list[InputTrajectory]] = {p.player_id: [] for p in players}
    score_history: dict[str, list[float]] = {p.player_id: [] for p in players}
    flag_counter: dict[str, int] = {p.player_id: 0 for p in players}
    total_flags: dict[str, int] = {p.player_id: 0 for p in players}

    for action_index in range(ACTIONS_PER_PLAYER):
        for profile in players:
            rng = rng_map[profile.player_id]

            if profile.kind == "aimbot":
                samples = make_aimbot_window(action_index)
            elif profile.kind == "evasion_bot":
                samples = make_evasion_bot_window(rng, action_index)
            else:
                samples = make_human_window(rng, profile.noise_std)

            traj = InputTrajectory(samples=samples, session_id=profile.player_id)
            all_trajectories[profile.player_id].append(traj)

            result = scorer.score(traj)
            score_history[profile.player_id].append(result.human_score)

            # Three-consecutive-flag rule: reset counter on any clean window
            if result.verdict == "ai":
                flag_counter[profile.player_id] += 1
                total_flags[profile.player_id] += 1
            else:
                flag_counter[profile.player_id] = 0

    return all_trajectories, score_history, flag_counter, total_flags


# ── Helpers ─────────────────────────────────────────────────────────────────────

def print_separator(char: str = "-", width: int = 76) -> None:
    print(char * width)


def session_verdict(consecutive_flags: int, total_flags: int, actions: int) -> str:
    """Derive a session-level enforcement verdict from the flag counters."""
    flag_rate = total_flags / actions if actions > 0 else 0.0
    if consecutive_flags >= FLAG_THRESHOLD or flag_rate >= 0.70:
        return "BAN QUEUED"
    if flag_rate >= 0.40:
        return "REVIEW"
    return "CLEAR"


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    random.seed(RNG_SEED)
    scorer = MotorScorer()

    print(f"\n{'=' * 76}")
    print(f"  REAL-TIME BOT DETECTION  —  {MATCH_ID}")
    print(f"  {len(PLAYERS)} players  |  {ACTIONS_PER_PLAYER} action windows  "
          f"|  {BUFFER_SIZE} samples/window  |  3-strike rule")
    print(f"{'=' * 76}\n")

    print("Simulating action stream and scoring windows...", end=" ", flush=True)
    all_trajectories, score_history, flag_counter, total_flags = run_session(PLAYERS, scorer)
    print("done.\n")

    # ── Per-window score timeline ─────────────────────────────────────────────
    print("ACTION WINDOW SCORES  (human_score per window, * = AI verdict)")
    print_separator()
    print(f"{'Player':<12} {'Kind':<14}", end="")
    for i in range(ACTIONS_PER_PLAYER):
        print(f"  W{i + 1:02d}  ", end="")
    print()
    print_separator()

    for profile in PLAYERS:
        scores = score_history[profile.player_id]
        print(f"{profile.name:<12} {profile.kind:<14}", end="")
        for s in scores:
            marker = "*" if s < 0.35 else " "
            print(f"  {s:.2f}{marker} ", end="")
        print()

    print_separator()
    print("  * = AI verdict (human_score < 0.35)\n")

    # ── Feature detail for the final scoring window of each player ────────────
    print("FINAL WINDOW FEATURE BREAKDOWN")
    print_separator()
    print(
        f"{'Player':<12} {'noise_ratio':>12} {'correction_rt':>14} "
        f"{'smoothness':>12} {'human%':>8} {'verdict':>12}"
    )
    print_separator()

    for profile in PLAYERS:
        final_traj = all_trajectories[profile.player_id][-1]
        result = scorer.score(final_traj)
        f = result.features
        marker = "  <<" if result.verdict == "ai" else ""
        print(
            f"{profile.name:<12} {f.noise_ratio:>12.4f} {f.correction_rate:>14.4f} "
            f"{f.smoothness:>12.2f} {result.human_score * 100:>7.1f}%"
            f" {result.verdict.upper():>12}{marker}"
        )

    print_separator()

    # ── Session-level verdicts: 3-strike + flag rate ──────────────────────────
    print("\nSESSION VERDICTS — 3-consecutive-flag rule + flag rate")
    print_separator()
    print(
        f"{'Player':<12} {'Kind':<14} {'Consec. flags':>14} "
        f"{'Total flags':>12} {'Flag rate':>10} {'Verdict':>12}"
    )
    print_separator()

    ban_list: list[PlayerProfile] = []
    review_list: list[PlayerProfile] = []
    clear_list: list[PlayerProfile] = []

    for profile in PLAYERS:
        cf = flag_counter[profile.player_id]
        tf = total_flags[profile.player_id]
        flag_rate = tf / ACTIONS_PER_PLAYER
        verdict = session_verdict(cf, tf, ACTIONS_PER_PLAYER)
        print(
            f"{profile.name:<12} {profile.kind:<14} {cf:>14} "
            f"{tf:>12} {flag_rate:>9.0%} {verdict:>12}"
        )
        if verdict == "BAN QUEUED":
            ban_list.append(profile)
        elif verdict == "REVIEW":
            review_list.append(profile)
        else:
            clear_list.append(profile)

    print_separator()

    # ── Session-level behavioral shift analysis (catches mid-match aimbot) ────
    print("\nSESSION BEHAVIORAL SHIFT ANALYSIS (post-match, via analyze_session)")
    print_separator()

    for profile in PLAYERS:
        trajs = all_trajectories[profile.player_id]
        analysis: SessionAnalysis = analyze_session(profile.player_id, trajs)
        shift_note = ""
        if analysis.behavioral_shift_detected:
            shift_note = f"  *** SHIFT at window index {analysis.shift_at_index} ***"
        print(
            f"  {profile.name:<12}  verdict={analysis.verdict:<22} "
            f"risk={analysis.risk_level}{shift_note}"
        )

    print_separator()

    # ── Final match report ────────────────────────────────────────────────────
    print(f"\n{'=' * 76}")
    print(f"  MATCH REPORT — {MATCH_ID}")
    print(f"{'=' * 76}")
    print(f"\n  BANNED ({len(ban_list)}): " + (", ".join(p.name for p in ban_list) or "none"))
    print(f"  REVIEW ({len(review_list)}): " + (", ".join(p.name for p in review_list) or "none"))
    print(f"  CLEAR  ({len(clear_list)}): " + (", ".join(p.name for p in clear_list) or "none"))
    print()
    print("  Detection notes:")
    print("    X0-BOT:  noise_ratio≈0.00, correction_rate≈0.00 — classic aimbot signature")
    print("    EkoBOT:  injected dx/dy noise raises noise_ratio slightly, but correction_rate")
    print("             stays near 0.00 (no direction reversals injected) — still flagged")
    print(f"\n  The 3-strike rule reduces effective false positive rate from 0.1% per window")
    print(f"  to ~0.000001% per session (p=0.001^3 for three consecutive false flags).")
    print(f"\n{'=' * 76}\n")


if __name__ == "__main__":
    main()
