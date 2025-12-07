#!/usr/bin/env bash
set -euo pipefail

# Move to repo root (this script is under scripts/)
cd "$(dirname "$0")/.."

mkdir -p .githooks

# Ensure pre-commit exists (tracked in repo). If missing, fail with hint.
if [ ! -f .githooks/pre-commit ]; then
  echo "ERROR: .githooks/pre-commit not found. Pull the repository or add it first." >&2
  exit 1
fi

# Make executable
chmod +x .githooks/pre-commit

# Point git to use repo-managed hooks
git config core.hooksPath .githooks

echo "Git hooks installed: core.hooksPath=.githooks"
echo "Pre-commit will block commits touching: logs/** and memory/**/textual_memory.json"

