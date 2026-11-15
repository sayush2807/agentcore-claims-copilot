// A signed-in supervisor may approve a payout at or below 250,000, the largest
// coverage limit the insurer writes. Nothing above that is permitted to anyone.
permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"claims-actions___approve_payout",
  resource == AgentCore::Gateway::"{{GATEWAY_ARN:AdjusterActions}}"
)
when {
  principal.hasTag("custom:role") &&
  principal.getTag("custom:role") == "supervisor" &&
  context.input has amount &&
  context.input.amount <= 250000
};
