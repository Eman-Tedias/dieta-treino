import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "agent"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat import chat
from overview import render_overview_html
from utils import ARTIFACTS_DIR

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="treino-dieta")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="artifacts")


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    artifact_url: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/overview.html", response_class=HTMLResponse)
def overview():
    return render_overview_html()


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest):
    result = chat(payload.thread_id, payload.message)
    return ChatResponse(**result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
