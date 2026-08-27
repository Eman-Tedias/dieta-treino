"""End-to-end tests for the full router -> math_agent -> html_agent pipeline.

These make real, PAID API calls (Gemini for agent reasoning, OpenAI/gpt-5.6-luna
via harpy for HTML generation). They do not run by default -- set
RUN_E2E_TESTS=1 to opt in:

    RUN_E2E_TESTS=1 pytest tests/test_e2e.py -v
"""
import json
import os

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("RUN_E2E_TESTS") != "1",
        reason="costs real money (OpenAI/Gemini) -- set RUN_E2E_TESTS=1 to run",
    ),
]


def test_text_only_question_does_not_generate_a_dashboard():
    from graph import ask

    resposta = ask("Quantos treinos eu fiz em junho de 2026?")
    assert isinstance(resposta, str)
    assert "12" in resposta


def test_dashboard_question_produces_a_saved_artifact():
    from pathlib import Path

    from graph import html_agent_tool, math_agent_tool
    from utils import ARTIFACTS_DIR

    dados = math_agent_tool.invoke({
        "question": "Volume de treino por grupo muscular em junho de 2026",
    })
    parsed = json.loads(dados)
    assert "error" not in parsed
    assert parsed["columns"]
    assert parsed["rows"]

    resultado = html_agent_tool.invoke({
        "question": "Grafico de volume de treino por grupo muscular em junho de 2026",
        "data_json": dados,
    })
    parsed_result = json.loads(resultado)
    assert "error" not in parsed_result, parsed_result.get("error")
    assert "url" in parsed_result

    saved_file = ARTIFACTS_DIR / f"{parsed_result['id']}.html"
    assert saved_file.exists()
    assert saved_file.read_text(encoding="utf-8").lower().startswith("<!doctype html")
