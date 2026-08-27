import pytest

from utils import as_text, cosine_similarity


def test_plain_string_passthrough():
    assert as_text("resposta simples") == "resposta simples"


def test_extracts_text_from_gemini_style_block_list():
    content = [{"type": "text", "text": "resposta do gemini", "extras": {"signature": "abc"}}]
    assert as_text(content) == "resposta do gemini"


def test_concatenates_multiple_text_blocks():
    content = [
        {"type": "text", "text": "parte 1. "},
        {"type": "text", "text": "parte 2."},
    ]
    assert as_text(content) == "parte 1. parte 2."


def test_ignores_non_text_blocks():
    content = [
        {"type": "thinking", "thinking": "raciocinio interno"},
        {"type": "text", "text": "resposta final"},
    ]
    assert as_text(content) == "resposta final"


def test_empty_list_returns_empty_string():
    assert as_text([]) == ""


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert cosine_similarity([1.0, 2.0], [-1.0, -2.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_returns_zero_instead_of_dividing_by_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
