from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    hooks_dir = repo_root / ".githooks"

    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        check=True,
        cwd=repo_root,
    )

    if os.name != "nt":
        for hook_path in hooks_dir.iterdir():
            if hook_path.is_file():
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print("Installed git hooks from .githooks")
    print("To bypass temporarily, set CHECKPOINTFLOW_SKIP_HOOKS=1")


if __name__ == "__main__":
    main()
