"""
Mock Billing API Service (Port 8001)
Owned by Janani (branch: feat/janani-agents-vaccine)

Features:
- Seeded Orders: 9901 (Acme-India, $4500) and 9902 (Globex-Corp, $1850).
- Unknown Order IDs return 404.
- POST /v1/orders: Deprecated endpoint returning 422 with a realistic ~15,000 token multi-kilobyte diagnostic trace.
- POST /v2/orders: Modern endpoint requiring X-Tenant-ID, Idempotency-Key (for live mutations), and supporting ?dry_run=true / X-Dry-Run: true.
- GET /openapi.json: OpenAPI 3.1 spec marking /v1/orders deprecated and /v2/orders active with required X-Tenant-ID.
"""

import copy
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mock_billing_api")

app = FastAPI(
    title="SwitchBlade Mock Enterprise Billing API",
    description="Simulates an enterprise billing system experiencing API version drift between v1 and v2.",
    version="2.0.0",
)

# Seeded Orders Store
INITIAL_SEEDED_ORDERS: Dict[int, Dict[str, Any]] = {
    9901: {
        "order_id": 9901,
        "amount": 4500.00,
        "customer": "Acme-India",
        "tenant_id": "acme-corp",
        "status": "pending",
        "settled_at": None,
    },
    9902: {
        "order_id": 9902,
        "amount": 1850.00,
        "customer": "Globex-Corp",
        "tenant_id": "acme-corp",
        "status": "pending",
        "settled_at": None,
    },
}

# Live state initialized with deepcopy to preserve int keys
orders_db: Dict[int, Dict[str, Any]] = copy.deepcopy(INITIAL_SEEDED_ORDERS)
idempotency_cache: Dict[str, Dict[str, Any]] = {}


def find_order(order_id: int) -> Optional[Dict[str, Any]]:
    """Helper to locate order by int or str representation."""
    if order_id in orders_db:
        return orders_db[order_id]
    if str(order_id) in orders_db:
        return orders_db[str(order_id)]  # type: ignore
    return None


class OrderPayload(BaseModel):
    order_id: int = Field(..., description="Unique ID of the order to settle")
    amount: Optional[float] = Field(None, description="Order total amount")
    customer: Optional[str] = Field(None, description="Customer name")


