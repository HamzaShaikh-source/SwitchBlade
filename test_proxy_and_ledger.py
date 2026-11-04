"""
End-to-End Unit & Integration Tests for proxy.py and ledger.py
Author: Santosh Subramanian (feat/santosh-proxy-ledger)

Covers Milestone S2 & S3 requirements:
1. SQLite Ledger Cryptographic Chaining & Checkpoint Triggering
2. Tamper Detection & verify_ledger CLI
3. Escrow State Machine & asyncio.Future resolution
4. All narrow SwitchBlade proxy endpoints (/proxy/execute_tool, /surgeon/prune, /scout/dryrun, /compiler/propose, /escrow/decision, /state)
5. Authorization allowlist & Hash-Bound verification
6. Zero-retry Pre-send Vaccine Request Rewrite
"""

import asyncio
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from ledger import LedgerManager
from schemas import (
    Decision,
    EscrowState,
    ExecuteToolRequest,
    LedgerEventType,
    TaskContext,
    VaccineStatus,
)
import proxy
from proxy import app, escrow_mgr, ledger_mgr


@pytest.fixture
def test_client():
    """Provides a fresh TestClient with reset in-memory state and temp ledger."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        temp_db_path = tmp.name

    # Point ledger manager to temporary DB
    temp_ledger = LedgerManager(db_path=temp_db_path)
    old_ledger = proxy.ledger_mgr
    old_escrow_mgr = proxy.escrow_mgr

    proxy.ledger_mgr = temp_ledger
    proxy.escrow_mgr = proxy.EscrowManager(ledger=temp_ledger)
    proxy.escrow_mgr.vaccines.clear()

    client = TestClient(app)
    yield client

    # Cleanup
    proxy.ledger_mgr = old_ledger
    proxy.escrow_mgr = old_escrow_mgr
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass


def test_ledger_chaining_and_checkpoints():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        mgr = LedgerManager(db_path=db_path)

        # Append 5 entries to trigger the checkpoint at seq 5
        checkpoint_obj = None
        for i in range(1, 6):
            entry, cp = mgr.append_entry(
                escrow_id=f"esc-{i}",
                event_type=LedgerEventType.ESCROW_TRIPPED,
                payload={"order_id": 9900 + i, "step": i},
            )
            assert entry.seq_no == i
            if i == 5:
                checkpoint_obj = cp

        assert checkpoint_obj is not None
        assert checkpoint_obj.seq == 5
        assert len(checkpoint_obj.head_hash) == 64

        # Verify internal integrity
        is_valid, msg, failed_seq = mgr.verify_chain(
            expected_checkpoint_hash=checkpoint_obj.head_hash,
            expected_seq=5,
        )
        assert is_valid is True
        assert failed_seq is None

        # Verify tamper detection
        mgr.corrupt_row_for_demo(seq_no=2)
        is_valid_after_tamper, msg_tamper, failed_seq_tamper = mgr.verify_chain()
        assert is_valid_after_tamper is False
        assert failed_seq_tamper == 2
        assert "TAMPER DETECTED AT SEQ 2" in msg_tamper

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


def test_proxy_health_and_state(test_client):
    resp = test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "switchblade-proxy"
    assert data["port"] == 8002

    resp_state = test_client.get("/state")
    assert resp_state.status_code == 200
    state_data = resp_state.json()
    assert "escrows" in state_data
    assert "vaccines" in state_data
    assert state_data["active_mode"] == "LIVE"


def test_full_d1_green_lifecycle(test_client):
    """
    Simulates the complete d1-green end-to-end flow:
    1. Worker trips circuit breaker on 3rd retry
    2. Escrow created in PENDING state with registered asyncio.Future
    3. Context Surgeon prunes history (/surgeon/prune)
    4. Scout dry-runs fix (/scout/dryrun)
    5. Compiler proposes vaccine + change_hash (/compiler/propose)
    6. Allowlist verification prevents unauthorized approvals
    7. Human posts APPROVE <escrow_id> <change_hash> (/escrow/decision)
    8. Future is resolved and Vaccine is promoted to ENFORCE
    9. Next tool call applies vaccine pre-send rewrite on Turn 1!
    """
    task_id = "task-order-9901"
    context = {
        "task_id": task_id,
        "order_id": 9901,
        "tenant_id": "acme-corp",
        "amount": 4500.0,
        "customer": "Acme-India",
    }
    tool_req = {
        "task_id": task_id,
        "tool_name": "sync_customer_order",
        "arguments": {"order_id": 9901},
        "context": context,
    }

    # Turns 1 & 2 fail downstream (mock API not up, returning 503)
    resp1 = test_client.post("/proxy/execute_tool", json=tool_req)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "error"

    resp2 = test_client.post("/proxy/execute_tool", json=tool_req)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "error"

    # Turn 3: Circuit breaker TRIPS
    resp3 = test_client.post("/proxy/execute_tool", json=tool_req)
    assert resp3.status_code == 200
    trip_data = resp3.json()
    assert trip_data["status"] == "tripped"
    escrow_id = trip_data["escrow_id"]
    assert escrow_id.startswith("esc-")

    # Verify Future was pre-registered
    assert escrow_id in proxy.escrow_mgr.futures
    future = proxy.escrow_mgr.futures[escrow_id]
    assert not future.done()

    # Step 3: Context Surgeon compacts history
    resp_prune = test_client.post("/surgeon/prune", json={"escrow_id": escrow_id})
    assert resp_prune.status_code == 200
    prune_data = resp_prune.json()
    assert prune_data["history_tokens_after"] < prune_data["history_tokens_before"]
    assert prune_data["history_tokens_after"] == 380

    # Step 4: Scout dry-run
    resp_scout = test_client.post("/scout/dryrun", json={"escrow_id": escrow_id})
    assert resp_scout.status_code == 200
    scout_data = resp_scout.json()
    assert scout_data["success"] is True
    assert scout_data["proposed_route"] == "/v2/orders"

    # Step 5: Compiler proposes vaccine
    resp_comp = test_client.post("/compiler/propose", json={"escrow_id": escrow_id})
    assert resp_comp.status_code == 200
    comp_data = resp_comp.json()
    change_hash = comp_data["change_hash"]
    assert len(change_hash) == 8

    # Step 6: Authorization check - Agent identity cannot self-approve
    agent_decision = {
        "escrow_id": escrow_id,
        "approved": True,
        "approver_id": "sb-compiler",  # Agent identity forbidden!
        "change_hash": change_hash,
    }
    resp_agent = test_client.post("/escrow/decision", json=agent_decision)
    assert resp_agent.status_code == 403

    # Step 7: Hash-Bound check - Wrong hash is rejected
    wrong_hash_decision = {
        "escrow_id": escrow_id,
        "approved": True,
        "approver_id": "santosh-lead",
        "change_hash": "deadbeef",
    }
    resp_badhash = test_client.post("/escrow/decision", json=wrong_hash_decision)
    assert resp_badhash.status_code == 403

    # Step 8: Valid Human Approval
    valid_decision = {
        "escrow_id": escrow_id,
        "approved": True,
        "approver_id": "santosh-lead",
        "change_hash": change_hash,
        "reason": "Dry run verified and diff audited",
    }
    resp_approve = test_client.post("/escrow/decision", json=valid_decision)
    assert resp_approve.status_code == 200
    assert resp_approve.json()["state"] == "APPROVED"

    # Verify Future was resolved
    assert future.done()
    assert future.result().approved is True

    # Step 9: Verify Vaccine was promoted to ENFORCE
    assert "VACCINE-042" in proxy.escrow_mgr.vaccines
    assert proxy.escrow_mgr.vaccines["VACCINE-042"].status == VaccineStatus.ENFORCE

    # Step 10: Verify Pre-Send rewrite triggers on subsequent tool call
    # Next call on Order 9902 gets vaccinated
    order_9902_req = {
        "task_id": "task-order-9902",
        "tool_name": "sync_customer_order",
        "arguments": {"order_id": 9902},
        "context": {
            "task_id": "task-order-9902",
            "order_id": 9902,
            "tenant_id": "acme-corp",
            "amount": 1850.0,
            "customer": "Globex-Corp",
        },
    }
    resp_next = test_client.post("/proxy/execute_tool", json=order_9902_req)
    # Even if mock API is offline (returning 503), the proxy records vaccine_applied
    assert resp_next.json()["vaccine_applied"] == "VACCINE-042"


def test_escrow_rejection_flow(test_client):
    """Verifies human rejection safely halts worker without hanging."""
    task_id = "task-reject-test"
    tool_req = {
        "task_id": task_id,
        "tool_name": "sync_customer_order",
        "arguments": {"order_id": 1234},
        "context": {
            "task_id": task_id,
            "order_id": 1234,
            "tenant_id": "acme-corp",
            "amount": 100.0,
            "customer": "TestCustomer",
        },
    }

    # Trip breaker
    for _ in range(3):
        resp = test_client.post("/proxy/execute_tool", json=tool_req)
    escrow_id = resp.json()["escrow_id"]

    # Reject
    reject_decision = {
        "escrow_id": escrow_id,
        "approved": False,
        "approver_id": "santosh-lead",
        "reason": "Unrecognized tool arguments",
    }
    resp_reject = test_client.post("/escrow/decision", json=reject_decision)
    assert resp_reject.status_code == 200
    assert resp_reject.json()["state"] == "REJECTED"

    # Verify escrow state in telemetry
    state = test_client.get("/state").json()
    assert state["escrows"][escrow_id]["state"] == "REJECTED"
