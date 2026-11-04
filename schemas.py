"""
SwitchBlade Shared Schemas (v2)
Author: Santosh Subramanian (feat/santosh-proxy-ledger)

Core runtime contracts shared across all SwitchBlade components:
- Member 1 (Hamza Shaikh): Rich Cockpit UI & Switch Room Cards
- Member 2 (Santosh Subramanian): Core Runtime Proxy, Escrow State Machine & Canonical Ledger
- Member 3 (Aaditya Arunpal): Switch Console Bridge & WebSocket/HTTP Ops Protocol
- Member 4 (Janani): AI Agents, Context Surgery, Vaccine Registry & Mock Billing API
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EscrowState(str, Enum):
    """Lifecycle states of an Escrow record."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class VaccineStatus(str, Enum):
    """Two-stage governance states for Vaccine rules."""
    SHADOW = "SHADOW"
    ENFORCE = "ENFORCE"
    ROLLED_BACK = "ROLLED_BACK"


class LedgerEventType(str, Enum):
    """Event types recorded in the tamper-evident SQLite ledger."""
    GENESIS = "GENESIS"
    ESCROW_TRIPPED = "ESCROW_TRIPPED"
    CONTEXT_SURGERY_COMPLETED = "CONTEXT_SURGERY_COMPLETED"
    DRY_RUN_EXECUTED = "DRY_RUN_EXECUTED"
    VACCINE_PROPOSED = "VACCINE_PROPOSED"
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_REJECTED = "DECISION_REJECTED"
    VACCINE_PROMOTED = "VACCINE_PROMOTED"
    VACCINE_ROLLED_BACK = "VACCINE_ROLLED_BACK"
    LEDGER_CHECKPOINT = "LEDGER_CHECKPOINT"


# ---------------------------------------------------------------------------
# Canonical Serialization & Hashing Helpers
# ---------------------------------------------------------------------------

def canonical_json_dumps(obj: Any) -> str:
    """
    Serializes an object to deterministic canonical JSON:
    - Sorted keys
    - No unnecessary whitespace (separators=(',', ':'))
    - Safe handling of Pydantic models, dicts, enums, floats
    """
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    elif isinstance(obj, Enum):
        obj = obj.value

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(
    seq_no: int,
    timestamp: float,
    escrow_id: str,
    event_type: str,
    payload: Dict[str, Any],
    prev_hash: str,
) -> str:
    """
    Computes a SHA-256 hash for a ledger entry anchored with domain prefix.
    Format:
    SWITCHBLADE-LEDGER-V1|{seq_no}|{timestamp:.6f}|{escrow_id}|{event_type}|{canonical_payload}|{prev_hash}
    """
    canonical_payload = canonical_json_dumps(payload)
    raw = (
        f"SWITCHBLADE-LEDGER-V1|{seq_no}|{timestamp:.6f}|"
        f"{escrow_id}|{event_type}|{canonical_payload}|{prev_hash}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_change_hash(rule_data: Union[Dict[str, Any], BaseModel, str], diff_text: str = "") -> str:
    """
    Computes an 8-character SHA-256 change hash over canonical vaccine JSON + code diff.
    Used for hash-bound human approval (e.g. APPROVE <escrow_id> <change_hash>).
    """
    if isinstance(rule_data, BaseModel):
        canonical_rule = canonical_json_dumps(rule_data.model_dump(mode="json"))
    elif isinstance(rule_data, dict):
        canonical_rule = canonical_json_dumps(rule_data)
    else:
        canonical_rule = str(rule_data).strip()

    raw = f"{canonical_rule}|{diff_text.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def compute_progress_hash(
    tool_name: str,
    canonical_args: Union[Dict[str, Any], str],
    status_code: int,
    response_fingerprint: str,
) -> str:
    """
    Computes progress hash across consecutive turns to detect Zero-Progress Spin Cycles.
    sha256(f"{tool_name}|{canonical_args}|{status_code}|{response_fingerprint}")
    """
    if not isinstance(canonical_args, str):
        canonical_args = canonical_json_dumps(canonical_args)
    raw = f"{tool_name}|{canonical_args}|{status_code}|{response_fingerprint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Core Milestone S1 Pydantic Models
