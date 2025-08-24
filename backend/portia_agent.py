"""
Portia AI agent stub for demo. This is optional for the MVP backend
and serves to illustrate how you'd configure storage_class="LOCAL".
"""
from typing import Any, Dict

# Try multiple known import paths for the Portia SDK (portia-sdk-python)
AgentType = object
try:
    # common package name
    from portia_sdk import Agent as AgentType  # type: ignore
except Exception:
    try:
        # sometimes exposed as 'portia'
        from portia import Agent as AgentType  # type: ignore
    except Exception:
        try:
            # alternate name
            from portia_sdk_python import Agent as AgentType  # type: ignore
        except Exception:  # pragma: no cover - library may not be installed in dev
            AgentType = object  # fallback to keep file importable


class CostTrackerAgent:
    def __init__(self):
        # Example configuration: storage is local for hackathon demo
        self.storage_class = "LOCAL"
        # If Portia requires initialization, do it here:
        try:
            self.agent = AgentType(storage_class=self.storage_class)  # type: ignore
        except Exception:
            self.agent = None

    def info(self) -> Dict[str, Any]:
        return {
            "name": "CostTrackerAgent",
            "storage_class": self.storage_class,
            "portia_available": bool(self.agent),
        }
