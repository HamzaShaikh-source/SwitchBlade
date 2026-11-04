# Building an In-Flight FinOps Escrow Control Plane on the Switch WebSocket Agent Protocol

**Targeting**: Track 01: Best Business Workflow ($2,000) & Best Blog (AirPods 5)  
**Authors**: Hamza Shaikh, Santosh Subramanian, Aaditya Arunpal, and Janani (Team 1)  
**Project**: [SwitchBlade on GitHub](https://github.com/HamzaShaikh-source/SwitchBlade)  

---

## 1. Introduction: The \$47,000 Agentic Doom Loop

When companies deploy autonomous AI agents for background operational workflows—such as reconciling ERP ledger transactions, processing customer invoices, or settling payment orders—they face an existential reliability problem: **unbounded agentic retry loops**.

In traditional software, an unhandled exception triggers a crash or circuit trip. In autonomous LLM agent systems, however, a failing tool call does something far more insidious: **the model attempts to reason through the failure**. On each retry, the agent appends the diagnostic stack trace, schema validation error, and past attempts to its conversational message history.

A recent empirical study analyzing 6,549 open-source AI agent repositories ([arXiv:2607.01641](https://arxiv.org/abs/2607.01641)) discovered 68 confirmed unbounded loop patterns, finding that **95.6% of them led directly to API cost exhaustion**. Because message histories grow linearly ($15\text{k} \rightarrow 30\text{k} \rightarrow 45\text{k}$ tokens per retry), the cumulative input tokens billed across $n$ turns grow **quadratically**:

$$\text{Cumulative Tokens Billed} = \sum_{i=1}^{n} (i \times T_{\text{error}} + T_{\text{prompt}}) \approx \mathcal{O}(n^2)$$

Real-world community post-mortems have documented single-weekend runaway agent loops racking up tens of thousands of dollars in LLM API bills without settling a single order.

---

## 2. Why Existing Gateway Solutions Fail

Existing AI gateways approach this problem with crude, blunt instruments:

* **Budget Caps & Iteration Limits (e.g., LiteLLM `max_iterations`)**: Terminate the agent on the $N$-th turn with an HTTP `429` or error status. The task fails completely, the context is discarded, and the underlying API drift remains unaddressed.
* **Terminal Doom-Loop Detectors**: Pause the agent and ask a human to *"break or continue"*. If the human presses continue, the agent retries the identical broken call; if break, the background workflow halts with uncommitted state.

Neither solution diagnoses the upstream API schema change, repairs the tool call, prunes the contaminated context history, or immunizes sibling worker agents.

---

## 3. Switch as the Control Plane: The SwitchBlade Architecture

When building SwitchBlade for the **Flip the Switch Hackathon**, our core architectural thesis was clear: **Switch MUST be the control plane, not a notification sink.** If Switch were removed, the system would stop working.

```
                          ┌──────────────────────────────────────┐
                          │         Switch Room (Mattermost)     │
                          │   @{team}-surgeon   @{team}-scout   │
                          │        @{team}-compiler              │
                          └──────────────────▲───────────────────┘
                                             │ WebSocket & HTTP Ops
                                             ▼
┌──────────────────┐               ┌──────────────────────────────────────┐
│  Worker Agent    │  execute_tool  │         SwitchBlade Proxy (:8002)    │
│  (Anthropic SDK) ├──────────────►│ 1. Progress-Hash Circuit Breaker     │
│                  │               │ 2. Escrow State Machine (PENDING)    │
│  Order #9901 ❌  │◄──────────────┤ 3. Atomic (tool_use, tool_result)    │
│  Order #9902 💉  │ (Vaccinated)  │ 4. Pre-Send Intercept Registry       │
└──────────────────┘               └──────────────────▲───────────────────┘
                                                      │ ?dry_run=true
                                                      ▼
                                   ┌──────────────────────────────────────┐
                                   │      Mock Billing API (:8001)        │
                                   │  /v1/orders (Deprecated 422)         │
                                   │  /v2/orders (Active + X-Tenant-ID)   │
                                   └──────────────────────────────────────┘
```

SwitchBlade implements a five-pillar governance architecture:

### Pillar 1: Error-Class & Progress-Hash Circuit Breaker
Rather than relying on fuzzy semantic heuristics, SwitchBlade computes a deterministic progress hash over consecutive turns:

$$\text{hash} = \text{sha256}(\text{tool\_name} \mid \text{canonical\_args} \mid \text{http\_status} \mid \text{response\_fingerprint})$$

* **Permanent Client Errors (`400`, `404`, `422`)**: 3 consecutive identical failures trigger an immediate circuit trip.
* **Transient Errors (`408`, `425`, `429`, `503`)**: Honored via upstream `Retry-After` headers without tripping.
* **The Escrow Lock**: Tripping does not kill the process. Instead, it transitions the worker into an `Escrow` state machine (`PENDING`), suspending the execution coroutine on an `asyncio.Future` with a strict TTL.

### Pillar 2: API-Valid Context Surgery
Console-managed coding agents running in isolated PTYs cannot directly tamper with runtime memory. Instead, `{team}-surgeon` calls the proxy's `POST /surgeon/prune` endpoint:
1. **Atomic Pair Pruning**: Claude's API requires strict role alternation and `tool_use`/`tool_result` pair equality. Arbitrary truncation causes API schema rejections. SwitchBlade prunes failed turns as atomic tuples.
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
3. Once approved, the rule enters `ENFORCE` mode. Subsequent tasks (e.g., Order `#9902`) are intercepted **in-memory before sending**, rewriting the request in **$1.2\,\mu\text{s}$ on Turn 1 with zero retries**.

### Pillar 5: Tamper-Evident Ledger Anchored in Switch Room
All escrow events are committed to a canonical SQLite chain using monotonic sequence numbers, domain separation (`SWITCHBLADE-LEDGER-V1`), and `BEGIN IMMEDIATE` transactions. Every 5 events, the proxy broadcasts:
```text
LEDGER_CHECKPOINT seq=15 head_hash=a37f81b2c90e...
```
The Switch Room chat log serves as an immutable, tamper-evident external witness.

---

## 4. Benchmark & Financial Impact

Using the reproducible `bench/run_bench.py` suite across 10,000 iterations:

| Metric | Unguarded Loop | SwitchBlade Guarded | Impact |
| :--- | :---: | :---: | :---: |
| **Turns to Settle** | 10 (Safety Cap) | **4 (Healed)** | Arrested at Turn 3 |
| **Tokens Billed** | 860,000 tokens | **108,260 tokens** | **-751,740 tokens saved** |
| **API Cost Billed** | \$12.90 | **\$1.62** | **87.4% COST REDUCTION** |
| **Vaccine Rewrite Latency** | N/A | **p50: 1.20μs / p99: 1.60μs** | Microsecond speed |
| **Sibling Order #9902** | 3 retries (unbounded) | **0 retries (Turn 1)** | **100% Zero-Retry Fleetwide** |

---

## 5. Conclusion

By building on the **Switch WebSocket Agent Protocol**, SwitchBlade proves that human-in-the-loop governance does not have to mean slow, manual ticket escalation. With in-flight escrows, context surgery, and pre-send vaccines, autonomous background agents can heal in seconds while cutting LLM operational costs by over 87%.

*Code, benchmarks, and templates are open-sourced under the MIT license on [GitHub](https://github.com/HamzaShaikh-source/SwitchBlade).*
