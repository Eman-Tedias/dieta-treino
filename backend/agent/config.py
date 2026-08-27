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

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=1.0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

embedding_model = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview"
)