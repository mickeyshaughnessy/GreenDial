"""
GreenDial ↔ ListeningAI bridge.

GreenDial is the reference production deployment of the listening_ai package.

What this module does:
  1. Configures listening_ai Settings from GreenDial's config.py (OpenRouter +
     DigitalOcean Spaces under greendial/listening_ai/).
  2. Builds a ToolRegistry that wraps GreenDial's HEALTH_TOOLS / _execute_health_tool.
  3. Exposes helpers used by handlers.py (agentic loop) and api_server.py
     (mounts the ListeningAI blueprint at /listening).

Install the package once (local + server)::

    pip install -e ../ListeningAI[spaces]
    # or on the droplet: pip install -e /root/ListeningAI[spaces]
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Import host config BEFORE any sys.path changes — the ListeningAI checkout
# also has a config.py, and inserting it on sys.path would shadow GreenDial's.
import config as greendial_config

# Allow workspace-relative import only when the package is not installed yet
try:
    import listening_ai  # noqa: F401
except ImportError:
    _sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ListeningAI"))
    if os.path.isdir(_sibling) and _sibling not in sys.path:
        sys.path.insert(0, _sibling)

from listening_ai import (
    ChatController,
    Settings,
    ToolRegistry,
    configure_app,
    create_blueprint,
    default_registry,
)

_CONFIGURED = False
_LISTENING_PREFIX = "greendial/listening_ai/"


def _settings_from_greendial() -> Settings:
    """Map GreenDial config.py into listening_ai Settings (Spaces backend)."""
    base = Settings.from_config_module(greendial_config)
    # Force Spaces for the reference deployment when credentials are present
    has_spaces = bool(
        getattr(greendial_config, "DO_SPACES_KEY", None)
        and getattr(greendial_config, "DO_SPACES_BUCKET", None)
    )
    backend = getattr(greendial_config, "LISTENING_AI_STORE", None) or (
        "spaces" if has_spaces else "json"
    )
    base.store_backend = backend
    # Isolate ListeningAI objects from GreenDial's own user records
    base.spaces_prefix = getattr(greendial_config, "LISTENING_AI_PREFIX", _LISTENING_PREFIX)
    # Do not inherit GreenDial's S3_PREFIX (greendial/) via from_config_module
    # if LISTENING_AI_PREFIX is unset — from_config_module maps S3_PREFIX → spaces_prefix.
    if not getattr(greendial_config, "LISTENING_AI_PREFIX", None):
        # Only override when Spaces prefix was taken from GreenDial's main S3_PREFIX
        if base.spaces_prefix in ("greendial/", getattr(greendial_config, "S3_PREFIX", None)):
            base.spaces_prefix = _LISTENING_PREFIX
    base.openrouter_site_name = "GreenDial"
    base.openrouter_site_url = getattr(
        greendial_config, "OPENROUTER_SITE_URL", "https://greendial.org"
    )
    # Prefer a local data dir for json fallback so we don't write next to the package
    base.data_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "listening_ai"
    )
    base.db_path = os.path.join(base.data_dir, "db.json")
    # Listen more than speak: prioritize tools, then compress final replies.
    # Host can override via LISTENING_AI_REPLY_BREVITY / REPLY_BREVITY in config.
    base.reply_brevity = getattr(
        greendial_config, "LISTENING_AI_REPLY_BREVITY", None
    ) or getattr(greendial_config, "REPLY_BREVITY", None) or "very_short"
    return base


def ensure_configured() -> Settings:
    """Idempotent startup: configure settings + store once per process.

    Safe to call from api_server (blueprint mount), handlers (agentic loop),
    and utils (plain completion) — first caller wins.
    """
    global _CONFIGURED
    if _CONFIGURED:
        from listening_ai import get_settings
        return get_settings()
    settings = configure_app(_settings_from_greendial())
    _CONFIGURED = True
    print(
        f"[ListeningAI] configured store_backend={settings.store_backend} "
        f"prefix={settings.spaces_prefix!r} "
        f"model={settings.openrouter_model!r} "
        f"reply_brevity={settings.reply_brevity!r}"
    )
    return settings


def build_health_registry(agent_id: str = "doc") -> ToolRegistry:
    """
    ToolRegistry wrapping GreenDial's HEALTH_TOOLS.

    Handlers are bound to ``agent_id`` so queue_notification / call_specialist
    attribute correctly. Import of handlers is deferred to avoid circular imports
    at module load time.
    """
    import handlers  # local import — handlers imports this module for run_loop

    registry = ToolRegistry()
    for schema in handlers.HEALTH_TOOLS:
        func = schema.get("function") or {}
        name = func.get("name")
        if not name:
            continue

        def _make(tool_name: str):
            def handler(user_id: str, **kwargs):
                return handlers._execute_health_tool(tool_name, kwargs, user_id, agent_id)
            return handler

        registry.register(
            name,
            func.get("description", name),
            func.get("parameters") or {"type": "object", "properties": {}},
            _make(name),
        )
    return registry


def run_agentic_loop(
    messages: List[Dict[str, Any]],
    system_prompt: str,
    user_id: str,
    agent_id: str = "doc",
    max_steps: int = 6,
) -> Tuple[str, Dict[str, str], str]:
    """
    Drop-in replacement for handlers._run_agentic_loop.

    Returns (final_text, profile_updates, model_used) — same shape GreenDial
    expects, so call sites stay unchanged.
    """
    settings = ensure_configured()
    registry = build_health_registry(agent_id=agent_id)
    controller = ChatController(
        tool_registry=registry,
        system_prompt=system_prompt,
        max_steps=max_steps,
        reply_brevity=settings.reply_brevity,
    )
    final_text, model_used, tool_log = controller.run_loop(
        messages, user_id, system_prompt=system_prompt
    )

    # Collect profile mutations for the host response payload.
    # Tools already persist via handlers._execute_health_tool; this is for
    # the chat API to report profile_updated + return the new profile.
    profile_updates: Dict[str, Any] = {}
    for entry in tool_log:
        if entry.get("name") != "update_profile":
            continue
        inp = entry.get("input") or {}
        field = (inp.get("field") or "").strip() if isinstance(inp.get("field"), str) else inp.get("field")
        if not field:
            continue
        value = inp.get("value")
        if isinstance(value, str) and value.strip().lower() in ("null", "none", ""):
            value = None
        # Include null so host apply logic can delete the field
        profile_updates[field] = value

    return final_text, profile_updates, model_used


def make_blueprint(url_prefix: str = "/listening"):
    """
    Flask blueprint with default ListeningAI tools + a GreenDial-flavored
    health tip tool. Mounted at /listening so it coexists with GreenDial's
    native /auth and /chat routes.
    """
    ensure_configured()
    registry = default_registry()

    def greendial_status(user_id: str, **_kwargs):
        return (
            "You are on GreenDial, the reference ListeningAI deployment. "
            "Native health chat lives at POST /chat (X-Session-Token). "
            f"This /listening surface is the portable ListeningAI API (user={user_id})."
        )

    registry.register(
        "greendial_status",
        "Explain how this ListeningAI surface relates to GreenDial's main app.",
        {"type": "object", "properties": {}, "required": []},
        greendial_status,
    )

    return create_blueprint(
        tool_registry=registry,
        url_prefix=url_prefix,
        name="listening_ai",
        system_prompt=(
            "You are the ListeningAI console embedded in GreenDial. "
            "You listen better than you speak. Use tools to read and update "
            "profile, settings, inbox, and notifications for the user on this "
            "ListeningAI store (separate from GreenDial's main health profile "
            "unless they ask about greendial_status)."
        ),
    )
