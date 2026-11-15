// A signed-in adjuster may approve a payout at or below 10,000.
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"claims-actions___approve_payout",
  resource == AgentCore::Gateway::"{{GATEWAY_ARN:AdjusterActions}}"
)
when {
  principal.hasTag("custom:role") &&
  principal.getTag("custom:role") == "adjuster" &&
  context.input has amount &&
  context.input.amount <= 10000
};
