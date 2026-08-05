#!/usr/bin/env bash
# curl smoke: GET team members under both READ_EMPLOYEES states.
# Assumes a test BE started on the port in $PORT (default 8091).
#
# Env:
#   TOKEN   — JWT for a user with hiring_request.view on the target tenant
#   HRID    — hiring_request_id with >=1 team member
#   PORT    — test BE port (default 8091)
#   OUT_DIR — where to save flag-off/on responses (default /tmp)

set -euo pipefail

: "${TOKEN:?export TOKEN=<jwt>}"
: "${HRID:?export HRID=<hiring_request_uuid>}"
PORT="${PORT:-8091}"
OUT_DIR="${OUT_DIR:-/tmp}"

url="http://127.0.0.1:${PORT}/api/v1/hiring-requests/${HRID}/team"

fetch() {
    local label="$1"
    curl -sS -H "Authorization: Bearer $TOKEN" "$url" \
        | python -c "
import sys, json
d = json.load(sys.stdin)
data = d.get('data', [])
data.sort(key=lambda m: m['user_id'])
print(json.dumps({
    'total': d.get('total'),
    'members': [(m['user_id'], m['name'], m.get('designation'), m['is_owner']) for m in data],
}, indent=2))
" > "$OUT_DIR/team-${label}.json"
    echo "→ saved $OUT_DIR/team-${label}.json"
    cat "$OUT_DIR/team-${label}.json"
}

echo "─── ${1:-current-flag} response ───"
fetch "${1:-current}"
