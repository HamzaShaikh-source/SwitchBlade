"""
Unit & Integration Tests for PolicyBot (Milestone A3)
Author: Aaditya Arunpal (feat/aaditya-switch-bridge)

Verifies the automated @policy-bot actor in SwitchBlade rooms:
1. Auto-approval flow triggered by status cards.
2. Scripted rejection flow on flagged escrows.
3. Vaccine promotion command issuance.
4. Prevention of infinite message echo loops.
5. Integration with SwitchBridge.
"""

import json
import pytest
from switch_bridge import SwitchBridge, BridgeMode, PolicyBot


@pytest.fixture
def bridge_with_bot():
    bridge = SwitchBridge(
        mode=BridgeMode.MOCK,
        human_allowlist={"aaditya", "hamza", "santosh", "janani", "policy-bot"},
        agent_ids={"switchblade-proxy", "sb-surgeon", "sb-scout", "sb-compiler"},
    )
    bridge.enable_policy_bot(
        auto_approve=True,
        auto_promote=True,
        reject_escrows={"escrow-bad-policy": "Cost threshold exceeded"},
    )
    return bridge


@pytest.mark.asyncio
async def test_policy_bot_auto_approve(bridge_with_bot, monkeypatch):
    """
    Verifies that when an agent posts a DRY_RUN_VERIFIED status card,
    @policy-bot detects the APPROVE command block and issues the approval.
    """
    dispatched_decisions = []

    async def mock_dispatch(self, escrow_id, change_hash, approver):
        dispatched_decisions.append({
            "escrow_id": escrow_id,
            "change_hash": change_hash,
            "approver": approver,
            "action": "APPROVE",
        })
        return {"status": "success", "state": "APPROVED"}

    monkeypatch.setattr(SwitchBridge, "_dispatch_approval", mock_dispatch)

    # Agent @sb-scout posts the verification card into the room
    scout_card = (
        "### 🛡️ [DRY RUN VERIFIED] Escrow: `escrow-auto-101` | Change Hash: `a1b2c3d4`\n"
        "**Fix Proposal:** Spec-differ verified: `/v1/orders` -> `/v2/orders`\n"
        "**Action Required:** Human reply `APPROVE escrow-auto-101 a1b2c3d4` or `REJECT escrow-auto-101 <reason>`"
    )

    await bridge_with_bot.handle_room_message(
        sender="@sb-scout",
        body=scout_card,
        message_id="msg-scout-card-01",
        addressed=True,
    )

    assert len(dispatched_decisions) == 1
    decision = dispatched_decisions[0]
    assert decision["escrow_id"] == "escrow-auto-101"
    assert decision["change_hash"] == "a1b2c3d4"
    assert decision["approver"] == "policy-bot"


@pytest.mark.asyncio
async def test_policy_bot_reject_flow(bridge_with_bot, monkeypatch):
    """
    Verifies that when an escrow is flagged in reject_escrows,
    @policy-bot issues REJECT instead of APPROVE.
    """
    dispatched_rejections = []

    async def mock_reject(self, escrow_id, reason, approver):
        dispatched_rejections.append({
            "escrow_id": escrow_id,
            "reason": reason,
            "approver": approver,
            "action": "REJECT",
        })
        return {"status": "success", "state": "REJECTED"}

    monkeypatch.setattr(SwitchBridge, "_dispatch_rejection", mock_reject)

    bad_card = (
        "### 🚨 [DRY RUN VERIFIED] Escrow: `escrow-bad-policy` | Change Hash: `ffff0000`\n"
        "Action Required: Human reply `APPROVE escrow-bad-policy ffff0000`"
    )

    await bridge_with_bot.handle_room_message(
        sender="@sb-scout",
        body=bad_card,
        message_id="msg-bad-card-01",
        addressed=True,
    )

    assert len(dispatched_rejections) == 1
    rejection = dispatched_rejections[0]
    assert rejection["escrow_id"] == "escrow-bad-policy"
    assert rejection["reason"] == "Cost threshold exceeded"
    assert rejection["approver"] == "policy-bot"


@pytest.mark.asyncio
async def test_policy_bot_promote_flow(bridge_with_bot, monkeypatch):
    """
    Verifies that when a vaccine promotion prompt is detected,
    @policy-bot issues PROMOTE <vaccine_id> <change_hash>.
    """
    dispatched_promotes = []

    async def mock_promote(self, vaccine_id, change_hash, approver):
        dispatched_promotes.append({
            "vaccine_id": vaccine_id,
            "change_hash": change_hash,
            "approver": approver,
        })
        return {"status": "success", "state": "ENFORCE"}

    monkeypatch.setattr(SwitchBridge, "_dispatch_promote", mock_promote)

    compiler_card = (
        "### 💉 [VACCINE COMPILED] Vaccine: `VACCINE-099` | Hash: `abcd1234`\n"
        "Candidate vaccine staged in SHADOW mode.\n"
        "Prompt: Run PROMOTE VACCINE-099 abcd1234 to enter ENFORCE mode."
    )

    await bridge_with_bot.handle_room_message(
        sender="@sb-compiler",
        body=compiler_card,
        message_id="msg-compiler-card-01",
        addressed=True,
    )

    assert len(dispatched_promotes) == 1
    prom = dispatched_promotes[0]
    assert prom["vaccine_id"] == "VACCINE-099"
    assert prom["change_hash"] == "abcd1234"
    assert prom["approver"] == "policy-bot"


@pytest.mark.asyncio
async def test_policy_bot_ignores_self_echoes(bridge_with_bot):
    """
    Verifies that messages sent by @policy-bot do not trigger self-echo loops.
    """
    res = await bridge_with_bot.policy_bot.on_room_message(
        sender="@policy-bot",
        body="APPROVE escrow-123 11223344",
        message_id="msg-policy-bot-self",
    )
    assert res is None
