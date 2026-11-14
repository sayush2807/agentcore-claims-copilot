#!/usr/bin/env bash
# Deploys everything declared in agentcore/agentcore.json to AWS (us-east-2):
# the agent on AgentCore Runtime, its Memory, the Gateway, and the Lambda
# function behind it. Then asks the deployed agent about one claim.
# Output is saved to deploy.log.
set -uo pipefail
cd "$(dirname "$0")/.."

export AWS_REGION="us-east-2"
export AWS_DEFAULT_REGION="us-east-2"
LOG="deploy.log"
: > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  say "AWS session expired; signing in again (a browser window will open)..."
  aws login --region "$AWS_REGION"
fi
say "Deploying to account $(aws sts get-caller-identity --query Account --output text) in $AWS_REGION"

if [ ! -d agentcore/cdk/node_modules ]; then
  say "Installing CDK dependencies..."
  (cd agentcore/cdk && npm install --no-audit --no-fund) >>"$LOG" 2>&1 || { say "npm install failed. See $LOG"; exit 1; }
fi

say "Running unit tests..."
if ! uv run --no-project --with pytest python -m pytest tests -q >>"$LOG" 2>&1; then
  say "Tests failed; not deploying. See $LOG"; exit 1
fi

say "Deploying (first run can take 10 minutes or more)..."
if ! agentcore deploy --region "$AWS_REGION" 2>&1 | tee -a "$LOG"; then
  say "Deploy failed. See $LOG"; exit 1
fi

say ""
say "=== Status ==="
agentcore status --region "$AWS_REGION" 2>&1 | tee -a "$LOG"

say ""
say "=== Asking the deployed agent about CLM-9001 ==="
agentcore invoke --runtime agent --region "$AWS_REGION" \
  --payload '{"prompt": "Review claim CLM-9001 and give me your recommendation."}' 2>&1 | tee -a "$LOG"

say ""
say "Done. Full log: $LOG"
