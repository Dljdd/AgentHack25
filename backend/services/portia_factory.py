from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AgentRun, ToolCall

try:
    # Portia SDK imports
    from portia import (
        Config as PortiaConfig,
        LLMProvider,
        Portia as PortiaClient,
        example_tool_registry,
    )
except Exception:  # pragma: no cover
    PortiaClient = None  # type: ignore
    LLMProvider = None  # type: ignore
    PortiaConfig = None  # type: ignore
    example_tool_registry = None  # type: ignore


class CostHooks:
    def __init__(self, db: Session, agent_run: AgentRun):
        self.db = db
        self.agent_run = agent_run

    def before_plan_run(self, **kwargs):
        self.agent_run.started_at = datetime.utcnow()
        self.db.add(self.agent_run)
        self.db.commit()

    def before_tool_call(self, tool_name: str, **kwargs):
        call = ToolCall(
            agent_run_id=self.agent_run.id,
            tool_name=tool_name,
            started_at=datetime.utcnow(),
            status="running",
        )
        self.db.add(call)
        self.db.commit()
        return call.id

    def after_tool_call(
        self,
        tool_call_id: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        status: str = "ok",
        **kwargs,
    ):
        call: ToolCall = self.db.get(ToolCall, tool_call_id)
        if call:
            call.ended_at = datetime.utcnow()
            if call.started_at and call.ended_at:
                call.duration_ms = int((call.ended_at - call.started_at).total_seconds() * 1000)
            call.input_tokens = input_tokens
            call.output_tokens = output_tokens
            call.cost_usd = cost_usd
            call.status = status
            self.db.add(call)
        # Update rollups on AgentRun
        self.agent_run.calls += 1
        self.agent_run.input_tokens += input_tokens
        self.agent_run.output_tokens += output_tokens
        self.agent_run.cost_usd += cost_usd
        self.db.add(self.agent_run)
        self.db.commit()

    def after_plan_run(
        self,
        success: bool,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.agent_run.success = success
        self.agent_run.provider = provider or self.agent_run.provider
        self.agent_run.model = model or self.agent_run.model
        self.agent_run.ended_at = datetime.utcnow()
        if self.agent_run.started_at and self.agent_run.ended_at:
            self.agent_run.duration_ms = int((self.agent_run.ended_at - self.agent_run.started_at).total_seconds() * 1000)
        self.db.add(self.agent_run)
        self.db.commit()


def make_portia(db: Session, customer_id: int, prompt: str, provider: str = "google", model: str = "google/gemini-2.0-flash"):
    """Factory that returns a Portia instance (or Dummy) and a new AgentRun. Robust to SDK/config issues."""
    # Fallback runner that simulates a run without external API calls
    class DummyPortia:
        def run(self, _prompt: str):
            import time
            time.sleep(0.2)
            return {"ok": True}

    try:
        # Create AgentRun
        ar = AgentRun(customer_id=customer_id, prompt=prompt, provider=provider, model=model)
        db.add(ar)
        db.commit()
        db.refresh(ar)

        # Proceed to try real Portia below; will fallback to DummyPortia on errors

        # Map provider str -> LLMProvider enum
        prov_map = {
            "google": getattr(LLMProvider, "GOOGLE", None),
            "openai": getattr(LLMProvider, "OPENAI", None),
            "anthropic": getattr(LLMProvider, "ANTHROPIC", None),
            "groq": getattr(LLMProvider, "GROQ", None),
        }
        llm_provider = prov_map.get(provider.lower())

        cfg_kwargs = {"llm_provider": llm_provider, "default_model": model}
        if settings.GOOGLE_API_KEY:
            cfg_kwargs["google_api_key"] = settings.GOOGLE_API_KEY
        if settings.OPENAI_API_KEY:
            cfg_kwargs["openai_api_key"] = settings.OPENAI_API_KEY
        if settings.ANTHROPIC_API_KEY:
            cfg_kwargs["anthropic_api_key"] = settings.ANTHROPIC_API_KEY

        # Build config if possible
        try:
            config = PortiaConfig.from_default(**cfg_kwargs)
        except Exception:
            config = None

        # Try to instantiate real client; if it fails, use dummy
        try:
            if config is not None:
                portia = PortiaClient(config=config, tools=example_tool_registry)
            else:
                portia = DummyPortia()
        except Exception:
            portia = DummyPortia()

        return portia, ar
    except Exception:
        # As a last resort, still create a minimal AgentRun so the API doesn't 500
        ar = AgentRun(customer_id=customer_id, prompt=prompt, provider=provider, model=model)
        try:
            db.add(ar)
            db.commit()
            db.refresh(ar)
        except Exception:
            pass
        return DummyPortia(), ar
