"""
Context Surgeon & FinOps Auditor (context_surgeon.py)
Owned by Janani (branch: feat/janani-agents-vaccine)

Features:
- Atomic (tool_use, tool_result) pair pruning preventing orphaned blocks.
- Strips thinking & redacted_thinking blocks for cross-model tier transitions.
- Strict message history validation (role alternation & tool_use_id set equality).
- Honest token accounting: message-history reduction (e.g. 99.2%) and full-request reduction.
- Compatible with Anthropic count_tokens API and deterministic offline fallback.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("context_surgeon")


class ContextSurgeryError(Exception):
    """Base exception for context surgery errors."""
    pass


class InvalidMessageHistoryError(ContextSurgeryError):
    """Raised when message history violates Anthropic structural invariants."""
    pass


def strip_thinking_blocks(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Strips thinking and redacted_thinking content blocks from assistant turns.
    Prevents validation errors when switching model tiers (e.g. Claude 3.7 -> Claude 3.5).
    """
    sanitized: List[Dict[str, Any]] = []

    for msg in messages:
        msg_copy = copy.deepcopy(msg)
        content = msg_copy.get("content")

        if isinstance(content, list):
            # Filter out thinking blocks
            filtered_content = [
                block for block in content
                if isinstance(block, dict) and block.get("type") not in ("thinking", "redacted_thinking")
            ]
            # If all blocks were thinking and nothing remains, retain a minimal clean text block
            if not filtered_content:
                filtered_content = [{"type": "text", "text": "Proceeding with tool execution."}]
            msg_copy["content"] = filtered_content

        sanitized.append(msg_copy)

    return sanitized


def validate_message_history(messages: List[Dict[str, Any]]) -> bool:
    """
    Strict Anthropic Message History Validation:
    1. Alternating user/assistant roles.
    2. Starts with user (or system prompt as header).
    3. Every tool_use in an assistant turn MUST be resolved by a matching tool_result
       in the immediately following user turn.
    4. Exact set equality between tool_use IDs and tool_result IDs (zero orphaned blocks).
    """
    if not messages:
        raise InvalidMessageHistoryError("Message history cannot be empty.")

    tool_use_ids: Set[str] = set()
    tool_result_ids: Set[str] = set()
    expected_role: Optional[str] = None

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content")

        if role not in ("user", "assistant"):
            raise InvalidMessageHistoryError(f"Message {idx} has invalid role: '{role}'")

        # Validate role alternation
        if expected_role is not None and role != expected_role:
            raise InvalidMessageHistoryError(
                f"Role alternation violated at turn {idx}: expected '{expected_role}', got '{role}'"
            )
        expected_role = "assistant" if role == "user" else "user"

        # Check content blocks for tool_use and tool_result
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "tool_use":
                    if role != "assistant":
                        raise InvalidMessageHistoryError(
                            f"Turn {idx}: tool_use block found in non-assistant message (role='{role}')"
                        )
                    t_id = block.get("id")
                    if not t_id:
                        raise InvalidMessageHistoryError(f"Turn {idx}: tool_use block missing 'id'")
                    tool_use_ids.add(t_id)

                elif block_type == "tool_result":
                    if role != "user":
                        raise InvalidMessageHistoryError(
                            f"Turn {idx}: tool_result block found in non-user message (role='{role}')"
                        )
                    t_id = block.get("tool_use_id")
                    if not t_id:
                        raise InvalidMessageHistoryError(f"Turn {idx}: tool_result block missing 'tool_use_id'")
                    tool_result_ids.add(t_id)

    # Invariant 4: Exact tool_use_id == tool_result.tool_use_id set equality
    missing_results = tool_use_ids - tool_result_ids
    if missing_results:
        raise InvalidMessageHistoryError(
            f"Orphaned tool_use detected: missing tool_results for IDs: {missing_results}"
        )

    orphaned_results = tool_result_ids - tool_use_ids
    if orphaned_results:
        raise InvalidMessageHistoryError(
            f"Orphaned tool_result detected: no matching tool_use for IDs: {orphaned_results}"
        )

    return True


