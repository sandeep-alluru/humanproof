"""Closed-loop approval gate for humanproof (Non-Ornament L7 / APPROVAL-GATE).

Who reads the output?
  CI jobs, agent runtimes, publish loops, eagle-eyes dogfood — anything that
  must *block* a high-risk action until a human issues an approval token.

What outcome changes?
  Without a valid, unconsumed token for a high-risk action, the gate returns
  FAIL_LOUD (exit 2) or FAIL (exit 1). The action must not proceed.

Farm cases:
  * APPROVAL-GATE — X-lane auto-post without owner (FULLAUTO flag removed the
    1-tap gate; product library must still provide a required-token gate).
  * Public: Replit AI DB deletion, Google Antigravity wipe, OpenClaw mass
    email delete — destructive tools without human approval.
  * Public (HN): Guardian Runtime, AgentWatch — runaway / budget firewalls
    map to max high-risk actions per session before re-approval.

Never treat a missing token as PASS. Never auto-mint tokens for agents.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

# Action names / prefixes that always require approval (destructive / external).
DEFAULT_HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        "post",
        "publish",
        "auto_post",
        "delete",
        "rm",
        "wipe",
        "drop",
        "truncate",
        "send_email",
        "mass_email",
        "transfer",
        "deploy_prod",
        "git_push_force",
        "shell_rm",
        "db_drop",
        "db_wipe",
    }
)


class ApprovalError(ValueError):
    """Raised when an action is refused for missing/invalid approval."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of an approval gate check.

    Attributes:
        ok: True only when the action may proceed.
        verdict: ``PASS``, ``FAIL``, or ``FAIL_LOUD``.
        reason: Human-readable explanation (always non-empty).
        exit_code: 0 PASS, 1 FAIL (policy deny), 2 FAIL_LOUD (missing/empty).
        action: Canonical action name that was gated.
        risk: ``safe`` or ``high_risk``.
        human_required: True when a human must issue a token.
        token_id: Consumed or matched token id when present.
        approvals_remaining: Budget remaining in the session after this check.
    """

    ok: bool
    verdict: str
    reason: str
    exit_code: int
    action: str | None = None
    risk: str | None = None
    human_required: bool = False
    token_id: str | None = None
    approvals_remaining: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "action": self.action,
            "risk": self.risk,
            "human_required": self.human_required,
            "token_id": self.token_id,
            "approvals_remaining": self.approvals_remaining,
        }


@dataclass
class ApprovalToken:
    """Single-use (or multi-use) human-issued approval credential.

    Agents must never create these for themselves in production; only a human
    (or an out-of-band owner control plane) calls :meth:`ApprovalSession.issue`.
    """

    token_id: str
    secret: str
    action: str  # exact action, or "*" for any high-risk action
    issued_at: float
    expires_at: float | None = None
    max_uses: int = 1
    uses: int = 0
    issuer: str = "owner"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def exhausted(self) -> bool:
        return self.uses >= self.max_uses

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at

    def matches_action(self, action: str) -> bool:
        if self.action == "*":
            return True
        return self.action == _canonical_action(action)

    def fingerprint(self) -> str:
        """Public id for logs — not the secret."""
        return self.token_id


class ApprovalSession:
    """In-process approval ledger for one agent run / publish session.

    Enforces:
      * required token for high-risk actions
      * single-use (or capped) consumption
      * optional runaway budget (max high-risk successes per session)

    This is the load-bearing *reader* for APPROVAL-GATE — not a flag file.
    """

    def __init__(
        self,
        *,
        high_risk_actions: Iterable[str] | None = None,
        max_high_risk_per_session: int | None = None,
        session_id: str | None = None,
    ) -> None:
        base = set(DEFAULT_HIGH_RISK_ACTIONS)
        if high_risk_actions is not None:
            base |= {_canonical_action(a) for a in high_risk_actions}
        self.high_risk_actions: frozenset[str] = frozenset(base)
        self.max_high_risk_per_session = max_high_risk_per_session
        self.session_id = session_id or secrets.token_hex(4)
        self._tokens: dict[str, ApprovalToken] = {}
        self._high_risk_passes: int = 0

    def classify(self, action: str) -> str:
        """Return ``high_risk`` or ``safe`` for *action*."""
        canon = _canonical_action(action)
        if not canon:
            return "high_risk"  # empty action is never safe
        if canon in self.high_risk_actions:
            return "high_risk"
        # prefix match: "post:x_thread" → post
        head = canon.split(":", 1)[0]
        if head in self.high_risk_actions:
            return "high_risk"
        return "safe"

    def issue(
        self,
        action: str = "*",
        *,
        ttl_seconds: float | None = 3600.0,
        max_uses: int = 1,
        issuer: str = "owner",
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalToken:
        """Mint a human approval token. Call only from owner / HITL UI."""
        if max_uses < 1:
            raise ApprovalError("max_uses must be >= 1")
        secret = secrets.token_urlsafe(24)
        token_id = hashlib.sha256(secret.encode()).hexdigest()[:16]
        now = time.time()
        expires = None if ttl_seconds is None else now + float(ttl_seconds)
        token = ApprovalToken(
            token_id=token_id,
            secret=secret,
            action=_canonical_action(action) if action != "*" else "*",
            issued_at=now,
            expires_at=expires,
            max_uses=max_uses,
            uses=0,
            issuer=issuer,
            metadata=dict(metadata or {}),
        )
        self._tokens[token_id] = token
        return token

    def peek(self, token_id: str) -> ApprovalToken | None:
        return self._tokens.get(token_id)

    @property
    def high_risk_pass_count(self) -> int:
        return self._high_risk_passes

    def remaining_budget(self) -> int | None:
        if self.max_high_risk_per_session is None:
            return None
        return max(0, self.max_high_risk_per_session - self._high_risk_passes)


def _canonical_action(action: str) -> str:
    return (action or "").strip().lower().replace(" ", "_")


def _fail_loud(
    reason: str,
    *,
    action: str | None = None,
    risk: str | None = None,
    human_required: bool = True,
    remaining: int | None = None,
) -> GateOutcome:
    return GateOutcome(
        ok=False,
        verdict="FAIL_LOUD",
        reason=reason,
        exit_code=2,
        action=action,
        risk=risk,
        human_required=human_required,
        token_id=None,
        approvals_remaining=remaining,
    )


def _fail(
    reason: str,
    *,
    action: str | None = None,
    risk: str | None = None,
    human_required: bool = True,
    token_id: str | None = None,
    remaining: int | None = None,
) -> GateOutcome:
    return GateOutcome(
        ok=False,
        verdict="FAIL",
        reason=reason,
        exit_code=1,
        action=action,
        risk=risk,
        human_required=human_required,
        token_id=token_id,
        approvals_remaining=remaining,
    )


def gate_approval(
    action: str,
    token: ApprovalToken | str | None = None,
    *,
    session: ApprovalSession | None = None,
    secret: str | None = None,
    consume: bool = True,
) -> GateOutcome:
    """Gate a proposed action: high-risk requires a valid human token.

    Args:
        action: Proposed action name (e.g. ``post``, ``db_wipe``, ``score``).
        token: :class:`ApprovalToken` or token_id string from :meth:`ApprovalSession.issue`.
        session: Session ledger; created empty if omitted (then only safe actions pass).
        secret: Optional secret if *token* is a token_id string (constant-time check).
        consume: If True (default), successful high-risk checks increment token uses.

    Returns:
        :class:`GateOutcome`. Callers should refuse the action unless ``ok``.
    """
    sess = session or ApprovalSession()
    remaining = sess.remaining_budget()
    canon = _canonical_action(action)

    if not canon:
        return _fail_loud(
            "empty action — refuse (APPROVAL-GATE: nothing to approve)",
            action=action or "",
            risk="high_risk",
            remaining=remaining,
        )

    risk = sess.classify(canon)

    if risk == "safe":
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=f"safe action {canon!r} — no approval required",
            exit_code=0,
            action=canon,
            risk="safe",
            human_required=False,
            token_id=None,
            approvals_remaining=remaining,
        )

    # High-risk: token required
    if token is None:
        return _fail_loud(
            f"high-risk action {canon!r} requires owner approval token "
            f"(APPROVAL-GATE / auto-post without owner)",
            action=canon,
            risk="high_risk",
            remaining=remaining,
        )

    # Resolve token object
    tok: ApprovalToken | None
    if isinstance(token, ApprovalToken):
        tok = token
        # Prefer session registry if present (authoritative uses counter)
        registered = sess.peek(token.token_id)
        if registered is not None:
            tok = registered
    else:
        tok = sess.peek(str(token))
        if tok is None:
            return _fail(
                f"unknown approval token_id {token!r} for action {canon!r}",
                action=canon,
                risk="high_risk",
                remaining=remaining,
            )

    if secret is not None and not secrets.compare_digest(tok.secret, secret):
        return _fail(
            "approval secret mismatch",
            action=canon,
            risk="high_risk",
            token_id=tok.token_id,
            remaining=remaining,
        )

    if tok.expired:
        return _fail(
            f"approval token {tok.token_id} expired",
            action=canon,
            risk="high_risk",
            token_id=tok.token_id,
            remaining=remaining,
        )

    if tok.exhausted:
        return _fail(
            f"approval token {tok.token_id} exhausted ({tok.uses}/{tok.max_uses} uses)",
            action=canon,
            risk="high_risk",
            token_id=tok.token_id,
            remaining=remaining,
        )

    if not tok.matches_action(canon):
        return _fail(
            f"token {tok.token_id} issued for action {tok.action!r}, not {canon!r}",
            action=canon,
            risk="high_risk",
            token_id=tok.token_id,
            remaining=remaining,
        )

    # Runaway budget (Guardian / AgentWatch class)
    if sess.max_high_risk_per_session is not None:
        if sess.high_risk_pass_count >= sess.max_high_risk_per_session:
            return _fail(
                f"session high-risk budget exhausted "
                f"({sess.high_risk_pass_count}/{sess.max_high_risk_per_session}) "
                f"— re-approval required (runaway guard)",
                action=canon,
                risk="high_risk",
                token_id=tok.token_id,
                remaining=0,
            )

    if consume:
        tok.uses += 1
        sess._tokens[tok.token_id] = tok
        sess._high_risk_passes += 1

    remaining_after = sess.remaining_budget()
    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"approved {canon!r} via token {tok.token_id} (issuer={tok.issuer})",
        exit_code=0,
        action=canon,
        risk="high_risk",
        human_required=False,
        token_id=tok.token_id,
        approvals_remaining=remaining_after,
    )


def assert_approved(
    action: str,
    token: ApprovalToken | str | None = None,
    **kwargs: Any,
) -> GateOutcome:
    """Gate and raise :class:`ApprovalError` unless outcome is ok."""
    outcome = gate_approval(action, token, **kwargs)
    if not outcome.ok:
        raise ApprovalError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def require_token_for(
    action: str,
    session: ApprovalSession,
) -> GateOutcome:
    """Convenience: gate without a token — always FAIL_LOUD for high-risk.

    Useful in tests and CI to prove the unattended path is blocked.
    """
    return gate_approval(action, token=None, session=session)
