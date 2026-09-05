from rag.config import Settings

def test_default_embedding_is_text_embedding_3_small():
    s = Settings(openai_api_key="sk-test")
    assert s.embedding_model == "text-embedding-3-small"
    assert s.embedding_dim == 1536