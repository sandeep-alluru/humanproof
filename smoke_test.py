"""
End-to-end smoke test for humanproof.

Simulates a user who just cloned the repo and wants to verify everything works.
No mocking, no fixtures — real behaviour, real CLI, real HTTP server.

Run from repo root:
    python smoke_test.py
    python smoke_test.py --verbose

Exit 0 = all passed. Exit 1 = at least one failure.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
REPO_ROOT = Path(__file__).parent
PYTHON = sys.executable

passed: list[str] = []
failed: list[tuple[str, str]] = []


def ok(name: str) -> None:
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name: str, reason: str) -> None:
    failed.append((name, reason))
    print(f"  {RED}✗{RESET} {name}")
    if VERBOSE:
        print(f"    {YELLOW}{reason}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def run(name: str, fn):  # noqa: ANN001
    try:
        fn()
        ok(name)
    except Exception as exc:
        reason = str(exc) if not VERBOSE else traceback.format_exc().strip()
        fail(name, reason)


# ── 1. Package import ─────────────────────────────────────────────────────────

section("1. Package import")

def _test_import_version():
    import humanproof
    assert humanproof.__version__, "__version__ is empty"
    assert humanproof.__version__ != "0.0.0"

def _test_import_public_api():
    # TODO: replace with your package's actual public API
    mod = importlib.import_module("humanproof")
    assert mod is not None

run("humanproof package imports", _test_import_version)
run("Public API importable", _test_import_public_api)


# ── 2. Domain-specific tests ──────────────────────────────────────────────────
#
# TODO: Replace this section with tests for your package's core data model,
# primary operations, and output formatters.
#
# Pattern to follow (see agentdelta's smoke_test.py as a reference):
#   section("2. Core data model")
#   def _test_create():  ...create a domain object, check fields...
#   def _test_round_trip(): ...serialize and deserialize, assert equality...
#   run("Create and inspect <entity>", _test_create)
#   run("<Entity> serializes and loads correctly", _test_round_trip)
#
#   section("3. Primary operation")
#   def _test_main_operation(): ...call your main function, assert result...
#   run("<verb>() works correctly on sample input", _test_main_operation)
#
#   section("4. Output formatters")
#   def _test_json_output(): ...call to_json(), parse result, check fields...
#   def _test_rich_output(): ...call print_..., capture console, check text...
#   run("to_json() returns valid JSON with expected keys", _test_json_output)
#   run("Rich formatter outputs expected text", _test_rich_output)


# ── 5. CLI ────────────────────────────────────────────────────────────────────

section("5. CLI (humanproof)")

def _test_cli_help():
    r = subprocess.run(
        [PYTHON, "-m", "humanproof.cli", "--help"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert len(r.stdout) > 20, "Help output is empty"

run("humanproof --help returns 0", _test_cli_help)

# TODO: Add CLI integration tests for each subcommand, e.g.:
#   def _test_cli_run():
#       r = subprocess.run([PYTHON, "-m", "humanproof.cli", "run", "--help"],
#                          capture_output=True, text=True)
#       assert r.returncode == 0
#   run("humanproof run --help returns 0", _test_cli_run)


# ── 6. FastAPI server ─────────────────────────────────────────────────────────

section("6. FastAPI server (humanproof[api])")

def _test_api_import():
    from humanproof.api import app
    assert app.title == "humanproof API"

def _test_api_health():
    from fastapi.testclient import TestClient
    from humanproof.api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()

run("humanproof.api imports and app.title is correct", _test_api_import)
run("GET /health returns {status: ok, version: ...}", _test_api_health)

# TODO: Add endpoint tests for your domain operations, e.g.:
#   def _test_api_primary_endpoint():
#       from fastapi.testclient import TestClient
#       from humanproof.api import app
#       client = TestClient(app)
#       r = client.post("/run", json={"input": "..."})
#       assert r.status_code == 200
#       assert "result" in r.json()
#   run("POST /run returns expected result", _test_api_primary_endpoint)


# ── 7. MCP server ─────────────────────────────────────────────────────────────

section("7. MCP server (humanproof[mcp])")

def _test_mcp_server_importable():
    import humanproof.mcp_server as m
    assert hasattr(m, "run_server")

def _test_mcp_server_loads_cleanly():
    import humanproof.mcp_server  # noqa: F401

run("mcp_server.py imports without error", _test_mcp_server_importable)
run("mcp_server module loads cleanly (no import-time crash)", _test_mcp_server_loads_cleanly)


# ── 8. Agent config files ─────────────────────────────────────────────────────

section("8. Agent config files (what a clone gives you)")

def _check_file_nonempty(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    assert p.stat().st_size > 50, f"File too small (likely empty): {rel}"

def _check_json_valid(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    json.loads(p.read_text())

def _check_yaml_parseable(rel: str) -> None:
    try:
        import yaml  # type: ignore[import-untyped]
        p = REPO_ROOT / rel
        assert p.exists(), f"Missing: {rel}"
        yaml.safe_load(p.read_text())
    except ImportError:
        content = (REPO_ROOT / rel).read_text()
        assert len(content) > 20, f"File appears empty: {rel}"

def _test_claude_commands():
    commands = list((REPO_ROOT / ".claude/commands").glob("*.md"))
    assert len(commands) >= 4, f"Expected ≥4 slash commands, found {len(commands)}"

def _test_openai_tools_valid():
    _check_json_valid("tools/openai-tools.json")
    tools = json.loads((REPO_ROOT / "tools/openai-tools.json").read_text())
    assert len(tools) >= 3
    assert all("function" in t for t in tools)

def _test_openapi_yaml_parseable():
    _check_yaml_parseable("openapi.yaml")

run("AGENTS.md exists and non-empty", lambda: _check_file_nonempty("AGENTS.md"))
run("CLAUDE.md exists and non-empty", lambda: _check_file_nonempty("CLAUDE.md"))
run("CODEX.md exists and non-empty", lambda: _check_file_nonempty("CODEX.md"))
run(".github/copilot-instructions.md exists", lambda: _check_file_nonempty(".github/copilot-instructions.md"))
def _test_cursor_rules():
    mdc_files = list((REPO_ROOT / ".cursor/rules").glob("*.mdc"))
    assert len(mdc_files) >= 1, f"Expected ≥1 .mdc file in .cursor/rules/, found none"

run(".cursor/rules/ has at least one .mdc file", _test_cursor_rules)
run(".windsurfrules exists", lambda: _check_file_nonempty(".windsurfrules"))
run(".aider.conf.yml exists", lambda: _check_file_nonempty(".aider.conf.yml"))
run(".continue/config.json is valid JSON", lambda: _check_json_valid(".continue/config.json"))
run(".claude/commands/ has ≥4 slash commands", _test_claude_commands)
run("tools/openai-tools.json is valid JSON with ≥3 tools", _test_openai_tools_valid)
run("openapi.yaml is parseable YAML", _test_openapi_yaml_parseable)


# ── 9. Docs site ──────────────────────────────────────────────────────────────

section("9. MkDocs documentation site")

def _test_mkdocs_yml():
    _check_file_nonempty("mkdocs.yml")
    content = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "site_name" in content
    assert "material" in content

def _test_docs_pages():
    docs = list((REPO_ROOT / "docs").glob("*.md"))
    assert len(docs) >= 8, f"Expected ≥8 doc pages, found {len(docs)}"
    names = {p.name for p in docs}
    for required in ("index.md", "quickstart.md", "architecture.md", "api-reference.md"):
        assert required in names, f"Missing docs/{required}"

run("mkdocs.yml exists with site_name and material theme", _test_mkdocs_yml)
run("docs/ has ≥8 pages including index, quickstart, architecture, api-reference", _test_docs_pages)


# ── 10. examples/demo.py ─────────────────────────────────────────────────────

section("10. examples/demo.py end-to-end")

def _test_demo_runs():
    demo = REPO_ROOT / "examples" / "demo.py"
    assert demo.exists(), "examples/demo.py not found"
    r = subprocess.run(
        [PYTHON, str(demo)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    if r.returncode != 0:
        raise AssertionError(f"demo.py exited {r.returncode}:\n{r.stderr[-500:]}")

run("examples/demo.py runs end-to-end without error", _test_demo_runs)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'═'*60}")
print(f"{BOLD}Results: {len(passed)}/{total} passed{RESET}")

if failed:
    print(f"{RED}Failed ({len(failed)}):{RESET}")
    for name, reason in failed:
        print(f"  {RED}✗{RESET} {name}")
        short = reason.split("\n")[0][:120]
        print(f"    {YELLOW}→ {short}{RESET}")
    print(f"\n{YELLOW}Tip: run with --verbose for full tracebacks{RESET}")
else:
    print(f"{GREEN}All {total} checks passed — humanproof is ready to ship{RESET}")

print(f"{'═'*60}\n")
sys.exit(0 if not failed else 1)
