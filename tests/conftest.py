import os


# Unit tests never download models, call LLM providers or access the real semantic index.
os.environ["AI_ENABLED"] = "false"
os.environ["AI_ENHANCE_ASSET_ANALYSIS"] = "false"
os.environ["NEWS_EMBEDDINGS_ENABLED"] = "false"
os.environ["FINANCIAL_NLP_ENABLED"] = "false"
