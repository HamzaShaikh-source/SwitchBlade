# SwitchBlade ⚡
### In-Flight FinOps Escrow & Self-Healing Control Plane for Autonomous Background Agents

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Switch Control Plane](https://img.shields.io/badge/Switch-WebSocket%20Control%20Plane-brightgreen.svg)](https://docs.switchagents.ai)

> Built by **Team 1** (**Hamza Shaikh, Santosh Subramanian, Aaditya Arunpal, and Janani**) for the [**Flip the Switch Hackathon**](https://www.wemakedevs.org/hackathons/switch), targeting **Track 01: Best Business Workflow ($2,000)**, **Wispr Flow ($500)**, and **Best Blog (AirPods 5)**.

* 📖 **[Read the Full Technical Blog Post (BLOG.md)](BLOG.md)** for the Best Blog track.
* 🎙️ **[Read the Wispr Flow Voice Governance Guide (WISPR_FLOW.md)](WISPR_FLOW.md)** for the Wispr Flow track.
* 🎬 **[View the 2:45 Demo Video Runbook (DEMO_RUNBOOK.md)](DEMO_RUNBOOK.md)** for recording walkthrough.

---

## 1. The Problem: Unbounded Agentic Retry Loops & FinOps Drain

Autonomous agents deployed for mission-critical background business operations (ERP sync, order settlement, invoice reconciliation) are vulnerable to **unbounded retry loops** when upstream APIs drift or deprecate.

* **Prevalence in Open Source**: A static-analysis survey of 6,549 open-source agent repositories confirmed 68 unbounded loop patterns where **95.6% led to API budget exhaustion** ([arXiv:2607.01641](https://arxiv.org/abs/2607.01641)).
* **Quadratic Context Cost Accumulation**: When an agent retries a failed API call, it appends the diagnostic stack trace to its message history. On every successive retry $i$, the history grows linearly:
  $$\text{Turn } i \approx i \times 15,000 \text{ tokens}$$
  Cumulative tokens billed across $n$ turns grow **quadratically**:
  $$\text{Cumulative Tokens} = \sum_{i=1}^{n} i \times 15,000 \approx \mathcal{O}(n^2)$$
* **Where Gateways Fall Short**: Existing API gateways (e.g., LiteLLM `max_iterations`) merely terminate execution with a hard `429` error once budgets are exhausted. They do **not** diagnose schema drift, heal broken tool calls, compact polluted message histories, or prevent sibling workers from repeating the same failure.

---

## 2. The Solution: SwitchBlade Architecture

SwitchBlade turns **Switch into an in-flight FinOps Escrow Control Plane**. Instead of letting runaway workers burn budgets or crashing silently, SwitchBlade pauses failing agents, repairs their context, verifies fixes in sandbox dry-runs, requires hash-bound human approval in the Switch room, and vaccinates the entire fleet against future retries.

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

---

## 3. The 5 Core Pillars

### 1. Error-Class & Progress-Hash Circuit Breaker (`proxy.py`)
* Distinguishes permanent client errors (`400`, `404`, `422` — immediate escrow trip after 3 identical failures) from transient network errors (`408`, `425`, `429`, `503` — honors `Retry-After`).
* Computes deterministic progress hashes:
  $$\text{sha256}(\text{tool\_name} \mid \text{canonical\_args} \mid \text{status\_code} \mid \text{response\_fingerprint})$$
* Halts zero-progress spin cycles into strongly-referenced `Escrow` state machines backed by `asyncio.Future(decision)`.

### 2. API-Valid Context Surgery (`context_surgeon.py` + `POST /surgeon/prune`)
* Compacting context cannot be arbitrary string truncation; Anthropic APIs strictly enforce role alternation and tool pair validity.
* Deletes failed retry turns as **atomic `(tool_use, tool_result)` pairs**, preventing orphaned tool calls.
* Closes trailing failed turns with structured `failed_attempts` directives and strips `thinking` blocks before cross-model tier transitions.
* **Honest Accounting**: Compresses message history from **45,200 tokens down to 380 tokens (99.2% reduction)**.

### 3. Non-Mutating Dry-Run & Context-Bound Tenant Header (`scout_agent` + `POST /scout/dryrun`)
* Diffs `/openapi.json` to identify route changes (`/v1/orders` $\rightarrow$ `/v2/orders`).
* Probes candidate fixes using non-mutating `POST /v2/orders?dry_run=true` (or header `X-Dry-Run: true`).
* **Confused Deputy Prevention**: The vaccine rule never hard-codes `"X-Tenant-ID": "acme-corp"`. Instead, it declares `"inject_headers_from_context": {"X-Tenant-ID": "task.tenant_id"}`, binding headers to authenticated session state.

### 4. Hash-Bound Human Room Approval & Pre-Send Vaccines
* When `{team}-compiler` proposes a fix, the proxy computes an 8-character SHA-256 `change_hash` over the rule JSON and Git patch diff.
* Human engineers authorize execution in the Switch room via:
  ```text
  APPROVE <escrow_id> <change_hash>
  ```
* Promoted rules enter `ENFORCE` mode and execute **in-memory pre-send rewrites** matching on `(tool_name, http_method, path_template)`. Subsequent calls (e.g., Order #9902) are rewritten on **Turn 1 with zero retries**.

### 5. Tamper-Evident Canonical Ledger Anchored in Switch Room (`ledger.py`)
* SQLite chain written under `BEGIN IMMEDIATE` transactions with domain prefix `SWITCHBLADE-LEDGER-V1`.
* Every 5 events, the control plane broadcasts `LEDGER_CHECKPOINT seq=<n> head_hash=<sha256>` into the Switch room.
* `verify_ledger.py` cryptographically checks sequential hash links and validates external room anchoring.

---

## 4. Benchmark Verification Results

Reproducible benchmarks generated by `bench/run_bench.py` on Intel/AMD64 hardware:

| Metric / Execution Mode | Unguarded Control Loop | SwitchBlade Guarded Run | Delta / FinOps Savings |
| :--- | :---: | :---: | :---: |
| **Total Turns to Settle** | 10 (Safety cap exhaustion) | **4 (Healed & settled)** | **Arrested at Turn 3** |
| **Cumulative Tokens Billed** | 860,000 tokens | **108,260 tokens** | **-751,740 tokens saved** |
| **Cumulative API Spend** | $12.9000 | **$1.6239** | **87.4% COST REDUCTION** |
| **Vaccine Rewrite Latency** | N/A | **p50: 1.20μs / p99: 1.60μs** | Microsecond in-memory speed |
| **Subsequent Order #9902** | 3 retries (unbounded) | **0 retries (Turn 1 rewrite)** | **100% Zero-Retry Fleetwide** |

*All metrics are verified and committed in [`bench/results.json`](file:///d:/SwitchBlade/bench/results.json).*

---

## 5. Rich Live Telemetry Cockpit

SwitchBlade provides a real-time, 4-panel terminal UI powered by `rich`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🧪 SELFTEST MODE   ⚡ SWITCHBLADE CONTROL PLANE | Room: 🛡️ LEDGER ANCHORED │
│                           @sb-switchblade | Task:                 (Seq #15) │
└────────────────── In-Flight FinOps Escrow for Autonomous Background Agents ─┘
┌─ Worker Stream & FinOps Telemetry ──┐┌─ Escrow Gate & Context Surgeon View ─┐
│ Turn  Endpoint      Status     Cost ││ Escrow ID: `esc-9901-trip`   State:  │
│  T1   /v1/orders   422 LOOP   $0.27 ││ ⏸ PENDING HUMAN APPROVAL             │
│  T2   /v1/orders   422 LOOP   $0.50 ││ Change Hash: 8f4b2a1c                │
│  T3   /v1/orders   422 LOOP   $0.72 ││ ────────────────────────────────────  │
│  T4   /v2/orders   200 SETTLED $0.05││ History: 45.2k ➔ 380 tokens (99.2%)   │
│ Cumulative FinOps Burn: $1.62       ││ Pair Integrity: ✔ ATOMIC (tool pairs) │
└─────────────────────────────────────┘└──────────────────────────────────────┘
┌─────── Fleet Defense: Vaccine Registry & Tamper-Evident Ledger Feed ────────┐
│ Active Vaccines: VACCINE-042 [ENFORCE] (POST /v1/orders ➔ POST /v2/orders)  │
│ Latency: p50: 1.2μs | p99: 1.6μs | Anchored Ledger Head: 888f48a9...        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Quickstart & Usage

### Prerequisites
* Python 3.12+
* Switch Console & Docker (for live Mattermost room integration)

### Installation
```bash
git clone https://github.com/HamzaShaikh-source/SwitchBlade.git
cd SwitchBlade
pip install -r requirements.txt
```

### 1. Verify Clean-Clone Reproduction (< 10s Spin-Up)
```bash
python verify_clean_clone.py
```

### 2. Run Terminal Telemetry Cockpit (Selftest Mode)
```bash
# Static snapshot view
python run_demo.py --mode selftest

# Real-time animated simulation demonstrating circuit breaker, surgery, and approval
python run_demo.py --mode selftest --animate
```

### 3. View Benchmark Comparison
```bash
python run_demo.py --show-bench
```

### 4. Run Benchmark Suite
```bash
python bench/run_bench.py
```

### 5. Run Live Telemetry with Proxy (:8002)
```bash
python run_demo.py --mode live --proxy-url http://localhost:8002
```

### 5. Review the Web Control Plane
```bash
python -m uvicorn proxy:app --host 127.0.0.1 --port 8002
```

Open `http://127.0.0.1:8002/` for the five-page operator UI: Overview, Activity, Escrows, Vaccines, and Ledger. The pages read live proxy events and persisted ledger entries. The escrow page exposes context pruning, sandbox dry run, proposal creation, and hold-to-confirm approval or rejection.

Start the seeded billing API in a second terminal with `python -m uvicorn mock_billing_api:app --host 127.0.0.1 --port 8001`. The proxy needs that service for a real dry run and vaccinated order execution. The bundled open-source React Bits effects can be rebuilt from `ui/effects` with `npm ci && npm run build`.

---

## 7. Team & Branch Ownership

| Teammate | Dedicated Branch | Role Title | Ownership Focus |
| :--- | :--- | :--- | :--- |
| **Hamza Shaikh** | `feat/hamza-cockpit-ui` | Frontend, Telemetry UI & Demo Lead | `run_demo.py`, `ui/cockpit.py`, `ui/room_cards.py`, `bench/run_bench.py`, `bench/results.json`, `README.md` |
| **Santosh Subramanian** | `feat/santosh-proxy-ledger` | Core Runtime, Escrow & Ledger Lead | `schemas.py`, `proxy.py`, `ledger.py`, `verify_ledger.py` |
| **Aaditya Arunpal** | `feat/aaditya-switch-bridge` | Switch WebSocket & Protocol Lead | `switchblade.template.yaml`, `switch_bridge.py`, `.env.example`, `verify_clean_clone.py` |
| **Janani** | `feat/janani-agents-vaccine` | AI Agents, Context Surgery & Vaccine Lead | `context_surgeon.py`, `vaccine_registry.py`, `worker_agent.py`, `mock_billing_api.py`, `test_suite.py` |

---

## 8. Prior-Library & Hackathon Disclosures
* Standard dependencies used: `rich`, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `anthropic`, `pyyaml`.
* All core control plane logic, circuit breakers, context surgery pruners, room cards, in-memory vaccines, and tamper-evident ledgers were designed and developed during the **Flip the Switch Hackathon (Nov 4–7, 2026)**.
