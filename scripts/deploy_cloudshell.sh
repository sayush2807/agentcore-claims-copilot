#!/usr/bin/env bash
# Deploys from AWS CloudShell instead of a laptop. Use this when the local
# network cannot upload the agent package to S3. CloudShell runs inside AWS,
# is already signed in as the console user, and has a fast path to S3.
#
# In CloudShell (us-east-2), run:
#   curl -fsSL https://raw.githubusercontent.com/sayush2807/agentcore-claims-copilot/main/scripts/deploy_cloudshell.sh | bash
set -uo pipefail

export AWS_REGION="us-east-2" AWS_DEFAULT_REGION="us-east-2"
WORK="/tmp/claims-copilot"          # /tmp: CloudShell's home directory is limited to 1 GB
export npm_config_cache="/tmp/npm-cache" npm_config_prefix="/tmp/npm-global" UV_CACHE_DIR="/tmp/uv-cache"
export PATH="/tmp/uv-bin:/tmp/npm-global/bin:$HOME/.local/bin:$PATH"
LOG="/tmp/deploy.log"
mkdir -p "$WORK" && cd "$WORK"
: > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

say "== Tools =="
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh 2>>"$LOG" | env UV_INSTALL_DIR=/tmp/uv-bin UV_NO_MODIFY_PATH=1 sh >>"$LOG" 2>&1
fi
command -v uv >/dev/null 2>&1 || { say "Could not install uv. See $LOG"; exit 1; }
command -v agentcore >/dev/null 2>&1 || npm install -g @aws/agentcore >>"$LOG" 2>&1
say "node $(node --version), $(uv --version), agentcore $(agentcore --version 2>/dev/null | tail -1)"

say "== Source =="
if [ -d repo/.git ]; then git -C repo pull -q --ff-only; else git clone -q https://github.com/sayush2807/agentcore-claims-copilot repo; fi
cd repo
say "at commit $(git log --oneline -1)"
(cd agentcore/cdk && npm install --no-audit --no-fund >>"$LOG" 2>&1) || { say "npm install failed. See $LOG"; exit 1; }

say "== Tests =="
uv run --no-project --with pytest python -m pytest tests -q 2>&1 | tail -1 | tee -a "$LOG"

say "== Identity =="
git checkout -q -- agentcore/agentcore.json
bash scripts/configure_identity.sh 2>&1 | tail -1 | tee -a "$LOG"

say "== Deploy (10 minutes or more on the first run) =="
if ! agentcore deploy --region "$AWS_REGION" 2>&1 | tee -a "$LOG"; then say "DEPLOY FAILED. See $LOG"; exit 1; fi

say "== Status =="
agentcore status --region "$AWS_REGION" 2>&1 | tee -a "$LOG"

say "== Invoke: CLM-9001 =="
agentcore invoke --runtime agent --region "$AWS_REGION" \
  --payload '{"prompt": "Review claim CLM-9001 and give me your recommendation."}' 2>&1 | tee -a "$LOG"

say "== DONE =="
