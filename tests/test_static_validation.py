from utils import static_validation

VALID_HTML = (
    "<!DOCTYPE html><html><head><style>body{background:#0f1117}</style></head>"
    "<body><header class='page-header'><h1>Teste</h1></header>"
    "<div class='card'>conteudo bem grande para passar do limite minimo de "
    "duzentos caracteres exigido pela validacao estatica do harpy</div>"
    "</body></html>"
)


def test_valid_html_passes():
    assert static_validation(VALID_HTML) == []


def test_doctype_check_is_case_insensitive_and_actually_matches():
    # Regression test: static_validation used to compare "<!DOCTYPE html" (mixed
    # case) against an already-lowercased slice of the html, so the check could
    # never pass, even for perfectly valid HTML starting with <!DOCTYPE html>.
    assert "does not start with <!DOCTYPE html>" not in static_validation(VALID_HTML)

    lowercase_variant = VALID_HTML.replace("<!DOCTYPE html>", "<!doctype html>")
    assert "does not start with <!DOCTYPE html>" not in static_validation(lowercase_variant)


def test_too_short_html_fails():
    problems = static_validation("<!DOCTYPE html><html></html>")
    assert "HTML too short" in problems


def test_missing_doctype_fails():
    html = "<html><body>" + "x" * 200 + "</body></html>"
    problems = static_validation(html)
    assert "does not start with <!DOCTYPE html>" in problems


def test_unclosed_tag_is_detected():
    # div/body/html are never closed at all (as opposed to closed in the
    # wrong order, which _TagChecker reports separately as "out-of-order").
    html = "<!DOCTYPE html><html><body><div>" + "x" * 200
    problems = static_validation(html)
    assert any("unclosed tags" in p for p in problems)


def test_out_of_order_closing_tag_is_detected():
    html = "<!DOCTYPE html><html><body><div><span>" + "x" * 200 + "</div></span></body></html>"
    problems = static_validation(html)
    assert any("out-of-order" in p for p in problems)


def test_allowed_cdn_script_passes():
    html = VALID_HTML.replace(
        "</body>",
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script></body>',
    )
    problems = static_validation(html)
    assert not any("external script" in p for p in problems)


def test_disallowed_external_script_fails():
    html = VALID_HTML.replace(
        "</body>",
        '<script src="https://evil.example.com/script.js"></script></body>',
    )
    problems = static_validation(html)
    assert any("external script not allowed" in p for p in problems)
