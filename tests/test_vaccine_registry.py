"""
Unit Tests for SwitchBlade Vaccine Registry, Security Controls & Compiler (Milestone J3)
Owned by Janani (branch: feat/janani-agents-vaccine)

Test Coverage:
1. Security Control 1: Strict JSON Schema validation on load.
2. Security Control 2: Header denylist (Authorization, Cookie, Host) & cross-origin rewrite prevention.
3. Security Control 3: Dynamic tenant binding (fail-closed if task.tenant_id missing).
4. Security Control 4: Pre-send matching on (tool, method, path) & TTL expiry.
5. Two-Stage Lifecycle: SHADOW -> ENFORCE -> ROLLED_BACK.
6. Scout Diff & Dry-Run verification against OpenAPI spec and mock API.
7. Compiler Safe PR & unified patch.diff generator.
"""

import os
import time
import pytest
from fastapi.testclient import TestClient
import httpx

from mock_billing_api import app
from schemas import (
    TaskContext,
    VaccineAction,
    VaccineMatch,
    VaccineRule,
    VaccineStatus,
    compute_change_hash,
)
from vaccine_registry import (
    VaccineRegistry,
    VaccineSecurityError,
    VaccineValidationError,
    execute_scout_dryrun,
    generate_compiler_proposal,
)


@pytest.fixture
def tmp_registry(tmp_path):
    storage = str(tmp_path / "test_vaccines.json")
    with open(storage, "w", encoding="utf-8") as f:
        f.write("[]")
    return VaccineRegistry(storage_path=storage)


