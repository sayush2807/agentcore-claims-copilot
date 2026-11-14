#!/usr/bin/env bash
# Deletes every AWS resource this project deployed, so nothing keeps billing.
# The CDK bootstrap stack (CDKToolkit) is left in place; it costs nothing idle.
set -euo pipefail
REGION="us-east-2"
STACK="AgentCore-ClaimsCopilot-default"

if ! aws sts get-caller-identity >/dev/null 2>&1; then aws login --region "$REGION"; fi
read -r -p "Delete stack $STACK in $REGION? This removes the agent, gateway, memory and Lambda. [y/N] " answer
[ "$answer" = "y" ] || { echo "Cancelled."; exit 0; }
aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION"
echo "Deleting... (a few minutes)"
aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$REGION"
echo "Deleted."
