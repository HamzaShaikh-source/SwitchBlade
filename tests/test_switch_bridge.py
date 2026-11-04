"""
Unit & Integration Tests for SwitchBridge (Milestone A2)
Author: Aaditya Arunpal (feat/aaditya-switch-bridge)
"""

import json
import pytest
from switch_bridge import SwitchBridge, BridgeMode


@pytest.fixture
def bridge():
    return SwitchBridge(
        switch_api_url="http://localhost:8000",
        switch_ws_url="ws://localhost:8000",
        proxy_url="http://localhost:8002",
        agent_id="switchblade-proxy",
        agent_token="mock-token-xyz",
        mode=BridgeMode.MOCK,
        human_allowlist={"aaditya", "hamza", "santosh", "janani", "policy-bot"},
        agent_ids={"switchblade-proxy", "sb-surgeon", "sb-scout", "sb-compiler"},
    )


def test_auth_headers(bridge):
    headers = bridge.get_auth_headers()
    assert headers["Authorization"] == "Bearer mock-token-xyz"
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Switch-Connection-Id"] == bridge.connection_id


def test_command_parsing(bridge):
    # Standard APPROVE
    cmd = bridge.parse_command("APPROVE escrow-101 a1b2c3d4")
    assert cmd is not None
    assert cmd["action"] == "APPROVE"
    assert cmd["escrow_id"] == "escrow-101"
    assert cmd["change_hash"] == "a1b2c3d4"

    # APPROVE with markdown code block
    cmd = bridge.parse_command("```APPROVE escrow-202 9876fedc```")
    assert cmd is not None
    assert cmd["action"] == "APPROVE"
    assert cmd["escrow_id"] == "escrow-202"
    assert cmd["change_hash"] == "9876fedc"

    # REJECT with reason
    cmd = bridge.parse_command("REJECT escrow-303 Breaches strict SLA policy")
    assert cmd is not None
    assert cmd["action"] == "REJECT"
    assert cmd["escrow_id"] == "escrow-303"
    assert cmd["reason"] == "Breaches strict SLA policy"

    # PROMOTE
    cmd = bridge.parse_command("PROMOTE VACCINE-042 1234abcd")
    assert cmd is not None
    assert cmd["action"] == "PROMOTE"
    assert cmd["vaccine_id"] == "VACCINE-042"
    assert cmd["change_hash"] == "1234abcd"

    # ROLLBACK
    cmd = bridge.parse_command("ROLLBACK VACCINE-042")
    assert cmd is not None
    assert cmd["action"] == "ROLLBACK"
    assert cmd["vaccine_id"] == "VACCINE-042"

    # Non-command chatter
    cmd = bridge.parse_command("Hello team, is the server running?")
    assert cmd is None


@pytest.mark.asyncio
async def test_message_deduplication(bridge):
    msg_id = "msg-duplicate-check-001"
    res1 = await bridge.handle_room_message(
        sender="@aaditya",
        body="APPROVE escrow-111 11112222",
        message_id=msg_id,
        addressed=True,
    )
    # Even if mock proxy dispatch fails or returns error dict, msg_id is marked seen
    assert msg_id in bridge.seen_message_ids

    # Second dispatch with identical message_id MUST be skipped immediately
    res2 = await bridge.handle_room_message(
        sender="@aaditya",
        body="APPROVE escrow-111 11112222",
        message_id=msg_id,
        addressed=True,
    )
    assert res2 is None


@pytest.mark.asyncio
async def test_agent_self_approval_blocked(bridge):
    # When an automated agent identity speaks in the room, it cannot approve escrows
    msg_id = "msg-agent-attempt"
    res = await bridge.handle_room_message(
        sender="@sb-surgeon",
        body="APPROVE escrow-999 deadbeef",
        message_id=msg_id,
        addressed=True,
    )
    assert res is None


@pytest.mark.asyncio
async def test_unauthorized_user_denied(bridge):
    msg_id = "msg-random-user"
    res = await bridge.handle_room_message(
        sender="@unauthorized_stranger",
        body="APPROVE escrow-888 cafebeef",
        message_id=msg_id,
        addressed=True,
    )
    assert res is not None
    assert res["status"] == "unauthorized"


@pytest.mark.asyncio
async def test_roundtrip_flow(bridge, monkeypatch):
    # Mock httpx dispatch to return success
    async def mock_post(client, url, *args, **kwargs):
        class MockResponse:
            status_code = 200
            text = '{"status": "success", "escrow_id": "test-1", "state": "APPROVED", "message": "OK"}'
            def json(self):
                return json.loads(self.text)
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    res = await bridge.handle_room_message(
        sender="@aaditya",
        body="APPROVE escrow-test-99 12345678",
        message_id="msg-roundtrip-ok",
        addressed=True,
    )
    assert res is not None
    assert res.get("status") == "success"
    assert res.get("state") == "APPROVED"