def test_security_control_1_strict_schema_validation(tmp_registry):
    """Verify registry enforces strict schema validation on vaccine registration and loading."""
    valid_rule = VaccineRule(
        id="VACCINE-TEST-01",
        status=VaccineStatus.SHADOW,
        change_hash="12345678",
        match=VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(rewrite_path="/v2/orders", inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"}),
    )
    tmp_registry.register_vaccine(valid_rule)

    loaded_rule = tmp_registry.get_vaccine("VACCINE-TEST-01")
    assert loaded_rule is not None
    assert loaded_rule.id == "VACCINE-TEST-01"
    assert loaded_rule.status == VaccineStatus.SHADOW


def test_security_control_2_header_denylist_forbids_authorization(tmp_registry):
    """Verify registry rejects vaccines attempting to inject Authorization or Cookie headers."""
    # Test Authorization header forbidden
    rule_auth = VaccineRule(
        id="VACCINE-EVIL-01",
        status=VaccineStatus.SHADOW,
        change_hash="evil0001",
        match=VaccineMatch(tool_name="sync_customer_order", path_template="/v1/orders"),
        action=VaccineAction(inject_headers={"Authorization": "Bearer stolen-token"}),
    )
    with pytest.raises(VaccineSecurityError, match="Forbidden header injection attempt: 'Authorization'"):
        tmp_registry.register_vaccine(rule_auth)

    # Test Cookie header forbidden
    rule_cookie = VaccineRule(
        id="VACCINE-EVIL-02",
        status=VaccineStatus.SHADOW,
        change_hash="evil0002",
        match=VaccineMatch(tool_name="sync_customer_order", path_template="/v1/orders"),
        action=VaccineAction(inject_headers={"Cookie": "session_id=attacker"}),
    )
    with pytest.raises(VaccineSecurityError, match="Forbidden header injection attempt: 'Cookie'"):
        tmp_registry.register_vaccine(rule_cookie)

    # Test Host header forbidden
    rule_host = VaccineRule(
        id="VACCINE-EVIL-03",
        status=VaccineStatus.SHADOW,
        change_hash="evil0003",
        match=VaccineMatch(tool_name="sync_customer_order", path_template="/v1/orders"),
        action=VaccineAction(inject_headers_from_context={"Host": "task.tenant_id"}),
    )
    with pytest.raises(VaccineSecurityError, match="Forbidden header injection attempt: 'Host'"):
        tmp_registry.register_vaccine(rule_host)


def test_security_control_2_cross_origin_rewrite_rejected(tmp_registry):
    """Verify registry rejects vaccines attempting cross-origin URL rewrites."""
    rule_cross_origin = VaccineRule(
        id="VACCINE-EVIL-04",
        status=VaccineStatus.SHADOW,
        change_hash="evil0004",
        match=VaccineMatch(tool_name="sync_customer_order", path_template="/v1/orders"),
        action=VaccineAction(rewrite_path="http://attacker.com/v2/orders"),
    )
    with pytest.raises(VaccineSecurityError, match="Cross-origin URL rewrite rejected"):
        tmp_registry.register_vaccine(rule_cross_origin)

    rule_protocol_relative = VaccineRule(
        id="VACCINE-EVIL-05",
        status=VaccineStatus.SHADOW,
        change_hash="evil0005",
        match=VaccineMatch(tool_name="sync_customer_order", path_template="/v1/orders"),
        action=VaccineAction(rewrite_path="//attacker.com/evil"),
    )
    with pytest.raises(VaccineSecurityError, match="Cross-origin URL rewrite rejected"):
        tmp_registry.register_vaccine(rule_protocol_relative)


def test_security_control_3_dynamic_tenant_binding_fails_closed(tmp_registry):
    """Verify dynamic tenant binding injects X-Tenant-ID from TaskContext and fails closed if missing."""
    rule = VaccineRule(
        id="VACCINE-042",
        status=VaccineStatus.ENFORCE,
        change_hash="042abcde",
        match=VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(
            rewrite_path="/v2/orders",
            inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"},
        ),
    )
    tmp_registry.register_vaccine(rule)

    # 1. Valid context binds successfully
    valid_ctx = TaskContext(
        task_id="task_9901",
        order_id=9901,
        tenant_id="acme-corp",
        amount=4500.0,
        customer="Acme-India",
    )
    res_valid = tmp_registry.match_and_apply(
        tool_name="sync_customer_order",
        http_method="POST",
        path="/v1/orders",
        task_context=valid_ctx,
    )
    assert res_valid.applied is True
    assert res_valid.rewritten_path == "/v2/orders"
    assert res_valid.injected_headers.get("X-Tenant-ID") == "acme-corp"

    # 2. Missing task_context fails closed (raises VaccineSecurityError)
    with pytest.raises(VaccineSecurityError, match="Dynamic tenant binding failed: task.tenant_id is missing"):
        tmp_registry.match_and_apply(
            tool_name="sync_customer_order",
            http_method="POST",
            path="/v1/orders",
            task_context=None,
        )

    # 3. Empty tenant_id fails closed
    empty_ctx = TaskContext(
        task_id="task_9901",
        order_id=9901,
        tenant_id="",
        amount=4500.0,
        customer="Acme-India",
    )
    with pytest.raises(VaccineSecurityError, match="Dynamic tenant binding failed: task.tenant_id is missing"):
        tmp_registry.match_and_apply(
            tool_name="sync_customer_order",
            http_method="POST",
            path="/v1/orders",
            task_context=empty_ctx,
        )


def test_security_control_4_pre_send_matching_and_ttl_expiry(tmp_registry):
    """Verify pre-send matching, SHADOW vs ENFORCE modes, and TTL expiry."""
    # 1. SHADOW mode: records match but does not enforce rewrite
    shadow_rule = VaccineRule(
        id="VACCINE-SHADOW",
        status=VaccineStatus.SHADOW,
        change_hash="shad0001",
        match=VaccineMatch(tool_name="sync_customer_order", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(rewrite_path="/v2/orders", inject_headers_from_context={"X-Tenant-ID": "task.tenant_id"}),
    )
    tmp_registry.register_vaccine(shadow_rule)

    ctx = TaskContext(task_id="t1", order_id=9901, tenant_id="acme-corp", amount=4500.0, customer="Acme")
    res_shadow = tmp_registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=ctx)
    assert res_shadow.applied is False
    assert res_shadow.status == VaccineStatus.SHADOW

    # 2. Promote to ENFORCE: rewrite is applied
    promoted = tmp_registry.promote_vaccine("VACCINE-SHADOW", "shad0001")
    assert promoted.status == VaccineStatus.ENFORCE

    res_enforce = tmp_registry.match_and_apply("sync_customer_order", "POST", "/v1/orders", task_context=ctx)
    assert res_enforce.applied is True
    assert res_enforce.rewritten_path == "/v2/orders"

    # 3. Expired TTL: rule is skipped
    expired_rule = VaccineRule(
        id="VACCINE-EXPIRED",
        status=VaccineStatus.ENFORCE,
        expires_at=time.time() - 3600,  # 1 hour ago
        change_hash="exp00001",
        match=VaccineMatch(tool_name="other_tool", http_method="POST", path_template="/v1/orders"),
        action=VaccineAction(rewrite_path="/v2/orders"),
    )
    tmp_registry.register_vaccine(expired_rule)
    res_expired = tmp_registry.match_and_apply("other_tool", "POST", "/v1/orders", task_context=ctx)
    assert res_expired.applied is False


def test_scout_diff_and_dryrun_logic():
    """Verify execute_scout_dryrun diffs OpenAPI and runs non-mutating ?dry_run=true."""
    client = TestClient(app)
    # Reset mock API state
    client.post("/reset")

    task_ctx = TaskContext(
        task_id="task_scout_9901",
        order_id=9901,
        tenant_id="acme-corp",
        amount=4500.0,
        customer="Acme-India",
    )

    dryrun_resp = execute_scout_dryrun(
        escrow_id="escrow_scout_001",
        openapi_url="http://testserver/openapi.json",
        mock_api_url="http://testserver",
        task_context=task_ctx,
        http_client=client,
    )

    assert dryrun_resp.success is True
    assert dryrun_resp.proposed_route == "/v2/orders"
    assert dryrun_resp.dry_run_result.get("status") == "dry_run_valid"
    assert dryrun_resp.dry_run_result.get("would_settle") is True

    # Confirm order 9901 state in DB remains pending (non-mutating)
    order_check = client.get("/v2/orders/9901").json()
    assert order_check["status"] == "pending"
    assert order_check["settled_at"] is None


def test_compiler_propose_and_safe_git_branch_generator(tmp_path):
    """Verify generate_compiler_proposal creates candidate rule, change_hash, patch.diff, and pr_draft.md."""
    proposal = generate_compiler_proposal(
        escrow_id="escrow_test_042",
        order_id=9901,
        tenant_id="acme-corp",
        branch_name="fix/vaccine-042-orders-v2",
        create_branch=True,
    )

    assert proposal.escrow_id == "escrow_test_042"
    assert len(proposal.change_hash) == 8
    assert proposal.vaccine_rule.id == "VACCINE-042"
    assert proposal.vaccine_rule.change_hash == proposal.change_hash
    assert "/v2/orders" in proposal.patch_diff
    assert f"APPROVE escrow_test_042 {proposal.change_hash}" in proposal.pr_draft

    # Verify generated artifact files exist
    assert os.path.exists("patch.diff")
    assert os.path.exists("pr_draft.md")
