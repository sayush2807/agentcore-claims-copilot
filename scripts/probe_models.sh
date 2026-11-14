#!/usr/bin/env bash
# Finds which Bedrock models this account can actually call in us-east-2 by
# sending each one a tiny request. Results go to model_probe.log.
set -uo pipefail
cd "$(dirname "$0")/.."
REGION="us-east-2"
LOG="model_probe.log"
: > "$LOG"

ids="$(aws bedrock list-inference-profiles --region "$REGION" \
        --query 'inferenceProfileSummaries[].inferenceProfileId' --output text 2>>"$LOG" | tr '\t' '\n')"
ids="$ids
$(aws bedrock list-foundation-models --region "$REGION" --by-output-modality TEXT \
        --query 'modelSummaries[?contains(inferenceTypesSupported, `ON_DEMAND`)].modelId' --output text 2>>"$LOG" | tr '\t' '\n')"

echo "Probing $(echo "$ids" | grep -c .) model IDs (a minute or two)..."
echo "$ids" | grep . | sort -u | while read -r id; do
  out="$(aws bedrock-runtime converse --region "$REGION" --model-id "$id" \
          --messages '[{"role":"user","content":[{"text":"Say OK"}]}]' \
          --inference-config '{"maxTokens":5}' --query 'stopReason' --output text 2>&1 | tail -1)"
  case "$out" in
    end_turn|max_tokens|stop_sequence) echo "OK    $id" | tee -a "$LOG" ;;
    *) echo "FAIL  $id  ${out:0:140}" >> "$LOG" ;;
  esac
done
echo "Done. Working models:"
grep -c '^OK' "$LOG" || true
