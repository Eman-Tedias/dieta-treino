import pytest

from template import COMPONENTES, montar_shell_prompt


def test_default_prompt_includes_all_components():
    prompt = montar_shell_prompt()
    for nome in COMPONENTES:
        assert nome in prompt


def test_subset_prompt_includes_only_requested_components():
    prompt = montar_shell_prompt(["page_header", "metric_card"])
    assert "page_header" in prompt
    assert "metric_card" in prompt
    assert "line_chart" not in prompt
    assert "data_table" not in prompt


def test_unknown_component_raises():
    with pytest.raises(ValueError):
        montar_shell_prompt(["gauge_3d"])


def test_prompt_always_includes_css_tokens():
    prompt = montar_shell_prompt(["page_header"])
    assert "--bg: #0f1117" in prompt
