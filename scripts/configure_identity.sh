#!/usr/bin/env bash
# Deploys the identity stack (Cognito) and writes its discovery URL and client ID
# into the working copy of agentcore/agentcore.json, replacing the placeholders.
# The substituted file is for deployment only: do not commit it.
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-us-east-2}"
STACK="ClaimsCopilot-Identity"

aws cloudformation deploy --stack-name "$STACK" --template-file infra/identity.yaml \
  --region "$REGION" --no-fail-on-empty-changeset >/dev/null
out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
          --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
DISCOVERY_URL="$(out DiscoveryUrl)" CLIENT_ID="$(out ClientId)" python3 - <<'PY'
import json, os
path = "agentcore/agentcore.json"
text = open(path).read()
config = json.loads(text)
for gateway in config["agentCoreGateways"]:
    jwt = gateway.get("authorizerConfiguration", {}).get("customJwtAuthorizer")
    if jwt:
        jwt["discoveryUrl"] = os.environ["DISCOVERY_URL"]
        jwt["allowedAudience"] = [os.environ["CLIENT_ID"]]
open(path, "w").write(json.dumps(config, indent=2) + "\n")
PY
echo "identity configured"
