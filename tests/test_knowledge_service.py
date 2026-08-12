from app.services.knowledge_service import KnowledgeService
from app.schemas.chat import ChatInputMessage
from app.services.chat_service import ChatService


class DisabledRepository:
    enabled = False


class DisabledEmbedder:
    enabled = False


class SemanticRepository:
    enabled = True

    def semantic_search(self, vector, limit):
        return [{"id": "noticias-preco", "similarity": 0.75}]


class SemanticEmbedder:
    enabled = True

    def encode_query(self, query):
        return [0.0] * 384


def service() -> KnowledgeService:
    return KnowledgeService(DisabledRepository(), DisabledEmbedder())


def test_knowledge_base_has_sixty_valid_unique_faqs():
    documents = service().load_documents()
    assert len(documents) == 60
    assert len({item["id"] for item in documents}) == 60
    assert all(item["category"] for item in documents)
    assert all(item["short_answer"] for item in documents)
    assert all(item["sources"] and item["sources"][0]["url"] for item in documents)


def test_knowledge_exact_question_returns_direct_match():
    results = service().search("O que é renda variável?")
    assert results[0]["id"] == "renda-variavel"
    assert results[0]["direct_match"] is True


def test_direct_answer_does_not_expose_editorial_headings():
    knowledge = service()
    document = knowledge.search("O que é renda variável?")[0]
    answer = knowledge.render_direct_answer(document)
    assert "Resposta curta" not in answer
    assert "Explicação" not in answer
    assert "Exemplo" not in answer
    assert "Pontos de atenção" not in answer


def test_knowledge_finds_synonym_without_title_words():
    results = service().search("Por que meu título caiu mesmo sendo renda fixa?")
    assert any(item["id"] == "marcacao-mercado" for item in results)


def test_knowledge_index_dry_run_is_safe_when_embeddings_disabled():
    result = service().index(dry_run=True)
    assert result["status"] == "disabled"
    assert result["total"] == 60


def test_knowledge_discards_unsubstantiated_semantic_result_below_strong_threshold():
    knowledge = KnowledgeService(SemanticRepository(), SemanticEmbedder())
    assert knowledge.search("Me cite dois ativos seguros para investir") == []


def test_safe_asset_request_uses_educational_orientation_fallback():
    chat = ChatService(service())
    chat.ai_enabled = False
    response = chat.answer([
        ChatInputMessage(role="user", content="Me cite dois ativos seguros para investir")
    ])
    assert response["mode"] == "knowledge_direct"
    assert response["retrieval"]["intent"] == "orientacao"
    assert response["retrieval"]["news_count"] == 0
    assert all(
        source["id"].split(":", 1)[0] in {"risco-retorno", "tesouro-selic", "cdb", "fgc"}
        for source in response["sources"]
    )
    assert "Tesouro Selic" in response["message"]
    assert "CDB" in response["message"]
    assert "não existe investimento totalmente seguro" in response["message"].lower()
    assert "Resposta curta" not in response["message"]
    assert "Base de conhecimento" not in response["message"]
    assert "Conceitos relacionados" not in response["message"]
