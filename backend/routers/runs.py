from __future__ import annotations
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from ..db_sa import get_db
from ..models import AgentRun
from ..services.portia_factory import make_portia
from sqlalchemy import func, Integer, cast

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    customer_id: int
    prompt: str
    provider: str = "google"
    model: str = "google/gemini-2.0-flash"


class AgentRunOut(BaseModel):
    id: int
    customer_id: int
    prompt: str
    provider: Optional[str]
    model: Optional[str]
    success: bool
    cost_usd: float
    calls: int

    class Config:
        from_attributes = True


@router.post("/start", response_model=AgentRunOut)
async def start_run(body: StartRunRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    portia, ar = make_portia(db=db, customer_id=body.customer_id, prompt=body.prompt, provider=body.provider, model=body.model)

    def _execute(run_id: int):
        # Re-open a session per background thread to avoid using closed session
        from ..db_sa import SessionLocal
        sess = SessionLocal()
        try:
            run: AgentRun | None = sess.get(AgentRun, run_id)
            if not run:
                return
            # Mark start
            from datetime import datetime
            run.started_at = run.started_at or datetime.utcnow()
            sess.add(run)
            sess.commit()

            try:
                portia.run(run.prompt)
                # If no exception, consider success
                run.success = True
            except Exception:
                # Failure
                run.success = False
            finally:
                # Always set end and duration
                run.ended_at = datetime.utcnow()
                if run.started_at and run.ended_at:
                    run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
                sess.add(run)
                sess.commit()
        finally:
            sess.close()

    bg.add_task(_execute, ar.id)
    return ar


@router.get("/by_customer/{customer_id}", response_model=List[AgentRunOut])
async def list_runs(customer_id: int, db: Session = Depends(get_db)):
    q = db.query(AgentRun).filter(AgentRun.customer_id == customer_id).order_by(AgentRun.started_at.desc())
    return q.all()


@router.get("/summary/{customer_id}")
async def run_summary(customer_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    totals = db.query(
        func.count(AgentRun.id),
        func.sum(AgentRun.cost_usd),
        func.avg(AgentRun.cost_usd),
        func.avg(cast(AgentRun.success, Integer)),
    ).filter(AgentRun.customer_id == customer_id).one()
    count = totals[0] or 0
    return {
        "total_runs": count,
        "total_cost_usd": float(totals[1] or 0.0),
        "avg_cost_usd": float(totals[2] or 0.0),
        "success_rate": float(totals[3] or 0.0) if count > 0 else 0.0,
    }
