import os

from strands.models.bedrock import BedrockModel

# Single place to change the model. Override with BEDROCK_MODEL_ID without
# touching code, for example to compare models during evaluation.
DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    return BedrockModel(model_id=os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID))
