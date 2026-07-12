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
