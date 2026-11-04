# Building an In-Flight FinOps Escrow Control Plane on the Switch WebSocket Agent Protocol

**Targeting**: Track 01: Best Business Workflow ($2,000), Wispr Flow ($500), and Best Blog (AirPods 5)  
**Authors**: Hamza Shaikh, Santosh Subramanian, Aaditya Arunpal, and Janani (Team 1)  
**Project**: [SwitchBlade on GitHub](https://github.com/HamzaShaikh-source/SwitchBlade)  
**Reproducibility**: Clean clone verified in **9.74 seconds** (`python verify_clean_clone.py`)

---

## 1. Introduction: The \$47,000 Agentic Doom Loop

When engineering organizations deploy autonomous LLM agents for background operational workflows—such as reconciling ERP ledger entries, synchronizing CRM pipelines, or settling billing orders—they encounter an existential reliability barrier: **unbounded agentic retry loops**.

In classical software systems, an unhandled exception crashes the process or trips a deterministic circuit breaker. In autonomous agent architectures, however, a failing tool call does something far more treacherous: **the model attempts to reason through the exception**. On each successive retry, the agent appends the diagnostic stack trace, schema validation error, and previous call attempts directly to its conversation context:

```
Turn 1: Tool Call fails (HTTP 422: Missing required header X-Tenant-ID)
Turn 2: Agent reasons on error trace (~15k tokens) ➔ Retries same tool call
Turn 3: Agent reasons on 2x error traces (~30k tokens) ➔ Retries same tool call
Turn 4: Agent reasons on 3x error traces (~45k tokens) ➔ Retries same tool call
...
Turn N: Token limit exhausted or wallet drained
```

A recent empirical study analyzing 6,549 open-source AI agent repositories ([arXiv:2607.01641](https://arxiv.org/abs/2607.01641)) identified 68 confirmed unbounded loop patterns, finding that **95.6% of them led directly to complete API budget exhaustion**. Because message histories grow linearly ($15\text{k} \rightarrow 30\text{k} \rightarrow 45\text{k}$ tokens per iteration), the cumulative input tokens billed across $n$ turns grow **quadratically**:

$$\text{Cumulative Tokens Billed} = \sum_{i=1}^{n} (i \times T_{\text{error}} + T_{\text{prompt}}) \approx \mathcal{O}(n^2)$$

Real-world community post-mortems have documented single-weekend runaway loops racking up tens of thousands of dollars in cloud LLM charges without settling a single business transaction ([TechStartups Incident Relay](https://techstartups.com/2025/11/14/ai-agents-horror-stories-how-a-47000-failure-exposed-the-hype-and-hidden-risks-of-multi-agent-systems/)).

---

## 2. Why Existing AI Gateways Fail

Existing API gateways and agent monitoring frameworks address runaway retries using crude, blunt instruments:

* **Budget Caps & Iteration Ceilings (e.g., LiteLLM `max_iterations`)**: Hard-kill the agent process on the $N$-th turn with an HTTP `429` or error status. The background business workflow fails completely, intermediate progress is discarded, and the underlying schema drift remains unaddressed.
* **Terminal Doom-Loop Detectors**: Pause execution and prompt a human operator in terminal stdout to *"break or continue"*. If the human presses continue, the agent retries the identical broken call; if break, the background workflow halts with corrupted, uncommitted state.

Neither approach diagnoses upstream API deprecations, repairs broken tool payloads, compacts polluted context histories, or immunizes sibling worker agents.

---

## 3. Switch as the Control Plane: The SwitchBlade Architecture

When designing SwitchBlade for the **Flip the Switch Hackathon**, our team established a non-negotiable architectural requirement: **Switch MUST be the control plane, not a passive notification sink.** The official judging rubric explicitly evaluates whether the system would *"stop working without Switch"*. If Switch were decoupled, SwitchBlade could not function.

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │                Switch Room (Mattermost)                │
                                  │      @{team}-surgeon    @{team}-scout   @{team}-compiler│
                                  │      Human Approver (Voice via Wispr Flow / Text)      │
                                  └───────────────────────────▲────────────────────────────┘
                                                              │ WebSocket (/agents/{id}/connection/ws)
                                                              │ HTTP Ops (/agents/{id}/ops/{op})
                                                              ▼
┌─────────────────────────┐   execute_tool    ┌────────────────────────────────────────────┐
│      Worker Agent       ├──────────────────►│         SwitchBlade Proxy (:8002)          │
│   (Anthropic SDK)       │                   │  1. Progress-Hash Circuit Breaker (3x 422) │
│                         │◄──────────────────┤  2. Escrow State Machine (asyncio.Future)  │
│  Order #9901 ❌ Tripped │ (Resumed & Healed)│  3. Atomic (tool_use, tool_result) Pruner  │
│  Order #9902 💉 Turn 1  │ (Pre-Send Intercept)│ 4. Cryptographic SQLite Ledger (:8002)   │
└─────────────────────────┘                   └───────────────────────▲────────────────────┘
                                                                      │ ?dry_run=true
                                                                      ▼
                                              ┌────────────────────────────────────────────┐
                                              │          Mock Billing API (:8001)          │
                                              │  POST /v1/orders (Deprecated 422 Trace)    │
                                              │  POST /v2/orders (Active + X-Tenant-ID)    │
                                              └────────────────────────────────────────────┘
```

SwitchBlade implements a five-pillar governance architecture:

### Pillar 1: Error-Class & Progress-Hash Circuit Breaker
Rather than relying on fragile semantic similarity heuristics, `proxy.py` computes a deterministic progress hash over consecutive turns:

$$\text{hash} = \text{sha256}(\text{tool\_name} \mid \text{canonical\_args} \mid \text{http\_status} \mid \text{response\_fingerprint})$$

* **Permanent Client Errors (`400`, `404`, `422`)**: 3 consecutive identical failures trigger an immediate circuit trip.
* **Transient Errors (`408`, `425`, `429`, `503`)**: Upstream `Retry-After` headers are honored without tripping.
* **The Escrow Lock**: Tripping does not kill the worker. Instead, it transitions the task into an `Escrow` state machine (`PENDING`), suspending the execution coroutine on an `asyncio.Future` with a strict TTL.

### Pillar 2: API-Valid Context Surgery
Template-managed Switch agents (`surgeon`, `scout`, `compiler`) run in isolated Switch Console PTYs and cannot directly mutate proxy memory. Instead, `{team}-surgeon` calls the proxy's narrow, idempotent `POST /surgeon/prune` endpoint:
1. **Atomic Pair Pruning**: Claude's API requires strict role alternation and `tool_use`/`tool_result` pair equality. Arbitrary text truncation causes API schema rejections. SwitchBlade prunes failed turns as atomic tuples.
2. **Trailing Directive Closure**: The final failed turn is closed with a structured `failed_attempts` directive forbidding repetition of the deprecated endpoint.
3. **Cross-Model Thinking Block Removal**: Strips internal `thinking` blocks so model-tier handoffs succeed cleanly.
4. **Result**: History compressed from **45,200 tokens down to 380 tokens (99.2% reduction)**.

### Pillar 3: Spec-Differ & Non-Mutating Sandbox Dry-Run
When upstream APIs deprecate (e.g., `/v1/orders` $\rightarrow$ `/v2/orders`), `{team}-scout` diffs `/openapi.json` to identify newly required parameters (`X-Tenant-ID`).
* **Non-Mutating Verification**: To prevent double-settling live orders, `{team}-scout` executes `POST /v2/orders?dry_run=true` (Kubernetes `dryRun=All` pattern).
* **Confused Deputy Prevention**: Vaccine rules never hardcode tenant secrets. Headers are dynamically resolved via `"inject_headers_from_context": {"X-Tenant-ID": "task.tenant_id"}`.

### Pillar 4: Hash-Bound Room Governance & Pre-Send Fleet Immunity
Room membership alone is not authorization:
1. When `{team}-compiler` proposes a fix, the proxy hashes the rule JSON and code diff into an 8-character SHA-256 `change_hash` (`8f4b2a1c`).
2. An allowlisted human engineer authorizes execution in the Switch Room:
   ```text
   APPROVE esc-9901 8f4b2a1c
   ```
3. Once approved, the rule enters `ENFORCE` mode. Subsequent tasks (e.g., Order `#9902`) are intercepted **in-memory before sending**, rewriting the request in **$1.20\,\mu\text{s}$ on Turn 1 with zero retries**.

### Pillar 5: Tamper-Evident Ledger Anchored in Switch Room
All escrow events are committed to a canonical SQLite chain using monotonic sequence numbers, domain separation (`SWITCHBLADE-LEDGER-V1`), and `BEGIN IMMEDIATE` transactions. Every 5 events, the proxy broadcasts:
```text
LEDGER_CHECKPOINT seq=15 head_hash=a37f81b2c90e...
```
The Switch Room chat log serves as an immutable, tamper-evident external witness.

---

## 4. Deep Dive: The Switch WebSocket Agent Protocol

A core technical contribution of SwitchBlade is our reference implementation of the **Switch Agent Protocol v1** (`switch_bridge.py`).

### Why WebSockets Over Legacy SSE
In early prototypes, agent bridges used Server-Sent Events (SSE). Under real network conditions, SSE exhibited severe drawbacks:
1. **Unidirectional Flow**: SSE only pushes events downstream; client responses require separate HTTP round-trips, introducing race conditions.
2. **Heartbeat Eviction**: Switch rooms enforce a strict **6-second heartbeat deadline**. If an agent fails to respond to a `ping` frame with a matching cursor acknowledgment, Switch immediately closes the connection with code `heartbeat_lapsed`.
3. **Connection Replay Floods**: Reconnecting SSE clients frequently re-received unacknowledged messages, causing duplicate escrow approvals.

### The Hardened WebSocket Implementation
SwitchBlade connects directly to the bi-directional Switch WebSocket gateway at:
```text
ws://localhost:3000/agents/{agent_id}/connection/ws
```

#### 1. Instant Cursor-Bound Heartbeat Response
To guarantee zero disconnects, `switch_bridge.py` processes incoming frames with immediate priority:
```python
if data.get("type") == "ping":
    cursor = data.get("cursor")
    pong_frame = json.dumps({"type": "pong", "cursor": cursor})
    await websocket.send(pong_frame)
    logger.debug(f"[SwitchBridge] Sent pong acknowledgment for cursor: {cursor}")
    continue
```

#### 2. $O(1)$ Bounded LRU Deduplication
To prevent replay attacks and network retransmission storms from triggering multiple state transitions, `SwitchBridge` maintains a bounded deque with an $O(1)$ lookup set:
```python
class BoundedDeduplicator:
    def __init__(self, max_size: int = 10_000):
        self.max_size = max_size
        self._seen = set()
        self._order = collections.deque()

    def check_and_add(self, message_id: str) -> bool:
        if message_id in self._seen:
            return False  # Duplicate detected
        if len(self._order) >= self.max_size:
            oldest = self._order.popleft()
            self._seen.discard(oldest)
        self._seen.add(message_id)
        self._order.append(message_id)
        return True
```

#### 3. Room Addressing & Security Enforcement
Only events where `event.addressed == True` or public room announcements trigger processing. Furthermore, `switch_bridge.py` enforces a cryptographic `HUMAN_ALLOWLIST`:
* Automated agent IDs (`@switchblade-proxy`, `@sb-surgeon`, `@sb-scout`, `@sb-compiler`) are **explicitly forbidden from self-approving escrows**.
* Approvals must originate from verified human usernames (or the `@policy-bot` governance actor during replay automation).

---

## 5. Hands-Free Voice Governance with Wispr Flow ($500 Track)

Operating an in-flight FinOps control plane requires sub-second incident response. When an agent enters a runaway loop burning \$2.00 per minute, requiring an on-call engineer to open an IDE or type an 8-character hex hash slows recovery.

By integrating **Wispr Flow**, SwitchBlade introduces hands-free voice governance directly into the Switch Room:

```
┌────────────────────────────────────────────────────────────────────────┐
│               On-Call Engineer (Voice via Wispr Flow)                  │
│   "Approve escrow nine nine zero one with hash eight f four b two..."  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Wispr Flow Dictation
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Switch Room (Mattermost / Slack)                     │
│               Message: `APPROVE esc-9901 8f4b2a1c`                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Switch WebSocket Protocol
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              SwitchBlade Proxy (:8002 /escrow/decision)                │
│    1. Verify allowlisted approver identity                             │
│    2. Compare SHA-256 change_hash                                      │
│    3. Resume suspended worker Future                                   │
└────────────────────────────────────────────────────────────────────────┘
```

### Voice Command Mappings
Wispr Flow transcribes natural spoken audio into deterministic SwitchBlade commands:

| Natural Voice Dictation | Cleaned Transcribed Text | Switch Control Action |
| :--- | :--- | :--- |
| *"Approve escrow esc-9901 with hash 8f4b2a1c"* | `APPROVE esc-9901 8f4b2a1c` | Resolves `asyncio.Future`, resumes worker, activates vaccine |
| *"Reject escrow esc-9903 untrusted schema rewrite"* | `REJECT esc-9903 Untrusted schema rewrite` | Fails escrow safely with structured tool error |
| *"Promote vaccine zero forty two with hash 8f4b2a1c"* | `PROMOTE VACCINE-042 8f4b2a1c` | Promotes rule from `SHADOW` to `ENFORCE` fleetwide |
| *"Rollback vaccine zero forty two"* | `ROLLBACK VACCINE-042` | Deactivates in-memory pre-send intercept rule immediately |

Wispr Flow eliminates typing latency, enabling true 2-second incident response from mobile or dual-monitor command desks.

---

## 6. Benchmark Verification & Financial Impact

All metrics reported below are measured and committed in `bench/results.json`, generated by running `python bench/run_bench.py` over 10,000 iterations:

| Metric / Execution Mode | Unguarded Control Loop | SwitchBlade Guarded Run | Delta / FinOps Savings |
| :--- | :---: | :---: | :---: |
| **Total Turns to Settle** | 10 (Safety Cap Exhaustion) | **4 (Healed & Settled)** | **Arrested at Turn 3** |
| **Cumulative Tokens Billed** | 860,000 tokens | **108,260 tokens** | **-751,740 tokens saved** |
| **Cumulative API Spend** | \$12.9000 | **\$1.6239** | **87.41% COST REDUCTION** |
| **Context History Reduction** | 0% (Accumulated error dumps) | **45,200 ➔ 380 tokens** | **99.2% Memory Pruned** |
| **Vaccine Rewrite Latency (p50)** | N/A | **1.20 μs** | In-memory speed |
| **Vaccine Rewrite Latency (p99)** | N/A | **2.60 μs** | Sub-3-microsecond tail |
| **Subsequent Sibling Order #9902** | 3 retries (unbounded) | **0 retries (Turn 1 rewrite)** | **100% Zero-Retry Fleetwide** |

### The Compounding Fleet Effect
The critical financial insight of SwitchBlade is **fleetwide immunization**. When Order `#9901` is healed, the resulting vaccine (`VACCINE-042`) is stored in-memory. When Order `#9902` executes, the proxy matches the request on `(tool_name, http_method, path_template)` **before** sending the HTTP frame:
* Turn 1 executes against `/v2/orders` with `X-Tenant-ID` pre-injected from `task.tenant_id`.
* The upstream billing API returns HTTP `200 OK` on Turn 1.
* Zero retries, zero context pollution, zero financial waste.

---

## 7. Clean-Clone Reproduction Guide (< 10 Minutes Guarantee)

To ensure full transparency and immediate reproducibility for hackathon judges, SwitchBlade includes an automated reproduction runner:

```bash
# 1. Clone the repository
git clone https://github.com/HamzaShaikh-source/SwitchBlade.git
cd SwitchBlade

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the automated clean-clone reproduction suite
python verify_clean_clone.py
```

### Verified Reproduction Output
```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ SwitchBlade: Clean-Clone Reproduction & Spin-Up Verification                │
│ Simulating pristine clone & verifying 10-minute spin-up requirement for     │
│ Flip the Switch Hackathon                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                SwitchBlade Clean-Clone Reproduction Checklist                 
┌─────────────────────────┬─────────────────────────────────────────┬─────────┬────────┐
│ Step                    │ Verification Details                    │ Duration│ Status │
├─────────────────────────┼─────────────────────────────────────────┼─────────┼────────┤
│ 1. Pristine Workspace   │ Isolated sandbox created & files copied │ 0.12s   │ PASS   │
│ 2. Switch Template Spec │ v1 schema valid (params, machine, dir)  │ 0.05s   │ PASS   │
│ 3. Dependencies & Config│ Core Python packages & .env.example     │ 2.10s   │ PASS   │
│ 4. Switch WebSocket     │ Agent protocol, heartbeat & APPROVE     │ 2.40s   │ PASS   │
│ 5. Ledger Tamper Demo   │ Cryptographic chain caught seq #2 tamper│ 0.85s   │ PASS   │
│ 6. Master Cockpit       │ 4-panel Rich terminal UI rendered       │ 0.90s   │ PASS   │
│ 7. Core Test Suite      │ Surgery atomicity, confused deputy      │ 3.32s   │ PASS   │
└─────────────────────────┴─────────────────────────────────────────┴─────────┴────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│ [PASS] REPRODUCTION SUCCESSFUL IN 9.74 SECONDS                              │
│ Official Hackathon Requirement: < 600.00s (10 minutes) | Margin: 590.26s    │
│ under limit                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Team Roster & Module Ownership

| Team Member | Dedicated Branch | Role Title | Core Module Ownership |
| :--- | :--- | :--- | :--- |
| **Hamza Shaikh** | `feat/hamza-cockpit-ui` | Frontend, Telemetry UI & Demo Lead | `run_demo.py`, `ui/cockpit.py`, `ui/room_cards.py`, `bench/run_bench.py`, `bench/results.json`, `README.md` |
| **Santosh Subramanian** | `feat/santosh-proxy-ledger` | Core Runtime, Escrow & Ledger Lead | `schemas.py`, `proxy.py`, `ledger.py`, `verify_ledger.py` |
| **Aaditya Arunpal** | `feat/aaditya-switch-bridge` | Switch WebSocket & Protocol Lead | `switchblade.template.yaml`, `switch_bridge.py`, `.env.example`, `verify_clean_clone.py` |
| **Janani** | `feat/janani-agents-vaccine` | AI Agents, Context Surgery & Vaccine Lead | `mock_billing_api.py`, `context_surgeon.py`, `vaccine_registry.py`, `worker_agent.py`, `test_suite.py` |

---

## 9. Conclusion

By building on the **Switch WebSocket Agent Protocol**, SwitchBlade demonstrates that human-in-the-loop governance does not have to mean slow, manual ticket escalation or catastrophic process crashes. With in-flight escrows, atomic context surgery, voice-driven room approvals, and pre-send vaccines, autonomous background agents can heal in seconds while cutting LLM operational costs by **87.4%**.

*All code, templates, and benchmark datasets are open-sourced under the MIT license at [https://github.com/HamzaShaikh-source/SwitchBlade](https://github.com/HamzaShaikh-source/SwitchBlade).*
