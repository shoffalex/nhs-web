"""FastAPI entry point.

This app owns /api/* and nothing else. The static site is served by Caddy
straight off site/ — see deploy/caddy/Caddyfile. Keeping them separate means
the site stays up when this process is down; the calendar page degrades to a
"schedule unavailable" notice instead of taking the whole site with it.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import auth, events

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe on every boot — migrations/001_init.sql is all IF NOT EXISTS. If the
    # schema starts changing in ways that need backfills, bring in real
    # migration tooling and drop this.
    init_db()
    yield


app = FastAPI(
    title="Pine View School NHS API",
    description="Calendar events for the chapter site.",
    version="0.1.0",
    lifespan=lifespan,
)

# Development only. In production Caddy serves the site and the API from one
# origin, so the browser never issues a cross-origin request.
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(events.router)
app.include_router(auth.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
