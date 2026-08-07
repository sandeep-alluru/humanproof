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

## Case MASS-EMAIL — OpenClaw bulk external side effects

**Source:** Matrix public corpus **partial** until this ship + Track B
(`20260807T081227Z` Guardian/AgentWatch runaway class):

| Incident | Failure class |
|----------|---------------|
| OpenClaw mass email delete | Bulk external side effect without inventory/gate |
| Guardian Runtime (HN) | Local firewall / cost runaway |
| AgentWatch (HN) | Session budget before re-approval |

**What fails:**

1. Agents call `mass_email` / `send_email` / `mass_delete` with **empty**
   recipient lists (or no list) and still claim success.
2. Oversized recipient blasts exceed any human-intended bulk limit.
3. Session loops mass actions until spam/delete damage is done — only a
   single high-risk token budget was not enough without a **mass** budget.

**Product in this repo:**

| Control | API |
|---------|-----|
| Classifier | `is_mass_action(action)` / `DEFAULT_MASS_ACTIONS` |
| Pre-exec gate | `gate_mass_action(action, recipients, token=..., session=...)` |
| Inventory | empty recipients → **FAIL_LOUD** |
| Bulk max | `max_recipients` / `ApprovalSession.max_recipients_per_mass` |
| Mass budget | `max_mass_actions_per_session` (default 3) |
| Raise form | `assert_mass_action_ok(...)` |

**Rules (load-bearing):**

- Mass action + empty inventory → **FAIL_LOUD**
- recipient_count > max → **FAIL_LOUD**
- No approval token → **FAIL_LOUD** (via `gate_approval`)
- Mass session budget exhausted → **FAIL**
- Non-mass actions fall through to `gate_approval`

**Tests:** `tests/test_mass_email_gate.py`

**Non-Ornament:** Call `gate_mass_action` **before** any bulk email/delete tool.
Pair with `gate_approval` tokens issued only by humans. High-risk defaults alone
are not a full OpenClaw fixture — inventory + bulk + mass budget are.

## Related queue IDs

- **APPROVAL-GATE** — this case (P0)
- **MASS-EMAIL** — OpenClaw bulk fixture (this section)
- **NORM-ENFORCE** (normsync) — unattended post without norm (sibling)
- **SILENT-SUCCESS** (notarize/groundcrew) — success without effects
- **DB-WIPE** (groundcrew) — destructive SQL/shell inventory + approval
