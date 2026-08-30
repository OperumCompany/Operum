import os


# Unit tests never download models or access the real semantic index.
os.environ["NEWS_EMBEDDINGS_ENABLED"] = "false"
