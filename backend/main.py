from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime

from .db import init_db, insert_usage, recent_usage, aggregate_summary, timeseries, period_bounds
from .config import settings
from .db_sa import ENGINE
from .models import Base
from .routers.customers import router as customers_router
from .routers.runs import router as runs_router
from .routers.billing import router as billing_router

# Pricing (example; adjust as needed)
GROQ_PRICE_PER_1K = 0.001  # $ per 1K tokens
GEMINI_PRICE_PER_1K = 0.0014  # $ per 1K tokens

app = FastAPI(title="AI Cost Tracker (Groq + Gemini)")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrackRequest(BaseModel):
    user_id: str = Field(default="demo-user")
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 1
    created_at: Optional[datetime] = None


class TrackResponse(BaseModel):
    id: int
    provider: str
    model: str
    tokens: int
    calls: int
    cost: float
    created_at: datetime


@app.on_event("startup")
async def on_startup():
    # Initialize lightweight SQLite usage DB (legacy endpoints)
    init_db()
    # Create SQLAlchemy tables for expanded features
    Base.metadata.create_all(bind=ENGINE)
    # Mount routers
    app.include_router(customers_router)
    app.include_router(runs_router)
    app.include_router(billing_router)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _calc_cost(tokens: int, price_per_1k: float) -> float:
    return round((tokens / 1000.0) * price_per_1k, 8)


@app.post("/track/groq", response_model=TrackResponse)
async def track_groq(req: TrackRequest):
    total_tokens = max(0, req.input_tokens) + max(0, req.output_tokens)
    cost = _calc_cost(total_tokens, GROQ_PRICE_PER_1K)
    rec = {
        "user_id": req.user_id,
        "provider": "groq",
        "model": req.model,
        "input_tokens": req.input_tokens,
        "output_tokens": req.output_tokens,
        "calls": req.calls,
        "cost": cost,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }
    new_id = insert_usage(rec)
    return TrackResponse(
        id=new_id,
        provider="groq",
        model=req.model,
        tokens=total_tokens,
        calls=req.calls,
        cost=cost,
        created_at=req.created_at or datetime.utcnow(),
    )


@app.post("/track/gemini", response_model=TrackResponse)
async def track_gemini(req: TrackRequest):
    total_tokens = max(0, req.input_tokens) + max(0, req.output_tokens)
    cost = _calc_cost(total_tokens, GEMINI_PRICE_PER_1K)
    rec = {
        "user_id": req.user_id,
        "provider": "gemini",
        "model": req.model,
        "input_tokens": req.input_tokens,
        "output_tokens": req.output_tokens,
        "calls": req.calls,
        "cost": cost,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }
    new_id = insert_usage(rec)
    return TrackResponse(
        id=new_id,
        provider="gemini",
        model=req.model,
        tokens=total_tokens,
        calls=req.calls,
        cost=cost,
        created_at=req.created_at or datetime.utcnow(),
    )


@app.get("/recent")
async def get_recent(limit: int = 50) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    rows = recent_usage(limit)
    return {
        "items": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "provider": r["provider"],
                "model": r["model"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "calls": r["calls"],
                "cost": r["cost"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    }


@app.get("/summary")
async def get_summary(period: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    if period and (start or end):
        raise HTTPException(status_code=400, detail="Provide either period or start/end, not both")

    if period:
        start, end = period_bounds(period)
    data = aggregate_summary(start, end)
    data["window"] = {"start": start, "end": end}
    return data


@app.get("/timeseries")
async def get_timeseries(granularity: str = "day", days: int = 7, provider: Optional[str] = None) -> Dict[str, Any]:
    days = max(1, min(days, 90))
    series = timeseries(granularity=granularity, days=days, provider=provider)
    return {"granularity": granularity, "days": days, "provider": provider, "series": series}


@app.get("/alerts")
async def get_alerts(threshold: float = 10.0, period: str = "day") -> Dict[str, Any]:
    start, end = period_bounds(period)
    data = aggregate_summary(start, end)
    over = data["total"]["cost"] >= threshold
    return {
        "period": period,
        "threshold": threshold,
        "total_cost": data["total"]["cost"],
        "over_threshold": over,
        "window": {"start": start, "end": end},
    }
