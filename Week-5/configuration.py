from langchain_aws import ChatBedrockConverse


class Config:
    """System Settings"""
    MAX_RESULTS = 5
    MAX_FILE_SIZE = 10
    SUPPORTED_FILE_TYPES = ['.txt', '.md', '.pdf']

def get_chat_model(temp: float = 0.2, name: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0") :
    """Returns a aws bedrock model instance"""
    model = ChatBedrockConverse(model_id=name, temperature=temp)
    return model