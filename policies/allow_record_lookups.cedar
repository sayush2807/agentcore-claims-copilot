// Read-only lookups are open to any caller the agent-facing Gateway has authenticated.
permit(
  principal,
  action in [
    AgentCore::Action::"legacy-api___get_claim",
    AgentCore::Action::"legacy-api___get_policy",
    AgentCore::Action::"legacy-api___list_claims_for_policy"
  ],
  resource == AgentCore::Gateway::"{{GATEWAY_ARN:LegacySystems}}"
);