# ---------------------------------------------------------------------------

class TaskContext(BaseModel):
    """
    Context-bound task identity used for tenant isolation and idempotency.
    Guarantees no Confused Deputy vulnerabilities when injecting headers.
    """
    task_id: str = Field(..., description="Unique task execution ID")
    order_id: int = Field(..., description="Order identifier being processed")
    tenant_id: str = Field(..., description="Authenticated tenant identifier (e.g. acme-corp)")
    amount: float = Field(..., description="Monetary settlement amount")
    customer: str = Field(..., description="Customer identifier or name")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, *args: Any, **data: Any):
        if args:
            field_names = ["task_id", "order_id", "tenant_id", "amount", "customer"]
            for name, val in zip(field_names, args):
                data[name] = val
        super().__init__(**data)


class EscrowRecord(BaseModel):
    """
    State-machine record created when the circuit breaker trips.
    Holds frozen execution state pending human or automated Switch governance.
    """
    escrow_id: str = Field(..., description="Unique escrow identifier")
    task_id: str = Field(..., description="Associated task ID")
    state: EscrowState = Field(default=EscrowState.PENDING, description="State of escrow")
    change_hash: Optional[str] = Field(
        default=None, description="8-character SHA-256 change hash of proposed fix"
    )
    created_at: float = Field(
        default_factory=lambda: time.time(), description="Creation epoch timestamp"
    )
    expires_at: Optional[float] = Field(
        default=None, description="Expiration epoch timestamp (TTL timeout)"
    )
    failed_attempts: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None, description="Diagnostic summary of failed retry attempts"
    )
    compacted_messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Surgeon-pruned Anthropic-valid message history"
    )

    # Optional metadata fields to assist proxy runtime, telemetry UI, and audits
    task_context: Optional[TaskContext] = Field(default=None, description="Task context snapshot")
    tool_name: Optional[str] = Field(default=None, description="Tool that triggered the escrow trip")
    error_message: Optional[str] = Field(default=None, description="Last error message or status")
    trip_reason: Optional[str] = Field(
        default=None, description="Circuit breaker trip reason: PERMANENT_ERROR_LOOP or ZERO_PROGRESS_SPIN_CYCLE"
    )
    retry_after: Optional[float] = Field(default=None, description="Retry-after seconds if transient")
    proposed_diff: Optional[str] = Field(default=None, description="Candidate code diff or patch")
    proposed_vaccine: Optional[Dict[str, Any]] = Field(
        default=None, description="Candidate vaccine rule dict"
    )
    decision: Optional["Decision"] = Field(default=None, description="Resolved decision if completed")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, *args: Any, **data: Any):
        if args:
            field_names = [
                "escrow_id",
                "task_id",
                "state",
                "change_hash",
                "created_at",
                "expires_at",
                "failed_attempts",
                "compacted_messages",
            ]
            for name, val in zip(field_names, args):
                data[name] = val
        super().__init__(**data)


class Decision(BaseModel):
    """
    Human or Policy-Bot decision resolving an EscrowRecord.
    Strictly verified by approver allowlist and change_hash equality.
    """
    escrow_id: str = Field(..., description="Target escrow identifier")
    approved: bool = Field(..., description="True if approved, False if rejected")
    approver_id: str = Field(..., description="Identifier of allowlisted approver")
    change_hash: Optional[str] = Field(
        default=None, description="Submitted change hash to match escrow"
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for rejection or approval commentary"
    )
    timestamp: float = Field(
        default_factory=lambda: time.time(), description="Epoch timestamp of decision"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, *args: Any, **data: Any):
        if args:
            field_names = ["escrow_id", "approved", "approver_id", "change_hash", "reason"]
            for name, val in zip(field_names, args):
                data[name] = val
        super().__init__(**data)