def generate_v1_diagnostic_trace(order_id: int, order: Dict[str, Any]) -> str:
    """
    Generates a realistic multi-kilobyte diagnostic stack trace and schema dump.
    Sized so that Anthropic count_tokens measures ~15,000 tokens (approx 55,000-58,000 characters).
    """
    header_block = (
        f"CRITICAL ERROR [FATAL_SCHEMA_MIGRATION_REQUIRED]: Endpoint /v1/orders is decommissioned under RFC-8412.\n"
        f"Order ID: {order_id} | Customer: {order.get('customer')} | Registered Tenant: {order.get('tenant_id')}\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"Reason: In-flight settlement rejected. The v1 billing contract lacks mandatory cryptographic idempotency "
        f"and context-bound multi-tenant isolation headers required by BillingGatewayEngine v2.4.0.\n"
        f"{'='*80}\n"
    )

    # Realistic enterprise trace frames
    frames = [
        ("billing.gateway.router.DispatchEngine", "dispatch_request", "/opt/billing/gateway/router.py", 142),
        ("billing.v1.pipeline.OrderPipelineV1", "execute_settlement", "/opt/billing/v1/pipeline.py", 88),
        ("billing.v1.validators.ContractValidator", "validate_request_envelope", "/opt/billing/v1/validators.py", 312),
        ("billing.core.security.TenantGuard", "assert_tenant_context", "/opt/billing/core/security.py", 59),
        ("billing.core.compliance.RFC8412Auditor", "check_deprecation_policy", "/opt/billing/core/compliance.py", 204),
        ("billing.ledger.transaction.JournalWriter", "prepare_entry", "/opt/billing/ledger/journal.py", 419),
        ("billing.db.pool.ConnectionWrapper", "begin_immediate_transaction", "/opt/billing/db/pool.py", 77),
        ("billing.telemetry.diagnostics.DeepTraceInspector", "capture_execution_context", "/opt/billing/telemetry.py", 511),
    ]

    traceback_lines = ["Traceback (most recent call last):"]
    for i in range(12):  # repeat call layers with varied frame contexts
        for cls, func, path, line in frames:
            traceback_lines.append(f'  File "{path}", line {line + (i*7)}, in {func}')
            traceback_lines.append(f'    frame_context_{i}_{func}(session_id="sess_sb_{order_id}_{i:03d}")')
            traceback_lines.append(
                f'    SchemaValidationFailure: Field "X-Tenant-ID" is missing from envelope headers. '
                f'Caller attempted legacy unauthenticated mutate on tenant record "{order.get("tenant_id")}".'
            )

    full_traceback = "\n".join(traceback_lines)

    # Detailed OpenAPI & JSON Schema diff dump showing why v1 fails and what v2 expects
    schema_diff_payload = {
        "error_code": "ERR_V1_ENDPOINT_DEPRECATED_STRICT_MIGRATION",
        "http_status": 422,
        "failing_endpoint": "/v1/orders",
        "canonical_active_endpoint": "/v2/orders",
        "diagnostics": {
            "missing_headers": ["X-Tenant-ID"],
            "missing_live_headers": ["Idempotency-Key"],
            "permitted_dry_run_flags": ["?dry_run=true", "X-Dry-Run: true"],
            "detected_payload": {
                "order_id": order_id,
                "amount": order.get("amount"),
                "customer": order.get("customer"),
            },
            "remediation_instructions": [
                "1. Update tool call path from /v1/orders to /v2/orders",
                "2. Inject mandatory header X-Tenant-ID matching task.tenant_id",
                "3. Inject mandatory header Idempotency-Key on live mutating requests",
                "4. For validation without settlement, invoke with ?dry_run=true or X-Dry-Run: true",
            ],
            "v1_deprecated_json_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "LegacyOrderRequestV1",
                "type": "object",
                "deprecated": True,
                "deprecation_date": "2026-01-01T00:00:00Z",
                "properties": {
                    "order_id": {"type": "integer"},
                    "amount": {"type": "number"},
                    "customer": {"type": "string"},
                },
                "required": ["order_id"],
            },
            "v2_active_json_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "ModernOrderRequestV2",
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "minimum": 1},
                    "amount": {"type": "number", "minimum": 0.01},
                    "customer": {"type": "string", "minLength": 1},
                },
                "required_headers": {
                    "X-Tenant-ID": {
                        "type": "string",
                        "description": "Authenticated multi-tenant partition key",
                    },
                    "Idempotency-Key": {
                        "type": "string",
                        "format": "sha256",
                        "description": "Unique deterministic idempotency token for live settlement",
                    },
                },
                "optional_headers": {
                    "X-Dry-Run": {"type": "string", "enum": ["true", "false"]}
                },
            },
            "ast_inspection_dump": [
                {
                    "node_id": f"ast_node_{k}_{order_id}",
                    "ast_type": "HttpRouteHandler",
                    "route": "/v1/orders",
                    "status": "DISABLED",
                    "compiler_optimization": "BYPASS_STATION_FAILURE",
                    "memory_footprint_bytes": 1024 * (k + 1),
                    "stack_canary": f"0xCAFE{k:04x}BEEF{order_id:04x}",
                    "diagnostic_note": (
                        "Legacy endpoint invocation rejected at Gateway boundary. "
                        "Agent must compact execution trace and upgrade calling contract."
                    ),
                }
                for k in range(35)
            ],
        },
    }

    schema_dump_str = json.dumps(schema_diff_payload, indent=2)

    # Combine blocks
    combined = f"{header_block}\n{full_traceback}\n\n{'='*80}\nSCHEMA DUMP & SPEC DIFFERENTIAL:\n{schema_dump_str}\n"

    # Target character count: ~55,500 characters (approx 15,000 Anthropic tokens)
    target_chars = 55500
    current_chars = len(combined)
    if current_chars < target_chars:
        padding_needed = target_chars - current_chars
        # Generate structured audit log padding
        log_block = (
            "\n[AUDIT_LOG_STREAM_BEGIN]\n"
            + "\n".join(
                f"[TRACE-LOG-{i:05d}] {datetime.now(timezone.utc).isoformat()} "
                f"AUDIT_EVENT=E_DEPRECATION_ATTEMPT order_id={order_id} tenant={order.get('tenant_id')} "
                f"severity=HIGH violation_code=V1_DEPRECATED_CALL stack_depth={i % 64} "
                f"payload_hash=sha256:d8e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4"
                for i in range((padding_needed // 180) + 10)
            )
            + "\n[AUDIT_LOG_STREAM_END]\n"
        )
        combined += log_block[:padding_needed]
    elif current_chars > target_chars + 1000:
        combined = combined[:target_chars]

    return combined


@app.post(
    "/v1/orders",
    deprecated=True,
    status_code=422,
    summary="Legacy Order Settlement (Deprecated)",
    description="Deprecated v1 endpoint. Returns 422 with realistic multi-kilobyte diagnostic trace (~15k tokens).",
)
async def settle_order_v1(payload: OrderPayload):
    """
    Legacy v1 settlement endpoint.
    Returns 404 if order does not exist.
    Returns 422 with a realistic ~15,000 token multi-kilobyte diagnostic stack trace if order exists.
    """
    order_id = payload.order_id
    order = find_order(order_id)
    if not order:
        logger.warning(f"POST /v1/orders: Order {order_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    diagnostic_trace = generate_v1_diagnostic_trace(order_id, order)

    logger.info(
        f"POST /v1/orders: Rejecting legacy settlement for order {order_id} with 422 "
        f"(diagnostic size: {len(diagnostic_trace)} chars, ~{len(diagnostic_trace)//3.7:.0f} tokens)"
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": "ENDPOINT_DEPRECATED_UNPROCESSABLE_ENTITY",
            "message": "Endpoint /v1/orders is deprecated. Upgrade to /v2/orders with required headers.",
            "order_id": order_id,
            "status_code": 422,
            "diagnostic_stack_trace": diagnostic_trace,
        },
    )


@app.post(
    "/v2/orders",
    status_code=status.HTTP_200_OK,
    summary="Modern Order Settlement (Active)",
    description="Active v2 settlement endpoint requiring X-Tenant-ID header and Idempotency-Key on live calls.",
)
async def settle_order_v2(
    payload: OrderPayload,
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_dry_run: Optional[str] = Header(None, alias="X-Dry-Run"),
    dry_run: Optional[bool] = Query(False, description="Run validation without mutating state"),
):
    """
    Active v2 settlement endpoint.
    - Requires header X-Tenant-ID (422 if missing).
    - Supports dry-run via ?dry_run=true or X-Dry-Run: true.
    - Requires header Idempotency-Key on live calls (400 if missing).
    - Caches settled responses by Idempotency-Key so retries never double-charge.
    """
    order_id = payload.order_id

    # 1. Require X-Tenant-ID header
    if not x_tenant_id or not x_tenant_id.strip():
        logger.warning(f"POST /v2/orders: Missing required X-Tenant-ID for order {order_id}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "MISSING_TENANT_HEADER",
                "detail": "Missing required header: X-Tenant-ID",
                "status": "invalid_tenant",
            },
        )

    # 2. Check Order Existence
    order = find_order(order_id)
    if not order:
        logger.warning(f"POST /v2/orders: Order {order_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )

    # Validate tenant isolation
    if order["tenant_id"] != x_tenant_id:
        logger.warning(
            f"POST /v2/orders: Tenant mismatch for order {order_id} "
            f"(expected {order['tenant_id']}, got {x_tenant_id})"
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "TENANT_MISMATCH",
                "detail": f"Tenant '{x_tenant_id}' is not authorized to access order {order_id}",
            },
        )

    # 3. Detect Dry-Run (via query parameter or header)
    is_dry_run = dry_run or (x_dry_run is not None and x_dry_run.lower() in ("true", "1", "yes"))

    if is_dry_run:
        logger.info(f"POST /v2/orders: Dry-run validation succeeded for order {order_id}")
        # Validate payload and tenant without mutating order state
        return {
            "status": "dry_run_valid",
            "order_id": order_id,
            "would_settle": True,
        }

    # 4. Live Mutation requires Idempotency-Key
    if not idempotency_key or not idempotency_key.strip():
        logger.warning(f"POST /v2/orders: Missing required Idempotency-Key on live call for order {order_id}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "MISSING_IDEMPOTENCY_KEY",
                "detail": "Missing required header: Idempotency-Key",
            },
        )

    # 5. Check Idempotency Cache
    if idempotency_key in idempotency_cache:
        cached_response = idempotency_cache[idempotency_key]
        logger.info(f"POST /v2/orders: Cache hit for Idempotency-Key '{idempotency_key}', returning cached settlement")
        return cached_response

    # 6. Settle Order
    order["status"] = "settled"
    order["settled_at"] = datetime.now(timezone.utc).isoformat()

    response_data = {
        "status": "settled",
        "order_id": order["order_id"],
        "amount": order["amount"],
        "customer": order["customer"],
        "tenant_id": order["tenant_id"],
        "settled_at": order["settled_at"],
        "idempotency_key": idempotency_key,
    }

    # Cache settled response so future retries with same key never double-charge
    idempotency_cache[idempotency_key] = response_data
    logger.info(f"POST /v2/orders: Order {order_id} settled successfully (Idempotency-Key: {idempotency_key})")
    return response_data


