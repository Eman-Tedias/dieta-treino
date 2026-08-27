import json
import logging
import time

from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from config import model
from prompts import CONVERSATIONAL_SYSTEM_PROMPT
from graph import ask
from utils import as_text, last_tool_message

logger = logging.getLogger("treino_dieta.chat")

checkpointer = InMemorySaver()


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


def chat(thread_id: str, message: str) -> dict:
    """Sends a message on a given conversation thread.

    Returns {'answer': str, 'artifact_url': str | None}. artifact_url comes
    straight from router_tool's raw JSON result (ultimately from
    html_agent_tool), never retyped by any LLM layer in between.
    """
    start = time.perf_counter()
    logger.info("chat start [thread=%s]: %r", thread_id, message)

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