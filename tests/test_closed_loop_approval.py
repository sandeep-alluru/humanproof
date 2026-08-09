"""APPROVAL-GATE - high-risk actions require owner token (not auto-pass).

Farm: X-lane FULL AUTO-POST removed the 1-tap gate (Qdrant decision).
Public: Replit DB wipe / Antigravity / Guardian Runtime / AgentWatch.
"""

from __future__ import annotations

import time

import pytest

from humanproof.closed_loop import (
    ApprovalError,
    ApprovalSession,
    ApprovalToken,
    assert_approved,
    gate_approval,
    require_token_for,
)


def test_safe_action_passes_without_token() -> None:
    sess = ApprovalSession()
    out = gate_approval("score", token=None, session=sess)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.exit_code == 0
    assert out.risk == "safe"
    assert out.human_required is False


def test_post_without_token_fails_loud() -> None:
    """APPROVAL-GATE: auto-post without owner must never be ok=True."""
    sess = ApprovalSession()
    out = gate_approval("post", token=None, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert out.human_required is True
    assert out.risk == "high_risk"
    assert "approval" in out.reason.lower() or "token" in out.reason.lower()


def test_db_wipe_without_token_fails_loud() -> None:
    """Public Replit / Antigravity class - destructive without human."""
    out = gate_approval("db_wipe", token=None)
    assert out.verdict == "FAIL_LOUD"
    assert out.ok is False


def test_empty_action_fails_loud() -> None:
    out = gate_approval("", token=None)
    assert out.verdict == "FAIL_LOUD"
    assert out.ok is False


def test_issue_and_consume_token_for_post() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post", max_uses=1, issuer="owner")
    assert isinstance(tok, ApprovalToken)
    out = gate_approval("post", tok, session=sess)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.token_id == tok.token_id
    # Single-use exhausted
    out2 = gate_approval("post", tok, session=sess)
    assert out2.ok is False
    assert out2.verdict == "FAIL"
    assert "exhausted" in out2.reason.lower()


def test_token_action_mismatch() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post")
    out = gate_approval("db_wipe", tok, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "not" in out.reason.lower() or "issued" in out.reason.lower()


def test_wildcard_token_allows_any_high_risk() -> None:
    sess = ApprovalSession()
    tok = sess.issue("*", max_uses=2)
    assert gate_approval("publish", tok, session=sess).ok is True
    assert gate_approval("delete", tok, session=sess).ok is True


def test_token_id_string_lookup() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post")
    out = gate_approval("post", tok.token_id, session=sess)
    assert out.ok is True


def test_unknown_token_id_fails() -> None:
    sess = ApprovalSession()
    out = gate_approval("post", "deadbeefdeadbeef", session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL"


def test_secret_mismatch_fails() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post")
    out = gate_approval("post", tok.token_id, session=sess, secret="wrong-secret")
    assert out.ok is False
    assert "secret" in out.reason.lower()


def test_expired_token_fails() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post", ttl_seconds=0.01)
    time.sleep(0.05)
    out = gate_approval("post", tok, session=sess)
    assert out.ok is False
    assert "expired" in out.reason.lower()


def test_runaway_budget_blocks_after_limit() -> None:
    """AgentWatch / Guardian class: max high-risk successes per session."""
    sess = ApprovalSession(max_high_risk_per_session=2)
    tok = sess.issue("*", max_uses=10)
    assert gate_approval("post", tok, session=sess).ok is True
    assert gate_approval("post", tok, session=sess).ok is True
    out = gate_approval("post", tok, session=sess)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "budget" in out.reason.lower() or "runaway" in out.reason.lower()
    assert out.approvals_remaining == 0


def test_assert_approved_raises() -> None:
    with pytest.raises(ApprovalError, match="FAIL_LOUD"):
        assert_approved("auto_post", token=None)


def test_assert_approved_returns_on_pass() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post")
    out = assert_approved("post", tok, session=sess)
    assert out.ok is True


def test_require_token_for_blocks_unattended() -> None:
    sess = ApprovalSession()
    out = require_token_for("publish", sess)
    assert out.ok is False
    assert out.exit_code == 2


def test_prefixed_action_post_x_thread_is_high_risk() -> None:
    sess = ApprovalSession()
    out = gate_approval("post:x_thread", token=None, session=sess)
    assert out.verdict == "FAIL_LOUD"
    assert out.risk == "high_risk"


def test_custom_high_risk_action() -> None:
    sess = ApprovalSession(high_risk_actions=["mint_nft"])
    out = gate_approval("mint_nft", token=None, session=sess)
    assert out.verdict == "FAIL_LOUD"
    tok = sess.issue("mint_nft")
    assert gate_approval("mint_nft", tok, session=sess).ok is True


def test_to_dict_serialisable() -> None:
    out = gate_approval("post", token=None)
    payload = out.to_dict()
    assert payload["ok"] is False
    assert payload["verdict"] == "FAIL_LOUD"
    assert payload["human_required"] is True
    assert payload["action"] == "post"


def test_consume_false_does_not_exhaust() -> None:
    sess = ApprovalSession()
    tok = sess.issue("post", max_uses=1)
    out = gate_approval("post", tok, session=sess, consume=False)
    assert out.ok is True
    # Still usable
    out2 = gate_approval("post", tok, session=sess, consume=True)
    assert out2.ok is True
