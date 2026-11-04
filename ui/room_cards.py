"""
ui/room_cards.py - Formatted Markdown Status Cards for Switch Rooms (Mattermost/Slack)
Part of SwitchBlade: In-Flight FinOps Escrow Control Plane for Autonomous Agents.

Author: Hamza Shaikh (feat/hamza-cockpit-ui)
Role: Frontend, Live Telemetry UI & Visual Demo Lead

These scannable 4-line Markdown templates are posted into the Switch Room by the
SwitchBlade control plane and agents (@switchblade-proxy, @{team}-surgeon, @{team}-scout,
@{team}-compiler).
"""

from typing import Optional, Dict, Any


def card_escrow_tripped(
    escrow_id: str,
    task_id: str,
    tool_name: str,
    error_status: int = 422,
    failure_count: int = 3,
    burned_tokens: int = 45200,
    burned_cost_usd: float = 0.6780,
    team: str = "sb",
    **_kwargs: Any,
) -> str:
    """
    Card 1: ESCROW_TRIPPED Alert Card
    Posted by @switchblade-proxy when the circuit breaker trips on repeated permanent errors.
    4 scannable lines.
    """
    return (
        f"### 🚨 [ESCROW TRIPPED] Escrow: `{escrow_id}` | Task: `{task_id}`\n"
        f"**Circuit Breaker:** {failure_count}x `{error_status}` on tool `{tool_name}` (Unbounded loop detected)\n"
        f"**FinOps Burn:** {burned_tokens:,} tokens wasted (~${burned_cost_usd:.4f}) | Worker paused in `PENDING` escrow\n"
        f"**Handoff:** Invoking @{team}-surgeon for atomic context surgery and history compaction."
    )


def card_context_surgery_complete(
    escrow_id: str,
    tokens_before: int = 45200,
    tokens_after: int = 380,
    full_request_before: int = 48500,
    full_request_after: int = 3680,
    team: str = "sb",
    **_kwargs: Any,
) -> str:
    """
    Card 2: CONTEXT_SURGERY_COMPLETE Before/After Token Diff Card
    Posted by @{team}-surgeon after calling POST /surgeon/prune.
    4 scannable lines with honest token accounting.
    """
    reduction_pct = ((tokens_before - tokens_after) / tokens_before) * 100 if tokens_before else 0.0
    tokens_saved = tokens_before - tokens_after
    return (
        f"### ✂️ [CONTEXT SURGERY] Escrow: `{escrow_id}` — History Pruning Complete\n"
        f"**History Compaction:** {tokens_before:,} ➔ {tokens_after:,} tokens (**{reduction_pct:.1f}% reduction** | -{tokens_saved:,} tokens)\n"
        f"**Full Request (count_tokens):** {full_request_before:,} ➔ {full_request_after:,} tokens | Role alternation & tool pairs valid\n"
        f"**Integrity:** Closed trailing call with `failed_attempts` directive. Handing off to @{team}-scout."
    )


def card_dry_run_verified(
    escrow_id: str,
    change_hash: str,
    original_route: str = "POST /v1/orders",
    candidate_route: str = "POST /v2/orders",
    dry_run_result: str = "200 OK (?dry_run=true, would_settle=True)",
    pr_branch: str = "fix/vaccine-042-orders-v2",
    **_kwargs: Any,
) -> str:
    """
    Card 3: DRY_RUN_VERIFIED Approval Prompt Card
    Posted by @{team}-scout after dry-running against mock billing API.
    4 scannable lines with explicit copy-pasteable approval commands.
    """
    return (
        f"### 🛡️ [DRY RUN VERIFIED] Escrow: `{escrow_id}` | Change Hash: `{change_hash}`\n"
        f"**Fix Proposal:** Spec-differ verified: `{original_route}` ➔ `{candidate_route}` ({dry_run_result})\n"
        f"**Git Branch:** `{pr_branch}` staged with context-bound tenant header injection\n"
        f"**Action Required:** Human reply ```APPROVE {escrow_id} {change_hash}``` or ```REJECT {escrow_id} <reason>```"
    )


def card_vaccine_promoted(
    vaccine_id: str,
    change_hash: str,
    mode: str = "ENFORCE",
    approver: str = "@hamza",
    target_match: str = "POST /v1/orders",
    rewrite_target: str = "POST /v2/orders",
    p50_us: float = 1.2,
    **_kwargs: Any,
) -> str:
    """
    Card 4A: VACCINE_PROMOTED Card
    Posted by @switchblade-proxy when human approves and vaccine rule is locked.
    4 scannable lines.
    """
    return (
        f"### 💉 [VACCINE PROMOTED] Vaccine: `{vaccine_id}` | Mode: `{mode}`\n"
        f"**Pre-Send Rewrite:** `{target_match}` ➔ `{rewrite_target}` (Zero-retry Turn 1, p50: {p50_us:.1f}μs)\n"
        f"**Security & Authority:** Approved by `{approver}` | change_hash: `{change_hash}` | Tenant context-bound\n"
        f"**Fleet Protection:** In-memory rule active. Worker resumed and sibling orders protected."
    )


def card_ledger_checkpoint(
    seq_no: int,
    head_hash: str,
    event_type: str = "LEDGER_CHECKPOINT",
    record_count: int = 5,
    **_kwargs: Any,
) -> str:
    """
    Card 4B: LEDGER_CHECKPOINT Card
    Posted by @switchblade-proxy every 5 events to externally anchor ledger integrity.
    4 scannable lines.
    """
    return (
        f"### 🔗 [LEDGER CHECKPOINT] Seq: #{seq_no} | Anchor: `{head_hash[:16]}...`\n"
        f"**Domain:** `SWITCHBLADE-LEDGER-V1` | Transaction batch size: {record_count} events\n"
        f"**Head Hash:** `{head_hash}`\n"
        f"**Auditor Verify:** `python verify_ledger.py --checkpoint-hash {head_hash[:8]} --expected-seq {seq_no}`"
    )


# Convenience dictionary mapping event type to template function
CARD_TEMPLATES = {
    "ESCROW_TRIPPED": card_escrow_tripped,
    "CONTEXT_SURGERY_COMPLETE": card_context_surgery_complete,
    "DRY_RUN_VERIFIED": card_dry_run_verified,
    "VACCINE_PROMOTED": card_vaccine_promoted,
    "LEDGER_CHECKPOINT": card_ledger_checkpoint,
}


def render_card(event_type: str, **kwargs: Any) -> str:
    """Render any registered card by event type."""
    fn = CARD_TEMPLATES.get(event_type)
    if not fn:
        raise ValueError(f"Unknown event type '{event_type}'. Valid types: {list(CARD_TEMPLATES.keys())}")
    return fn(**kwargs)
