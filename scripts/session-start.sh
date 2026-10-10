#!/bin/bash
# Claude Code SessionStart hook: install dependencies in cloud sessions so tests and lint work right away.
set -euo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
cd "${CLAUDE_PROJECT_DIR:-.}"
poetry install --no-root --extras dev --no-interaction >/dev/null
