import json
import logging
import re
import sqlite3
import time

from harpy import text
from harpy.schema import Criteria, EvalConfig
from pydantic import ValidationError

from langchain.tools import tool

from template import montar_shell_prompt
from utils import (
    ARTIFACTS_DB_PATH,
    ARTIFACTS_DIR,
    DB_PATH,
    cosine_similarity,
    render_artifact,
    save_dashboard_metadata,
    static_validation,
)
from schemas import HarpyResult
from config import embedding_model

logger = logging.getLogger("treino_dieta.tools")


@tool
def generate_dashboard(
    pergunta: str,
    dados_json: str,
    componentes: list[str] | None = None,
    existing_html: str | None = None,
) -> str:
    """Gera HTML do dashboard via harpy + gate de avaliação; valida e salva.

    Se existing_html for passado (HTML de um dashboard salvo anteriormente,
    obtido via search_dashboards), o harpy edita esse HTML em vez de gerar
    do zero, aplicando só a mudança pedida em `pergunta`.

    Retorna JSON {'url', 'id'} ou {'error'}.
    """
    start = time.perf_counter()
    mode = "edit" if existing_html else "new"
    logger.info("generate_dashboard start (mode=%s) pergunta=%r", mode, pergunta[:80])

    try:
        shell = montar_shell_prompt(componentes)
    except ValueError as e:
        logger.warning("generate_dashboard invalid componentes: %s", e)
        return json.dumps({"error": str(e)})

    if existing_html:
        user_prompt = (
            "HTML existente:\n{existing}\n\n"
            "Pedido de modificação: {pergunta}\n\n"
            "Dados atualizados (resultado de query SQLite):\n{dados}\n\n"
            "Modifique o HTML existente para atender o pedido, mantendo o "
            "design system e a estrutura, alterando só o necessário."
        )
        context = dict(pergunta=pergunta, dados=dados_json, existing=existing_html)
    else:
        user_prompt = "Pedido: {pergunta}\n\nDados (resultado de query SQLite):\n{dados}"
        context = dict(pergunta=pergunta, dados=dados_json)

    resultado = (
        text.openai(model="gpt-5.6-luna")
        .prompts(
            system=shell,
            user=user_prompt,
        )
        .context(**context)
        .evaluate(
            config=EvalConfig(criteria={
                "html_valido": Criteria(
                    description="HTML bem formado, tags balanceadas, começa com <!DOCTYPE html>",
                    type="bool", threshold=1.0,
                ),
                "dados_corretos": Criteria(
                    description="usa EXATAMENTE os números dos dados fornecidos",
                    type="bool", threshold=1.0,
                ),
                "design_system": Criteria(
                    description="usa somente as classes CSS fornecidas, fundo #0f1117, cards #1a1d27",
                    type="bool", threshold=1.0,
                ),
                "grafico_legivel": Criteria(
                    description="título claro, eixos rotulados, sem poluição visual",
                    type="bool", threshold=1.0,
                ),
            }),
            judge_model="gemini/gemini-3.5-flash-lite",
        )
        .fallback()
        .run()
    )
    try:
        html_out = HarpyResult(html=resultado).html.strip()
    except ValidationError as e:
        logger.warning("generate_dashboard bad harpy output: %s", e)
        return json.dumps({"error": f"harpy retornou tipo inesperado: {e}"})

    problemas = static_validation(html_out)
    if problemas:
        logger.warning("generate_dashboard failed static_validation: %s", problemas)
        return json.dumps({"error": f"HTML reprovado na validação estática: {problemas}"})

    artifact = render_artifact(html_out, pergunta[:60])
    save_dashboard_metadata(
        id=artifact["id"],
        question=pergunta,
        componentes=componentes,
        data_json=dados_json,
        url=artifact["url"],
    )
    elapsed = time.perf_counter() - start
    logger.info("generate_dashboard done in %.2fs -> %s", elapsed, artifact["url"])
    return json.dumps(artifact)


