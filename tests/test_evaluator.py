from __future__ import annotations

from typing import Any

import pytest

from checkpointflow.engine.evaluator import (
    EvaluatorError,
    evaluate_condition,
    interpolate,
    resolve_path,
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
