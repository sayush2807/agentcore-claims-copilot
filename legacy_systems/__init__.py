"""Mock systems of record for the fictional insurer.

These stand in for the customer's existing policy administration and claims
systems. The agent never reads the data files directly: it goes through these
service interfaces, which are later deployed as AWS Lambda functions and
exposed to the agent as tools through AgentCore Gateway.
"""
