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

# The agent package is about 44 MB. The deploy tool uploads it in four parallel
# parts, which times out on slow or unstable connections. Upload it here as a
# single stream first; the deploy then finds it in place and skips the upload.
say "Building deployable packages..."
agentcore build --region "$AWS_REGION" >>"$LOG" 2>&1 || { say "Build failed. See $LOG"; exit 1; }
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
python3 - "$ACCOUNT" "$AWS_REGION" <<'PY' > .asset_list
import glob, json, sys
account, region = sys.argv[1], sys.argv[2]
for manifest in glob.glob("agentcore/cdk/cdk.out/*-default.assets.json"):
    for entry in json.load(open(manifest)).get("files", {}).values():
        path = entry["source"].get("path", "")
        if not path.endswith(".zip"):
            continue
        for dest in entry["destinations"].values():
            bucket = dest["bucketName"].replace("${AWS::AccountId}", account).replace("${AWS::Region}", region)
            print(f"agentcore/cdk/cdk.out/{path}\t{bucket}\t{dest['objectKey']}")
PY
while IFS=$'\t' read -r file bucket key; do
  if aws s3api head-object --bucket "$bucket" --key "$key" >/dev/null 2>&1; then
    say "Already uploaded: $(basename "$file")"
  else
    say "Uploading $(basename "$file") ($(du -h "$file" | cut -f1)) as a single stream; this can take several minutes..."
    aws s3api put-object --bucket "$bucket" --key "$key" --body "$file" \
      --cli-read-timeout 0 --cli-connect-timeout 60 >>"$LOG" 2>&1 || { say "Upload failed. See $LOG"; rm -f .asset_list; exit 1; }
  fi
done < .asset_list
rm -f .asset_list

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
