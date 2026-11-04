"""
Unit tests for schemas.py
Verifies Pydantic v2 schemas, positional & keyword construction, and hashing utilities.
"""

import time
import pytest
from schemas import (
    TaskContext,
    EscrowRecord,
    EscrowState,
    Decision,
    VaccineRule,
    VaccineStatus,
    VaccineMatch,
    VaccineAction,
    LedgerEntry,
    LedgerCheckpoint,
    ExecuteToolRequest,
    ExecuteToolResponse,
    SurgeryPruneRequest,
    SurgeryPruneResponse,
    DryRunRequest,
    DryRunResponse,
    CompilerProposeRequest,
    CompilerProposeResponse,
    DecisionResponse,
    ProxyState,
    canonical_json_dumps,
    compute_entry_hash,
    compute_change_hash,
    compute_progress_hash,
)


def test_task_context():
    # Keyword construction
    ctx = TaskContext(
        task_id="task-101",
        order_id=9901,
        tenant_id="acme-corp",
        amount=4500.0,
        customer="Acme-India"
    )
    assert ctx.task_id == "task-101"
    assert ctx.order_id == 9901
    assert ctx.tenant_id == "acme-corp"
    assert ctx.amount == 4500.0
    assert ctx.customer == "Acme-India"

    # Positional construction
    ctx_pos = TaskContext("task-102", 9902, "globex-corp", 1850.0, "Globex-Corp")
    assert ctx_pos.task_id == "task-102"
    assert ctx_pos.order_id == 9902


def test_escrow_record():
    now = time.time()
    rec = EscrowRecord(
        escrow_id="esc-001",
        task_id="task-101",
        state=EscrowState.PENDING,
        change_hash="a1b2c3d4",
        created_at=now,
        expires_at=now + 300,
        failed_attempts=[{"tool": "orders_tool", "status_code": 422, "count": 3}],
        compacted_messages=[{"role": "user", "content": "sync order"}],
    )
    assert rec.escrow_id == "esc-001"
    assert rec.state == EscrowState.PENDING
    assert rec.change_hash == "a1b2c3d4"
    assert len(rec.failed_attempts) == 1
    assert len(rec.compacted_messages) == 1

    # Positional initialization check
    rec_pos = EscrowRecord(
        "esc-002",
        "task-102",
        EscrowState.APPROVED,
        "e5f6a7b8",
        now,
        now + 300,
        [],
        []
    )
    assert rec_pos.escrow_id == "esc-002"
    assert rec_pos.state == EscrowState.APPROVED


def test_decision():
    dec = Decision(
        escrow_id="esc-001",
        approved=True,
        approver_id="santosh-lead",
        change_hash="a1b2c3d4",
        reason="Verified dry-run on /v2/orders passed with 200 OK"
    )
    assert dec.approved is True
    assert dec.approver_id == "santosh-lead"
    assert dec.change_hash == "a1b2c3d4"

    # Positional initialization check
    dec_pos = Decision("esc-002", False, "security-reviewer", "badhash", "Malformed tenant")
    assert dec_pos.approved is False
    assert dec_pos.reason == "Malformed tenant"


def test_vaccine_rule():
    match = VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders")
    action = VaccineAction(
        rewrite_path="/v2/orders",
        inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"}
    )
    rule = VaccineRule(
        id="VACCINE-042",
        status=VaccineStatus.SHADOW,
        created_at=time.time(),
        expires_at=time.time() + 86400,
        linked_pr="fix/vaccine-042-orders-v2",
        change_hash="a1b2c3d4",
        match=match,
        action=action,
        description="Migrate deprecated /v1/orders to /v2/orders with contextual X-Tenant-ID"
    )
    assert rule.id == "VACCINE-042"
    assert rule.status == VaccineStatus.SHADOW
    assert rule.linked_pr == "fix/vaccine-042-orders-v2"
    assert rule.action.rewrite_path == "/v2/orders"


def test_ledger_entry():
    entry = LedgerEntry(
        seq_no=1,
        timestamp=1700000000.0,
        escrow_id="esc-001",
        event_type="ESCROW_TRIPPED",
        payload={"order_id": 9901, "error": 422},
        prev_hash="0" * 64,
        entry_hash="f" * 64
    )
    assert entry.seq_no == 1
    assert entry.escrow_id == "esc-001"
    assert entry.prev_hash == "0" * 64


def test_canonical_json_dumps():
    data = {"b": 2, "a": 1, "nested": {"z": 10, "y": 20}}
    dumped = canonical_json_dumps(data)
    assert dumped == '{"a":1,"b":2,"nested":{"y":20,"z":10}}'


def test_compute_hashes():
    # Entry hash determinism
    h1 = compute_entry_hash(
        seq_no=1,
        timestamp=1700000000.0,
        escrow_id="esc-001",
        event_type="ESCROW_TRIPPED",
        payload={"order_id": 9901},
        prev_hash="0" * 64
    )
    h2 = compute_entry_hash(
        seq_no=1,
        timestamp=1700000000.0,
        escrow_id="esc-001",
        event_type="ESCROW_TRIPPED",
        payload={"order_id": 9901},
        prev_hash="0" * 64
    )
    assert h1 == h2
    assert len(h1) == 64

    # Change hash is exactly 8 hex chars
    ch = compute_change_hash({"rewrite_path": "/v2/orders"}, diff_text="--- a\n+++ b")
    assert len(ch) == 8

    # Progress hash determinism
    ph1 = compute_progress_hash("sync_customer_order", {"order_id": 9901}, 422, "err_fingerprint")
    ph2 = compute_progress_hash("sync_customer_order", {"order_id": 9901}, 422, "err_fingerprint")
    assert ph1 == ph2
    assert len(ph1) == 64


def test_proxy_state_and_requests():
    req = ExecuteToolRequest(
        task_id="task-1",
        tool_name="sync_customer_order",
        arguments={"order_id": 9901}
    )
    assert req.tool_name == "sync_customer_order"

    state = ProxyState(
        active_mode="LIVE",
        ledger_head_seq=5,
        ledger_head_hash="abc"
    )
    assert state.ledger_head_seq == 5
    assert state.active_mode == "LIVE"
