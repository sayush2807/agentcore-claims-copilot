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
# Upload one file in 5 MB parts, one part at a time, retrying each part.
# Slow, but a dropped connection only costs one part instead of the whole file.
upload_in_parts() {
  local file="$1" bucket="$2" key="$3" tmp upload_id n=0 total parts="" etag ok start
  tmp="$(mktemp -d)"
  split -b 5m "$file" "$tmp/part."
  total="$(ls "$tmp" | wc -l | tr -d ' ')"
  upload_id="$(aws s3api create-multipart-upload --bucket "$bucket" --key "$key" \
                --content-type application/zip --query UploadId --output text 2>>"$LOG")" || return 1
  for part in "$tmp"/part.*; do
    n=$((n + 1)); ok=""
    for attempt in 1 2 3 4 5 6 7 8; do
      start="$(date +%s)"
      if etag="$(aws s3api upload-part --bucket "$bucket" --key "$key" --part-number "$n" \
                  --upload-id "$upload_id" --body "$part" --cli-read-timeout 0 --cli-connect-timeout 60 \
                  --query ETag --output text 2>>"$LOG")"; then
        say "  part $n of $total uploaded in $(( $(date +%s) - start ))s"
        ok="yes"; break
      fi
      say "  part $n of $total failed (attempt $attempt after $(( $(date +%s) - start ))s); retrying..."
      sleep 3
    done
    if [ -z "$ok" ]; then
      aws s3api abort-multipart-upload --bucket "$bucket" --key "$key" --upload-id "$upload_id" >>"$LOG" 2>&1
      rm -rf "$tmp"; return 1
    fi
    parts="$parts{\"ETag\":$etag,\"PartNumber\":$n},"
  done
  rm -rf "$tmp"
  aws s3api complete-multipart-upload --bucket "$bucket" --key "$key" --upload-id "$upload_id" \
    --multipart-upload "{\"Parts\":[${parts%,}]}" >>"$LOG" 2>&1
}

while IFS=$'\t' read -r file bucket key; do
  if aws s3api head-object --bucket "$bucket" --key "$key" >/dev/null 2>&1; then
    say "Already uploaded: $(basename "$file")"
  else
    say "Uploading $(basename "$file") ($(du -h "$file" | cut -f1 | tr -d ' ')) in 5 MB parts..."
    upload_in_parts "$file" "$bucket" "$key" < /dev/null || { say "Upload failed. See $LOG"; rm -f .asset_list; exit 1; }
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
