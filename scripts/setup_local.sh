#!/usr/bin/env bash
# One-time local setup: checks tools, signs the AWS CLI in with your console
# session (no long-lived access keys), and confirms which account is in use.
set -euo pipefail

REGION="us-east-2"
need() { command -v "$1" >/dev/null 2>&1; }

echo "== Checking tools =="
if ! need aws; then
  if need brew; then
    echo "Installing AWS CLI with Homebrew..."
    brew install awscli
  else
    echo "AWS CLI not found. Install it from:"
    echo "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    echo "then run this script again."
    exit 1
  fi
fi
aws --version

if ! need node; then echo "Node.js 20+ is required: https://nodejs.org"; exit 1; fi
echo "node $(node --version)"

if ! need uv; then
  if need brew; then brew install uv; else echo "uv is required: https://docs.astral.sh/uv/"; exit 1; fi
fi
uv --version

if ! need agentcore; then
  echo "Installing the AgentCore CLI..."
  npm install -g @aws/agentcore
fi
echo "agentcore $(agentcore --version 2>/dev/null | tail -1)"

echo
echo "== Signing in to AWS (a browser window will open) =="
aws login --region "$REGION"

echo
echo "== Signed in as =="
aws sts get-caller-identity --region "$REGION"

echo
echo "Setup complete. Region: $REGION"
