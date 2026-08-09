"""MASS-EMAIL / OpenClaw bulk external side-effect gate.

Public cases (Track B + matrix partial):
  * OpenClaw mass email delete - external side effect without gate
  * Guardian Runtime / AgentWatch - runaway bulk budget (HN 20260807T081227Z)

Pre-fix hole: mass_email only marked high-risk; agents can still attempt
bulk send with empty/oversized recipient lists or loop mass actions.
"""

from __future__ import annotations

import pytest

from humanproof.closed_loop import (
    ApprovalError,
    ApprovalSession,
    assert_mass_action_ok,
    gate_mass_action,
    is_mass_action,
)


def test_is_mass_action() -> None:
    assert is_mass_action("mass_email") is True
    assert is_mass_action("bulk_delete") is True
    assert is_mass_action("send_email") is True
    assert is_mass_action("post") is False
    assert is_mass_action("score") is False


def test_empty_recipients_fails_loud() -> None:
    sess = ApprovalSession()
    tok = sess.issue("mass_email", max_uses=5)
    out = gate_mass_action("mass_email", [], token=tok, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert out.human_required is True
    assert out.recipient_count == 0
    assert "inventory" in out.reason.lower() or "OpenClaw" in out.reason


def test_no_token_fails_loud() -> None:
    out = gate_mass_action(
        "mass_email",
        ["a@example.com", "b@example.com"],
        token=None,
        session=ApprovalSession(),
    )
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.recipient_count == 2
    assert "MASS-EMAIL" in out.reason or "OpenClaw" in out.reason


def test_oversized_recipient_list_fails_loud() -> None:
    sess = ApprovalSession(max_recipients_per_mass=5)
    tok = sess.issue("*", max_uses=5)
    recips = [f"u{i}@ex.com" for i in range(20)]
    out = gate_mass_action("mass_email", recips, token=tok, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.recipient_count == 20
    assert "exceeds" in out.reason.lower() or "max" in out.reason.lower()


def test_authorised_mass_email_passes() -> None:
    sess = ApprovalSession(max_mass_actions_per_session=5)
    tok = sess.issue("mass_email", max_uses=5)
    recips = ["a@ex.com", "b@ex.com", "c@ex.com"]
    out = gate_mass_action("mass_email", recips, token=tok, session=sess)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.recipient_count == 3
    assert out.mass_action_count == 1
    assert out.token_id == tok.token_id
    payload = out.to_dict()
    assert payload["recipient_count"] == 3


def test_mass_budget_exhausted() -> None:
    sess = ApprovalSession(max_mass_actions_per_session=2)
    tok = sess.issue("*", max_uses=10)
    recips = ["a@ex.com"]
    assert gate_mass_action("mass_email", recips, token=tok, session=sess).ok
    assert gate_mass_action("mass_email", recips, token=tok, session=sess).ok
    out = gate_mass_action("mass_email", recips, token=tok, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "budget" in out.reason.lower()
    assert out.human_required is True


def test_mass_delete_fixture_openclaw() -> None:
    """OpenClaw class: mass_delete of messages without inventory/token fails."""
    out = gate_mass_action("mass_delete", recipients=None, token=None)
    assert out.verdict == "FAIL_LOUD"
    assert out.human_required is True


def test_assert_mass_action_ok_raises() -> None:
    with pytest.raises(ApprovalError):
        assert_mass_action_ok("mass_email", ["x@y.com"], token=None)


def test_assert_mass_action_ok_passes() -> None:
    sess = ApprovalSession()
    tok = sess.issue("bulk_email", max_uses=1)
    out = assert_mass_action_ok(
        "bulk_email",
        ["one@ex.com"],
        token=tok,
        session=sess,
    )
    assert out.ok is True


def test_non_mass_falls_through_to_approval() -> None:
    """score is not mass - should use standard gate (safe path)."""
    out = gate_mass_action("score", recipients=None, token=None)
    assert out.ok is True
    assert out.risk == "safe" or out.verdict == "PASS"
