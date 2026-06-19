"""Esports tournament integrity monitoring for a championship match.

Story: ESL-2026-Finals — 6 players, 20 simulated minutes of gameplay.
Players 1-4 are legitimate humans (varied skill levels). Players 5-6 use
aimbots. Player 5 switches from human-like play to aimbot at minute 8.

After the match the system generates an integrity report flagging the cheaters
and includes a timeline analysis showing exactly when the behavior changed.

Run from repo root:
    python examples/esports_integrity_monitor.py
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from humanproof.scorer import MotorScore, MotorScorer
from humanproof.trajectory import InputSample, InputTrajectory

MATCH_ID = "ESL-2026-Finals"
MATCH_MINUTES = 20
SAMPLES_PER_MINUTE = 300   # ~5 samples/second — realistic for 16-20ms polling
WINDOW_MINUTES = 4         # analyze in 4-minute windows for timeline


@dataclass
class PlayerProfile:
    name: str
    player_id: str
    skill: str          # "pro", "amateur", "aimbot", "hybrid"
    noise_std: float    # gaussian noise std for human simulation
    seed: int


PLAYERS = [
    PlayerProfile("Viper",     "player_001", "pro",     2.8,  101),
    PlayerProfile("ShadowFox", "player_002", "pro",     3.2,  202),
    PlayerProfile("Nova",      "player_003", "amateur", 5.1,  303),
    PlayerProfile("KraZy",     "player_004", "amateur", 6.4,  404),
    PlayerProfile("XB0T",      "player_005", "hybrid",  4.0,  505),  # switches at min 8
    PlayerProfile("AimGod",    "player_006", "aimbot",  0.0,  606),
]


def make_human_samples(
    rng: random.Random,
    count: int,
    noise_std: float,
    ts_start: float,
) -> list[InputSample]:
    """Generate count human-like input samples starting at ts_start."""
    samples: list[InputSample] = []
    ts = ts_start

    for _ in range(count):
        dx = rng.gauss(4.0, noise_std)
        dy = rng.gauss(3.0, noise_std * 0.85)
        dt = rng.uniform(14.0, 28.0)

        # Micro-corrections ~18% of samples
        if rng.random() < 0.18:
            dx *= -rng.uniform(0.2, 0.7)
            dy *= -rng.uniform(0.2, 0.7)

        # Occasional burst (reaction to threat)
        if rng.random() < 0.04:
            dx *= rng.uniform(2.0, 3.5)

        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    return samples


def make_bot_samples(count: int, ts_start: float) -> list[InputSample]:
    """Generate count perfectly smooth aimbot samples."""
    samples: list[InputSample] = []
    ts = ts_start

    dx, dy, dt = 4.0, 3.0, 16.0  # constant — mechanically perfect
    for _ in range(count):
        samples.append(InputSample(dx=dx, dy=dy, dt=dt, timestamp=ts))
        ts += dt

    return samples


def build_trajectory(profile: PlayerProfile) -> InputTrajectory:
    """Build a full match trajectory (MATCH_MINUTES minutes) for a player."""
    rng = random.Random(profile.seed)
    samples: list[InputSample] = []
    ts = 0.0

    total_samples = MATCH_MINUTES * SAMPLES_PER_MINUTE

    if profile.skill == "aimbot":
        samples = make_bot_samples(total_samples, ts)

    elif profile.skill == "hybrid":
        # Human-like for first 8 minutes, then aimbot
        human_samples_count = 8 * SAMPLES_PER_MINUTE
        bot_samples_count = total_samples - human_samples_count
        human_part = make_human_samples(rng, human_samples_count, profile.noise_std, ts)
        if human_part:
            ts = human_part[-1].timestamp + 16.0
        bot_part = make_bot_samples(bot_samples_count, ts)
        samples = human_part + bot_part

    else:
        # Pure human (pro or amateur)
        samples = make_human_samples(rng, total_samples, profile.noise_std, ts)

    return InputTrajectory(samples=samples, session_id=profile.player_id)


def build_window_trajectories(profile: PlayerProfile) -> list[tuple[str, InputTrajectory]]:
    """Build per-window trajectories for timeline analysis."""
    rng = random.Random(profile.seed + 9000)
    windows: list[tuple[str, InputTrajectory]] = []
    ts = 0.0

    for window_start in range(0, MATCH_MINUTES, WINDOW_MINUTES):
        window_end = window_start + WINDOW_MINUTES
        label = f"min {window_start:02d}-{window_end:02d}"
        count = WINDOW_MINUTES * SAMPLES_PER_MINUTE

        # Determine behavior in this window
        if profile.skill == "aimbot":
            samps = make_bot_samples(count, ts)
        elif profile.skill == "hybrid" and window_start >= 8:
            samps = make_bot_samples(count, ts)
        elif profile.skill == "hybrid":
            samps = make_human_samples(rng, count, profile.noise_std, ts)
        else:
            samps = make_human_samples(rng, count, profile.noise_std, ts)

        if samps:
            ts = samps[-1].timestamp + 20.0

        traj = InputTrajectory(samples=samps, session_id=f"{profile.player_id}_w{window_start}")
        windows.append((label, traj))

    return windows


def print_separator(char: str = "-", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    scorer = MotorScorer()

    print(f"\n{'=' * 72}")
    print(f"  TOURNAMENT INTEGRITY MONITOR  —  {MATCH_ID}")
    print(f"  Analyzing {MATCH_MINUTES}-minute match  |  {len(PLAYERS)} players")
    print(f"{'=' * 72}\n")

    # ── Score full-match trajectories ─────────────────────────────────────────
    print("Building trajectories and scoring...", end=" ", flush=True)

    full_scores: list[tuple[PlayerProfile, MotorScore]] = []
    for profile in PLAYERS:
        traj = build_trajectory(profile)
        score = scorer.score(traj)
        full_scores.append((profile, score))

    print("done.\n")

    # ── Summary table ──────────────────────────────────────────────────────────
    print("FULL-MATCH FEATURE SUMMARY")
    print_separator()
    print(
        f"{'Player':<12} {'ID':<12} {'noise_ratio':>12} "
        f"{'corr_rate':>10} {'smooth':>8} {'verdict':>10}"
    )
    print_separator()

    flagged_players: list[PlayerProfile] = []
    human_count = 0

    for profile, score in full_scores:
        f = score.features
        verdict_str = score.verdict.upper()
        flag = "  <<" if score.verdict == "ai" else ""

        print(
            f"{profile.name:<12} {profile.player_id:<12} {f.noise_ratio:>12.4f} "
            f"{f.correction_rate:>10.4f} {f.smoothness:>8.2f} {verdict_str:>10}{flag}"
        )

        if score.verdict == "ai":
            flagged_players.append(profile)
        else:
            human_count += 1

    print_separator()

    # ── Timeline analysis — run for ALL players, flag behavior changes ────────
    print("\nTIMELINE ANALYSIS (4-minute windows)")
    print_separator()

    # Track per-player window verdicts and behavior changes
    behavior_change_flagged: set[str] = set()  # player_ids with detected change

    # Run timeline for flagged players first, then hybrid (XB0T) for completeness
    timeline_subjects = [p for p in PLAYERS if p.player_id in
                         {fp.player_id for fp in flagged_players} or p.skill in ("hybrid", "aimbot")]

    for profile in timeline_subjects:
        print(f"\n  {profile.name.upper()} ({profile.player_id})")
        windows = build_window_trajectories(profile)

        prev_nr: float | None = None
        for label, traj in windows:
            ws = scorer.score(traj)
            nr = ws.features.noise_ratio
            cr = ws.features.correction_rate
            v = ws.verdict.upper()

            transition = ""
            if prev_nr is not None and prev_nr > 0.30 and nr < 0.10:
                transition = "  *** BEHAVIOR CHANGE DETECTED ***"
                behavior_change_flagged.add(profile.player_id)

            print(
                f"    {label}: noise_ratio={nr:.4f}  corr_rate={cr:.4f}"
                f"  verdict={v}{transition}"
            )
            prev_nr = nr

    # Add timeline-flagged players to the flagged list (if not already there)
    for profile in PLAYERS:
        if profile.player_id in behavior_change_flagged and profile not in flagged_players:
            flagged_players.append(profile)
            human_count -= 1  # transfer from human count

    # ── Integrity report ──────────────────────────────────────────────────────
    print()
    print_separator("=")
    print(f"\nTOURNAMENT INTEGRITY REPORT — Game #{MATCH_ID}")
    print(f"  {human_count} players HUMAN   |   {len(flagged_players)} players FLAGGED for review\n")

    for profile in flagged_players:
        score_entry = next(s for p, s in full_scores if p.player_id == profile.player_id)
        conf = score_entry.ai_score * 100

        print(f"  {profile.player_id.upper()} ({profile.name})")
        if profile.player_id in behavior_change_flagged:
            print(f"    Confidence:  HIGH — timeline behavior change detected")
            print(f"    Full-match noise_ratio: {score_entry.features.noise_ratio:.4f} "
                  f"(averaged, masks window-level change)")
            print(
                f"    Timeline note: human-like play until minute 8, then "
                f"noise_ratio dropped from ~0.68 to ~0.00 — aimbot activation suspected"
            )
        else:
            print(f"    Confidence:  {conf:.0f}% AI/bot (full-match)")
            print(f"    noise_ratio: {score_entry.features.noise_ratio:.4f} (threshold: <0.15)")
            print(f"    Anomaly flags: {', '.join(score_entry.flags)}")
        print(f"    Recommended action: DISQUALIFY + refer to anti-cheat committee\n")

    print(f"  Legitimate players: ", end="")
    flagged_ids = {fp.player_id for fp in flagged_players}
    human_names = [p.name for p in PLAYERS if p.player_id not in flagged_ids]
    print(", ".join(human_names))
    print()
    print_separator("=")
    print()


if __name__ == "__main__":
    main()
