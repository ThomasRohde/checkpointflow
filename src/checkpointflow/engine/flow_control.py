from __future__ import annotations

from typing import Any


def resolve_switch_jump(
    result_outputs: dict[str, Any],
    all_steps: list[Any],
    step_ids: list[str],
) -> tuple[list[Any], int] | None:
    """Resolve a SwitchStep jump target. Returns (remaining_steps, target_idx) or None."""
    next_step_id = result_outputs.get("_next_step_id")
    if next_step_id and next_step_id in step_ids:
        target_idx = step_ids.index(next_step_id)
        return list(all_steps[target_idx:]), target_idx
    return None