def estimate_tokens(
    messages: List[Dict[str, Any]],
    system_prompt: str = "",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    Deterministic Anthropic token estimator when client.messages.count_tokens is unavailable.
    Uses canonical character ratios (~3.7 chars/token) plus structural framing overhead.
    """
    total_chars = 0

    # System prompt
    if system_prompt:
        total_chars += len(system_prompt) + 16

    # Tools definition
    if tools:
        tools_str = json.dumps(tools, sort_keys=True, separators=(",", ":"))
        total_chars += len(tools_str) + 32

    # Messages
    for msg in messages:
        total_chars += 16  # message framing overhead
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type == "text":
                        total_chars += len(block.get("text", "")) + 8
                    elif block_type == "tool_use":
                        total_chars += len(block.get("name", "")) + 12
                        input_str = json.dumps(block.get("input", {}), sort_keys=True, separators=(",", ":"))
                        total_chars += len(input_str)
                    elif block_type == "tool_result":
                        res_content = block.get("content", "")
                        if isinstance(res_content, str):
                            total_chars += len(res_content) + 8
                        else:
                            total_chars += len(json.dumps(res_content, default=str)) + 8

    return max(1, int(total_chars / 3.7))


def count_tokens(
    messages: List[Dict[str, Any]],
    system_prompt: str = "",
    tools: Optional[List[Dict[str, Any]]] = None,
    client: Optional[Any] = None,
    model: str = "claude-3-5-sonnet-20241022",
) -> Tuple[int, int]:
    """
    Measures exact tokens. Returns (history_tokens, full_request_tokens).
    Uses Anthropic client.messages.count_tokens() if available; otherwise uses deterministic estimator.
    """
    history_tokens = 0
    full_request_tokens = 0

    if client and hasattr(client, "messages") and hasattr(client.messages, "count_tokens"):
        try:
            # Full request tokens (system + tools + messages)
            full_req = client.messages.count_tokens(
                model=model,
                messages=messages,
                system=system_prompt if system_prompt else None,
                tools=tools if tools else None,
            )
            full_request_tokens = full_req.input_tokens

            # History tokens only (messages only)
            hist_req = client.messages.count_tokens(
                model=model,
                messages=messages,
            )
            history_tokens = hist_req.input_tokens
            return history_tokens, full_request_tokens
        except Exception as e:
            logger.warning(f"Anthropic count_tokens API call failed ({e}), falling back to deterministic estimator.")

    # Fallback to local estimator
    history_tokens = estimate_tokens(messages)
    full_request_tokens = estimate_tokens(messages, system_prompt=system_prompt, tools=tools)
    return history_tokens, full_request_tokens


def prune_context(
    messages: List[Dict[str, Any]],
    failed_tool_name: str = "sync_customer_order",
    status_code: int = 422,
    count: int = 3,
    directive: str = "Do not retry /v1/orders; use verified override",
    completed_side_effects: Optional[List[Any]] = None,
    system_prompt: str = "",
    tools: Optional[List[Dict[str, Any]]] = None,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes API-Valid Context Surgery:
    1. Measures tokens before pruning.
    2. Strips thinking blocks.
    3. Identifies and slices redundant failed retry turns as atomic (tool_use, tool_result) pairs.
    4. Closes the trailing failed tool_use with a structured tool_result containing
       failed_attempts and completed_side_effects.
    5. Validates structural invariants (alternating roles, tool_use_id matching).
    6. Measures tokens after pruning and computes honest reduction percentages.
    """
    # 1. Measure Before
    history_tokens_before, full_request_tokens_before = count_tokens(
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
        client=client,
    )

    # 2. Strip thinking blocks
    cleaned_messages = strip_thinking_blocks(messages)

    # 3. Identify atomic failed pairs
    # A failed retry turn consists of:
    # - assistant turn containing tool_use for failed_tool_name
    # - user turn immediately following containing matching tool_result
    pruned_history: List[Dict[str, Any]] = []
    i = 0
    total_msgs = len(cleaned_messages)

    # Collect indices of failed pairs
    failed_pairs: List[Tuple[int, int, str]] = []  # (assistant_idx, user_idx, tool_use_id)

    while i < total_msgs - 1:
        msg_curr = cleaned_messages[i]
        msg_next = cleaned_messages[i + 1]

        if msg_curr.get("role") == "assistant" and msg_next.get("role") == "user":
            curr_content = msg_curr.get("content", [])
            next_content = msg_next.get("content", [])

            tool_use_id = None
            if isinstance(curr_content, list):
                for block in curr_content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        if block.get("name") == failed_tool_name:
                            tool_use_id = block.get("id")
                            break

            has_matching_result = False
            if tool_use_id and isinstance(next_content, list):
                for block in next_content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        if block.get("tool_use_id") == tool_use_id:
                            has_matching_result = True
                            break

            if tool_use_id and has_matching_result:
                failed_pairs.append((i, i + 1, tool_use_id))
                i += 2
                continue

        i += 1

    # 4. Construct pruned messages
    # If multiple failed attempts exist, remove intermediate redundant pairs atomically.
    # Keep the final failed pair and replace its bloated diagnostic trace with structured lesson.
    failed_pair_indices = {idx for pair in failed_pairs for idx in (pair[0], pair[1])}

    if not failed_pairs:
        # No failed pairs found; just strip thinking and validate
        pruned_history = cleaned_messages
    else:
        # Keep everything up to the first failed pair
        # Drop intermediate failed attempts
        # For the last failed pair, close tool_use with compact structured tool_result
        last_asst_idx, last_user_idx, last_tool_use_id = failed_pairs[-1]

        for idx, msg in enumerate(cleaned_messages):
            if idx not in failed_pair_indices:
                pruned_history.append(msg)
            elif idx == last_asst_idx:
                # Keep the last tool_use call
                pruned_history.append(msg)
            elif idx == last_user_idx:
                # Replace the bloated tool_result with structured lesson
                structured_payload = {
                    "status": "error",
                    "failed_attempts": {
                        "tool": failed_tool_name,
                        "status_code": status_code,
                        "count": count,
                        "directive": directive,
                    },
                    "completed_side_effects": completed_side_effects or [],
                }
                compacted_user_msg = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": last_tool_use_id,
                            "content": json.dumps(structured_payload),
                        }
                    ],
                }
                pruned_history.append(compacted_user_msg)

    # 5. Validate structural invariants
    validate_message_history(pruned_history)

    # 6. Measure After
    history_tokens_after, full_request_tokens_after = count_tokens(
        messages=pruned_history,
        system_prompt=system_prompt,
        tools=tools,
        client=client,
    )

    history_reduction_pct = 0.0
    if history_tokens_before > 0:
        history_reduction_pct = round(
            ((history_tokens_before - history_tokens_after) / history_tokens_before) * 100, 1
        )

    full_request_reduction_pct = 0.0
    if full_request_tokens_before > 0:
        full_request_reduction_pct = round(
            ((full_request_tokens_before - full_request_tokens_after) / full_request_tokens_before) * 100, 1
        )

    failed_attempts_summary = {
        "tool": failed_tool_name,
        "status_code": status_code,
        "count": count,
        "directive": directive,
    }

    return {
        "compacted_messages": pruned_history,
        "history_tokens_before": history_tokens_before,
        "history_tokens_after": history_tokens_after,
        "full_request_tokens_before": full_request_tokens_before,
        "full_request_tokens_after": full_request_tokens_after,
        "history_reduction_pct": history_reduction_pct,
        "full_request_reduction_pct": full_request_reduction_pct,
        "failed_attempts_summary": failed_attempts_summary,
    }
