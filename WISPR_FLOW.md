# Hands-Free Voice Governance with Wispr Flow
**Wispr Flow Side Track ($500) | SwitchBlade Integration Guide**

---

## 1. Overview

**Wispr Flow** enables high-speed, noise-resilient natural voice dictation directly into any text input surface. In **SwitchBlade**, Wispr Flow provides hands-free operational governance for on-call engineers managing autonomous AI agents in real time.

When background agents process critical business workflows (ERP reconciliation, invoice processing, order settlements), incident responders often monitor telemetry from mobile devices or secondary monitors while multitasking. Wispr Flow allows engineers to dictate room approvals, rejections, or promotions into the Switch room with zero typing latency.

---

## 2. Voice Governance Architecture

```
   ┌──────────────────────────────────────────────────────────────┐
   │             On-Call Engineer (Voice via Wispr Flow)          │
   │ "Approve escrow nine nine zero one with hash eight f four... │
   └──────────────────────────────┬───────────────────────────────┘
                                  │ Wispr Flow Dictation
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                  Switch Room (Mattermost / Slack)            │
   │           Message: `APPROVE esc-9901 8f4b2a1c`               │
   └──────────────────────────────┬───────────────────────────────┘
                                  │ Switch WebSocket Protocol
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │            SwitchBlade Proxy (:8002 /escrow/decision)         │
   │         1. Verify allowlisted approver identity              │
   │         2. Compare SHA-256 change_hash                       │
   │         3. Resume suspended worker Future                    │
   └──────────────────────────────────────────────────────────────┘
```

---

## 3. Supported Voice Commands & Spoken Mappings

Wispr Flow translates natural spoken language into deterministic SwitchBlade governance commands:

| Voice Dictation Example | Raw Transcript Cleaned by Wispr | Parsed SwitchBlade Governance Command |
| :--- | :--- | :--- |
| *"Approve escrow nine nine zero one with hash eight f four b two a one c"* | `APPROVE esc-9901 8f4b2a1c` | Resolves escrow `asyncio.Future` to `APPROVED`, unfreezes worker, promotes vaccine. |
| *"Reject escrow nine nine zero three untrusted schema rewrite"* | `REJECT esc-9903 Untrusted schema rewrite` | Resolves escrow to `REJECTED`, stops worker gracefully without financial burn. |
| *"Promote vaccine zero forty two with hash eight f four b two a one c"* | `PROMOTE VACCINE-042 8f4b2a1c` | Promotes rule from `SHADOW` to `ENFORCE` fleetwide. |
| *"Rollback vaccine zero forty two"* | `ROLLBACK VACCINE-042` | Deactivates in-memory pre-send intercept rule immediately. |

---

## 4. Why Wispr Flow Matters for FinOps & Escrows

1. **Sub-Second Incident Response**: When a runaway agent enters an unbounded loop, every turn costs money and adds latency. Wispr Flow allows the human engineer to review the 4-line Markdown diff card in the Switch room and approve the fix in seconds.
2. **Accurate Alphanumeric Dictation**: Wispr Flow accurately transcribes hex hashes (`8f4b2a1c`) and identifier tokens without misinterpreting letters and numbers.
3. **Seamless Switch Room Integration**: Because Switch rooms operate on standard chat bridges (Mattermost, Slack), Wispr Flow operates natively without custom browser extensions or proprietary drivers.

---

## 5. Live Demo Script (Wispr Flow Walkthrough)

1. **Step 1**: An alert appears in `@sb-switchblade`: `🚨 [ESCROW TRIPPED] Escrow: esc-9901`.
2. **Step 2**: The engineer clicks the Switch room input box and speaks into Wispr Flow:
   > *"Approve escrow esc-9901 with hash 8f4b2a1c"*
3. **Step 3**: Wispr Flow outputs:
   ```text
   APPROVE esc-9901 8f4b2a1c
   ```
4. **Step 4**: `@switchblade-proxy` reads the message over WebSocket, verifies authorization, and immediately logs:
   ```text
   [INFO] Proxy accepted APPROVE for escrow esc-9901 from @hamza (via Wispr Flow)
   ```
5. **Step 5**: The Rich Cockpit UI immediately turns green, showing the worker resumed and order settled!
