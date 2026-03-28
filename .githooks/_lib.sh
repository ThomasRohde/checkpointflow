#!/usr/bin/env sh

set -eu

if [ "${CHECKPOINTFLOW_SKIP_HOOKS:-0}" = "1" ]; then
  echo "Skipping checkpointflow git hook because CHECKPOINTFLOW_SKIP_HOOKS=1"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "checkpointflow git hooks require uv on PATH." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

run_step() {
  printf '==> %s\n' "$1"
  shift
  "$@"
}