@tool
def reuse_dashboard(id: str) -> str:
    """Reuses a previously generated dashboard by id (the id of a
    search_dashboards candidate) instead of generating a new one. Returns
    the exact JSON {'url', 'id'} for that dashboard, or {'error'} if the id
    doesn't exist. Use this instead of typing the url out yourself.
    """
    start = time.perf_counter()
    con = sqlite3.connect(ARTIFACTS_DB_PATH)
    row = con.execute("SELECT id, url FROM dashboard_artifact WHERE id = ?", (id,)).fetchone()
    con.close()
    elapsed = time.perf_counter() - start
    if row is None:
        logger.warning("reuse_dashboard: no dashboard with id=%r (%.3fs)", id, elapsed)
        return json.dumps({"error": f"no dashboard found with id '{id}'"})
    logger.info("reuse_dashboard: reusing %s in %.3fs", row[0], elapsed)
    return json.dumps({"id": row[0], "url": row[1]})


@tool
def search_dashboards(question: str, top_k: int = 3) -> str:
    """Searches previously generated dashboards for ones whose original
    question is semantically close to the given one. Returns JSON:
    {"candidates": [{id, question, componentes, data_json, html, url,
    similarity}, ...]}, most similar first, or an empty list if none saved
    yet. html is the full saved HTML, needed if you want to edit it via
    generate_dashboard's existing_html.
    """
    start = time.perf_counter()
    try:
        con = sqlite3.connect(ARTIFACTS_DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, question, componentes, data_json, url, embedding FROM dashboard_artifact"
        ).fetchall()
        con.close()
    except sqlite3.OperationalError:
        logger.info("search_dashboards: no dashboard_artifact table yet")
        return json.dumps({"candidates": []})

    if not rows:
        logger.info("search_dashboards: table empty, nothing to compare")
        return json.dumps({"candidates": []})

    query_embedding = embedding_model.embed_query(question)

    candidates = []
    for row in rows:
        score = cosine_similarity(query_embedding, json.loads(row["embedding"]))
        html_path = ARTIFACTS_DIR / f"{row['id']}.html"
        candidates.append({
            "id": row["id"],
            "question": row["question"],
            "componentes": json.loads(row["componentes"]) if row["componentes"] else None,
            "data_json": row["data_json"],
            "html": html_path.read_text(encoding="utf-8") if html_path.exists() else None,
            "url": row["url"],
            "similarity": round(score, 4),
        })

    candidates.sort(key=lambda c: c["similarity"], reverse=True)
    top = candidates[:top_k]
    elapsed = time.perf_counter() - start
    best = f"{top[0]['similarity']:.4f}" if top else "n/a"
    logger.info(
        "search_dashboards: %d candidates, best similarity=%s (%.2fs)",
        len(rows), best, elapsed,
    )
    return json.dumps({"candidates": top})

@tool
def query_db(sql: str) -> str:
    """Executa SELECT (ou WITH ... SELECT, CTE) no db e retorna JSON:
    {'columns': [...], 'rows': [[...]]}
    Regras:
    - só aceita a primeira palavra = SELECT ou WITH (rejeita INSERT/UPDATE/DROP/PRAGMA/ATTACH)
    - multiplos statements -> rejeitar (checar ';' no meio)
    - LIMIT automático: se não houver LIMIT no SQL, appenda LIMIT 500
    - erro do sqlite -> retorna JSON {'error': str} em vez de levantar (o agente precisa ler o erro e se autocorrigir no loop)
    """
    start = time.perf_counter()
    sql = sql.strip().rstrip(";")

    first = sql.split(maxsplit=1)[0].upper() if sql else ""
    if first not in ("SELECT", "WITH"):
        logger.warning("query_db rejected (not SELECT/WITH): %s", sql[:100])
        return json.dumps({"error": f"Somente SELECT ou WITH (CTE) são permitidos (recebendo: '{first}')"})

    if ";" in sql:
        logger.warning("query_db rejected (multiple statements): %s", sql[:100])
        return json.dumps({"error": "Múltiplos statements não são permitidos"})

    if not re.search(r"\bLIMIT\s+\d+\b", sql, re.IGNORECASE):
        sql += " LIMIT 500"

    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        con.close()
        rows = [[v.decode("utf-8", "replace") if isinstance(v, bytes) else v for v in row] for row in rows]
        elapsed = time.perf_counter() - start
        logger.info("query_db done in %.3fs (%d rows): %s", elapsed, len(rows), sql[:150])
        return json.dumps({"columns": columns, "rows": rows})
    except sqlite3.Error as e:
        logger.warning("query_db SQLite error: %s | sql=%s", e, sql[:150])
        return json.dumps({"error": f"SQLite: {e}"})