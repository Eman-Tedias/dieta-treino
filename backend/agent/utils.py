import json
import math
import os
import re
import sqlite3
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from langchain_core.messages import ToolMessage

from config import embedding_model

ALLOWED_CDNS = re.compile(
    r"^https://(cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)/", re.I
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "treino_dieta.db"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DB_PATH = BASE_DIR / "data" / "artifacts.db"
RUNS_DIR = BASE_DIR / "runs"

BUCKET_NAME = os.environ.get("BUCKET_NAME")


def _bucket():
    from google.cloud import storage as gcs

    return gcs.Client().bucket(BUCKET_NAME)


def sync_from_bucket() -> None:
    """Downloads treino_dieta.db, artifacts.db and artifacts/*.html from the
    GCS bucket to local disk. No-op if BUCKET_NAME isn't set (local dev).
    Call once at app startup, before serving any requests, since Cloud Run's
    local filesystem is wiped on every cold start.

    treino_dieta.db is read-only for the app (only the local ETL writes it),
    so its "upload" side isn't sync_to_bucket, it's you manually running
    `gcloud storage cp data/treino_dieta.db gs://<bucket>/treino_dieta.db`
    after regenerating it locally.
    """
    if not BUCKET_NAME:
        return

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    bucket = _bucket()

    main_db_blob = bucket.blob("treino_dieta.db")
    if main_db_blob.exists():
        main_db_blob.download_to_filename(str(DB_PATH))

    db_blob = bucket.blob("artifacts.db")
    if db_blob.exists():
        db_blob.download_to_filename(str(ARTIFACTS_DB_PATH))

    for blob in bucket.list_blobs(prefix="artifacts/"):
        if blob.name.endswith(".html"):
            blob.download_to_filename(str(ARTIFACTS_DIR / Path(blob.name).name))


def sync_to_bucket() -> None:
    """Uploads artifacts.db and artifacts/*.html to the GCS bucket. No-op if
    BUCKET_NAME isn't set (local dev). Call after any write to either.
    """
    if not BUCKET_NAME:
        return

    bucket = _bucket()

    if ARTIFACTS_DB_PATH.exists():
        bucket.blob("artifacts.db").upload_from_filename(str(ARTIFACTS_DB_PATH))

    for html_file in ARTIFACTS_DIR.glob("*.html"):
        bucket.blob(f"artifacts/{html_file.name}").upload_from_filename(str(html_file))

class _TagChecker(HTMLParser):
    """Minimal parser that detects unclosed or out-of-order tags."""

    VOID = {"br", "hr", "img", "input", "meta", "link"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            self.errors.append(f"out-of-order closing tag: </{tag}>")
            while self.stack and self.stack.pop() != tag:
                pass


def static_validation(html: str) -> list[str]:
    """Free sanity checks on generated HTML.

    Returns a list of problems; an empty list means approved.
    """
    problems = []
    if len(html) < 200:
        problems.append("HTML too short")
    if "<!doctype html" not in html[:100].lower():
        problems.append("does not start with <!DOCTYPE html>")

    checker = _TagChecker()
    try:
        checker.feed(html)
        if checker.stack:
            problems.append(f"unclosed tags: {checker.stack}")
        problems.extend(checker.errors)
    except Exception as e:
        problems.append(f"unparseable HTML: {e}")

    for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
        if not ALLOWED_CDNS.match(src):
            problems.append(f"external script not allowed: {src}")

    return problems


def last_tool_message(messages: list, tool_name: str) -> str | None:
    """Finds the last raw ToolMessage content from a given tool call in an
    agent's message history. Used to bypass an agent's own final paraphrase
    and forward exactly what a tool returned (numbers, urls, etc.).
    """
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == tool_name:
            return msg.content
    return None


def _save_trace_message(msg, index: int, out_dir: Path) -> None:
    role = msg.__class__.__name__.removesuffix("Message")
    lines = [f"# {index:02d} - {role}"]

    name = getattr(msg, "name", None)
    if name:
        lines.append(f"**tool:** `{name}`")

    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        lines.append("**tool_calls:**")
        for tc in tool_calls:
            lines.append(f"- `{tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})`")

    content = msg.content
    content_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
    lines.append("\n```\n" + content_text + "\n```")

    slug = name or role.lower()
    (out_dir / f"{index:02d}_{slug}.md").write_text("\n\n".join(lines), encoding="utf-8")


def save_run_trace(messages: list, question: str, duration: float) -> Path:
    """Saves a full ReAct trace (every message, in order) as numbered .md
    files under a timestamped folder in runs/, for post-hoc debugging.
    duration is the total wall-clock seconds the whole request took.
    """
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = RUNS_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "00_meta.md").write_text(
        f"# Meta\n\n**question:** {question}\n\n**duration:** {duration:.2f}s\n",
        encoding="utf-8",
    )

    for i, msg in enumerate(messages, start=1):
        _save_trace_message(msg, i, out_dir)

    return out_dir


def as_text(content: str | list) -> str:
    """Normalizes a message's content to plain text.

    Some providers (e.g. Gemini via langchain_google_genai) return content as
    a list of blocks (text/thinking/etc.) instead of a plain string.
    """
    if isinstance(content, str):
        return content
    return "".join(
        block["text"] for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def render_artifact(html: str, titulo: str) -> dict:
    """Salva um artifact HTML e retorna a URL para o frontend embutir em iframe."""
    html = (html or "").strip()
    # Sinceramente, eu vou fazer um sistema de evaluation mais inteligente, onde a gente roda o html para testar erros de runtime, e depois fazemos uma validação via LLM
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    slug = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()[:60] or "artifact"
    filename = f"{slug}-{int(time.time())}.html"

    path = ARTIFACTS_DIR / filename
    path.write_text(html, encoding="utf-8")
    return {"url": f"/artifacts/{filename}", "id": filename.removesuffix(".html")}

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two embedding vectors, in [-1, 1]."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def save_dashboard_metadata(
    id: str,
    question: str,
    componentes: list[str] | None,
    data_json: str,
    url: str,
) -> None:
    """Saves a generated dashboard's metadata plus a question embedding, so a
    later request with a similar question can be matched and reused instead
    of regenerating from scratch.
    """
    embedding = embedding_model.embed_query(question)

    con = sqlite3.connect(ARTIFACTS_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_artifact (
            id          TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL,
            question    TEXT NOT NULL,
            componentes TEXT,
            data_json   TEXT NOT NULL,
            url         TEXT NOT NULL,
            embedding   TEXT NOT NULL
        )
    """)
    con.execute(
        "INSERT INTO dashboard_artifact "
        "(id, created_at, question, componentes, data_json, url, embedding) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            id,
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            question,
            json.dumps(componentes),
            data_json,
            url,
            json.dumps(embedding),
        ),
    )
    con.commit()
    con.close()