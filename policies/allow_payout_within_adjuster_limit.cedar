// A payout approval is permitted only at or below the adjuster limit.
// Anything larger matches no permit and is denied by default, whatever the
// agent or the calling application was told to do.
permit(
  principal,
  action == AgentCore::Action::"legacy-api___approve_payout",
  resource == AgentCore::Gateway::"{{GATEWAY_ARN}}"
)
when {
  context.input has amount &&
  context.input.amount <= 10000
};
