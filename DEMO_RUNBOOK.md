# SwitchBlade Demo Runbook & 2:45 Split-Screen Recording Script
**Track 01: Best Business Workflow ($2,000) | Wispr Flow ($500) | Best Blog (AirPods 5)**

---

## 1. Split-Screen Layout Setup

* **Left 50% (Terminal)**:
  ```bash
  python run_demo.py --mode live
  ```
  *Font*: JetBrains Mono / Fira Code, 14pt.
  *Shows*: 4-panel telemetry cockpit (turn-by-turn stream, USD burn bar, context surgery compaction gauge, vaccine registry, and anchored SQLite ledger).

* **Right 50% (Browser / Switch Room)**:
  * Open Mattermost / Switch Console room `sb-switchblade`.
  * Shows room members: `@sb-surgeon`, `@sb-scout`, `@sb-compiler`, and human engineer `@hamza`.

---

## 2. Second-by-Second Video Script (Total: 2 Minutes 45 Seconds)

### Act I: The Problem & The Circuit Trip (0:00 – 0:45)
* **Visual**: Left terminal shows worker agent processing Order `#9901`. Turns 1, 2, 3 fail on deprecated `POST /v1/orders` returning HTTP 422 with a 15k token diagnostic stack trace.
* **Telemetry**: Cumulative burn bar rapidly climbs from \$0.22 to \$0.68.
* **Event**: On Turn 3, the progress-hash circuit breaker halts execution. Escrow enters `PENDING` state.
* **Right Panel**: `@switchblade-proxy` posts `🚨 [ESCROW TRIPPED]` card into the Switch room:
  ```markdown
  ### 🚨 [ESCROW TRIPPED] Escrow: `esc-9901` | Task: `task-order-9901`
  **Circuit Breaker:** 3x `422` on tool `sync_customer_order` (Unbounded loop detected)
  **FinOps Burn:** 45,200 tokens wasted (~$0.6780) | Worker paused in `PENDING` escrow
  **Handoff:** Invoking @sb-surgeon for atomic context surgery and history compaction.
  ```

### Act II: Context Surgery & Hash-Bound Approval (0:45 – 1:30)
* **Visual**: `@sb-surgeon` calls `POST /surgeon/prune`.
* **Telemetry**: Context compression gauge visibly drops: **45,200 ➔ 380 tokens (99.2% history reduction)**. Atomic `(tool_use, tool_result)` pair closed with `failed_attempts` directive.
* **Room Action**: `@sb-scout` runs non-mutating `POST /v2/orders?dry_run=true`, diffs `/openapi.json`, and `@sb-compiler` posts the proposal card with 8-character change hash `8f4b2a1c`.
* **The Approval**: Human engineer (`@hamza`) types into the Switch Room:
  ```text
  APPROVE esc-9901 8f4b2a1c
  ```
* **Result**: `switch_bridge.py` verifies authorization, resolves the escrow `asyncio.Future` to `APPROVED`, and promotes `VACCINE-042` to `ENFORCE`.

### Act III: Pre-Send Fleet Defense (Turn-1 Zero Retry) (1:30 – 2:05)
* **Visual**: Order `#9901` resumes with clean context and settles with `200 OK`.
* **The Killer Feature**: Worker is dispatched Order `#9902` (still configured with old `/v1/orders` code).
* **Telemetry**: Vaccine registry intercepts the tool call in-process *before sending* ($p50: 1.2\,\mu\text{s}$). It rewrites to `/v2/orders` and injects `X-Tenant-ID: acme-corp`.
* **Result**: Order `#9902` succeeds on **Turn 1 with ZERO retries**! Fleet immunity achieved.

### Act IV: Governance Rejection Safety Path (2:05 – 2:30)
* **Visual**: A faulty or unverified fix is proposed for an unauthorized escrow.
* **Room Action**: Human engineer types:
  ```text
  REJECT esc-9903 Untrusted schema rewrite
  ```
* **Result**: Escrow transitions to `REJECTED`, worker halts gracefully with structured error `tool_result`, preventing corrupted state or financial waste.

### Act V: Cryptographic Proof & Ledger Verification (2:30 – 2:45)
* **Visual**: In terminal, run:
  ```bash
  python verify_ledger.py --tamper-demo
  ```
* **Output**:
  1. Chain 1 (Untampered): `[OK] ALL 15 EVENTS VERIFIED. ROOM ANCHOR MATCHES.`
  2. Chain 2 (Tampered): `[FAIL] TAMPER DETECTED AT SEQ #3. Cryptographic hash collision prevented.`
* **Closing**: "SwitchBlade: Turning Switch from a passive notification sink into an active, tamper-evident FinOps Control Plane."

---

## 3. Quick Demo Launch Commands

```bash
# Terminal 1: Mock Billing API (:8001)
python mock_billing_api.py

# Terminal 2: SwitchBlade Proxy (:8002)
python proxy.py

# Terminal 3: Rich Telemetry Cockpit (10 FPS Live Polling)
python run_demo.py --mode live

# Terminal 4: Run Benchmarks & View Comparison Table
python bench/run_bench.py
python run_demo.py --show-bench
```
