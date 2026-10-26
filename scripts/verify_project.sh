#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

printf '%s\n' '[1/3] Unified backend and InsightHub Worker tests'
(cd "$ROOT_DIR/backend" && uv run pytest tests -q)

printf '%s\n' '[2/3] Frontend tests'
(cd "$ROOT_DIR/frontend" && npm test)

printf '%s\n' '[3/3] Frontend production build check'
(cd "$ROOT_DIR/frontend" && npm run check)

printf '%s\n' 'Project verification passed.'
