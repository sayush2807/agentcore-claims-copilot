#!/usr/bin/env bash
# One-time local setup: checks tools, signs the AWS CLI in with your console
# session (no long-lived access keys), and confirms which account is in use.
set -euo pipefail

REGION="us-east-2"
need() { command -v "$1" >/dev/null 2>&1; }

echo "== Checking tools =="
# Use the official AWS CLI installer, which bundles its own Python. The Homebrew
# build can fail on some macOS versions with a pyexpat "Symbol not found" error.
install_official_awscli() {
  echo "Installing the official AWS CLI (you will be asked for your Mac password)..."
  tmp="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "$tmp/AWSCLIV2.pkg"
  sudo installer -pkg "$tmp/AWSCLIV2.pkg" -target /
  rm -rf "$tmp"
  hash -r
}
if need brew && brew list awscli >/dev/null 2>&1; then
  echo "Removing the Homebrew AWS CLI in favour of the official installer..."
  brew uninstall awscli
  hash -r
fi
if ! need aws; then install_official_awscli; fi
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
