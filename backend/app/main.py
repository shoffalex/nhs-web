"""FastAPI entry point.

This app owns /api/* and nothing else. The static site is served by nginx
straight off site/ — see deploy/nginx/nhs.conf. Keeping them separate means the
site stays up when this process is down; the calendar page degrades to a
"schedule unavailable" notice instead of taking the whole site with it.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, events

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fine at this scale: one table, additive changes. If the schema starts
    # changing in ways that need backfills, bring in Alembic and drop this.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Pine View School NHS API",
    description="Calendar events for the chapter site.",
    version="0.1.0",
    lifespan=lifespan,
)

# Development only. In production nginx serves the site and the API from one
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
