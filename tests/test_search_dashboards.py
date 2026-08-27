import json

import tools
from tools import search_dashboards


def test_returns_empty_candidates_when_nothing_saved_yet(tmp_path, monkeypatch):
    # Point at a fresh, empty DB path (the table won't even exist yet) so
    # this doesn't depend on the real artifacts.db being empty, which stops
    # being true as soon as the app generates real dashboards. With zero
    # rows there's nothing to compare against, so search_dashboards should
    # short-circuit before ever calling the embedding API.
    monkeypatch.setattr(tools, "ARTIFACTS_DB_PATH", tmp_path / "empty.db")

    result = json.loads(search_dashboards.invoke({"question": "qualquer coisa"}))
    assert result == {"candidates": []}
