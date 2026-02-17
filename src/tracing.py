"""
LangSmith tracing wrapper for the Critical Minerals Signal Hunter pipeline.

Every agent node is wrapped with trace() to ensure:
  - All LLM calls are captured in LangSmith with run_id linkage
  - The LangSmith trace URL is available for inclusion in SignalModel
  - Errors are tagged and surfaced in the LangSmith UI

Usage
-----
    from src.tracing import trace, get_langsmith_url

    @trace(name="filing_scanner", tags=["phase-1"])
    def filing_scanner_node(state: AgentState) -> dict:
        ...

Configuration (via environment variables, loaded from .env):
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=ls__...
    LANGCHAIN_PROJECT=critical-minerals-agent
    LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangSmith availability check
# ---------------------------------------------------------------------------

_LANGSMITH_AVAILABLE = False
try:
    from langsmith import traceable  # noqa: F401
    from langsmith import Client as LangSmithClient

    _LANGSMITH_AVAILABLE = bool(os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true")
except ImportError:
    logger.warning("langsmith not installed — tracing disabled")

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# trace decorator
# ---------------------------------------------------------------------------


def trace(
    name: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator that wraps a LangGraph node function with LangSmith tracing.

    Falls back to a no-op if LangSmith is not configured, so agents run
    correctly in environments without LANGCHAIN_TRACING_V2=true.

    Parameters
    ----------
    name : str, optional
        Display name in LangSmith UI. Defaults to the function name.
    tags : list[str], optional
        Tags to apply to the trace (e.g. ["phase-1", "filing"]).
    metadata : dict, optional
        Additional key/value metadata attached to the trace.
    """

    def decorator(fn: F) -> F:
        node_name = name or fn.__name__

        if not _LANGSMITH_AVAILABLE:
            # No-op wrapper — pass through unchanged
            @functools.wraps(fn)
            def passthrough(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

            return passthrough  # type: ignore[return-value]

        try:
            from langsmith import traceable

            traced = traceable(
                name=node_name,
                tags=tags or [],
                metadata=metadata or {},
            )(fn)

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return traced(*args, **kwargs)

            return wrapper  # type: ignore[return-value]

        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to apply LangSmith trace to %s: %s", node_name, exc)

            @functools.wraps(fn)
            def fallback(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

            return fallback  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# LangSmith URL helpers
# ---------------------------------------------------------------------------


def get_langsmith_run_url(run_id: str) -> str:
    """
    Construct a LangSmith trace URL for a given run_id.

    Returns a placeholder URL if LangSmith is not configured, so that
    SignalModel.langsmith_url is always populated (Pydantic required field).
    """
    project = os.getenv("LANGCHAIN_PROJECT", "critical-minerals-agent")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    if not _LANGSMITH_AVAILABLE:
        return f"langsmith://not-configured/runs/{run_id}"

    # Standard LangSmith UI URL pattern
    base = "https://smith.langchain.com"
    return f"{base}/o/default/projects/{project}/runs/{run_id}"


def get_langsmith_project_url() -> str:
    """Return the LangSmith project overview URL."""
    project = os.getenv("LANGCHAIN_PROJECT", "critical-minerals-agent")
    return f"https://smith.langchain.com/o/default/projects/{project}"


# ---------------------------------------------------------------------------
# LangSmith client (for eval dataset management in Phase 3)
# ---------------------------------------------------------------------------


def get_langsmith_client() -> Any:
    """
    Return a LangSmith Client instance, or None if not configured.
    Used in Phase 3 for creating/updating eval datasets.
    """
    if not _LANGSMITH_AVAILABLE:
        logger.warning("LangSmith not configured — client unavailable")
        return None

    try:
        from langsmith import Client

        return Client()
    except Exception as exc:
        logger.error("Failed to create LangSmith client: %s", exc)
        return None
