import json
import logging
import time

from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from config import model
from prompts import MATH_AGENT_SYSTEM_PROMPT, HTML_AGENT_SYSTEM_PROMPT, ROUTER_SYSTEM_PROMPT
from schemas import QueryResult
from tools import query_db, generate_dashboard, reuse_dashboard, search_dashboards
from utils import as_text, last_tool_message, save_run_trace

logger = logging.getLogger("treino_dieta.graph")

math_agent = create_react_agent(
    model=model,
    tools=[query_db],
    prompt=MATH_AGENT_SYSTEM_PROMPT,
)

html_agent = create_react_agent(
    model=model,
    tools=[generate_dashboard, reuse_dashboard],
    prompt=HTML_AGENT_SYSTEM_PROMPT,
)


@tool
def math_agent_tool(question: str) -> str:
    """Ask the math/SQL specialist agent a data question about training or
    diet. Returns the raw query_db JSON result ({'columns', 'rows'} or
    {'error'}), not a paraphrase.
    """
    start = time.perf_counter()
    logger.info("math_agent_tool start: %r", question[:80])
    result = math_agent.invoke({"messages": [{"role": "user", "content": question}]})
    elapsed = time.perf_counter() - start

    raw = last_tool_message(result["messages"], "query_db")
    if raw is None:
        logger.warning("math_agent_tool: math_agent never called query_db (%.2fs)", elapsed)
        return json.dumps({"error": "math_agent did not call query_db"})

    parsed = json.loads(raw)
    if "error" in parsed:
        logger.warning("math_agent_tool: query_db error (%.2fs): %s", elapsed, parsed["error"])
        return raw

    try:
        QueryResult(**parsed)
    except ValidationError as e:
        logger.warning("math_agent_tool: unexpected query_db shape (%.2fs): %s", elapsed, e)
        return json.dumps({"error": f"query_db returned unexpected shape: {e}"})

    logger.info("math_agent_tool done in %.2fs (%d rows)", elapsed, len(parsed.get("rows", [])))
    return raw


@tool
def html_agent_tool(question: str, data_json: str, candidates_json: str = "") -> str:
    """Ask the HTML specialist agent to build a dashboard for the given
    question using data_json (the JSON returned by math_agent_tool). Pass
    candidates_json (the raw output of search_dashboards) when a prior search
    found similar existing dashboards, so html_agent can reuse or edit one
    instead of generating from scratch.

    Returns the raw JSON result ({'url', 'id'} or {'error'}) of whichever
    tool html_agent called (generate_dashboard for new/edited dashboards,
    reuse_dashboard for an exact match), never a free-text paraphrase.
    """
    start = time.perf_counter()
    logger.info(
        "html_agent_tool start: %r (with %d candidate(s))",
        question[:80], candidates_json.count('"id":') if candidates_json else 0,
    )
    prompt = f"Pedido: {question}\n\nDados (JSON): {data_json}"
    if candidates_json:
        prompt += f"\n\nDashboards existentes possivelmente relacionados (JSON): {candidates_json}"
    result = html_agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    elapsed = time.perf_counter() - start

    for tool_name in ("generate_dashboard", "reuse_dashboard"):
        raw = last_tool_message(result["messages"], tool_name)
        if raw is not None:
            logger.info("html_agent_tool done in %.2fs via %s", elapsed, tool_name)
            return raw

    logger.warning("html_agent_tool: no dashboard tool called (%.2fs)", elapsed)
    return json.dumps({"error": "html_agent did not call generate_dashboard or reuse_dashboard"})


router_agent = create_react_agent(
    model=model,
    tools=[math_agent_tool, html_agent_tool, search_dashboards],
    prompt=ROUTER_SYSTEM_PROMPT,
)


def ask(question: str) -> dict:
    """Runs the router on a single, self-contained question.

    Returns {'answer': str, 'artifact_url': str | None}. artifact_url comes
    straight from html_agent_tool's raw JSON result (if it called it), never
    from the router's own text, so it can't get mistyped in prose.
    """
    start = time.perf_counter()
    logger.info("ask start: %r", question)

    result = router_agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"recursion_limit": 15},
    )
    elapsed = time.perf_counter() - start

    artifact_url = None
    raw = last_tool_message(result["messages"], "html_agent_tool")
    if raw is not None:
        parsed = json.loads(raw)
        artifact_url = parsed.get("url")

    logger.info("ask done in %.2fs (artifact_url=%s)", elapsed, artifact_url)

    try:
        trace_dir = save_run_trace(result["messages"], question, elapsed)
        logger.info("trace saved: %s", trace_dir)
    except Exception:
        logger.exception("failed to save run trace")

    return {
        "answer": as_text(result["messages"][-1].content),
        "artifact_url": artifact_url,
    }