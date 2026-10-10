from __future__ import annotations

from app.models import Action, ScanResult, ToolEvent

ORDERS = {
    "123": {"id": "123", "item": "Laptop stand", "status": "shipped", "customer": "Ada"},
    "456": {"id": "456", "item": "USB-C hub", "status": "processing", "customer": "Lin"},
}

CUSTOMERS = {
    "ada": {"name": "Ada", "email": "ada@example.com", "plan": "pro"},
    "lin": {"name": "Lin", "email": "lin@example.com", "plan": "starter"},
}

EMAIL_ALLOWLIST = {"ada@example.com", "support@example.com"}

TOOL_DECLS = [
    {
        "name": "get_order",
        "description": "Look up an order by id.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "search_customer",
        "description": "Search a customer by name.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email. Restricted tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "body"],
        },
    },
]


def tool_allowed(name: str, arguments: dict, scan: ScanResult, user_input: str) -> tuple[bool, str]:
    dangerous = {"tool_abuse", "secret_extraction", "indirect_prompt_injection"}
    if name == "send_email":
        if scan.action == Action.BLOCK:
            return False, "firewall blocked the request"
        if dangerous & set(scan.attack_types):
            return False, "tool gate: send_email denied after injection/tool-abuse signal"
        to = str(arguments.get("to") or "").lower()
        if to not in EMAIL_ALLOWLIST:
            return False, f"tool gate: recipient {to!r} is not allowlisted"
        if "email" not in user_input.lower() and "send" not in user_input.lower():
            return False, "tool gate: user intent did not request email"
        return True, "allowlisted send_email"
    if scan.action == Action.BLOCK:
        return False, "firewall blocked the request"
    return True, "read tool allowed"


def execute_tool(name: str, arguments: dict) -> str:
    if name == "get_order":
        oid = str(arguments.get("order_id") or "")
        order = ORDERS.get(oid)
        return str(order) if order else f"No order {oid}"
    if name == "search_customer":
        q = str(arguments.get("query") or "").lower()
        for key, row in CUSTOMERS.items():
            if q in key or q in row["name"].lower():
                return str(row)
        return "No customer found"
    if name == "send_email":
        return f"Email queued to {arguments.get('to')}"
    return f"Unknown tool {name}"


def gated_call(name: str, arguments: dict, scan: ScanResult, user_input: str) -> ToolEvent:
    allowed, reason = tool_allowed(name, arguments, scan, user_input)
    result = execute_tool(name, arguments) if allowed else None
    return ToolEvent(name=name, arguments=arguments, allowed=allowed, reason=reason, result=result)
