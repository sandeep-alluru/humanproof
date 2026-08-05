# Real-world cases driving humanproof

Mined from farm_memory (Qdrant), Foundry X-lane decisions, and public
incidents (eagle-eyes Track B / PUBLIC_FAILURE_CORPUS).

## Case APPROVAL-GATE (farm) — CRITICAL

**Source:** Qdrant `farm_memory` decision/status on Pioneer Content Foundry
X-lane auto-post (2026-07-22); eagle-eyes `REAL_WORK_QUEUE` P0.

**What failed:**

The X-lane publish loop evolved:

1. Fully unattended auto-post was **blocked** by an auto-mode classifier.
2. Owner chose auto-build + **1-tap approve**.
3. Later owner said *“i approve for all auto posts remove the approval gate”*
   → flag file `posts/AUTO_LOOP_FULLAUTO` = posts with **no gate**.

Product risk: once the flag is present, **no library-level control** forces a
human token for high-risk side effects (`post`, `publish`, `delete`, …). Agents
and cron can externalize actions without a load-bearing reader.

**Public twins:**

| Incident | Failure class |
|----------|---------------|
| Replit AI DB deletion | Destructive tool without approval |
| Google Antigravity wipe | Unattended destructive filesystem |
| OpenClaw mass email delete | External side effect without gate |
| Guardian Runtime (HN / PyPI) | Local firewall for coding agents / runaway cost |
| AgentWatch (HN) | Runtime budget before re-approval |

**Product fix in this repo:**

| Control | API |
|---------|-----|
| Required token for high-risk | `gate_approval(action, token, session=...)` |
| Session ledger + issue | `ApprovalSession.issue` / `peek` |
| Single-use / TTL tokens | `ApprovalToken` (`max_uses`, `expires_at`) |
| Runaway budget | `ApprovalSession(max_high_risk_per_session=N)` |
| Raise form | `assert_approved(...)` |
| Unattended probe | `require_token_for(action, session)` → FAIL_LOUD |

Default high-risk set includes `post`, `publish`, `auto_post`, `delete`,
`db_wipe`, `send_email`, … — empty action is never safe.

**Tests:** `tests/test_closed_loop_approval.py`

**Non-Ornament:** Integrators must call `gate_approval` **before** side effects
and refuse when `ok is False`. A flag file alone is not a closed loop.

---

## Related queue IDs

- **APPROVAL-GATE** — this case (P0)
- **NORM-ENFORCE** (normsync) — unattended post without norm (sibling)
- **SILENT-SUCCESS** (notarize/groundcrew) — success without effects
