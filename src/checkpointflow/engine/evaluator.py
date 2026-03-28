from __future__ import annotations

import re
from typing import Any


class EvaluatorError(Exception):
    pass


def resolve_path(expression: str, context: dict[str, Any]) -> Any:
    """Resolve a dotted path like 'inputs.page_id' against the context dict."""
    parts = expression.strip().split(".")
    current: Any = context
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            msg = f"Cannot resolve path '{expression}': key '{part}' not found"
            raise EvaluatorError(msg)
        current = current[part]
    return current


def interpolate(template: str, context: dict[str, Any]) -> str:
    """Replace ${...} expressions in a template string with resolved values."""

    def _replacer(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        value = resolve_path(expr, context)
        return str(value)

    return re.sub(r"\$\{([^}]+)\}", _replacer, template)


def _parse_literal(token: str) -> Any:
    """Parse a literal value from the right-hand side of a comparison."""
    # Quoted string
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1]
    # Boolean
    if token == "true":
        return True
    if token == "false":
        return False
    if token == "null":
        return None
    # Number
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _evaluate_comparison(expr: str, context: dict[str, Any]) -> bool:
    """Evaluate a single comparison like 'inputs.x == "value"'."""
    for op in ("!=", "=="):
        if op in expr:
            left_str, right_str = expr.split(op, 1)
            left_val = resolve_path(left_str.strip(), context)
            right_val = _parse_literal(right_str.strip())
            # Coerce for comparison: compare string representations
            # if types differ (e.g., bool True vs string "true")
            if type(left_val) is not type(right_val):
                left_val = str(left_val).lower()
                right_val = str(right_val).lower()
            if op == "==":
                return left_val == right_val  # type: ignore[no-any-return]
            return left_val != right_val  # type: ignore[no-any-return]

    msg = f"Invalid condition expression: '{expr}'"
    raise EvaluatorError(msg)


def evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """Evaluate a boolean condition with support for ==, !=, and, or."""
    condition = condition.strip()
    if not condition:
        msg = "Empty condition expression"
        raise EvaluatorError(msg)

    # Split on ' or ' first (lower precedence)
    or_parts = re.split(r"\s+or\s+", condition)
    if len(or_parts) > 1:
        return any(evaluate_condition(part, context) for part in or_parts)

    # Split on ' and ' (higher precedence)
    and_parts = re.split(r"\s+and\s+", condition)
    if len(and_parts) > 1:
        return all(evaluate_condition(part, context) for part in and_parts)

    return _evaluate_comparison(condition, context)
