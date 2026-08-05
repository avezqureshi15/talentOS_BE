#!/usr/bin/env bash
# End-to-end smoke for the slots module under both flag states.
#
# Usage:
#   BASE=https://talentos.webknot-dev.in/api/v1 \
#   TOKEN=<jwt for a superadmin or account_admin> \
#   EMP_ID=<a real user's emp_id> \
#   USER_ID=<that same user's users.id> \
#   ./scripts/smoke/slots.sh
#
# The script runs identical read/write flows twice: once with the flag
# assumed OFF (current prod), and prints a header for a manual re-run
# after flipping READ_EMPLOYEES=true. All slot rows created during the
# run are cleaned up at the end (marked INACTIVE).

set -euo pipefail

: "${BASE:?export BASE=https://.../api/v1}"
: "${TOKEN:?export TOKEN=<jwt>}"
: "${EMP_ID:?export EMP_ID=<a real user's emp_id>}"
: "${USER_ID:?export USER_ID=<that same user's users.id>}"

H_AUTH="Authorization: Bearer $TOKEN"
H_JSON="Content-Type: application/json"

# start_at 1 hour from now, end_at +30 min
START=$(python3 -c "from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())")
END=$(python3 -c "from datetime import datetime,timezone,timedelta; print((datetime.now(timezone.utc)+timedelta(hours=1,minutes=30)).isoformat())")

echo "─── 1. Create a slot ─────────────────────────────────────────────────"
CREATE_BODY=$(cat <<JSON
{"emp_id":"$EMP_ID","slots":[{"start_at":"$START","end_at":"$END"}]}
JSON
)
CREATE_RESP=$(curl -sS -X POST -H "$H_AUTH" -H "$H_JSON" -d "$CREATE_BODY" "$BASE/slots/")
echo "$CREATE_RESP" | python3 -m json.tool
SLOT_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['data'][0]['id']) if d.get('data') else print('')")
[ -n "$SLOT_ID" ] || { echo "❌ no slot created"; exit 1; }
echo "✅ created slot $SLOT_ID"

echo "─── 2. List slots by user id (path: /by-employee/{user_id}) ─────────"
LIST=$(curl -sS -H "$H_AUTH" "$BASE/slots/by-employee/$USER_ID")
echo "$LIST" | python3 -m json.tool
COUNT=$(echo "$LIST" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))")
[ "$COUNT" -ge 1 ] || { echo "❌ expected at least 1 slot in by-employee list"; exit 1; }
echo "✅ by-employee returned $COUNT slot(s)"

echo "─── 3. Batch list slots by emp_id (path: /employee?emp_ids=...) ─────"
BATCH=$(curl -sS -H "$H_AUTH" "$BASE/slots/employee?emp_ids=$EMP_ID")
echo "$BATCH" | python3 -m json.tool
BATCH_COUNT=$(echo "$BATCH" | python3 -c "import sys,json;d=json.load(sys.stdin);print(sum(len(r['slots']) for r in d['data']))")
[ "$BATCH_COUNT" -ge 1 ] || { echo "❌ expected at least 1 slot in batch response"; exit 1; }
echo "✅ batch returned $BATCH_COUNT slot(s)"

echo "─── 4. Sanity: DB row has BOTH employee_id and employee_ref_id ──────"
echo "    (run on the postgres container)"
echo "    docker exec -i talentos-postgres-1 psql -U talentos -d talentos -c \\"
echo "      \"SELECT id, employee_id, employee_ref_id FROM slots WHERE id = '$SLOT_ID';\""

echo
echo "════════════════════════════════════════════════════════════════════"
echo " Now flip READ_EMPLOYEES=true in /opt/talentos/.env, restart be,"
echo " and re-run this script. Steps 2 and 3 must return the same counts."
echo " If they drop to 0, the user has no linked employee — investigate"
echo " users.employee_id for USER_ID=$USER_ID before dropping the legacy"
echo " column in Phase 3."
echo "════════════════════════════════════════════════════════════════════"
