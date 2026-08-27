import json

from tools import query_db


def test_only_select_is_allowed():
    result = json.loads(query_db.invoke({"sql": "DROP TABLE treino_sessao"}))
    assert "error" in result
    assert "SELECT" in result["error"]


def test_insert_is_rejected():
    result = json.loads(query_db.invoke({"sql": "INSERT INTO treino_sessao VALUES (1)"}))
    assert "error" in result


def test_with_cte_is_allowed():
    # Regression test: query_db used to reject any query not starting with
    # SELECT, including read-only CTEs (WITH ... SELECT), which blocked
    # legitimate comparisons like "first vs last session per exercise".
    result = json.loads(query_db.invoke({
        "sql": "WITH totals AS (SELECT treino, COUNT(*) AS n FROM treino_sessao "
               "WHERE data >= '2026-06-01' AND data < '2026-07-01' GROUP BY treino) "
               "SELECT SUM(n) AS total FROM totals"
    }))
    assert "error" not in result
    assert result["rows"][0][0] == 12


def test_multiple_statements_rejected():
    result = json.loads(query_db.invoke({"sql": "SELECT 1; SELECT 2"}))
    assert "error" in result
    assert "statements" in result["error"].lower() or "multiplos" in result["error"].lower()


def test_valid_query_returns_columns_and_rows():
    result = json.loads(query_db.invoke({"sql": "SELECT 1 AS x, 2 AS y"}))
    assert result == {"columns": ["x", "y"], "rows": [[1, 2]]}


def test_limit_is_appended_when_missing():
    result = json.loads(query_db.invoke({"sql": "SELECT data FROM treino_sessao"}))
    assert "error" not in result
    assert len(result["rows"]) <= 500


def test_explicit_limit_is_respected():
    result = json.loads(query_db.invoke({"sql": "SELECT data FROM treino_sessao LIMIT 3"}))
    assert "error" not in result
    assert len(result["rows"]) <= 3


def test_sql_error_returns_error_json_instead_of_raising():
    result = json.loads(query_db.invoke({"sql": "SELECT * FROM tabela_que_nao_existe"}))
    assert "error" in result
    assert "SQLite" in result["error"]


def test_june_2026_session_count_matches_known_value():
    # June 2026 is a closed historical month (unlike the current month, which
    # keeps gaining sessions), so this count should stay stable over time.
    result = json.loads(query_db.invoke({
        "sql": "SELECT COUNT(*) AS n FROM treino_sessao "
               "WHERE data >= '2026-06-01' AND data < '2026-07-01'"
    }))
    assert result["rows"][0][0] == 12