class VaccineMatch(BaseModel):
    """Criteria matching incoming tool calls for pre-send request rewrite."""
    tool_name: str = Field(..., description="Tool name (e.g. sync_customer_order)")
    http_method: str = Field(default="POST", description="HTTP method")
    path_template: str = Field(..., description="Path template (e.g. /v1/orders)")

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class VaccineAction(BaseModel):
    """Transformation applied when a vaccine match succeeds."""
    rewrite_path: Optional[str] = Field(default=None, description="Rewritten URL path (e.g. /v2/orders)")
    inject_headers_from_context: Dict[str, str] = Field(
        default_factory=dict,
        description="Context bindings, e.g. {'X-Tenant-ID': 'task.tenant_id'}"
    )
    inject_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Static HTTP headers to inject"
    )
    add_query_params: Dict[str, str] = Field(
        default_factory=dict,
        description="Query parameters to inject"
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class VaccineRule(BaseModel):
    """
    Zero-retry in-process rewrite rule.
    First registered in SHADOW mode, promoted to ENFORCE after human approval.
    """
    id: str = Field(..., description="Unique vaccine identifier (e.g. VACCINE-042)")
    status: VaccineStatus = Field(default=VaccineStatus.SHADOW, description="SHADOW or ENFORCE")
    created_at: float = Field(default_factory=lambda: time.time(), description="Creation timestamp")
    expires_at: Optional[float] = Field(default=None, description="TTL expiry timestamp")
    linked_pr: Optional[str] = Field(
        default=None, description="Linked Git PR or branch name (e.g. fix/vaccine-042-orders-v2)"
    )
    change_hash: str = Field(..., description="8-character SHA-256 change hash")
    match: Union[VaccineMatch, Dict[str, Any]] = Field(..., description="Match condition")
    action: Union[VaccineAction, Dict[str, Any]] = Field(..., description="Action directives")
    description: Optional[str] = Field(default=None, description="Human description of vaccine rule")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, *args: Any, **data: Any):
        if args:
            field_names = [
                "id",
                "status",
                "created_at",
                "expires_at",
                "linked_pr",
                "change_hash",
                "match",
                "action",
            ]
            for name, val in zip(field_names, args):
                data[name] = val
        super().__init__(**data)


class LedgerEntry(BaseModel):
    """
    Append-only tamper-evident ledger entry with SHA-256 cryptographic chaining.
    Anchored periodically into the Switch room.
    """
    seq_no: int = Field(..., description="Monotonically increasing sequence number")
    timestamp: float = Field(default_factory=lambda: time.time(), description="Creation timestamp")
    escrow_id: str = Field(..., description="Associated escrow identifier or system id")
    event_type: str = Field(..., description="Event type name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload dictionary")
    prev_hash: str = Field(..., description="SHA-256 hash of previous block or 64-char zeroes")
    entry_hash: str = Field(..., description="Canonical SHA-256 hash of this entry")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def __init__(self, *args: Any, **data: Any):
        if args:
            field_names = [
                "seq_no",
                "timestamp",
                "escrow_id",
                "event_type",
                "payload",
                "prev_hash",
                "entry_hash",
            ]
            for name, val in zip(field_names, args):
                data[name] = val
        super().__init__(**data)


# ---------------------------------------------------------------------------
# API Request & Response Schemas for Switch & Proxy Interop
# ---------------------------------------------------------------------------

class ExecuteToolRequest(BaseModel):
    """Payload sent by worker agent when executing a tool call through proxy."""
    task_id: str = Field(..., description="Task execution ID")
    tool_name: str = Field(..., description="Target tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool call arguments")
    context: Optional[TaskContext] = Field(default=None, description="Task context")

    model_config = ConfigDict(extra="allow")


class ExecuteToolResponse(BaseModel):
    """Response returned to worker agent from proxy tool execution."""
    status: str = Field(..., description="'success', 'error', 'tripped', 'rejected', or 'expired'")
    result: Optional[Any] = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    escrow_id: Optional[str] = Field(default=None, description="Escrow ID if circuit breaker tripped")
    vaccine_applied: Optional[str] = Field(default=None, description="ID of vaccine rule applied, if any")
    retry_after: Optional[float] = Field(
        default=None, description="Seconds to wait before retrying on transient error (honoring Retry-After)"
    )
    trip_reason: Optional[str] = Field(
        default=None, description="Circuit breaker trip reason: PERMANENT_ERROR_LOOP or ZERO_PROGRESS_SPIN_CYCLE"
    )

    model_config = ConfigDict(extra="allow")


