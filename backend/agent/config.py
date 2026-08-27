import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy third-party libs so our own INFO logs aren't buried.
for noisy in ("httpx", "httpcore", "google_genai.models"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODEL = "gemini-3.1-flash-lite"


def _gemini(model_name: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )


# Gemini's flash-lite tier throws transient 503s ("high demand") fairly often,
# and 429s once the free-tier per-minute quota is hit. with_fallbacks retries
# the whole call on the previous generation instead of failing the request.
model = _gemini(PRIMARY_MODEL).with_fallbacks([_gemini(FALLBACK_MODEL)])

embedding_model = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview"
)