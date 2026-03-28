from __future__ import annotations

from checkpointflow.models.errors import ErrorCode, ExitCode


def test_exit_code_success_is_zero() -> None:
    assert ExitCode.SUCCESS == 0


def test_exit_code_validation_error_is_ten() -> None:
    assert ExitCode.VALIDATION_ERROR == 10


def test_exit_code_internal_error_is_ninety() -> None:
    assert ExitCode.INTERNAL_ERROR == 90


def test_error_codes_are_prefixed() -> None:
    for code in ErrorCode:
        assert code.value.startswith("ERR_"), f"{code.name} does not start with ERR_"