@app.get("/orders/{order_id}", summary="Get Order Details")
@app.get("/v2/orders/{order_id}", summary="Get Order Details v2")
async def get_order(order_id: int):
    """Retrieve current order state."""
    order = find_order(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return order


@app.post("/reset", summary="Reset Seeded Orders State")
async def reset_state():
    """Resets orders and idempotency cache to clean initial test state."""
    global orders_db, idempotency_cache
    orders_db = copy.deepcopy(INITIAL_SEEDED_ORDERS)
    idempotency_cache.clear()
    logger.info("Mock Billing API state reset to initial seeded values.")
    return {"status": "reset_complete", "seeded_orders": list(orders_db.keys())}


def custom_openapi():
    """Customize OpenAPI 3.1.0 schema to strictly match milestone requirements."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="SwitchBlade Mock Enterprise Billing API",
        version="2.0.0",
        openapi_version="3.1.0",
        description="Enterprise billing service with OpenAPI 3.1 specifications marking /v1/orders deprecated and /v2/orders active.",
        routes=app.routes,
    )

    # Ensure /v1/orders is marked deprecated
    if "/v1/orders" in openapi_schema.get("paths", {}):
        if "post" in openapi_schema["paths"]["v1/orders"] if "v1/orders" in openapi_schema["paths"] else openapi_schema["paths"]["/v1/orders"]:
            openapi_schema["paths"]["/v1/orders"]["post"]["deprecated"] = True

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_billing_api:app", host="0.0.0.0", port=8001, reload=True)
