"""
SwitchBlade Test Suite
Owned by Janani (branch: feat/janani-agents-vaccine)

Runs automated validation for:
- Seeded Idempotent Mock Billing API (:8001) [Milestone J1]
- Context Surgeon atomic pair validity, thinking stripper, and token compaction [Milestone J2]
- Worker Agent tool execution loop and Anthropic message formatting [Milestone J2]
"""

from tests.test_mock_billing_api import (
    test_seeded_orders_exist,
    test_unknown_order_returns_404,
    test_v1_orders_returns_422_with_15k_tokens_trace,
    test_v2_orders_requires_x_tenant_id,
    test_v2_orders_rejects_tenant_mismatch,
    test_v2_orders_requires_idempotency_key_on_live_call,
    test_v2_orders_dry_run_via_query_param_does_not_mutate,
    test_v2_orders_dry_run_via_header_does_not_mutate,
    test_v2_orders_live_settlement_and_idempotency_cache,
    test_openapi_spec_marks_v1_deprecated_and_v2_active,
    test_orders_tool_definition_and_execution,
    reset_api,
    client,
)

from tests.test_context_surgeon import (
    test_strip_thinking_blocks,
    test_validate_message_history_valid,
    test_validate_message_history_role_alternation_violation,
    test_validate_message_history_orphaned_tool_use,
    test_validate_message_history_orphaned_tool_result,
    test_context_surgery_atomic_pruning_and_token_reduction,
    test_worker_agent_simulation_and_history_validity,
)

if __name__ == "__main__":
    import pytest
    import sys
    sys.exit(pytest.main(["-v", __file__]))
