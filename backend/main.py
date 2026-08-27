import hashlib
import hmac
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "agent"))

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat import chat
from overview import render_overview_html
from utils import ARTIFACTS_DIR, sync_from_bucket

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend_dist"

APP_PASSWORD = os.environ.get("APP_PASSWORD")
# Cookies with secure=True are dropped over plain http, which is what local
# dev uses. Cloud Run is always https, so this only relaxes things locally.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"
# Signing key for the session cookie. Falls back to a per-process random key,
# which means restarting the server invalidates existing sessions (fine, users
# just log in again), but set SESSION_SECRET in production to keep them valid
# across deploys.
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
SESSION_COOKIE = "td_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
sync_from_bucket()

app = FastAPI(title="treino-dieta")

# In production the frontend is served from this same origin, so CORS isn't
# needed there. It only matters for local dev, where Vite runs on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sign(expires_at: int) -> str:
    payload = str(expires_at)
    signature = hmac.new(
        SESSION_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def _is_valid_session(cookie_value: str | None) -> bool:
    if not cookie_value or "." not in cookie_value:
        return False
    payload, _, signature = cookie_value.rpartition(".")
    expected = hmac.new(
        SESSION_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        return int(payload) > int(time.time())
    except ValueError:
        return False


def require_session(request: Request) -> None:
    """Dependency that rejects requests without a valid session cookie.

    If APP_PASSWORD isn't set (local dev), auth is disabled entirely.
    """
    if not APP_PASSWORD:
        return
    if not _is_valid_session(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="not authenticated")


class LoginRequest(BaseModel):
    password: str


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    artifact_url: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/session")
def session_status(request: Request):
    """Lets the frontend know whether it needs to show the login screen."""
    if not APP_PASSWORD:
        return {"authenticated": True, "auth_required": False}
    return {
        "authenticated": _is_valid_session(request.cookies.get(SESSION_COOKIE)),
        "auth_required": True,
    }


@app.post("/api/login")
def login(payload: LoginRequest, response: Response):
    if not APP_PASSWORD:
        return {"authenticated": True}

    # compare_digest to avoid leaking the password length/prefix via timing
    if not hmac.compare_digest(payload.password, APP_PASSWORD):
        raise HTTPException(status_code=401, detail="senha incorreta")

    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    response.set_cookie(
        SESSION_COOKIE,
        _sign(expires_at),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return {"authenticated": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"authenticated": False}


@app.get("/overview.html", response_class=HTMLResponse)
def overview(_: None = Depends(require_session)):
    return render_overview_html()


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, _: None = Depends(require_session)):
    result = chat(payload.thread_id, payload.message)
    return ChatResponse(**result)


@app.get("/artifacts/{filename}", response_class=HTMLResponse)
def artifact(filename: str, _: None = Depends(require_session)):
    """Serves a generated dashboard. A plain StaticFiles mount would bypass
    require_session, leaving everyone's dashboards readable by URL, so this
    goes through a route instead.
    """
    # Reject anything that isn't a bare .html filename, so a crafted name
    # can't escape ARTIFACTS_DIR.
    if "/" in filename or "\\" in filename or ".." in filename or not filename.endswith(".html"):
        raise HTTPException(status_code=404, detail="not found")

    path = ARTIFACTS_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return path.read_text(encoding="utf-8")

# Serve the built frontend (mounted last so it doesn't shadow the API routes).
# Only active when frontend_dist/ exists, i.e. in the Docker image.
if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
