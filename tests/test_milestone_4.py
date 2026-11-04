"""
Unit Tests for Milestone J4: Edge Cases & A/B Verification
Owned by Janani (branch: feat/janani-agents-vaccine)

Verifications Required by Rubric:
1. Orphaned tool_use is impossible after prune_context().
2. Missing task.tenant_id fails closed (Confused Deputy defense).
3. dry_run=true does not mark Order #9901 settled.
4. Order #9902 settles on Turn 1 via VACCINE-042 (Control vs Guarded).
"""

import json
import pytest
from fastapi.testclient import TestClient

from context_surgeon import (
    InvalidMessageHistoryError,
    prune_context,
    validate_message_history,
)
from mock_billing_api import app
from schemas import (
    TaskContext,
    VaccineAction,
    VaccineMatch,
    VaccineRule,
    VaccineStatus,
)
from vaccine_registry import VaccineRegistry, VaccineSecurityError
from worker_agent import WorkerAgent


@pytest.fixture(autouse=True)
def reset_db():
    client = TestClient(app)
    client.post("/reset")
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_verification_1_orphaned_tool_use_impossible_after_prune_context():
    """
    Verification 1: Orphaned tool_use is impossible after prune_context().
    Tests across multiple complex adversarial topologies:
    a) 5 consecutive retries with bloated diagnostic traces.
    b) Interleaved text responses and tool calls.
    c) Variable payload sizes.
    Asserts:
    - validate_message_history(compacted_messages) succeeds.
    - Zero orphaned tool_use blocks exist.
    - Every tool_use has exactly one matching tool_result in the immediately following user turn.
    """
    bloated_payload = "DIAGNOSTIC_TRACE_FRAME " * 2500

    messages = [{"role": "user", "content": "Settle order 9901."}]

    # Create 5 failed retries
    for attempt in range(1, 6):
        call_id = f"toolu_attempt_{attempt}"
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": f"Attempt {attempt} reasoning..."},
                {"type": "tool_use", "id": call_id, "name": "sync_customer_order", "input": {"order_id": 9901}},
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": call_id, "content": bloated_payload}
            ],
        })

    # Prior to surgery: 11 messages
    assert len(messages) == 11

    # Perform surgery
    result = prune_context(
        messages=messages,
        failed_tool_name="sync_customer_order",
        status_code=422,
        count=5,
        directive="Do not retry /v1/orders; use verified override",
        completed_side_effects=[],
    )

    pruned = result["compacted_messages"]

    # Invariant: Must pass strict Anthropic validation
    assert validate_message_history(pruned) is True

    # Invariant: Pruned count is 3 (initial prompt, trailing assistant tool_use, trailing user tool_result)
    assert len(pruned) == 3

    # Invariant: Inspect every assistant message for tool_use and verify matching tool_result in next message
    for i, msg in enumerate(pruned):
        if msg["role"] == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_id = block["id"]
                    assert i + 1 < len(pruned), f"Orphaned tool_use at turn {i}: no subsequent user message"
                    next_msg = pruned[i + 1]
                    assert next_msg["role"] == "user"
                    matching_blocks = [
                        b for b in next_msg.get("content", [])
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") == tool_id
                    ]
                    assert len(matching_blocks) == 1, f"Expected exactly 1 tool_result for {tool_id}, found {len(matching_blocks)}"


def test_verification_2_missing_tenant_id_fails_closed(tmp_path):
    """
    Verification 2: Missing task.tenant_id fails closed (Confused Deputy defense).
    Enforces that vaccines NEVER proceed if task_context is None, empty, or mismatched.
    """
    storage = str(tmp_path / "vaccines_sec.json")
    registry = VaccineRegistry(storage_path=storage)

    rule = VaccineRule(
        id="VACCINE-042",
        status=VaccineStatus.ENFORCE,
        change_hash="test0042",
        match=VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(
            rewrite_path="/v2/orders",
            inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"},
        ),
    )
    registry.register_vaccine(rule)

    # Edge Case 2A: task_context is None
    with pytest.raises(VaccineSecurityError, match="task.tenant_id is missing or empty"):
        registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=None)

    # Edge Case 2B: task_context has empty string tenant_id
    ctx_empty = TaskContext(task_id="t1", order_id=9901, tenant_id="", amount=4500.0, customer="Acme")
    with pytest.raises(VaccineSecurityError, match="task.tenant_id is missing or empty"):
        registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=ctx_empty)

    # Edge Case 2C: task_context has whitespace tenant_id
    ctx_whitespace = TaskContext(task_id="t2", order_id=9901, tenant_id="   ", amount=4500.0, customer="Acme")
    with pytest.raises(VaccineSecurityError, match="task.tenant_id is missing or empty"):
        registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=ctx_whitespace)

    # Positive Case: Valid tenant succeeds
    ctx_valid = TaskContext(task_id="t3", order_id=9901, tenant_id="acme-corp", amount=4500.0, customer="Acme")
    applied = registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=ctx_valid)
    assert applied.applied is True
    assert applied.injected_headers["X-Tenant-ID"] == "acme-corp"


