from app.services.llm_service import LLMService


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