class SurgeryPruneRequest(BaseModel):
    """Sent by {team}-surgeon to compact frozen worker history."""
    escrow_id: str = Field(..., description="Target escrow identifier")

    model_config = ConfigDict(extra="allow")


class SurgeryPruneResponse(BaseModel):
    """Returned to {team}-surgeon after atomic context pruning."""
    escrow_id: str = Field(..., description="Escrow identifier")
    history_tokens_before: int = Field(..., description="Message history tokens before pruning")
    history_tokens_after: int = Field(..., description="Message history tokens after pruning")
    full_request_tokens_before: int = Field(..., description="Full request tokens before pruning")
    full_request_tokens_after: int = Field(..., description="Full request tokens after pruning")
    cost_usd: float = Field(..., description="Cumulative cost logged up to trip")
    failed_attempts_summary: Union[Dict[str, Any], List[Any]] = Field(
        ..., description="Preserved failed attempts summary"
    )

    model_config = ConfigDict(extra="allow")


class DryRunRequest(BaseModel):
    """Sent by {team}-scout to validate candidate fix against API schema."""
    escrow_id: str = Field(..., description="Target escrow identifier")

    model_config = ConfigDict(extra="allow")


class DryRunResponse(BaseModel):
    """Returned to {team}-scout with dry-run verification results."""
    escrow_id: str = Field(..., description="Escrow identifier")
    success: bool = Field(..., description="Whether non-mutating dry-run succeeded")
    proposed_route: str = Field(..., description="Proposed route (e.g. /v2/orders)")
    dry_run_result: Dict[str, Any] = Field(default_factory=dict, description="Mock API response")
    message: str = Field(..., description="Diagnostic output from dry-run")

    model_config = ConfigDict(extra="allow")


class CompilerProposeRequest(BaseModel):
    """Sent by {team}-compiler to generate vaccine rule and git diff."""
    escrow_id: str = Field(..., description="Target escrow identifier")

    model_config = ConfigDict(extra="allow")


class CompilerProposeResponse(BaseModel):
    """Returned to {team}-compiler with proposed vaccine rule and patch."""
    escrow_id: str = Field(..., description="Escrow identifier")
    change_hash: str = Field(..., description="8-character SHA-256 change hash")
    vaccine_rule: VaccineRule = Field(..., description="Proposed vaccine rule")
    patch_diff: str = Field(..., description="Unified git patch diff")
    pr_draft: str = Field(..., description="Draft PR description markdown")

    model_config = ConfigDict(extra="allow")


class DecisionResponse(BaseModel):
    """Returned from POST /escrow/decision when human submits approval/rejection."""
    status: str = Field(..., description="'success' or 'error'")
    escrow_id: str = Field(..., description="Escrow identifier")
    state: EscrowState = Field(..., description="Resulting state: APPROVED or REJECTED")
    message: str = Field(..., description="Human-readable result summary")

    model_config = ConfigDict(extra="allow")


class LedgerCheckpoint(BaseModel):
    """External checkpoint broadcast to Switch Room every 5 ledger entries."""
    seq: int = Field(..., description="Head sequence number")
    head_hash: str = Field(..., description="SHA-256 entry hash of head block")
    timestamp: float = Field(default_factory=lambda: time.time(), description="Checkpoint timestamp")

    model_config = ConfigDict(extra="allow")


class ProxyState(BaseModel):
    """Full telemetry snapshot read by Rich Cockpit UI via GET /state."""
    escrows: Dict[str, EscrowRecord] = Field(default_factory=dict, description="Active and past escrows")
    vaccines: List[VaccineRule] = Field(default_factory=list, description="Active and past vaccines")
    ledger_head_seq: int = Field(default=0, description="Highest ledger sequence number")
    ledger_head_hash: str = Field(default="0" * 64, description="Current ledger head hash")
    active_mode: str = Field(default="LIVE", description="LIVE, REPLAY, or SELFTEST")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Operational metrics")

    model_config = ConfigDict(extra="allow")