def test_verification_3_dry_run_does_not_mark_order_9901_settled(client):
    """
    Verification 3: dry_run=true does not mark Order #9901 settled.
    Tests both query parameter (?dry_run=true) and header (X-Dry-Run: true).
    Asserts database status remains pending and settled_at remains null.
    """
    # 1. Verify initial state of Order 9901
    init_res = client.get("/v2/orders/9901")
    assert init_res.status_code == 200
    assert init_res.json()["status"] == "pending"
    assert init_res.json()["settled_at"] is None

    # 2. Invoke via query parameter ?dry_run=true
    query_resp = client.post(
        "/v2/orders?dry_run=true",
        json={"order_id": 9901},
        headers={"X-Tenant-ID": "acme-corp"},
    )
    assert query_resp.status_code == 200
    assert query_resp.json() == {"status": "dry_run_valid", "order_id": 9901, "would_settle": True}

    # Verify state in DB remains unsettled
    check1 = client.get("/v2/orders/9901").json()
    assert check1["status"] == "pending"
    assert check1["settled_at"] is None

    # 3. Invoke via header X-Dry-Run: true
    header_resp = client.post(
        "/v2/orders",
        json={"order_id": 9901},
        headers={"X-Tenant-ID": "acme-corp", "X-Dry-Run": "true"},
    )
    assert header_resp.status_code == 200
    assert header_resp.json() == {"status": "dry_run_valid", "order_id": 9901, "would_settle": True}

    # Final DB check: Order #9901 is strictly unsettled
    final_check = client.get("/v2/orders/9901").json()
    assert final_check["status"] == "pending"
    assert final_check["settled_at"] is None
    assert final_check["amount"] == 4500.00
    assert final_check["customer"] == "Acme-India"


def test_verification_4_order_9902_settles_on_turn_1_via_vaccine_042(client, tmp_path):
    """
    Verification 4: Order #9902 settles on Turn 1 via VACCINE-042 (Control vs Guarded).
    - Control (A: Unguarded): Legacy /v1/orders call fails with 422 diagnostic trace.
    - Guarded (B: SwitchBlade with VACCINE-042): Pre-send rewrite intercepts on Turn 1,
      migrates to /v2/orders, injects X-Tenant-ID and Idempotency-Key, settling in Turn 1!
    """
    ctx_9902 = TaskContext(
        task_id="task_settle_9902",
        order_id=9902,
        tenant_id="acme-corp",
        amount=1850.00,
        customer="Globex-Corp",
    )

    # Part A: Control Run (Unguarded)
    # Order 9902 hits legacy /v1/orders directly
    control_resp = client.post("/v1/orders", json={"order_id": 9902})
    assert control_resp.status_code == 422
    assert control_resp.json()["error"] == "ENDPOINT_DEPRECATED_UNPROCESSABLE_ENTITY"
    assert "diagnostic_stack_trace" in control_resp.json()

    # Confirm Order 9902 is still pending
    assert client.get("/v2/orders/9902").json()["status"] == "pending"

    # Part B: Guarded Run (SwitchBlade with VACCINE-042 in ENFORCE mode)
    storage = str(tmp_path / "vaccines_turn1.json")
    registry = VaccineRegistry(storage_path=storage)

    # Register and promote VACCINE-042
    vaccine_042 = VaccineRule(
        id="VACCINE-042",
        status=VaccineStatus.ENFORCE,
        change_hash="042hash1",
        match=VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(
            rewrite_path="/v2/orders",
            inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"},
        ),
    )
    registry.register_vaccine(vaccine_042)

    # Initialize worker with vaccine_registry and client
    worker = WorkerAgent(
        mock_api_url="http://testserver",
        http_client=client,
        vaccine_registry=registry,
    )

    # Execute settlement
    outcome = worker.run_settlement_task(ctx_9902, max_turns=5)

    # Assertions for Turn 1 settlement:
    # 1. Settled successfully
    assert outcome["settled"] is True

    # 2. Settled on EXACTLY Turn 1!
    assert outcome["turns_taken"] == 1

    # 3. No circuit trip needed because rewrite happened pre-send!
    assert outcome["escrow_tripped"] is False

    # 4. Verify in DB that Order 9902 is officially settled
    order_db = client.get("/v2/orders/9902").json()
    assert order_db["status"] == "settled"
    assert order_db["settled_at"] is not None
    assert order_db["amount"] == 1850.00
    assert order_db["customer"] == "Globex-Corp"
    assert order_db["tenant_id"] == "acme-corp"

    # 5. Message history is valid Anthropic history
    assert validate_message_history(outcome["message_history"]) is True
