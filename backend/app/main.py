import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.agent import router as agent_router
from app.api.eval import router as eval_router
from app.api.scan import router as scan_router
from app.config import settings
from app.logging_setup import configure_logging, get_request_id, set_request_id

configure_logging()
logger = logging.getLogger("sentinel")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "sentinel started model=%s gemini_key=%s cors=%s",
        settings.gemini_model,
        "set" if settings.gemini_api_key else "missing",
        [o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    )
    yield


app = FastAPI(title="Sentinel Prompt Injection Firewall", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = set_request_id(request.headers.get("x-request-id"))
        logger.info("http %s %s", request.method, request.url.path)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        logger.info("http %s %s -> %s", request.method, request.url.path, response.status_code)
        return response


app.add_middleware(RequestLogMiddleware)
app.include_router(scan_router)
app.include_router(agent_router)
app.include_router(eval_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "request_id": get_request_id(), "model": settings.gemini_model}


@app.get("/health/gemini")
def health_gemini() -> dict:
    if not settings.gemini_api_key:
        return {"ok": False, "model": settings.gemini_model, "error": "GEMINI_API_KEY missing"}
    try:
        from google.genai import types

        from app.gemini_client import client, disable_afc, http_options

        response = client().models.generate_content(
            model=settings.gemini_model,
            contents="Reply with exactly: pong",
            config=types.GenerateContentConfig(
                temperature=0,
                automatic_function_calling=disable_afc(),
                http_options=http_options(timeout_ms=20_000, attempts=1),
            ),
        )
        text = (response.text or "").strip()
        logger.info("gemini health ok model=%s reply=%s", settings.gemini_model, text[:80])
        return {"ok": True, "model": settings.gemini_model, "reply": text}
    except Exception as exc:
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        logger.warning("gemini health failed type=%s status=%s error=%s", type(exc).__name__, status, str(exc)[:240])
        return {
            "ok": False,
            "model": settings.gemini_model,
            "error": type(exc).__name__,
            "status": status,
            "detail": str(exc)[:240],
        }
