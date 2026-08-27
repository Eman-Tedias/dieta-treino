import pytest
from pydantic import ValidationError

from schemas import HarpyResult, QueryResult


def test_harpy_result_accepts_string():
    assert HarpyResult(html="<!DOCTYPE html></html>").html == "<!DOCTYPE html></html>"


@pytest.mark.parametrize("bad_value", [123, None, {"a": 1}, ["x"], 3.14])
def test_harpy_result_rejects_non_string(bad_value):
    with pytest.raises(ValidationError):
        HarpyResult(html=bad_value)


def test_query_result_accepts_valid_shape():
    q = QueryResult(columns=["a", "b"], rows=[[1, 2], [3, 4]])
    assert q.columns == ["a", "b"]
    assert q.rows == [[1, 2], [3, 4]]


def test_query_result_accepts_empty_rows():
    assert QueryResult(columns=["a"], rows=[]).rows == []


@pytest.mark.parametrize("bad_payload", [
    {"error": "SQLite: no such table"},
    {"columns": ["a"]},
    {"rows": [[1]]},
    {"columns": "a", "rows": [[1]]},
])
def test_query_result_rejects_malformed_payload(bad_payload):
    with pytest.raises(ValidationError):
        QueryResult(**bad_payload)
