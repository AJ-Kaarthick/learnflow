import pytest

from app.services.ai.base_provider import AIProviderError
from app.services.ai.structured_output import parse_json_array


def test_parses_plain_json_array():
    result = parse_json_array('[{"a": 1}]', required_keys={"a"})
    assert result == [{"a": 1}]


def test_strips_markdown_code_fences():
    result = parse_json_array('```json\n[{"a": 1}]\n```', required_keys={"a"})
    assert result == [{"a": 1}]


def test_raises_on_invalid_json():
    with pytest.raises(AIProviderError):
        parse_json_array("not json at all", required_keys={"a"})


def test_raises_when_not_a_list():
    with pytest.raises(AIProviderError):
        parse_json_array('{"a": 1}', required_keys={"a"})


def test_raises_when_required_key_missing():
    with pytest.raises(AIProviderError):
        parse_json_array('[{"b": 1}]', required_keys={"a"})


def test_extract_json_returns_object():
    from app.services.ai.structured_output import extract_json

    assert extract_json('{"title": "Root"}') == {"title": "Root"}


def test_extract_json_strips_code_fences_for_object():
    from app.services.ai.structured_output import extract_json

    assert extract_json('```json\n{"title": "Root"}\n```') == {"title": "Root"}


def test_extract_json_raises_on_invalid_json():
    from app.services.ai.structured_output import extract_json

    with pytest.raises(AIProviderError):
        extract_json("not json at all")


def test_extract_json_handles_preamble_and_embedded_fence():
    from app.services.ai.structured_output import extract_json

    raw = "Here is the result:\n```json\n{\"title\": \"Root\", \"nodes\": []}\n```\nHope that helps!"
    assert extract_json(raw) == {"title": "Root", "nodes": []}


def test_extract_json_handles_unescaped_control_characters():
    from app.services.ai.structured_output import extract_json

    # String with literal unescaped newline inside JSON string literal
    raw = '{\n  "explanation": "Line 1\nLine 2"\n}'
    assert extract_json(raw) == {"explanation": "Line 1\nLine 2"}


def test_extract_json_handles_conversational_text_without_fences():
    from app.services.ai.structured_output import extract_json

    raw = 'Sure! Here is the JSON: {"nodes": [1, 2, 3]} Best regards.'
    assert extract_json(raw) == {"nodes": [1, 2, 3]}
