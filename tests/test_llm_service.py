from app.services.llm_service import LLMService


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": '{"answer":"Não existe investimento sem risco. Compare prazo e liquidez."}'}}


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, *args, **kwargs):
        schema = kwargs["json"]["format"]
        assert schema["required"] == ["answer"]
        return FakeResponse()


def test_extract_json_from_plain_text():
    service = LLMService()
    parsed = service._extract_json('{"headline":"ok","strengths":["a"]}')
    assert parsed["headline"] == "ok"
    assert parsed["strengths"] == ["a"]


def test_extract_json_from_fenced_block():
    service = LLMService()
    parsed = service._extract_json(
        """```json
{"headline":"ok","strengths":["a"]}
```"""
    )
    assert parsed["headline"] == "ok"


def test_extract_json_raises_when_missing():
    service = LLMService()
    try:
        service._extract_json("sem json aqui")
        assert False, "Era esperado erro de JSON ausente"
    except ValueError:
        assert True


def test_normalize_reasoning_content_into_final_answer():
    service = LLMService()
    normalized = service._normalize_possible_reasoning(
        'Okay, the user wants me to answer. It should be something like: "Liquidez e a capacidade de vender um ativo com facilidade sem afetar muito o preco."'
    )
    assert normalized == "Liquidez e a capacidade de vender um ativo com facilidade sem afetar muito o preco."


def test_chat_answer_returns_natural_markdown_without_fixed_sections(monkeypatch):
    service = LLMService()
    service.enabled = True
    service.provider = "ollama"
    monkeypatch.setattr("app.services.llm_service.httpx.Client", FakeClient)
    answer = service.chat_answer("Responda em PT-BR", "Cite exemplos")
    assert answer == "Não existe investimento sem risco. Compare prazo e liquidez."
    assert "## Resumo" not in answer
    assert "## Análise" not in answer
