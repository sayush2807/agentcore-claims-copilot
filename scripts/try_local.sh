#!/usr/bin/env bash
# Runs the agent locally against a real Bedrock model and asks it about two
# claims. Output is saved to local_run.log so it can be shared for debugging.
set -uo pipefail
cd "$(dirname "$0")/.."

export AWS_REGION="us-east-2"
export AWS_DEFAULT_REGION="us-east-2"
LOG="local_run.log"
: > "$LOG"

echo "Starting local dev server (first run installs dependencies; this can take a few minutes)..."
agentcore dev --no-traces >>"$LOG" 2>&1 &
DEV_PID=$!
trap 'kill $DEV_PID 2>/dev/null' EXIT

for i in $(seq 1 120); do
  if curl -s -o /dev/null "http://127.0.0.1:8080/ping"; then break; fi
  if ! kill -0 $DEV_PID 2>/dev/null; then echo "Dev server exited early. See $LOG"; tail -40 "$LOG"; exit 1; fi
  sleep 3
done

ask() {
  echo; echo "=== Q: $1 ===" | tee -a "$LOG"
  agentcore invoke --runtime agent --local --payload "{\"prompt\": \"$1\"}" 2>&1 | tee -a "$LOG"
  echo
}

ask "Review claim CLM-9000 and give me your recommendation."
ask "Review claim CLM-9004 and give me your recommendation."

echo
echo "Done. Full log: $LOG"
