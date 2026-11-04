"""
Orders Tool for SwitchBlade Worker Agent
Owned by Janani (branch: feat/janani-agents-vaccine)

Initial implementation:
Targets legacy /v1/orders endpoint (which triggers 422 diagnostic loops in unpatched environments).
Later patched to /v2/orders by Vaccine Compiler (fix/vaccine-042-orders-v2).
"""

from typing import Any, Dict, Optional
import httpx
import logging

logger = logging.getLogger("orders_tool")

# Official Anthropic Claude Tool Specification
SYNC_CUSTOMER_ORDER_TOOL = {
    "name": "sync_customer_order",
    "description": "Synchronize and settle customer order in billing system",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "integer",
                "description": "The unique order ID to sync and settle (e.g. 9901 or 9902)",
            },
            "amount": {
                "type": "number",
                "description": "Order total amount in USD",
            },
            "customer": {
                "type": "string",
                "description": "Customer name",
            },
        },
        "required": ["order_id"],
    },
}


def sync_customer_order(
    order_id: int,
    amount: Optional[float] = None,
    customer: Optional[str] = None,
    base_url: str = "http://localhost:8001",
    proxy_url: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Executes order settlement.
    In v1 (pre-vaccine), calls legacy /v1/orders without X-Tenant-ID or Idempotency-Key.
    Can route directly to mock_billing_api (:8001) or through proxy (:8002/proxy/execute_tool).
    """
    payload: Dict[str, Any] = {"order_id": order_id}
    if amount is not None:
        payload["amount"] = amount
    if customer is not None:
        payload["customer"] = customer

    headers = {"Content-Type": "application/json"}
    if custom_headers:
        headers.update(custom_headers)

    # If proxy_url is specified, route via proxy execution endpoint
    if proxy_url:
        target_url = f"{proxy_url.rstrip('/')}/proxy/execute_tool"
        req_body = {
            "tool_name": "sync_customer_order",
            "arguments": payload,
            "target_url": f"{base_url.rstrip('/')}/v1/orders",
            "http_method": "POST",
            "headers": headers,
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(target_url, json=req_body)
            return {
                "status_code": resp.status_code,
                "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
            }

    # Direct call to legacy v1 endpoint
    target_url = f"{base_url.rstrip('/')}/v1/orders"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(target_url, json=payload, headers=headers)
        return {
            "status_code": resp.status_code,
            "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
        }
