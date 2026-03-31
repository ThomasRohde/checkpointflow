from __future__ import annotations

from typing import Any

import pytest

from checkpointflow.engine.evaluator import (
    EvaluatorError,
    _parse_literal,
    evaluate_condition,
    interpolate,
    interpolate_values,
    resolve_path,
    strip_expression_wrapper,
)


@pytest.fixture()
def ctx() -> dict[str, Any]:
    return {
        "inputs": {
            "page_id": "123",
            "source_file": "docs/arch.md",
            "count": 42,
            "flag": True,
            "config": {"timeout": 30, "nested": {"deep": "value"}},
        },
        "steps": {
            "plan": {
                "outputs": {
                    "plan_file": "/tmp/plan.json",
                    "risk_level": "high",
                },
            },
        },
    }


# --- resolve_path ---


def test_resolve_path_simple_input(ctx: dict[str, Any]) -> None:
    assert resolve_path("inputs.page_id", ctx) == "123"


def test_resolve_path_nested(ctx: dict[str, Any]) -> None:
    assert resolve_path("inputs.config.timeout", ctx) == 30


def test_resolve_path_deeply_nested(ctx: dict[str, Any]) -> None:
    assert resolve_path("inputs.config.nested.deep", ctx) == "value"


def test_resolve_path_step_output(ctx: dict[str, Any]) -> None:
    assert resolve_path("steps.plan.outputs.plan_file", ctx) == "/tmp/plan.json"


def test_resolve_path_missing_key_raises(ctx: dict[str, Any]) -> None:
    with pytest.raises(EvaluatorError, match="nonexistent"):
        resolve_path("inputs.nonexistent", ctx)


def test_resolve_path_invalid_root_raises(ctx: dict[str, Any]) -> None:
    with pytest.raises(EvaluatorError, match="unknown"):
        resolve_path("unknown.x", ctx)


# --- interpolate ---


def test_interpolate_single_var(ctx: dict[str, Any]) -> None:
    assert interpolate("echo ${inputs.page_id}", ctx) == "echo 123"


def test_interpolate_multiple_vars(ctx: dict[str, Any]) -> None:
    result = interpolate("cmd --id ${inputs.page_id} --file ${inputs.source_file}", ctx)
    assert result == "cmd --id 123 --file docs/arch.md"


def test_interpolate_step_output(ctx: dict[str, Any]) -> None:
    result = interpolate("apply --plan ${steps.plan.outputs.plan_file}", ctx)
    assert result == "apply --plan /tmp/plan.json"


def test_interpolate_no_vars(ctx: dict[str, Any]) -> None:
    assert interpolate("echo hello", ctx) == "echo hello"


def test_interpolate_non_string_value(ctx: dict[str, Any]) -> None:
    assert interpolate("count is ${inputs.count}", ctx) == "count is 42"


def test_interpolate_missing_var_raises(ctx: dict[str, Any]) -> None:
    with pytest.raises(EvaluatorError):
        interpolate("echo ${inputs.nope}", ctx)


# --- evaluate_condition ---


def test_evaluate_condition_equality_true(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('inputs.page_id == "123"', ctx) is True


def test_evaluate_condition_equality_false(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('inputs.page_id == "456"', ctx) is False


def test_evaluate_condition_inequality(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('inputs.page_id != "456"', ctx) is True


def test_evaluate_condition_boolean_literal(ctx: dict[str, Any]) -> None:
    assert evaluate_condition("inputs.flag == true", ctx) is True


def test_evaluate_condition_step_output(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('steps.plan.outputs.risk_level == "high"', ctx) is True


def test_evaluate_condition_and(ctx: dict[str, Any]) -> None:
    assert (
        evaluate_condition(
            'inputs.page_id == "123" and steps.plan.outputs.risk_level == "high"', ctx
        )
        is True
    )


def test_evaluate_condition_and_false(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('inputs.page_id == "123" and inputs.page_id == "999"', ctx) is False


def test_evaluate_condition_or(ctx: dict[str, Any]) -> None:
    assert evaluate_condition('inputs.page_id == "999" or inputs.page_id == "123"', ctx) is True


def test_evaluate_condition_int_comparison(ctx: dict[str, Any]) -> None:
    assert evaluate_condition("inputs.count == 42", ctx) is True


def test_evaluate_condition_int_mismatch(ctx: dict[str, Any]) -> None:
    assert evaluate_condition("inputs.count == 99", ctx) is False


def test_evaluate_condition_mixed_type_string_vs_int(ctx: dict[str, Any]) -> None:
    # count is int 42, comparing against string "42" — type coercion should match
    assert evaluate_condition('inputs.count == "42"', ctx) is True


# --- _parse_literal ---


def test_parse_literal_int() -> None:
    assert _parse_literal("42") == 42
    assert isinstance(_parse_literal("42"), int)


def test_parse_literal_float() -> None:
    assert _parse_literal("3.14") == 3.14
    assert isinstance(_parse_literal("3.14"), float)


def test_parse_literal_null() -> None:
    assert _parse_literal("null") is None


def test_parse_literal_bare_token() -> None:
    assert _parse_literal("hello") == "hello"


# --- strip_expression_wrapper ---


def test_strip_expression_wrapper_strips() -> None:
    assert strip_expression_wrapper("${inputs.x}") == "inputs.x"


def test_strip_expression_wrapper_leaves_plain() -> None:
    assert strip_expression_wrapper("plain") == "plain"


def test_strip_expression_wrapper_partial() -> None:
    assert strip_expression_wrapper("${incomplete") == "${incomplete"


# --- interpolate_values ---


def test_interpolate_values_pure_reference(ctx: dict[str, Any]) -> None:
    assert interpolate_values("${inputs.page_id}", ctx) == "123"


def test_interpolate_values_mixed_string(ctx: dict[str, Any]) -> None:
    assert interpolate_values("id-${inputs.page_id}-end", ctx) == "id-123-end"


def test_interpolate_values_nested_dict(ctx: dict[str, Any]) -> None:
    result = interpolate_values({"key": "${inputs.page_id}"}, ctx)
    assert result == {"key": "123"}


def test_interpolate_values_list(ctx: dict[str, Any]) -> None:
    result = interpolate_values(["${inputs.page_id}", "static"], ctx)
    assert result == ["123", "static"]


def test_interpolate_values_non_string_passthrough() -> None:
    assert interpolate_values(42, {}) == 42
    assert interpolate_values(True, {}) is True
    assert interpolate_values(None, {}) is None


def test_interpolate_values_preserves_type_for_full_expr() -> None:
    ctx: dict[str, Any] = {"inputs": {"count": 42}}
    result = interpolate_values("${inputs.count}", ctx)
    assert result == 42
    assert isinstance(result, int)
