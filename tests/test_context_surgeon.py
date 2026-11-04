"""
Unit Tests for SwitchBlade Context Surgeon & Worker Agent (Milestone J2)
Owned by Janani (branch: feat/janani-agents-vaccine)

Covers:
1. Slicing failed retry turns as atomic (tool_use, tool_result) pairs.
2. Closing the trailing failed tool_use with structured tool_result (failed_attempts + completed_side_effects).
3. Stripping thinking and redacted_thinking blocks.
4. Validating message history (alternating roles, tool_use_id matching).
5. Token accounting (history tokens reduction and full request reduction).
6. WorkerAgent autonomous loop and schema compliance.
"""

import json
import pytest

from context_surgeon import (
    ContextSurgeryError,
    InvalidMessageHistoryError,
    count_tokens,
    estimate_tokens,
    prune_context,
    strip_thinking_blocks,
    validate_message_history,
)
from schemas import TaskContext
from worker_agent import WorkerAgent


def test_strip_thinking_blocks():
    """Verify thinking and redacted_thinking blocks are stripped cleanly from assistant turns."""
    messages = [
        {"role": "user", "content": "Settle order 9901."},
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Internal reasoning about order 9901..."},
                {"type": "redacted_thinking", "data": "cryptographic_hash"},
                {"type": "tool_use", "id": "toolu_01", "name": "sync_customer_order", "input": {"order_id": 9901}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_01", "content": '{"status": "error"}'}
            ],
        },
    ]

    stripped = strip_thinking_blocks(messages)
    asst_blocks = stripped[1]["content"]

    block_types = [b.get("type") for b in asst_blocks]
    assert "thinking" not in block_types
    assert "redacted_thinking" not in block_types
    assert "tool_use" in block_types
    assert len(asst_blocks) == 1


def test_validate_message_history_valid():
    """Verify validate_message_history accepts valid alternating history with matching tool_use_id."""
    messages = [
        {"role": "user", "content": "Please process order 9901."},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_alpha_123", "name": "sync_customer_order", "input": {"order_id": 9901}}
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_alpha_123", "content": '{"status": "ok"}'}
            ],
        },
    ]
    assert validate_message_history(messages) is True


def test_validate_message_history_role_alternation_violation():
    """Verify validate_message_history rejects non-alternating roles."""
    messages = [
        {"role": "user", "content": "First user message."},
        {"role": "user", "content": "Second consecutive user message."},
    ]
    with pytest.raises(InvalidMessageHistoryError, match="Role alternation violated"):
        validate_message_history(messages)


def test_validate_message_history_orphaned_tool_use():
    """Verify validate_message_history rejects assistant tool_use without matching tool_result."""
    messages = [
        {"role": "user", "content": "Process order."},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_orphan_1", "name": "sync_customer_order", "input": {"order_id": 9901}}
            ],
        },
        {
            "role": "user",
            "content": "I am just replying with text instead of a tool_result.",
        },
    ]
    with pytest.raises(InvalidMessageHistoryError, match="Orphaned tool_use detected"):
        validate_message_history(messages)


def test_validate_message_history_orphaned_tool_result():
    """Verify validate_message_history rejects tool_result without preceding matching tool_use."""
    messages = [
        {"role": "user", "content": "Process order."},
        {"role": "assistant", "content": "I did not call any tools."},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_ghost_999", "content": '{"result": 123}'}
            ],
        },
    ]
    with pytest.raises(InvalidMessageHistoryError, match="Orphaned tool_result detected"):
        validate_message_history(messages)


def test_context_surgery_atomic_pruning_and_token_reduction():
    """
    Simulate a 3-retry loop accumulating ~45,000 tokens of 422 diagnostic stack traces.
    Verify context surgeon:
    1. Removes redundant intermediate pairs atomically.
    2. Closes trailing tool_use with structured tool_result.
    3. Produces a valid history passing validate_message_history.
    4. Achieves >98% message history token reduction.
    """
    # Create large 15,000-token diagnostic trace (approx 55,000 characters)
    bloated_trace = "ERR_422_DIAGNOSTIC_FRAME " * 2200

    messages = [
        {"role": "user", "content": "Settle Order 9901."}
    ]

    # Add 3 failed attempts (each ~15,000 tokens)
    for attempt in range(1, 4):
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
                {"type": "tool_result", "tool_use_id": call_id, "content": bloated_trace}
            ],
        })

    # Prior to surgery: 7 messages (1 initial user + 3*(asst + user))
    assert len(messages) == 7

    # Run context surgery
    result = prune_context(
        messages=messages,
        failed_tool_name="sync_customer_order",
        status_code=422,
        count=3,
        directive="Do not retry /v1/orders; use verified override",
        completed_side_effects=[],
        system_prompt="You are the SwitchBlade Order Settlement Worker.",
    )

    pruned = result["compacted_messages"]

    # Invariants verification
    assert validate_message_history(pruned) is True

    # Check atomic pruning: intermediate attempts 1 & 2 must be removed
    # Resulting history: [user prompt, assistant tool_use (attempt 3), user tool_result (structured)]
    assert len(pruned) == 3
    assert pruned[0]["role"] == "user"
    assert pruned[1]["role"] == "assistant"
    assert pruned[2]["role"] == "user"

    # Trailing tool_result must contain structured failed_attempts summary
    compacted_result_block = pruned[2]["content"][0]
    assert compacted_result_block["type"] == "tool_result"
    assert compacted_result_block["tool_use_id"] == "toolu_attempt_3"

    payload = json.loads(compacted_result_block["content"])
    assert payload["status"] == "error"
    assert payload["failed_attempts"]["tool"] == "sync_customer_order"
    assert payload["failed_attempts"]["status_code"] == 422
    assert payload["failed_attempts"]["count"] == 3
    assert payload["failed_attempts"]["directive"] == "Do not retry /v1/orders; use verified override"
    assert payload["completed_side_effects"] == []

    # Check token reduction accounting
    tokens_before = result["history_tokens_before"]
    tokens_after = result["history_tokens_after"]
    reduction_pct = result["history_reduction_pct"]

    assert tokens_before > 40000, f"Expected >40,000 tokens before, got {tokens_before}"
    assert tokens_after < 500, f"Expected <500 tokens after, got {tokens_after}"
    assert reduction_pct >= 98.0, f"Expected >= 98% reduction, got {reduction_pct}%"


def test_worker_agent_simulation_and_history_validity():
    """Verify WorkerAgent generates valid Anthropic message histories in autonomous loop."""
    ctx = TaskContext(
        task_id="task_test_9901",
        order_id=9901,
        tenant_id="acme-corp",
        amount=4500.0,
        customer="Acme-India",
    )

    def mock_executor(tool_name, tool_input, tool_use_id, context):
        return {
            "status_code": 422,
            "error": "ENDPOINT_DEPRECATED_UNPROCESSABLE_ENTITY",
            "order_id": context.order_id,
        }

    worker = WorkerAgent(tool_executor=mock_executor)
    outcome = worker.run_settlement_task(ctx, max_turns=2)

    assert outcome["task_id"] == "task_test_9901"
    assert outcome["order_id"] == 9901
    assert outcome["turns_taken"] == 2

    # Validate generated message history passes Anthropic structural validation
    history = outcome["message_history"]
    assert validate_message_history(history) is True
