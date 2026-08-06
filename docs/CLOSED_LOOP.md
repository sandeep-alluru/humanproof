# Closed loop — `humanproof`

**Status:** reader wired (eagle-eyes / 2026-08-05) — **APPROVAL-GATE**  
**Owner loop:** L7

## Load-bearing job

HITL checkpoints / approval gates before high-risk side effects

## Who reads the output?

- Library API: `humanproof.gate_approval` / `assert_approved` / `ApprovalSession` (`closed_loop.py`)
- CI / agent runtime / publish loop must `sys.exit(outcome.exit_code)` or refuse on `ok is False`
- eagle-eyes dogfood may import the gate without a full gaming scorer stack

## What outcome changes?

High-risk action (`post`, `db_wipe`, …) does not proceed without a valid owner
token; missing token → `FAIL_LOUD` (exit 2). Runaway budget → `FAIL` (exit 1).

## When NOT to use (anti-ornament)

Do not load as decorative MCP without wiring to real block. Do not auto-mint
tokens inside the agent process for “convenience.”

## Non-Ornament checklist

- [x] Reader implemented in CI, gate, or eagle-eyes script (`gate_approval` + tests)
- [x] Empty/wrong output fails loudly (`FAIL_LOUD`, exit 2)
- [x] Not exposed as free MCP that auto-approves
- [ ] Linked gap IDs in mem0 when improving

## Related failures (farm memory)

- 2026-07-22 MCP buffet trim: write-only tools removed from Foundry framework
- D-FOGHORN: misuse of append-only fact log as current state
- Dual-path mem0: never rely on MCP-only for critical memory

## Daily rotation note

This file exists so pillar **C (closed loop)** can rise with real wiring over time. Prefer small daily commits that move a checkbox toward done.

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2
