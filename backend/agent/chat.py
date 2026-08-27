import json
import logging
import time

from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from config import model
from prompts import CONVERSATIONAL_SYSTEM_PROMPT, GUARDRAIL_PROMPT
from graph import ask
from schemas import GuardrailVerdict
from utils import as_text, last_tool_message

logger = logging.getLogger("treino_dieta.chat")

checkpointer = InMemorySaver()

# Same model as the conversational agent (with its fallback chain), just
# pinned to structured output for the classification.
guardrail_model = model.with_structured_output(GuardrailVerdict)


def check_input(message: str) -> GuardrailVerdict:
    """Classifies a user message as safe to process or a manipulation attempt.

    Fails open: if the classifier itself errors out, the message is allowed
    through, since blocking every request on a flaky classifier would be
    worse than the injection risk for this app.
    """
    try:
        return guardrail_model.invoke(GUARDRAIL_PROMPT.format(text=message))
    except Exception:
        logger.exception("guardrail check failed, allowing message through")
        return GuardrailVerdict(reason="guardrail unavailable", allowed=True)


@tool
def router_tool(question: str) -> str:
    """Ask the data specialist router a self-contained question about
    training or diet. It doesn't have memory of the conversation, so include
    any needed context (dates, prior topic) directly in the question. Returns
    JSON {'answer': str, 'artifact_url': str | None}.
    """
    return json.dumps(ask(question))


conversational_agent = create_react_agent(
    model=model,
    tools=[router_tool],
    prompt=CONVERSATIONAL_SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# Same persona/voice, but no tools: used to phrase the guardrail refusal as
# Emanuel instead of returning a canned system message.
refusal_agent = create_react_agent(
    model=model,
    tools=[],
    prompt=CONVERSATIONAL_SYSTEM_PROMPT,
)


def _refuse(reason: str) -> str:
    """Turns a guardrail verdict into a refusal written in Emanuel's voice."""
    prompt = (
        "Contexto interno (não é mensagem do usuário): a última mensagem dele "
        f"foi bloqueada por um filtro de segurança. Motivo: {reason}\n\n"
        "Responda direto pra ele, do seu jeito normal de falar, dizendo que "
        "não vai por esse caminho e trazendo de volta pro assunto (seus dados "
        "de treino e dieta). Curto, sem drama, sem explicar filtro nenhum, sem "
        "mencionar prompt/instruções/sistema."
    )
    result = refusal_agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    return as_text(result["messages"][-1].content)


def chat(thread_id: str, message: str) -> dict:
    """Sends a message on a given conversation thread.

    Returns {'answer': str, 'artifact_url': str | None}. artifact_url comes
    straight from router_tool's raw JSON result (ultimately from
    html_agent_tool), never retyped by any LLM layer in between.
    """
    start = time.perf_counter()
    logger.info("chat start [thread=%s]: %r", thread_id, message)

    verdict = check_input(message)
    if not verdict.allowed:
        elapsed = time.perf_counter() - start
        logger.warning(
            "chat blocked by guardrail in %.2fs [thread=%s]: %s",
            elapsed, thread_id, verdict.reason,
        )
        # Deliberately not written to the conversation thread, so a blocked
        # attempt can't poison the history the agent sees on later turns.
        return {"answer": _refuse(verdict.reason), "artifact_url": None}

    result = conversational_agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 15},
    )
    elapsed = time.perf_counter() - start

    artifact_url = None
    raw = last_tool_message(result["messages"], "router_tool")
    if raw is not None:
        artifact_url = json.loads(raw).get("artifact_url")

    logger.info("chat done in %.2fs [thread=%s] (artifact_url=%s)", elapsed, thread_id, artifact_url)

    return {
        "answer": as_text(result["messages"][-1].content),
        "artifact_url": artifact_url,
    }