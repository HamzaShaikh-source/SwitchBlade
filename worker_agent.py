"""
SwitchBlade Worker Agent (worker_agent.py)
Owned by Janani (branch: feat/janani-agents-vaccine)

Autonomous order settlement worker executing sync_customer_order through
Santosh's proxy (:8002/proxy/execute_tool) using the official Anthropic SDK.
Supports pre-send Zero-Retry Turn 1 rewrite via VaccineRegistry.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional

import httpx

from schemas import TaskContext
from tools.orders_tool import SYNC_CUSTOMER_ORDER_TOOL, sync_customer_order

try:
    import anthropic
except ImportError:
    anthropic = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("worker_agent")

DEFAULT_SYSTEM_PROMPT = (
    "You are the SwitchBlade Order Settlement Worker. "
    "Your objective is to synchronize and settle customer orders in the billing system "
    "using the available sync_customer_order tool. Always inspect responses carefully."
)


class WorkerAgent:
    """Executes order settlement tasks through the SwitchBlade proxy gateway."""

    def __init__(
        self,
        proxy_url: str = "http://localhost:8002",
        mock_api_url: str = "http://localhost:8001",
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        tool_executor: Optional[Callable[..., Dict[str, Any]]] = None,
        vaccine_registry: Optional[Any] = None,
    ):
        self.proxy_url = os.environ.get("SWITCHBLADE_PROXY_URL", proxy_url).rstrip("/")
        self.mock_api_url = os.environ.get("MOCK_BILLING_API_URL", mock_api_url).rstrip("/")
        self.model = os.environ.get("SWITCHBLADE_MODEL", model)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=self.api_key) if (anthropic and self.api_key) else None
        self.http_client = http_client
        self.tool_executor = tool_executor
        self.vaccine_registry = vaccine_registry

    def execute_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: str,
        context: TaskContext,
    ) -> Dict[str, Any]:
        """Routes tool execution through custom executor, proxy, or direct vaccinated execution."""
        if self.tool_executor:
            return self.tool_executor(tool_name, tool_input, tool_use_id, context)

        # Pre-send Zero-Retry Vaccine Interception
        target_path = "/v1/orders"
        custom_headers: Dict[str, str] = {}
        if self.vaccine_registry:
            application = self.vaccine_registry.match_and_apply(
                tool_name=tool_name,
                http_method="POST",
                path=target_path,
                task_context=context,
            )
            if application.applied:
                target_path = application.rewritten_path or target_path
                custom_headers.update(application.injected_headers)
                if "Idempotency-Key" not in custom_headers:
                    custom_headers["Idempotency-Key"] = f"idem-key-{context.task_id}-{context.order_id}"
                logger.info(
                    f"Pre-send vaccine {application.vaccine_id} applied: "
                    f"rewrote to {target_path} with headers {list(custom_headers.keys())}"
                )

        try:
            client = self.http_client or httpx.Client(timeout=1.5)
            res = client.post(
                f"{self.proxy_url}/proxy/execute_tool",
                json={
                    "tool_name": tool_name,
                    "arguments": tool_input,
                    "tool_use_id": tool_use_id,
                    "context": context.model_dump(),
                },
            )
            if res.status_code in (200, 422, 503):
                return res.json()
        except Exception as e:
            logger.debug(f"Proxy unavailable at {self.proxy_url} ({e}); falling back to direct tool execution.")

        # Fallback direct execution
        return sync_customer_order(
            order_id=tool_input.get("order_id", context.order_id),
            amount=tool_input.get("amount", context.amount),
            customer=tool_input.get("customer", context.customer),
            base_url=self.mock_api_url,
            endpoint=target_path,
            custom_headers=custom_headers if custom_headers else None,
            http_client=self.http_client,
        )

    def run_settlement_task(self, context: TaskContext, max_turns: int = 5) -> Dict[str, Any]:
        """Runs the multi-turn Anthropic tool-use loop for order settlement."""
        logger.info(f"Starting settlement task for Order #{context.order_id} ({context.customer})...")
        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Please synchronize and settle customer order {context.order_id} "
                    f"for customer '{context.customer}' with amount ${context.amount:.2f}."
                ),
            }
        ]

        turn = 0
        escrow_tripped = False
        last_escrow_id: Optional[str] = None
        task_settled = False

        while turn < max_turns:
            turn += 1
            logger.info(f"--- Turn {turn} / {max_turns} ---")

            if self.client:
                # Real Anthropic SDK API call
                resp = self.client.messages.create(
                    model=self.model,
                    system=DEFAULT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=[SYNC_CUSTOMER_ORDER_TOOL],
                    max_tokens=1024,
                )
                assistant_content = [b.model_dump() for b in resp.content]
            else:
                # Deterministic simulation mode when ANTHROPIC_API_KEY is not set
                tool_use_id = f"toolu_sim_{context.order_id}_{turn:02d}"
                assistant_content = [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": "sync_customer_order",
                        "input": {"order_id": context.order_id},
                    }
                ]

            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_calls = [b for b in assistant_content if b.get("type") == "tool_use"]
            if not tool_calls:
                logger.info(f"Task completed with final text from assistant at Turn {turn}.")
                break

            user_results: List[Dict[str, Any]] = []
            for call in tool_calls:
                call_id = call.get("id", "toolu_default")
                tool_name = call.get("name", "sync_customer_order")
                tool_args = call.get("input", {})

                result = self.execute_tool_call(tool_name, tool_args, call_id, context)

                # Check if proxy tripped circuit breaker
                if isinstance(result, dict) and result.get("status") == "tripped":
                    escrow_tripped = True
                    last_escrow_id = result.get("escrow_id")
                    logger.warning(f"Circuit breaker tripped on Turn {turn}! Escrow ID: {last_escrow_id}")

                # Check if settled
                if isinstance(result, dict):
                    data = result.get("data") if "data" in result else result
                    if isinstance(data, dict) and data.get("status") == "settled":
                        task_settled = True

                user_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": json.dumps(result),
                    }
                )

            messages.append({"role": "user", "content": user_results})

            if escrow_tripped or task_settled:
                break

        return {
            "task_id": context.task_id,
            "order_id": context.order_id,
            "turns_taken": turn,
            "escrow_tripped": escrow_tripped,
            "escrow_id": last_escrow_id,
            "settled": task_settled,
            "message_history": messages,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwitchBlade Worker Agent")
    parser.add_argument("--order-id", type=int, default=9901, help="Order ID to settle")
    parser.add_argument("--customer", type=str, default="Acme-India", help="Customer name")
    parser.add_argument("--amount", type=float, default=4500.0, help="Order total")
    parser.add_argument("--tenant", type=str, default="acme-corp", help="Tenant ID")
    args = parser.parse_args()

    task_ctx = TaskContext(
        task_id=f"task_{args.order_id}",
        order_id=args.order_id,
        tenant_id=args.tenant,
        amount=args.amount,
        customer=args.customer,
    )

    worker = WorkerAgent()
    res = worker.run_settlement_task(task_ctx)
    print(json.dumps(res, indent=2))
