"""
Handlers Module - Core request processing
"""
import json
import uuid
import re
import base64
import random
import time
from datetime import datetime

import config
import utils
import s3_storage
from prompts import doc_v2, notifications, facilitator, supervisor as supervisor_module
from prompts import agents as agent_registry
from prompts.agents import base as agent_base
from prompts.shared.tools import TOOL_USE_INSTRUCTIONS
from prompts.shared.profile import PROFILE_UPDATE_SYNTAX
from prompts.shared import style as style_module
from prompts.shared import chat_only as chat_only_module
from prompts.shared import stickers as stickers_module
import threading

# In-memory TTL cache
_cache_store = {}
_cache_ts = {}

# In-memory session store
_sessions = {}

_TTL_USER = 60        # seconds
_TTL_SESSION = 300
_TTL_PARTICIPANT = 60
_TTL_CAMPAIGN = 300
_TTL_GROUP = 60


def _cache_set(namespace, key, data, ttl):
    _cache_store[(namespace, key)] = data
    _cache_ts[(namespace, key)] = time.time() + ttl


def _cache_get(namespace, key):
    k = (namespace, key)
    if k in _cache_store and time.time() < _cache_ts.get(k, 0):
        return _cache_store[k]
    return None


def _cache_del(namespace, key):
    k = (namespace, key)
    _cache_store.pop(k, None)
    _cache_ts.pop(k, None)


def _cache_user(user_id, data):
    _cache_set('user', user_id, data, _TTL_USER)


def _get_cached_user(user_id):
    return _cache_get('user', user_id)


def _cache_participant(participant_id, data):
    _cache_set('participant', participant_id, data, _TTL_PARTICIPANT)


def _get_cached_participant(participant_id):
    return _cache_get('participant', participant_id)


def _cache_campaign(campaign_id, data):
    _cache_set('campaign', campaign_id, data, _TTL_CAMPAIGN)


def _get_cached_campaign(campaign_id):
    return _cache_get('campaign', campaign_id)


def _cache_group(group_id, data):
    _cache_set('group', group_id, data, _TTL_GROUP)


def _get_cached_group(group_id):
    return _cache_get('group', group_id)


def _normalize_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits[-15:] if digits else ""


def _now_iso():
    return datetime.utcnow().isoformat()


# ============ AUTHENTICATION ============

def handle_auth(request):
    """Handle login/signup requests"""
    username = request.get('username', '').strip()
    passphrase = request.get('password', '')
    
    if not username:
        return json.dumps({"error": "Username required"}), 400
    
    user_id = f"user_{username.lower().replace(' ', '_').replace('@', '_')}"
    
    try:
        user = s3_storage.get_user(user_id)
    except Exception as e:
        print(f"[Auth] S3 error: {e}")
        user = None
    
    # LOGIN mode
    if not request.get('create_new'):
        if user:
            if user.get('passphrase') == passphrase:
                # Issue session token for authenticated requests
                token = uuid.uuid4().hex
                user['session_token'] = token
                try:
                    s3_storage.save_user(user_id, user)
                    _cache_user(user_id, user)
                except Exception as e:
                    print(f"[Auth] Token save failed: {e}")

                # Generate daily suggestions in background on login
                threading.Thread(target=generate_login_suggestions, args=(user_id,)).start()

                return json.dumps({
                    "user_id": user_id,
                    "username": user.get('username', username),
                    "settings": user.get('settings', {}),
                    "profile": user.get('profile', {}),
                    "token": token
                })
            return json.dumps({"error": "Invalid passphrase"}), 401
        return json.dumps({"error": "User not found"}), 404
    
    # SIGNUP mode
    if user:
        return json.dumps({"error": "User already exists"}), 409
    
    if not request.get('hipaa_waiver_accepted'):
        return json.dumps({"error": "HIPAA waiver must be accepted"}), 400
    
    profile = request.get('profile', {})
    signup_token = uuid.uuid4().hex
    new_user = {
        "user_id": user_id,
        "username": username,
        "passphrase": passphrase,
        "session_token": signup_token,
        "created": datetime.utcnow().isoformat(),
        "hipaa_waiver_accepted": True,
        "transcript": "",
        "settings": {
            "doc_style": "questioning",
            "theme": "dark",
            "notifications_enabled": True
        },
        "profile": profile,
        "notifications": []
    }
    
    try:
        s3_storage.save_user(user_id, new_user)
        _cache_user(user_id, new_user)
        
        # Generate initial suggestions in background
        threading.Thread(target=generate_login_suggestions, args=(user_id,)).start()
    except Exception as e:
        print(f"[Auth] Failed to save user: {e}")
        return json.dumps({"error": "Failed to create account"}), 500
    
    return json.dumps({
        "user_id": user_id,
        "username": username,
        "new_user": True,
        "settings": new_user["settings"],
        "profile": new_user["profile"],
        "token": signup_token
    })


def verify_basic_auth(auth_header):
    """Verify Basic Auth header"""
    if not auth_header or not auth_header.startswith('Basic '):
        return None, None
    
    try:
        encoded = auth_header[6:]
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, passphrase = decoded.split(':', 1)
        
        user_id = f"user_{username.lower().replace(' ', '_').replace('@', '_')}"
        user = s3_storage.get_user(user_id)
        
        if user and user.get('passphrase') == passphrase:
            return user_id, user
    except Exception as e:
        print(f"[Auth] Basic auth error: {e}")
    
    return None, None


# ============ USER PROFILE ============

def get_user_data(user_id):
    """Get user data from cache or S3"""
    if not user_id:
        return {}
    
    cached = _get_cached_user(user_id)
    if cached:
        return cached
    
    try:
        user = s3_storage.get_user(user_id)
        if user:
            _cache_user(user_id, user)
            return user
    except Exception as e:
        print(f"[User] Failed to get user: {e}")
    
    return {}


_PRIVATE_FIELDS = ('passphrase', 'session_token')


def session_ok(user_id, token):
    """Check that the supplied session token matches the user record."""
    if not user_id or not token:
        return False
    user = get_user_data(user_id)
    if user and user.get('session_token') == token:
        return True
    # Token rotates at login; another gunicorn worker may hold a stale cached
    # copy for up to the cache TTL. On mismatch, re-check against S3 directly.
    try:
        fresh = s3_storage.get_user(user_id)
        if fresh:
            _cache_user(user_id, fresh)
            return fresh.get('session_token') == token
    except Exception:
        pass
    return False


def demand_key_ok(key):
    """Check demand-side API key (POST /bounty, /generate). Fails closed if unconfigured."""
    expected = getattr(config, 'DEMAND_API_KEY', '')
    return bool(expected) and key == expected


def handle_get_user(user_id):
    """Get user profile (excludes private fields)"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    safe_user = {k: v for k, v in user.items() if k not in _PRIVATE_FIELDS}
    return json.dumps(safe_user)


_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_ETH_ADDR_RE = re.compile(r'^0x[a-fA-F0-9]{40}$')
_SOL_ADDR_RE = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')


def _validate_identity(data):
    """Validate identity fields. Returns error string or None. Empty values are allowed (clearing)."""
    email = (data.get('email') or '').strip()
    if email and not _EMAIL_RE.match(email):
        return "Invalid email address"
    wallets = data.get('wallets') or {}
    eth = (wallets.get('eth') or '').strip()
    if eth and not _ETH_ADDR_RE.match(eth):
        return "Invalid ETH address (expected 0x + 40 hex chars)"
    sol = (wallets.get('sol') or '').strip()
    if sol and not _SOL_ADDR_RE.match(sol):
        return "Invalid Solana address"
    return None


def handle_delete_user(user_id):
    """Delete the user's own account (route enforces session token)."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    try:
        s3_storage.delete_user(user_id)
        _cache_del('user', user_id)
        return json.dumps({"ok": True})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


def handle_update_user(user_id, data):
    """Update user profile"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    err = _validate_identity(data)
    if err:
        return json.dumps({"error": err}), 400

    allowed = ['username', 'settings', 'profile', 'first_name', 'last_name', 'email', 'wallets']
    for key in allowed:
        if key in data:
            if key in ('settings', 'profile', 'wallets') and isinstance(data[key], dict):
                user.setdefault(key, {}).update(data[key])
            else:
                user[key] = data[key]
    
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[User] Failed to update: {e}")
    
    safe_user = {k: v for k, v in user.items() if k not in _PRIVATE_FIELDS}
    return json.dumps({"success": True, "user": safe_user})


# ============ SETTINGS ============

def handle_get_settings(user_id):
    """Get user settings"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    default_settings = {
        "doc_style": "questioning",
        "theme": "dark",
        "ui_style": "page_default",
        "notifications_enabled": True,
        "chat_only_mode": True
    }
    
    settings = {**default_settings, **user.get('settings', {})}
    return json.dumps({"settings": settings})


def handle_update_settings(user_id, data):
    """Update user settings"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    if 'custom_agent_prompt' in data:
        data['custom_agent_prompt'] = str(data['custom_agent_prompt'])[:2000]

    user.setdefault('settings', {}).update(data)
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[Settings] Failed to update: {e}")
        return json.dumps({"error": "Failed to save settings"}), 500
    
    return json.dumps({"success": True, "settings": user['settings']})


# ============ WEB PUSH ============

def handle_push_subscribe(user_id, subscription):
    """Store a browser PushSubscription on the user record (de-duped, capped)."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    if not isinstance(subscription, dict) or not subscription.get('endpoint'):
        return json.dumps({"error": "Invalid subscription"}), 400

    subs = [s for s in (user.get('push_subscriptions') or [])
            if s.get('endpoint') != subscription['endpoint']]
    subs.append(subscription)
    user['push_subscriptions'] = subs[-10:]  # cap per user

    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[Push] Failed to save subscription: {e}")
        return json.dumps({"error": "Failed to save subscription"}), 500

    return json.dumps({"success": True})


def handle_push_unsubscribe(user_id, endpoint):
    """Remove a single push endpoint from the user record."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    subs = [s for s in (user.get('push_subscriptions') or []) if s.get('endpoint') != endpoint]
    user['push_subscriptions'] = subs
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception:
        return json.dumps({"error": "Failed to save"}), 500
    return json.dumps({"success": True})


# ============ AGENTS ============

# Fields that are worth tracking historically (time-series)
TRACKABLE_FIELDS = {
    'sleep_hours', 'weight', 'stress_level', 'mood', 'energy_level',
    'exercise_minutes', 'steps_per_day', 'water_intake_liters',
    'diet_notes', 'symptom_notes', 'resting_heart_rate',
    'blood_pressure_systolic', 'blood_pressure_diastolic',
}


def _append_history(user, field, value):
    """Append a timestamped entry to profile_history[field]."""
    if field not in TRACKABLE_FIELDS:
        return
    date = datetime.utcnow().strftime('%Y-%m-%d')
    history = user.setdefault('profile_history', {})
    entries = history.setdefault(field, [])
    # Avoid duplicate entries for the same date
    if entries and entries[-1].get('ts') == date:
        entries[-1]['v'] = str(value)
    else:
        entries.append({'ts': date, 'v': str(value)})
    # Cap at 365 entries per field
    history[field] = entries[-365:]


def handle_get_history(user_id, field=None, days=30):
    """Return profile history, optionally filtered by field and time window."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    history = user.get('profile_history', {})

    if field:
        entries = [e for e in history.get(field, []) if e.get('ts', '') >= cutoff]
        return json.dumps({field: entries})

    result = {}
    for f, entries in history.items():
        filtered = [e for e in entries if e.get('ts', '') >= cutoff]
        if filtered:
            result[f] = filtered
    return json.dumps(result)


# ============ TOOL DEFINITIONS ============

HEALTH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_profile",
            "description": "Read the user's current health profile. Call this at the start of any conversation to understand their health context.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_profile",
            "description": "Save or update a field in the user's health profile. Use for stable facts: conditions, medications, goals, preferences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Profile field name (e.g. sleep_hours, weight, primary_concern, goals)"},
                    "value": {"type": "string", "description": "Value to save"}
                },
                "required": ["field", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_health_data",
            "description": "Log a timestamped health data point for trend tracking. Use when the user reports a daily/recurring metric. Creates a time-series record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Trackable field. Must be one of: sleep_hours, weight, stress_level, mood, energy_level, exercise_minutes, steps_per_day, water_intake_liters, diet_notes, symptom_notes, resting_heart_rate, blood_pressure_systolic, blood_pressure_diastolic"
                    },
                    "value": {"type": "string", "description": "Value to record (numbers as strings, e.g. '7.5' for sleep hours)"}
                },
                "required": ["field", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_history",
            "description": "Read historical health data for a tracked field to analyze trends, averages, and patterns over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Field to retrieve history for (e.g. sleep_hours, mood, weight)"},
                    "days": {"type": "integer", "description": "Number of past days to retrieve (default 30)", "default": 30}
                },
                "required": ["field"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "call_specialist",
            "description": "Consult a specialist health agent for expert advice on a specific topic. Use when the question falls outside your primary domain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": ["diet", "exercise", "protect", "sleep", "mental_health", "relationships", "environment", "custom"],
                        "description": "Which specialist to consult"
                    },
                    "question": {"type": "string", "description": "Specific question to ask the specialist (provide full context)"}
                },
                "required": ["agent", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "queue_notification",
            "description": "Schedule a notification or reminder for the user (e.g. follow-up check, medication reminder, goal reminder).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Notification text shown to the user (max 25 words, specific and actionable)"},
                    "agent": {"type": "string", "description": "Agent ID to associate with this notification"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_sticker_board",
            "description": "Read the user's emoji sticker board showing recent daily check-ins across health areas (sleep, diet, exercise, mental_health, relationships, environment, protect).",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many recent days to include (default 14)", "default": 14}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_sticker",
            "description": "Record an emoji sticker on the user's health board for a specific area and date. Use when the user shares how they're doing in a health area — after a poll answer or when they volunteer info conversationally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "enum": ["sleep", "diet", "exercise", "mental_health", "relationships", "environment", "protect"],
                        "description": "Health area for the sticker"
                    },
                    "emoji": {"type": "string", "description": "The emoji reflecting how things went"},
                    "prompt": {"type": "string", "description": "The question asked or context (stored hidden under sticker)"},
                    "response": {"type": "string", "description": "User's text response if any (stored hidden, can be empty)"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format (defaults to today)"}
                },
                "required": ["area", "emoji"]
            }
        }
    }
]



def _is_numeric(s):
    try:
        float(str(s).replace(',', ''))
        return True
    except ValueError:
        return False


def _read_history_for_tool(user, field, days=30):
    """Return formatted history string for a field."""
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    entries = [e for e in user.get('profile_history', {}).get(field, [])
               if e.get('ts', '') >= cutoff]
    if not entries:
        return f"No history for {field} in the last {days} days."
    nums = [float(e['v']) for e in entries if _is_numeric(e['v'])]
    summary = f"{field} — {len(entries)} entries over {days} days"
    if nums:
        avg = sum(nums) / len(nums)
        summary += f" | avg {avg:.1f}, min {min(nums):.1f}, max {max(nums):.1f}"
    recent = entries[-10:]
    rows = "  ".join(f"{e['ts']}:{e['v']}" for e in recent)
    return f"{summary}\nRecent: {rows}"


def _execute_health_tool(name, inputs, user_id, agent_id):
    """Execute a health tool call and return a plain-text result string."""
    try:
        if name == "read_profile":
            u = get_user_data(user_id) if user_id else {}
            profile = (u or {}).get('profile', {})
            if not profile:
                return "Profile is empty — no data yet."
            return f"Current profile:\n{json.dumps(profile, indent=2)}"

        elif name == "update_profile":
            field = (inputs.get("field") or "").strip()
            value = (inputs.get("value") or "").strip()
            if not field or not value:
                return "Error: field and value are required."
            if user_id:
                u = get_user_data(user_id)
                if u:
                    u.setdefault('profile', {})[field] = value
                    u['last_updated'] = datetime.utcnow().isoformat()
                    _cache_user(user_id, u)
                    s3_storage.save_user(user_id, u)
            return f"Saved profile.{field} = {value!r}"

        elif name == "log_health_data":
            field = (inputs.get("field") or "").strip()
            value = (inputs.get("value") or "").strip()
            if not field or not value:
                return "Error: field and value are required."
            if field not in TRACKABLE_FIELDS:
                return f"Error: {field!r} is not a trackable field. Trackable: {', '.join(sorted(TRACKABLE_FIELDS))}"
            date = datetime.utcnow().strftime('%Y-%m-%d')
            if user_id:
                u = get_user_data(user_id)
                if u:
                    _append_history(u, field, value)
                    # Do NOT write to profile — trackable data lives in profile_history and sticker board
                    u['last_updated'] = datetime.utcnow().isoformat()
                    _cache_user(user_id, u)
                    s3_storage.save_user(user_id, u)
            return f"Logged: {field} = {value} on {date}"

        elif name == "read_history":
            field = (inputs.get("field") or "").strip()
            days = int(inputs.get("days") or 30)
            if not field:
                return "Error: field is required."
            if user_id:
                u = get_user_data(user_id)
                if u:
                    return _read_history_for_tool(u, field, days)
            return "User ID required to read history."

        elif name == "call_specialist":
            target = (inputs.get("agent") or "").strip()
            question = (inputs.get("question") or "").strip()
            if not target or not question:
                return "Error: agent and question are required."
            target_module = agent_registry.get_agent(target)
            if not target_module:
                return f"Error: unknown agent {target!r}"
            u = get_user_data(user_id) if user_id else {}
            profile = (u or {}).get('profile', {})
            specialist_resp = _run_agent(target, question, profile, "")
            name_str = getattr(target_module, 'AGENT_NAME', target)
            return f"{name_str} says: {specialist_resp or '(no response)'}"

        elif name == "queue_notification":
            message = (inputs.get("message") or "").strip()
            notif_agent = (inputs.get("agent") or agent_id or "doc").strip()
            if not message:
                return "Error: message is required."
            if user_id:
                u = get_user_data(user_id)
                if u:
                    notif = {
                        "id": str(uuid.uuid4()),
                        "type": f"{notif_agent}_reminder",
                        "agent": notif_agent,
                        "message": message,
                        "created": datetime.utcnow().isoformat(),
                        "read": False
                    }
                    u.setdefault('notifications', []).append(notif)
                    u['notifications'] = u['notifications'][-20:]
                    _cache_user(user_id, u)
                    s3_storage.save_user(user_id, u)
            return f"Notification queued: {message!r}"

        elif name == "read_sticker_board":
            days = int(inputs.get("days") or 14)
            if not user_id:
                return "User ID required to read sticker board."
            return _read_sticker_board_for_tool(user_id, days)

        elif name == "write_sticker":
            area = (inputs.get("area") or "").strip()
            emoji = (inputs.get("emoji") or "").strip()
            prompt = (inputs.get("prompt") or "").strip()
            response = (inputs.get("response") or "").strip()
            date = (inputs.get("date") or datetime.utcnow().strftime('%Y-%m-%d')).strip()
            if not area or not emoji:
                return "Error: area and emoji are required."
            if area not in stickers_module.STICKER_AREAS:
                return f"Error: area must be one of {stickers_module.STICKER_AREAS}"
            if user_id:
                _write_sticker_entry(user_id, area, date, emoji, prompt, response)
            return f"Sticker recorded: {area} {emoji} on {date}"

        else:
            return f"Unknown tool: {name!r}"

    except Exception as e:
        print(f"[Tool] Error in {name}: {e}")
        return f"Tool error: {e}"


def _run_agentic_loop(messages, system_prompt, user_id, agent_id, max_steps=6):
    """
    Core agentic loop via ListeningAI ChatController.

    GreenDial owns health tool handlers; ListeningAI owns the LLM + tool loop.
    Falls back to a local loop (still using ListeningAI completions via utils)
    only if the controller itself cannot be imported.
    Returns (final_text, profile_updates_dict, model_used).
    """
    try:
        import listening_bridge
        final_text, profile_updates, model_used = listening_bridge.run_agentic_loop(
            messages=messages,
            system_prompt=system_prompt,
            user_id=user_id,
            agent_id=agent_id,
            max_steps=max_steps,
        )
        print(f"[AgentLoop] ListeningAI run_loop done model={model_used}")
        return final_text, profile_updates, model_used
    except Exception as e:
        print(f"[AgentLoop] ListeningAI controller unavailable ({e}); using local loop")

    # ---- local loop using ListeningAI completions (utils → listening_ai.llm) ----
    final_text = ""
    profile_updates = {}
    model_used = config.OPENROUTER_TOOLS_MODEL
    working = list(messages)

    for step in range(max_steps):
        resp = utils.completion_with_tools(
            messages=working,
            tools=HEALTH_TOOLS,
            system_prompt=system_prompt
        )

        if resp.get("error"):
            print(f"[AgentLoop] Error at step {step}: {resp['error']} — falling back")
            last_user_content = next(
                (m["content"] for m in reversed(working) if m.get("role") == "user"), ""
            )
            final_text = utils.completion(
                prompt=last_user_content,
                system_prompt=system_prompt,
                temperature=config.LLM_TEMPERATURE
            )
            model_used = utils.get_last_model_used() or config.OPENROUTER_MODEL
            break

        if resp.get("model_used"):
            model_used = resp["model_used"]

        if resp.get("text"):
            final_text = resp["text"]

        tool_uses = resp.get("tool_uses") or resp.get("tool_calls") or []
        if not tool_uses or resp.get("stop_reason") == "end_turn":
            break

        raw = resp.get("raw_content") or resp.get("raw_message")
        if raw:
            working.append(raw)

        tool_results = []
        for tc in tool_uses:
            result = _execute_health_tool(tc["name"], tc["input"], user_id, agent_id)
            if tc["name"] in ("update_profile", "log_health_data"):
                f = tc["input"].get("field", "")
                v = tc["input"].get("value", "")
                if f and v:
                    profile_updates[f] = v
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })
            print(f"[AgentLoop] step={step} {tc['name']}({tc['input']}) → {str(result)[:80]}")

        working.extend(tool_results)

    if not final_text:
        resp = utils.completion_with_tools(
            messages=working,
            tools=HEALTH_TOOLS,
            system_prompt=system_prompt
        )
        final_text = resp.get("text") or "Done."
        if resp.get("model_used"):
            model_used = resp["model_used"]

    return final_text, profile_updates, model_used


def _save_profile_updates_from_tools(user_id, updates):
    """Apply tool-originated profile updates with history tracking and save."""
    if not updates or not user_id:
        return None
    u = get_user_data(user_id)
    if not u:
        return None
    updated = _apply_profile_updates_with_history(u, updates)
    u['last_updated'] = datetime.utcnow().isoformat()
    _cache_user(user_id, u)
    try:
        s3_storage.save_user(user_id, u)
    except Exception as e:
        print(f"[AgentLoop] Profile save error: {e}")
    return updated


def _parse_agent_dispatch(doc_response):
    """Extract **CALL_AGENT** directive from Doc's raw response, if present."""
    import re
    pattern = r'\*\*CALL_AGENT\*\*\s*(\{[^{}]*\})'
    match = re.search(pattern, doc_response, re.IGNORECASE)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get('agent')
        except json.JSONDecodeError:
            pass
    return None


def _parse_redirect(doc_response):
    """Extract **REDIRECT_TO** directive from Doc's response."""
    match = re.search(r'\*\*REDIRECT_TO\*\*\s*(\{[^{}]*\})', doc_response, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1)).get('agent')
        except json.JSONDecodeError:
            pass
    return None


def _clean_agent_directive(response):
    """Remove **CALL_AGENT** and **REDIRECT_TO** markers from response text."""
    cleaned = re.sub(r'\*\*CALL_AGENT\*\*\s*\{[^{}]*\}', '', response, flags=re.IGNORECASE)
    cleaned = re.sub(r'\*\*REDIRECT_TO\*\*\s*\{[^{}]*\}', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _parse_action_markers(response):
    """Extract **ACTION** directives from Doc's response."""
    actions = []
    for match in re.finditer(r'\*\*ACTION\*\*\s*(\{[^{}]*\})', response, re.IGNORECASE):
        try:
            actions.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass
    return actions


def _clean_action_markers(response):
    """Remove **ACTION** markers from response text."""
    cleaned = re.sub(r'\*\*ACTION\*\*\s*\{[^{}]*\}', '', response, flags=re.IGNORECASE)
    return cleaned.strip()


def _execute_chat_actions(user_id, actions):
    """Execute a list of ACTION dicts from Doc; return list of result strings."""
    results = []
    for action in actions:
        action_type = action.get('type')
        try:
            if action_type == 'accept_suggestion':
                handle_accept_suggestion(user_id, action.get('id', ''))
                results.append('suggestion_accepted')
            elif action_type == 'dismiss_suggestion':
                handle_dismiss_suggestion(user_id, action.get('id', ''))
                results.append('suggestion_dismissed')
            elif action_type == 'complete_activity':
                handle_update_activity(user_id, action.get('id', ''), {'status': 'completed'})
                results.append('activity_completed')
            elif action_type == 'abandon_activity':
                handle_update_activity(user_id, action.get('id', ''), {'status': 'abandoned'})
                results.append('activity_abandoned')
            elif action_type == 'dismiss_notification':
                handle_dismiss_notification(user_id, action.get('id', ''))
                results.append('notification_dismissed')
            elif action_type == 'submit_feedback':
                message = (action.get('message') or '').strip()
                username = (action.get('username') or '').strip()
                if not username:
                    u = get_user_data(user_id)
                    username = (u or {}).get('username', 'Guest')
                if message:
                    handle_post_feedback({'message': message, 'username': username})
                    results.append('feedback_submitted')
            elif action_type == 'update_settings':
                key = action.get('key', '')
                value = action.get('value')
                if key and value is not None:
                    handle_update_settings(user_id, {key: value})
                    results.append(f'settings_updated:{key}:{json.dumps(value)}')
            elif action_type == 'clear_history':
                handle_clear_transcript(user_id)
                results.append('history_cleared')
        except Exception as e:
            print(f"[Chat] Action failed: {action_type} — {e}")
    return results


def _build_injected_context(user, user_input_lower):
    """Inject live data into Doc's prompt based on message keywords."""
    parts = []

    # Always inject today's pending suggestions so Doc can proactively surface them
    suggestions = [s for s in user.get('suggestions', []) if s.get('status') == 'pending'][:3]
    if suggestions:
        lines = ['## TODAY\'S SUGGESTIONS']
        for i, s in enumerate(suggestions, 1):
            agent = s.get('agent_id', '')
            text = s.get('text', '')
            sid = s.get('id', '')
            price = f" 💰{s['price']} {s.get('currency','ETH')}" if s.get('price') else ''
            lines.append(f"{i}. [{agent}]{price} {text} (id: {sid})")
        parts.append('\n'.join(lines))

    if any(kw in user_input_lower for kw in ('activit', 'task', 'todo', 'to-do', 'done', 'finish', 'complet', 'abandon', 'log')):
        activities = [a for a in user.get('activities', []) if a.get('status') == 'active']
        if activities:
            lines = ['## ACTIVITIES (active)']
            for i, a in enumerate(activities[:5], 1):
                lines.append(f"{i}. [{a.get('agent_id','')}] {a.get('text','')} (id: {a.get('id','')})")
            parts.append('\n'.join(lines))

    if any(kw in user_input_lower for kw in ('notif', 'reminder', 'alert', 'dismiss', 'unread')):
        notifs = [n for n in user.get('notifications', []) if not n.get('read') and n.get('type') != 'sticker_poll']
        if notifs:
            lines = ['## TIPS & REMINDERS (unread)']
            for i, n in enumerate(notifs[:5], 1):
                lines.append(f"{i}. [{n.get('agent','')}] {n.get('message','')} (id: {n.get('id','')})")
            parts.append('\n'.join(lines))

    if any(kw in user_input_lower for kw in ('setting', 'preference', 'notification', 'style', 'tone', 'mode')):
        settings = user.get('settings', {})
        parts.append('## SETTINGS\n' + ', '.join([
            f"notifications: {'on' if settings.get('notifications_enabled', True) else 'off'}",
            f"doc_style: {settings.get('doc_style', 'questioning')}",
            f"chat_only_mode: {settings.get('chat_only_mode', True)}",
        ]))

    if any(kw in user_input_lower for kw in ('help', 'what can you', 'how do i', 'what can i', 'how does', 'what is chat')):
        parts.append(f"## CHAT-ONLY HELP\n{chat_only_module.HELP_TEXT}")

    return '\n\n'.join(parts) if parts else None


def _run_agent(agent_id, user_input, profile, recent_transcript):
    """Run a specialist agent and return its raw text response."""
    module = agent_registry.get_agent(agent_id)
    if not module:
        return None
    system_prompt = getattr(module, 'SYSTEM_PROMPT', None)

    agent_prompt = (
        f"Profile:\n{json.dumps(profile, indent=2) if profile else '{}'}\n\n"
        f"Recent:\n{recent_transcript or '(start of conversation)'}\n\n"
        f"User: {user_input}\n\n"
        f"Respond in 2-4 sentences. Use **PROFILE_UPDATE** if the user shared health info."
    )

    try:
        return utils.completion(
            prompt=agent_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )
    except Exception as e:
        print(f"[Agent] {agent_id} failed: {e}")
        return None


def _check_onboarding_needed(user):
    """Return (agent_id, turn_number) if a subscribed agent needs onboarding, else (None, 0)."""
    settings = user.get('settings', {})
    subscriptions = settings.get('agent_subscriptions', [])
    agent_prefs = settings.get('agent_prefs', {})
    profile = user.get('profile', {})

    for agent_id in subscriptions:
        if agent_registry.needs_onboarding(agent_id, profile, agent_prefs):
            turn = agent_prefs.get(agent_id, {}).get('onboard_turns', 0)
            if turn < 3:
                return agent_id, turn + 1
    return None, 0


def _run_agent_onboarding(agent_id, user_input, profile, transcript, turn_number):
    """Run an agent in onboarding/interview mode. Returns agent response text."""
    module = agent_registry.get_agent(agent_id)
    if not module:
        return None

    prompt = agent_base.build_onboarding_prompt(
        module=module,
        profile=profile,
        transcript=transcript[-1000:] if transcript else '',
        turn_number=turn_number
    )
    system_prompt = getattr(module, 'SYSTEM_PROMPT', None)
    try:
        return utils.completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=config.LLM_MAX_TOKENS
        )
    except Exception as e:
        print(f"[Onboarding] {agent_id} failed: {e}")
        return None


def _advance_onboarding(user, agent_id, turn_number):
    """Increment onboard_turns; mark onboarded if turn >= 3 or profile complete."""
    settings = user.setdefault('settings', {})
    agent_prefs = settings.setdefault('agent_prefs', {})
    prefs = agent_prefs.setdefault(agent_id, {})
    prefs['onboard_turns'] = turn_number
    profile = user.get('profile', {})
    missing = agent_registry.get_missing_onboarding_fields(agent_id, profile)
    if turn_number >= 3 or len(missing) == 0:
        prefs['onboarded'] = True
        print(f"[Onboarding] {agent_id} onboarding complete for {user.get('user_id')}")


def _run_cross_ai(matched_agent_ids, user_input, profile, transcript):
    """Run up to 3 specialist agents then synthesize with Cross AI. Returns synthesis text."""
    import concurrent.futures
    agents_to_run = matched_agent_ids[:3]

    specialist_responses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_run_agent, aid, user_input, profile, transcript): aid
            for aid in agents_to_run
        }
        for future in concurrent.futures.as_completed(futures, timeout=12):
            aid = futures[future]
            try:
                result = future.result()
                if result:
                    specialist_responses[aid] = result
            except Exception as e:
                print(f"[CrossAI] Agent {aid} failed: {e}")

    if not specialist_responses:
        return None

    cross_ai_module = agent_registry.get_agent('cross_ai')
    if not cross_ai_module:
        return None

    # Build synthesis prompt
    specialist_block = "\n\n".join(
        f"--- {agent_registry.REGISTRY[aid].AGENT_NAME} ---\n{resp}"
        for aid, resp in specialist_responses.items()
    )
    synthesis_prompt = f"""You are the Cross AI Coordinator. Synthesize these specialist perspectives into one cohesive, actionable response.

USER'S PROFILE:
{json.dumps(profile, indent=2) if profile else '{{}}'}

USER'S QUESTION:
{user_input}

SPECIALIST PERSPECTIVES:
{specialist_block}

Provide an integrated, holistic response (3-5 sentences). Connect the insights. End with ONE prioritized recommendation.
Emit **PROFILE_UPDATE** if the user shared new health info."""

    try:
        return utils.completion(
            prompt=synthesis_prompt,
            system_prompt=cross_ai_module.SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=config.LLM_MAX_TOKENS
        )
    except Exception as e:
        print(f"[CrossAI] Synthesis failed: {e}")
        return None


# ============ NOTIFICATIONS ============

def handle_get_notifications(user_id):
    """Get user notifications"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"notifications": []})
    
    notifications = user.get('notifications', [])
    # Only return unread or recent (last 10)
    return json.dumps({"notifications": notifications[-10:]})


def handle_dismiss_notification(user_id, notification_id):
    """Dismiss a notification"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    notifications = user.get('notifications', [])
    user['notifications'] = [n for n in notifications if n.get('id') != notification_id]
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[Notifications] Failed to dismiss: {e}")
    
    return json.dumps({"success": True})


def handle_get_today(user_id):
    """Single endpoint returning check-ins (all 7 areas), pending suggestions, and tips."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    today = datetime.utcnow().strftime('%Y-%m-%d')
    board = _get_or_create_sticker_board(user_id)
    rows = board.get('rows', {})

    check_ins = []
    for area in stickers_module.STICKER_AREAS:
        entry = rows.get(area, {}).get(today)
        template = stickers_module.POLL_TEMPLATES.get(area, {})
        area_label = stickers_module.AREA_LABELS.get(area, area)
        if entry:
            check_ins.append({
                "area": area, "area_label": area_label,
                "answered": True, "emoji": entry.get("emoji"), "prompt": entry.get("prompt"),
            })
        else:
            check_ins.append({
                "area": area, "area_label": area_label, "answered": False,
                "message": template.get("question", f"How is your {area_label.lower()} today?"),
                "emoji_options": stickers_module.build_poll_options(area, f"{user_id}:{area}:{today}"),
            })

    suggestions = [s for s in user.get('suggestions', []) if s.get('status') == 'pending'][:3]
    other_notifs = [n for n in user.get('notifications', []) if n.get('type') != 'sticker_poll'][-10:]

    unanswered = sum(1 for c in check_ins if not c['answered'])
    badge = unanswered + len(suggestions)

    return json.dumps({
        "check_ins": check_ins,
        "suggestions": suggestions,
        "notifications": other_notifs,
        "badge_count": badge,
    })


def _get_agent_transcript(user, agent_id):
    """Return the transcript for a specific agent."""
    return user.get('agent_transcripts', {}).get(agent_id, '')


def _update_agent_transcript(user_id, user, agent_id, user_input, agent_response):
    """Append a turn to the agent-specific transcript and save."""
    timestamp = datetime.utcnow().isoformat()
    agent_name = agent_id.replace('_', ' ').title()
    transcripts = user.setdefault('agent_transcripts', {})
    existing = transcripts.get(agent_id, '')
    existing += f"\n[{timestamp}] User: {user_input}\n[{timestamp}] {agent_name}: {agent_response}"
    lines = existing.split('\n')
    if len(lines) > 300:
        existing = '\n'.join(lines[-300:])
    transcripts[agent_id] = existing
    user['last_updated'] = timestamp


def handle_agent_chat(agent_id, request):
    """Direct chat with a specialist agent — uses real agentic tool loop (Gemini Flash)."""
    module = agent_registry.get_agent(agent_id)
    if not module:
        return json.dumps({"error": f"Unknown agent: {agent_id}"}), 404

    user_id = request.get('user_id')
    session_id = request.get('session_id') or str(uuid.uuid4())
    user_input = (request.get('text') or '').strip()
    is_init = request.get('init', False) or not user_input
    followup_context = (request.get('context') or '').strip()

    user = get_user_data(user_id) if user_id else {}
    transcript = _get_agent_transcript(user, agent_id) if user else ''
    recent = _get_recent_transcript(transcript, max_lines=6)

    agent_name = getattr(module, 'AGENT_NAME', agent_id)
    agent_intro = getattr(module, 'ONBOARDING_INTRO', '')
    agent_system = getattr(module, 'SYSTEM_PROMPT', '')

    # Combine agent persona with shared profile syntax and tool rules
    full_system = f"{agent_system}\n\n{PROFILE_UPDATE_SYNTAX}\n\n{TOOL_USE_INSTRUCTIONS}"

    # Build initial user message for the loop
    if is_init and followup_context:
        init_user_msg = (
            f"NOTIFICATION CONTEXT: {followup_context}\n\n"
            f"First call read_profile. Then ask ONE specific, warm check-in question "
            f"based on the context and profile. Do NOT re-introduce yourself."
        )
    elif is_init:
        init_user_msg = (
            f"The user just opened your chat for the first time. "
            f"First call read_profile to see what we know. "
            f"Then introduce yourself in 1 sentence and ask your most important opening question."
        )
    else:
        style_hint = style_module.build_style_instruction(user_input, transcript)
        recent_block = f"Recent conversation:\n{recent}\n\n" if recent else ""
        init_user_msg = f"{recent_block}STYLE: {style_hint}\n\nUser says: {user_input}"

    messages = [{"role": "user", "content": init_user_msg}]

    # Run the agentic loop
    final_text, tool_profile_updates, model_used = _run_agentic_loop(
        messages=messages,
        system_prompt=full_system,
        user_id=user_id,
        agent_id=agent_id,
        max_steps=6
    )

    # Also parse any old-style **PROFILE_UPDATE** markers (belt + suspenders)
    text_profile_updates = _parse_profile_updates(final_text)
    all_updates = {**tool_profile_updates, **text_profile_updates}

    # Save all profile updates
    updated_profile = _save_profile_updates_from_tools(user_id, all_updates) if all_updates else None

    clean_response = _clean_profile_markers(final_text)

    # Save transcript
    if user_id:
        u = get_user_data(user_id)
        if u:
            timestamp = datetime.utcnow().isoformat()
            agent_name_key = agent_id.replace('_', ' ').title()
            transcripts = u.setdefault('agent_transcripts', {})
            if is_init:
                existing = transcripts.get(agent_id, '')
                existing += f"\n[{timestamp}] {agent_name_key}: {clean_response}"
                transcripts[agent_id] = existing
            else:
                _update_agent_transcript(user_id, u, agent_id, user_input, clean_response)
            u['last_updated'] = timestamp
            _cache_user(user_id, u)
            try:
                s3_storage.save_user(user_id, u)
            except Exception as e:
                print(f"[AgentChat] Transcript save error: {e}")

    result = {
        "response": clean_response,
        "session_id": session_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "model_used": model_used
    }
    if updated_profile:
        result["profile_updated"] = True
        result["profile"] = updated_profile
    return json.dumps(result)


def handle_task(request):
    """Task mode for Doc — agentic loop for complex health tasks (Gemini Flash)."""
    user_id = request.get('user_id')
    task_text = (request.get('text') or '').strip()

    if not task_text:
        return json.dumps({"response": "What would you like me to help with?", "user_id": user_id})

    DOC_TASK_SYSTEM = f"""You are Doc, GreenDial's primary health coordinator. You have real tools.

{TOOL_USE_INSTRUCTIONS}

Your goal: Complete the user's health task using tools.
- Read the profile first to understand their context
- Log any data they provide (sleep, weight, mood, exercise, etc.)
- Consult specialists for domain-specific depth
- Give a clear, specific, actionable response when done
Be concise and direct — this is task mode, not open-ended chat."""

    messages = [{"role": "user", "content": task_text}]

    final_text, tool_updates, model_used = _run_agentic_loop(
        messages=messages,
        system_prompt=DOC_TASK_SYSTEM,
        user_id=user_id,
        agent_id="doc",
        max_steps=8
    )

    text_updates = _parse_profile_updates(final_text)
    all_updates = {**tool_updates, **text_updates}
    updated_profile = _save_profile_updates_from_tools(user_id, all_updates) if all_updates else None

    clean = _clean_profile_markers(final_text)

    if user_id:
        _update_transcript(user_id, task_text, clean)

    result = {"response": clean, "user_id": user_id, "model_used": model_used}
    if updated_profile:
        result["profile_updated"] = True
        result["profile"] = updated_profile
    return json.dumps(result)


def handle_get_agent_transcripts(user_id):
    """Return Doc transcript + all agent transcripts for the user."""
    if not user_id:
        return json.dumps({"doc_transcript": "", "agents": {}})
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"doc_transcript": "", "agents": {}})
    return json.dumps({
        "doc_transcript": user.get('transcript', ''),
        "agents": user.get('agent_transcripts', {})
    })


def handle_clear_agent_transcript(user_id, agent_id):
    """Clear one agent's transcript."""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    if agent_id == 'doc':
        user['transcript'] = ''
    else:
        user.setdefault('agent_transcripts', {}).pop(agent_id, None)
    user['last_updated'] = datetime.utcnow().isoformat()
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[AgentChat] Failed to clear transcript: {e}")
    return json.dumps({"success": True})


def generate_login_notifications(user_id):
    """Background task to generate contextual notifications"""
    import time
    
    # Wait a moment to not impact login response time
    time.sleep(2)
    
    user = get_user_data(user_id)
    if not user:
        return
        
    if not user.get('settings', {}).get('notifications_enabled', True):
        return

    # Check if we generated notifications recently (5 min debounce)
    last_gen = user.get('last_notification_gen')
    if last_gen:
        try:
            last_dt = datetime.fromisoformat(last_gen.replace('Z', '+00:00'))
            if (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds() < 300:
                return
        except:
            pass

    transcript = user.get('transcript', '')
    profile = user.get('profile', {})
    
    prompt = notifications.USER_TEMPLATE.format(
        profile_json=json.dumps(profile, indent=2),
        transcript=transcript[-2000:] if transcript else ""
    )
    
    response = utils.completion(
        prompt=prompt,
        system_prompt=notifications.SYSTEM_PROMPT,
        temperature=0.7,
        max_tokens=400
    )
    
    try:
        # Extract JSON
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        data = json.loads(text)
        new_notes = data.get('notifications', [])
        
        if new_notes:
            # Re-fetch before save: the LLM call takes seconds and another
            # request (e.g. login rotating the session token) may have written
            # the user record since we loaded it. Merge onto the fresh copy.
            try:
                fresh = s3_storage.get_user(user_id)
                if fresh:
                    user = fresh
            except Exception:
                pass
            current_notes = user.get('notifications', [])

            # Add IDs and timestamps
            for note in new_notes:
                note['id'] = str(uuid.uuid4())
                note['created'] = datetime.utcnow().isoformat()
                note['read'] = False
                current_notes.append(note)

            # Limit to 20
            user['notifications'] = current_notes[-20:]
            user['last_notification_gen'] = datetime.utcnow().isoformat()

            s3_storage.save_user(user_id, user)
            _cache_user(user_id, user)
            print(f"[Notifications] Generated {len(new_notes)} for {user_id}")
            
    except Exception as e:
        print(f"[Notifications] Generation failed: {e}")


def generate_notification(user_id):
    """Generate a contextual notification for the user (called periodically or on login)"""
    user = get_user_data(user_id)
    if not user:
        return None
    
    if not user.get('settings', {}).get('notifications_enabled', True):
        return None
    
    profile = user.get('profile', {})
    username = user.get('username', 'there')
    
    # Don't spam - check last notification time
    notifications = user.get('notifications', [])
    if notifications:
        last_time = notifications[-1].get('created')
        if last_time:
            try:
                last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                if (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds() < 3600:
                    return None  # Less than 1 hour ago
            except:
                pass
    
    notification = None
    
    # Priority: incomplete profile > goal reminder > tip
    missing_fields = []
    important_fields = ['primary_concern', 'health_conditions', 'goals']
    for field in important_fields:
        if not profile.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        field = missing_fields[0]
        field_names = {
            'primary_concern': 'your main health focus',
            'health_conditions': 'any health conditions',
            'goals': 'your health goals'
        }
        notification = {
            "id": str(uuid.uuid4()),
            "type": "profile_incomplete",
            "message": f"I'd love to learn more about {field_names.get(field, field)}. Share when you're ready!",
            "created": datetime.utcnow().isoformat(),
            "read": False
        }
    elif profile.get('goals'):
        goals = profile['goals']
        goal = goals[0] if isinstance(goals, list) else goals
        notification = {
            "id": str(uuid.uuid4()),
            "type": "goal_reminder",
            "message": f"How's your progress on: {goal}?",
            "created": datetime.utcnow().isoformat(),
            "read": False
        }
    else:
        tip = random.choice(doc_v2.HEALTH_TIPS)
        notification = {
            "id": str(uuid.uuid4()),
            "type": "tip",
            "message": tip,
            "created": datetime.utcnow().isoformat(),
            "read": False
        }
    
    if notification:
        user.setdefault('notifications', []).append(notification)
        # Keep only last 20 notifications
        user['notifications'] = user['notifications'][-20:]
        try:
            s3_storage.save_user(user_id, user)
            _cache_user(user_id, user)
        except:
            pass
    
    return notification


def handle_generate_notification(user_id):
    """API handler to generate a notification"""
    notification = generate_notification(user_id)
    if notification:
        return json.dumps({"notification": notification})
    return json.dumps({"notification": None})


# ============ STICKER BOARD ============

def _get_or_create_sticker_board(user_id):
    """Load sticker board from S3, creating an empty one if absent."""
    try:
        board = s3_storage.get_sticker_board(user_id)
    except Exception as e:
        print(f"[Stickers] Load error for {user_id}: {e}")
        board = None
    if not board:
        board = {
            "user_id": user_id,
            "token": None,
            "rows": {area: {} for area in stickers_module.STICKER_AREAS}
        }
    return board


def _write_sticker_entry(user_id, area, date, emoji, prompt, response):
    """Write a single sticker entry to the user's board."""
    board = _get_or_create_sticker_board(user_id)
    board.setdefault('rows', {}).setdefault(area, {})[date] = {
        "emoji": emoji,
        "prompt": prompt,
        "response": response,
        "ts": datetime.utcnow().isoformat()
    }
    try:
        s3_storage.save_sticker_board(user_id, board)
    except Exception as e:
        print(f"[Stickers] Save error for {user_id}: {e}")


def _read_sticker_board_for_tool(user_id, days=14):
    """Return a compact text summary of the sticker board for LLM context."""
    from datetime import timedelta
    board = _get_or_create_sticker_board(user_id)
    rows = board.get('rows', {})
    if not any(rows.get(a) for a in stickers_module.STICKER_AREAS):
        return "Sticker board is empty — no daily check-ins recorded yet."

    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    lines = [f"Sticker board (last {days} days):"]
    for area in stickers_module.STICKER_AREAS:
        entries = {d: e for d, e in rows.get(area, {}).items() if d >= cutoff}
        if not entries:
            lines.append(f"  {stickers_module.AREA_LABELS[area]}: (no data)")
        else:
            recent = sorted(entries.items())[-7:]
            dots = "  ".join(f"{d}:{e['emoji']}" for d, e in recent)
            lines.append(f"  {stickers_module.AREA_LABELS[area]}: {dots}")
    return "\n".join(lines)


def _build_sticker_context_for_doc(user_id):
    """Build a brief sticker board summary to inject into Doc's prompt."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    board = _get_or_create_sticker_board(user_id)
    rows = board.get('rows', {})

    filled_today = []
    missing_today = []
    for area in stickers_module.STICKER_AREAS:
        entry = rows.get(area, {}).get(today)
        label = stickers_module.AREA_LABELS[area]
        if entry:
            filled_today.append(f"{label}: {entry['emoji']}")
        else:
            missing_today.append(label)

    parts = []
    if filled_today:
        parts.append("Today filled: " + ", ".join(filled_today))
    if missing_today:
        parts.append("Not yet filled: " + ", ".join(missing_today))
    return "\n".join(parts) if parts else None


def _get_or_create_share_token(user_id):
    """Return existing share token for user, creating one if needed."""
    board = _get_or_create_sticker_board(user_id)
    token = board.get('token')
    if not token:
        import secrets
        token = secrets.token_urlsafe(9)  # ~12 chars, URL-safe
        board['token'] = token
        try:
            s3_storage.save_sticker_board(user_id, board)
            s3_storage.save_sticker_token(token, user_id)
        except Exception as e:
            print(f"[Stickers] Token create error: {e}")
    return token


def handle_get_sticker_board(user_id):
    """Authenticated: return the user's sticker board + share token."""
    board = _get_or_create_sticker_board(user_id)
    token = board.get('token') or _get_or_create_share_token(user_id)
    board_data = {
        "rows": board.get('rows', {}),
        "token": token,
        "share_url": f"/stickers/{token}"
    }
    return json.dumps(board_data)


def handle_write_sticker(user_id, data):
    """Authenticated: write a sticker entry."""
    area = (data.get('area') or '').strip()
    emoji = (data.get('emoji') or '').strip()
    prompt = (data.get('prompt') or '').strip()
    response = (data.get('response') or '').strip()
    date = (data.get('date') or datetime.utcnow().strftime('%Y-%m-%d')).strip()

    if not area or not emoji:
        return json.dumps({"error": "area and emoji are required"}), 400
    if area not in stickers_module.STICKER_AREAS:
        return json.dumps({"error": f"area must be one of {stickers_module.STICKER_AREAS}"}), 400

    _write_sticker_entry(user_id, area, date, emoji, prompt, response)
    return json.dumps({"ok": True, "area": area, "date": date, "emoji": emoji})


def handle_get_share_token(user_id):
    """Return or generate share token for this user."""
    token = _get_or_create_share_token(user_id)
    return json.dumps({"token": token, "share_url": f"/stickers/{token}"})


def handle_public_sticker_board(token):
    """Public (no auth): return sticker board data by share token."""
    try:
        user_id = s3_storage.get_sticker_token(token)
    except Exception as e:
        print(f"[Stickers] Token lookup error: {e}")
        return json.dumps({"error": "Not found"}), 404
    if not user_id:
        return json.dumps({"error": "Not found"}), 404

    board = _get_or_create_sticker_board(user_id)
    # Return board without user_id
    return json.dumps({
        "rows": board.get('rows', {}),
        "areas": stickers_module.STICKER_AREAS,
        "area_labels": stickers_module.AREA_LABELS,
        "area_emojis": stickers_module.AREA_EMOJIS,
    })


def generate_login_polls(user_id):
    """Background task: generate sticker_poll notifications for areas not yet filled today."""
    import time
    time.sleep(3)

    user = get_user_data(user_id)
    if not user:
        return
    if not user.get('settings', {}).get('notifications_enabled', True):
        return

    # Debounce: only once per day
    last_poll = user.get('last_poll_gen')
    if last_poll:
        try:
            last_date = last_poll[:10]  # YYYY-MM-DD
            if last_date == datetime.utcnow().strftime('%Y-%m-%d'):
                return
        except Exception:
            pass

    today = datetime.utcnow().strftime('%Y-%m-%d')
    board = _get_or_create_sticker_board(user_id)
    rows = board.get('rows', {})

    # Find areas with no sticker today
    unfilled = [a for a in stickers_module.STICKER_AREAS if not rows.get(a, {}).get(today)]
    if not unfilled:
        return  # Board is complete for today

    # Pick 1-2 areas to ask about (rotate: use last asked area to avoid repetition)
    last_areas = user.get('last_poll_areas', [])
    candidates = [a for a in unfilled if a not in last_areas] or unfilled
    to_ask = candidates[:2]

    new_polls = []
    for area in to_ask:
        template = stickers_module.POLL_TEMPLATES.get(area, {})
        if not template:
            continue
        poll = {
            "id": str(uuid.uuid4()),
            "type": "sticker_poll",
            "area": area,
            "message": template["question"],
            "emoji_options": stickers_module.build_poll_options(area, f"{user_id}:{area}:{today}"),
            "area_label": stickers_module.AREA_LABELS.get(area, area),
            "created": datetime.utcnow().isoformat(),
            "read": False
        }
        new_polls.append(poll)

    if not new_polls:
        return

    # Re-fetch fresh copy before writing
    try:
        fresh = s3_storage.get_user(user_id)
        if fresh:
            user = fresh
    except Exception:
        pass

    current_notifs = user.get('notifications', [])
    # Remove any old sticker_polls (replace with fresh ones)
    current_notifs = [n for n in current_notifs if n.get('type') != 'sticker_poll']
    current_notifs.extend(new_polls)
    user['notifications'] = current_notifs[-20:]
    user['last_poll_gen'] = datetime.utcnow().isoformat()
    user['last_poll_areas'] = to_ask

    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
        print(f"[Polls] Generated {len(new_polls)} poll(s) for {user_id}")
    except Exception as e:
        print(f"[Polls] Save error: {e}")


# ============ THIRD-PARTY API ============

def handle_api_profile_update(auth_header, data):
    """Third-party API: Update user profile"""
    user_id, user = verify_basic_auth(auth_header)
    
    if not user_id:
        return json.dumps({"error": "Invalid credentials"}), 401
    
    profile_data = data.get('profile', {})
    if not profile_data:
        return json.dumps({"error": "No profile data provided"}), 400
    
    user.setdefault('profile', {}).update(profile_data)
    user['last_updated'] = datetime.utcnow().isoformat()
    user['last_api_update'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[API] Failed to update profile: {e}")
        return json.dumps({"error": "Failed to save profile"}), 500
    
    return json.dumps({
        "success": True,
        "user_id": user_id,
        "updated_fields": list(profile_data.keys())
    })


def handle_api_profile_get(auth_header):
    """Third-party API: Get user profile"""
    user_id, user = verify_basic_auth(auth_header)
    
    if not user_id:
        return json.dumps({"error": "Invalid credentials"}), 401
    
    return json.dumps({
        "user_id": user_id,
        "username": user.get('username'),
        "profile": user.get('profile', {}),
        "created": user.get('created'),
        "last_updated": user.get('last_updated')
    })


# ============ CHAT ============

def _parse_profile_updates(response):
    """Extract profile updates from Doc's response"""
    updates = {}
    
    # Match both **PROFILE_UPDATE** and **PROFILE UPDATE** (with space or underscore)
    pattern = r'\*\*PROFILE[_ ]UPDATE\*\*\s*(\{[^{}]*\})'
    matches = re.finditer(pattern, response, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            updates.update(data)
            print(f"[Chat] Parsed profile update: {data}")
        except json.JSONDecodeError as e:
            print(f"[Chat] Failed to parse profile update: {json_str} - {e}")
    
    # Fallback: try more flexible matching if nothing found
    if not updates:
        alt_pattern = r'\*\*PROFILE[_ ]UPDATE\*\*\s*\n?\s*(\{[\s\S]*?\})'
        alt_matches = re.finditer(alt_pattern, response, re.IGNORECASE)
        for match in alt_matches:
            json_str = match.group(1).strip()
            json_str = re.sub(r'\s+', ' ', json_str)
            try:
                data = json.loads(json_str)
                updates.update(data)
                print(f"[Chat] Parsed profile update (alt): {data}")
            except json.JSONDecodeError as e:
                print(f"[Chat] Failed alt parse: {json_str} - {e}")
    
    return updates


def _apply_profile_updates(profile, updates):
    """
    Apply updates to profile with support for:
    - Setting fields: {"field": "value"}
    - Deleting fields: {"field": null}
    - Appending to fields: {"field": "+additional value"}
    - Nested objects: {"field": {"subfield": "value"}}
    """
    for key, value in updates.items():
        # Delete field if value is null/None
        if value is None:
            if key in profile:
                del profile[key]
                print(f"[Chat] Deleted profile field: {key}")
        
        # Append if value starts with "+"
        elif isinstance(value, str) and value.startswith('+'):
            append_value = value[1:].strip()
            if key in profile and profile[key]:
                existing = profile[key]
                if isinstance(existing, list):
                    profile[key].append(append_value)
                else:
                    profile[key] = f"{existing}, {append_value}"
            else:
                profile[key] = append_value
            print(f"[Chat] Appended to profile field {key}: {append_value}")
        
        # Merge nested objects
        elif isinstance(value, dict):
            if key not in profile or not isinstance(profile[key], dict):
                profile[key] = {}
            profile[key].update(value)
            print(f"[Chat] Updated nested profile field {key}: {value}")
        
        # Set field normally
        else:
            profile[key] = value
            print(f"[Chat] Set profile field {key}: {value}")

    return profile


def _apply_profile_updates_with_history(user, updates):
    """Apply profile updates and record trackable fields to history."""
    profile = user.setdefault('profile', {})
    _apply_profile_updates(profile, updates)
    for key, value in updates.items():
        if value is not None and key in TRACKABLE_FIELDS:
            _append_history(user, key, value)
    return profile


def _parse_sticker_updates(response):
    """Extract **STICKER_UPDATE** entries from response text."""
    updates = []
    for match in re.finditer(r'\*\*STICKER_UPDATE\*\*\s*(\{[^{}]*\})', response, re.IGNORECASE):
        try:
            data = json.loads(match.group(1))
            if data.get('area') and data.get('emoji'):
                updates.append(data)
        except json.JSONDecodeError:
            pass
    return updates


def _clean_sticker_markers(response):
    """Remove **STICKER_UPDATE** markers from response text."""
    return re.sub(r'\*\*STICKER_UPDATE\*\*\s*\{[^{}]*\}', '', response, flags=re.IGNORECASE).strip()


def _clean_profile_markers(response):
    """Remove profile update markers from response"""
    # Remove both **PROFILE_UPDATE** and **PROFILE UPDATE** variants
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*\{[^{}]*\}', '', response, flags=re.IGNORECASE)
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*\n?\s*\{[\s\S]*?\}', '', cleaned, flags=re.IGNORECASE)
    # Also clean any leftover markers without JSON
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _update_transcript(user_id, user_input, doc_response, session_id=None):
    """Update conversation history"""
    timestamp = datetime.utcnow().isoformat()
    
    if user_id:
        user = get_user_data(user_id)
        transcript = user.get('transcript', '')
        transcript += f"\n[{timestamp}] User: {user_input}\n[{timestamp}] Doc: {doc_response}"
        
        lines = transcript.split('\n')
        if len(lines) > 300:
            transcript = '\n'.join(lines[-300:])
        
        user['transcript'] = transcript
        user['last_updated'] = timestamp
        user['last_chat'] = timestamp
        
        _cache_user(user_id, user)
        try:
            s3_storage.save_user(user_id, user)
        except Exception as e:
            print(f"[Chat] Failed to save transcript: {e}")
    
    if session_id and session_id in _sessions:
        _sessions[session_id]['transcript'] = _sessions[session_id].get('transcript', '') + f"\nUser: {user_input}\nDoc: {doc_response}"
        _sessions[session_id]['last_updated'] = timestamp


def _get_recent_transcript(transcript, max_lines=10):
    """Get recent portion of transcript"""
    if not transcript:
        return ""
    lines = transcript.strip().split('\n')
    return '\n'.join(lines[-max_lines:])


def _get_summary(transcript, max_chars=2000):
    """Get summary of older conversation (placeholder - could use LLM)"""
    if not transcript or len(transcript) < 3000:
        return ""
    # For now, just truncate older content
    # Future: Use LLM to summarize older conversations
    older = transcript[:-2000]
    if len(older) > max_chars:
        older = older[-max_chars:]
    return f"[Earlier conversation covered various health topics]"


def _build_prompt(user_id=None, session_id=None, user_input="", style_hint=None, focus=None):
    """Build Doc's prompt with optional supervisor hints."""
    user = get_user_data(user_id) if user_id else {}
    session = _sessions.get(session_id, {})

    transcript = user.get('transcript', '') or session.get('transcript', '')
    recent_transcript = _get_recent_transcript(transcript, max_lines=10)
    username = user.get('username', 'Guest')
    profile = user.get('profile', {})
    settings = user.get('settings', {})
    chat_only = settings.get('chat_only_mode', True)

    chat_only_instructions = chat_only_module.CHAT_ONLY_INSTRUCTIONS if chat_only else None
    injected_context = _build_injected_context(user, user_input.lower()) if (user_id and chat_only) else None
    sticker_context = _build_sticker_context_for_doc(user_id) if user_id else None

    return doc_v2.build_doc_prompt(
        user_input=user_input,
        profile=profile,
        recent_transcript=recent_transcript,
        username=username,
        history_summary=utils.summarize_history(user),
        style_hint=style_hint,
        focus=focus,
        chat_only_instructions=chat_only_instructions,
        injected_context=injected_context,
        sticker_context=sticker_context
    )


def handle_chat(request):
    """Handle chat with Doc using two-stage LLM completion"""
    user_id = request.get('user_id')
    session_id = request.get('session_id') or str(uuid.uuid4())
    user_input = request.get('text', '').strip()
    
    if session_id not in _sessions:
        _sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "created": datetime.utcnow().isoformat(),
            "transcript": ""
        }
    
    if not user_input:
        return json.dumps({
            "response": "I didn't catch that. What's on your mind?",
            "session_id": session_id,
            "user_id": user_id
        })
    
    # Get user context
    user = get_user_data(user_id) if user_id else {}
    username = user.get('username', 'Guest')
    profile = user.get('profile', {})
    settings = user.get('settings', {})
    transcript = user.get('transcript', '') or _sessions.get(session_id, {}).get('transcript', '')
    recent_transcript = _get_recent_transcript(transcript, max_lines=8)
    
    # ── ONBOARDING CHECK ──────────────────────────────────────────────────────
    # If a newly subscribed agent needs to interview the user, hand off to it.
    onboard_agent_id, onboard_turn = (None, 0)
    if user_id:
        onboard_agent_id, onboard_turn = _check_onboarding_needed(user)

    redirect_agent = None
    if onboard_agent_id:
        print(f"[Chat] Onboarding: {onboard_agent_id} turn {onboard_turn}")
        agent_resp = _run_agent_onboarding(
            onboard_agent_id, user_input, profile, recent_transcript, onboard_turn
        )
        if agent_resp:
            _advance_onboarding(user, onboard_agent_id, onboard_turn)
            doc_response = agent_resp
        else:
            doc_response = "I'm having a little trouble right now — try again in a moment."
    else:
        # ── NORMAL CHAT FLOW ──────────────────────────────────────────────────
        # Check keyword matches — 2+ means Cross AI, 1 means specialist, 0 means Doc alone
        keyword_agents = agent_registry.agents_for_message(user_input)

        # Stage 0: Supervisor analysis — style + focus hints
        style_hint = style_module.build_style_instruction(user_input, recent_transcript)
        sup_hints = supervisor_module.analyze(
            user_input, profile, recent_transcript,
            utils_module=utils, config_module=config
        )
        focus = sup_hints.get("focus") or None

        # Stage 1: Doc generates initial response
        agent_context = None
        try:
            prompt = _build_prompt(
                user_id=user_id,
                session_id=session_id,
                user_input=user_input,
                style_hint=style_hint,
                focus=focus
            )
            doc_response = utils.completion(
                prompt=prompt,
                temperature=0.7,
                max_tokens=config.LLM_MAX_TOKENS
            )
        except Exception as e:
            print(f"[Chat] Completion error: {e}")
            doc_response = "I'm having trouble responding right now. Please try again."

        # Stage 2: Check for redirect first (takes priority over synthesis)
        redirect_agent = _parse_redirect(doc_response)
        if redirect_agent:
            print(f"[Chat] Redirect to: {redirect_agent}")
        else:
            doc_requested_agent = _parse_agent_dispatch(doc_response)
            if len(keyword_agents) >= 2 or doc_requested_agent == 'cross_ai':
                print(f"[Chat] Cross AI: synthesizing {keyword_agents}")
                cross_context = _run_cross_ai(keyword_agents or [doc_requested_agent], user_input, profile, recent_transcript)
                if cross_context:
                    try:
                        prompt_with_agent = doc_v2.build_doc_prompt(
                            user_input=user_input, profile=profile,
                            recent_transcript=recent_transcript, username=username,
                            agent_context=cross_context,
                            history_summary=utils.summarize_history(user),
                            style_hint=style_hint, focus=focus
                        )
                        doc_response = utils.completion(prompt=prompt_with_agent, temperature=0.7, max_tokens=config.LLM_MAX_TOKENS)
                    except Exception as e:
                        print(f"[Chat] Cross AI error: {e}")
            else:
                agent_id = doc_requested_agent or (keyword_agents[0] if keyword_agents else None)
                if agent_id and agent_id != 'cross_ai':
                    print(f"[Chat] Specialist: {agent_id}")
                    agent_context = _run_agent(agent_id, user_input, profile, recent_transcript)
                    if agent_context:
                        try:
                            prompt_with_agent = doc_v2.build_doc_prompt(
                                user_input=user_input, profile=profile,
                                recent_transcript=recent_transcript, username=username,
                                agent_context=agent_context,
                                history_summary=utils.summarize_history(user),
                                style_hint=style_hint, focus=focus
                            )
                            doc_response = utils.completion(prompt=prompt_with_agent, temperature=0.7, max_tokens=config.LLM_MAX_TOKENS)
                        except Exception as e:
                            print(f"[Chat] Agent-augmented error: {e}")

    # Remove any residual markers from the response
    doc_response = _clean_agent_directive(doc_response)

    # Execute and strip ACTION markers (chat-only mode)
    action_results = []
    if user_id:
        actions = _parse_action_markers(doc_response)
        if actions:
            action_results = _execute_chat_actions(user_id, actions)
            doc_response = _clean_action_markers(doc_response)
            print(f"[Chat] Action results: {action_results}")

    # Process sticker updates
    if user_id:
        sticker_updates = _parse_sticker_updates(doc_response)
        for su in sticker_updates:
            area = su.get('area', '')
            emoji = su.get('emoji', '')
            date = su.get('date') or datetime.utcnow().strftime('%Y-%m-%d')
            prompt = su.get('prompt', '')
            response_text = su.get('response', '')
            if area in stickers_module.STICKER_AREAS and emoji:
                _write_sticker_entry(user_id, area, date, emoji, prompt, response_text)
                print(f"[Chat] Sticker: {area} {emoji} on {date}")
        if sticker_updates:
            doc_response = _clean_sticker_markers(doc_response)

    # Extract and apply profile updates (with history tracking)
    profile_updates = _parse_profile_updates(doc_response)
    updated_profile = None
    needs_save = bool(profile_updates) or bool(onboard_agent_id)

    if needs_save and user_id:
        user = get_user_data(user_id)
        if user:
            if profile_updates:
                updated_profile = _apply_profile_updates_with_history(user, profile_updates)
                if onboard_agent_id:
                    missing_now = agent_registry.get_missing_onboarding_fields(onboard_agent_id, user['profile'])
                    if len(missing_now) == 0:
                        user.setdefault('settings', {}).setdefault('agent_prefs', {}).setdefault(onboard_agent_id, {})['onboarded'] = True
            user['last_updated'] = datetime.utcnow().isoformat()
            _cache_user(user_id, user)
            try:
                s3_storage.save_user(user_id, user)
            except Exception as e:
                print(f"[Chat] Failed to save: {e}")

    clean_response = _clean_profile_markers(doc_response)
    _update_transcript(user_id, user_input, clean_response, session_id)

    response_data = {
        "response": clean_response,
        "session_id": session_id,
        "user_id": user_id,
        "model_used": utils.get_last_model_used() or config.OPENROUTER_MODEL
    }
    if updated_profile:
        response_data["profile_updated"] = True
        response_data["profile"] = updated_profile
    if redirect_agent:
        response_data["redirect_to_agent"] = redirect_agent
    if action_results:
        response_data["action_results"] = action_results

    return json.dumps(response_data)


# ============ CONVERSATIONS ============

def handle_get_conversations(user_id):
    """Get conversation history"""
    if not user_id:
        return json.dumps({"conversations": [], "transcript": ""})
    
    user = get_user_data(user_id)
    transcript = user.get('transcript', '')
    
    try:
        conversations = s3_storage.list_conversations(user_id)
    except:
        conversations = []
    
    return json.dumps({
        "conversations": conversations,
        "transcript": transcript
    })


def handle_get_conversation(user_id, conversation_id):
    """Get specific conversation"""
    if not user_id or not conversation_id:
        return json.dumps({"error": "Missing parameters"}), 400
    
    try:
        conv = s3_storage.get_conversation(user_id, conversation_id)
        if conv:
            return json.dumps({"conversation": conv})
        return json.dumps({"error": "Conversation not found"}), 404
    except Exception as e:
        print(f"[Conversations] Error: {e}")
        return json.dumps({"error": str(e)}), 500


def handle_clear_transcript(user_id):
    """Clear conversation transcript (start fresh)"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    user['transcript'] = ""
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[Conversations] Failed to clear: {e}")
        return json.dumps({"error": "Failed to clear transcript"}), 500
    
    return json.dumps({"success": True})


# ============ UNPROMPTED (GROUP FACILITATOR) ============


def _build_participant_id(phone):
    norm = _normalize_phone(phone)
    if norm:
        return f"pt_{norm}"
    return f"pt_{uuid.uuid4().hex[:8]}"


def _get_participant_record(participant_id):
    if not participant_id:
        return None
    cached = _get_cached_participant(participant_id)
    if cached:
        return cached
    try:
        participant = s3_storage.get_unprompted_participant(participant_id)
        if participant:
            _cache_participant(participant_id, participant)
            return participant
    except Exception as e:
        print(f"[Unprompted] Failed to get participant: {e}")
    return None


def _save_participant_record(participant):
    if not participant or not participant.get('participant_id'):
        return
    try:
        s3_storage.save_unprompted_participant(participant)
        _cache_participant(participant['participant_id'], participant)
    except Exception as e:
        print(f"[Unprompted] Failed to save participant: {e}")


def _get_campaign_record(campaign_id):
    if not campaign_id:
        return None
    cached = _get_cached_campaign(campaign_id)
    if cached:
        return cached
    try:
        campaign = s3_storage.get_unprompted_campaign(campaign_id)
        if campaign:
            _cache_campaign(campaign_id, campaign)
            return campaign
    except Exception as e:
        print(f"[Unprompted] Failed to get campaign: {e}")
    return None


def _save_campaign_record(campaign):
    if not campaign or not campaign.get('campaign_id'):
        return
    try:
        s3_storage.save_unprompted_campaign(campaign)
        _cache_campaign(campaign['campaign_id'], campaign)
    except Exception as e:
        print(f"[Unprompted] Failed to save campaign: {e}")


def _get_group_record(group_id):
    if not group_id:
        return None
    cached = _get_cached_group(group_id)
    if cached:
        return cached
    try:
        group = s3_storage.get_unprompted_group(group_id)
        if group:
            _cache_group(group_id, group)
            return group
    except Exception as e:
        print(f"[Unprompted] Failed to get group: {e}")
    return None


def _save_group_record(group):
    if not group or not group.get('group_id'):
        return
    try:
        s3_storage.save_unprompted_group(group)
        _cache_group(group['group_id'], group)
    except Exception as e:
        print(f"[Unprompted] Failed to save group: {e}")


def _ensure_jeeves_in_group(group):
    participants = group.setdefault('participants', [])
    if 'jeeves' not in participants:
        participants.insert(0, 'jeeves')
    group['participants'] = participants


def _hydrate_participants(participant_ids):
    hydrated = []
    for pid in participant_ids or []:
        if pid == 'jeeves':
            hydrated.append({
                "participant_id": "jeeves",
                "name": "Jeeves",
                "phone": None,
                "location": None
            })
            continue
        participant = _get_participant_record(pid)
        if participant:
            hydrated.append({
                "participant_id": participant.get('participant_id'),
                "name": participant.get('name'),
                "phone": participant.get('phone'),
                "location": participant.get('location')
            })
    return hydrated


def _group_summary(group):
    return {
        "group_id": group.get('group_id'),
        "topic": group.get('topic'),
        "location": group.get('location'),
        "participant_count": len([p for p in group.get('participants', []) if p != 'jeeves']),
        "last_updated": group.get('last_updated')
    }


def _ensure_default_campaign(location=None):
    campaigns = s3_storage.list_unprompted_campaigns()
    for camp in campaigns:
        if camp.get('slug') == 'default' or camp.get('name', '').lower() == 'community agreements':
            return camp
    now = _now_iso()
    default_campaign = {
        "campaign_id": f"camp_{uuid.uuid4().hex[:6]}",
        "name": "Community Agreements",
        "slug": "default",
        "topics": ["general"],
        "location": location or "unspecified",
        "created": now,
        "created_by": None,
        "groups": []
    }
    _save_campaign_record(default_campaign)
    return default_campaign


def _find_group_for_topic(campaign, topic, location=None):
    for gmeta in campaign.get('groups', []):
        if gmeta.get('topic') != topic:
            continue
        loc_match = (not location) or (not gmeta.get('location')) or (gmeta.get('location') == location)
        if not loc_match:
            continue
        group = _get_group_record(gmeta.get('group_id'))
        if not group:
            continue
        current_size = len([p for p in group.get('participants', []) if p != 'jeeves'])
        if current_size < 5:
            return group
    return None


def _create_group(campaign, topic, location=None):
    now = _now_iso()
    group = {
        "group_id": f"gc_{uuid.uuid4().hex[:8]}",
        "campaign_id": campaign.get('campaign_id'),
        "topic": topic,
        "location": location or campaign.get('location') or "unspecified",
        "participants": ["jeeves"],
        "messages": [],
        "created": now,
        "last_updated": now
    }
    _append_message_to_group(group, "jeeves", "Jeeves", "facilitator", "I'm Jeeves, here to keep the conversation flowing. Share your thoughts when you're ready.", channel="system")
    _save_group_record(group)
    campaign.setdefault('groups', []).append({
        "group_id": group['group_id'],
        "topic": topic,
        "location": group['location'],
        "participant_count": 0,
        "last_updated": now
    })
    _save_campaign_record(campaign)
    return group


def _assign_participant_to_campaign(participant, campaign, topics=None):
    if not participant or not campaign:
        return []
    participant.setdefault('campaign_assignments', {})
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(',') if t.strip()]
    topics = topics or campaign.get('topics') or ["general"]
    topics = [t.strip() for t in topics if t]
    topics = topics[:3]
    assigned = []
    for topic in topics:
        group = _find_group_for_topic(campaign, topic, participant.get('location'))
        if not group:
            group = _create_group(campaign, topic, participant.get('location'))
        current_size = len([p for p in group.get('participants', []) if p != 'jeeves'])
        if participant.get('participant_id') not in group.get('participants', []):
            if current_size >= 5:
                group = _create_group(campaign, topic, participant.get('location'))
            group.setdefault('participants', []).append(participant['participant_id'])
        group['last_updated'] = _now_iso()
        _save_group_record(group)
        participant['campaign_assignments'].setdefault(campaign['campaign_id'], [])
        if group['group_id'] not in participant['campaign_assignments'][campaign['campaign_id']]:
            participant['campaign_assignments'][campaign['campaign_id']].append(group['group_id'])
        if not participant.get('default_group_id'):
            participant['default_group_id'] = group['group_id']
        assigned.append(_group_summary(group))
        # Update campaign metadata
        for gmeta in campaign.get('groups', []):
            if gmeta.get('group_id') == group['group_id']:
                gmeta['participant_count'] = len([p for p in group.get('participants', []) if p != 'jeeves'])
                gmeta['last_updated'] = group['last_updated']
                break
    participant['last_active'] = _now_iso()
    _save_campaign_record(campaign)
    _save_participant_record(participant)
    return assigned


def _append_message_to_group(group, sender_id, sender_name, sender_type, text, channel="web"):
    if not text:
        return None
    message = {
        "id": str(uuid.uuid4()),
        "sender_id": sender_id,
        "sender_name": sender_name,
        "sender_type": sender_type,
        "text": text,
        "channel": channel,
        "timestamp": _now_iso()
    }
    group.setdefault('messages', []).append(message)
    if len(group['messages']) > 200:
        group['messages'] = group['messages'][-200:]
    group['last_updated'] = message['timestamp']
    return message


def _prepare_group_response(group, campaign):
    _ensure_jeeves_in_group(group)
    participants = _hydrate_participants(group.get('participants', []))
    return {
        "group_id": group.get('group_id'),
        "campaign_id": group.get('campaign_id'),
        "topic": group.get('topic'),
        "location": group.get('location'),
        "participants": participants,
        "messages": group.get('messages', []),
        "campaign": {
            "campaign_id": campaign.get('campaign_id') if campaign else None,
            "name": campaign.get('name') if campaign else None,
            "topics": campaign.get('topics') if campaign else [],
            "location": campaign.get('location') if campaign else None
        }
    }


def _process_unprompted_message(participant, group, campaign, text, channel="web"):
    text = (text or "").strip()
    if not text:
        return {"error": "Empty message"}
    if not group or not campaign:
        return {"error": "Group not found"}
    _ensure_jeeves_in_group(group)
    if participant.get('participant_id') not in group.get('participants', []):
        current_size = len([p for p in group.get('participants', []) if p != 'jeeves'])
        if current_size >= 5:
            return {"error": "Group is full"}
        group['participants'].append(participant['participant_id'])
    user_msg = _append_message_to_group(group, participant['participant_id'], participant.get('name', 'Participant'), "participant", text, channel=channel)
    prompt = facilitator.build_prompt(campaign, group, group.get('messages', []), participants=_hydrate_participants(group.get('participants', [])))
    facilitator_response = utils.completion(
        prompt=prompt,
        system_prompt=facilitator.SYSTEM_PROMPT,
        temperature=0.6,
        max_tokens=220
    )
    facilitator_text = (facilitator_response or "...").strip() or "..."
    facilitator_msg = _append_message_to_group(group, "jeeves", "Jeeves", "facilitator", facilitator_text, channel="ai")
    _save_group_record(group)
    participant['last_active'] = _now_iso()
    _save_participant_record(participant)
    return {
        "message": user_msg,
        "facilitator_message": facilitator_msg,
        "reply": facilitator_text,
        "group": _prepare_group_response(group, campaign)
    }


def handle_unprompted_login(request):
    name = (request.get('name') or "").strip()
    phone = (request.get('phone') or "").strip()
    location = (request.get('location') or "").strip()
    if not phone:
        return json.dumps({"error": "Phone number required"}), 400
    if not name:
        name = "Guest"
    participant_id = _build_participant_id(phone)
    participant = _get_participant_record(participant_id) or {
        "participant_id": participant_id,
        "phone": phone,
        "phone_normalized": _normalize_phone(phone),
        "created": _now_iso(),
        "campaign_assignments": {}
    }
    participant['name'] = name
    participant['location'] = location
    participant['last_active'] = _now_iso()
    _save_participant_record(participant)
    return json.dumps({
        "participant": participant,
        "campaign_assignments": participant.get('campaign_assignments', {})
    })


def handle_unprompted_create_campaign(request):
    name = (request.get('name') or "").strip()
    if not name:
        return json.dumps({"error": "Campaign name required"}), 400
    topics = request.get('topics') or []
    if isinstance(topics, str):
        topics = [t.strip() for t in topics.split(',') if t.strip()]
    location = (request.get('location') or "").strip()
    campaign = {
        "campaign_id": f"camp_{uuid.uuid4().hex[:8]}",
        "name": name,
        "topics": topics or ["general"],
        "location": location or "unspecified",
        "created": _now_iso(),
        "created_by": request.get('created_by'),
        "groups": []
    }
    _save_campaign_record(campaign)
    return json.dumps({"campaign": campaign})


def handle_unprompted_list_campaigns():
    try:
        campaigns = s3_storage.list_unprompted_campaigns()
    except Exception as e:
        print(f"[Unprompted] List campaigns failed: {e}")
        campaigns = []
    return json.dumps({"campaigns": campaigns})


def handle_unprompted_assign(request):
    participant_id = request.get('participant_id')
    campaign_id = request.get('campaign_id')
    topics = request.get('topics')
    participant = _get_participant_record(participant_id)
    campaign = _get_campaign_record(campaign_id)
    if not participant:
        return json.dumps({"error": "Participant not found"}), 404
    if not campaign:
        return json.dumps({"error": "Campaign not found"}), 404
    assigned = _assign_participant_to_campaign(participant, campaign, topics)
    return json.dumps({
        "participant": participant,
        "assigned_groups": assigned,
        "campaign": campaign
    })


def handle_unprompted_get_group(group_id):
    group = _get_group_record(group_id)
    if not group:
        return json.dumps({"error": "Group not found"}), 404
    campaign = _get_campaign_record(group.get('campaign_id'))
    return json.dumps({"group": _prepare_group_response(group, campaign)})


def handle_unprompted_message(request):
    participant_id = request.get('participant_id')
    group_id = request.get('group_id')
    text = request.get('text', '')
    channel = request.get('channel', 'web')
    participant = _get_participant_record(participant_id)
    group = _get_group_record(group_id)
    if not participant:
        return json.dumps({"error": "Participant not found"}), 404
    if not group:
        return json.dumps({"error": "Group not found"}), 404
    campaign = _get_campaign_record(group.get('campaign_id'))
    result = _process_unprompted_message(participant, group, campaign, text, channel=channel)
    if result.get('error'):
        return json.dumps(result), 400
    return json.dumps(result)


def handle_unprompted_sms(form_data):
    phone = (form_data.get('From') or "").strip()
    text = (form_data.get('Body') or "").strip()
    if not phone or not text:
        return "", 400
    participant_id = _build_participant_id(phone)
    participant = _get_participant_record(participant_id)
    if not participant:
        participant = {
            "participant_id": participant_id,
            "phone": phone,
            "phone_normalized": _normalize_phone(phone),
            "name": form_data.get('ProfileName') or "SMS Friend",
            "location": form_data.get('FromCity') or "",
            "created": _now_iso(),
            "campaign_assignments": {}
        }
        _save_participant_record(participant)
    campaign = None
    if participant.get('campaign_assignments'):
        first_campaign_id = list(participant['campaign_assignments'].keys())[0]
        campaign = _get_campaign_record(first_campaign_id)
    if not campaign:
        campaign = _ensure_default_campaign(participant.get('location'))
        _assign_participant_to_campaign(participant, campaign, campaign.get('topics'))
    group_id = participant.get('default_group_id')
    if not group_id:
        assignments = _assign_participant_to_campaign(participant, campaign, campaign.get('topics'))
        if assignments:
            group_id = assignments[0].get('group_id')
    group = _get_group_record(group_id) if group_id else None
    if not group:
        fallback_topics = campaign.get('topics') or ['general']
        group = _create_group(campaign, fallback_topics[0], participant.get('location'))
        _assign_participant_to_campaign(participant, campaign, [group.get('topic')])
    result = _process_unprompted_message(participant, group, campaign, text, channel="sms")
    reply_text = (result.get('reply') or "...").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>{reply_text}</Message></Response>"
    return twiml


# ============ ADMIN ============

ADMIN_USER_IDS = {'user_mickey'}

BTC_ADDRESS = '139VrBnUEB3UgzwGCQwLxDHnDTUWoE96Y8'
ETH_ADDRESS = '0x58ed1da7a1A58DaB2Fb8d21317725D8760C816Fe'


def _admin_ok(user_id, token):
    """Admin check: known admin user AND valid session token."""
    return user_id in ADMIN_USER_IDS and session_ok(user_id, token)


def handle_admin_balances(requesting_user_id, token=None):
    """Fetch public crypto wallet balances for admin display"""
    if not _admin_ok(requesting_user_id, token):
        return json.dumps({"error": "Unauthorized"}), 403

    import requests as _requests

    result = {"btc": None, "eth": None, "btc_address": BTC_ADDRESS, "eth_address": ETH_ADDRESS}

    # BTC via blockchain.info
    try:
        r = _requests.get(
            f"https://blockchain.info/balance?active={BTC_ADDRESS}",
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            satoshis = data.get(BTC_ADDRESS, {}).get("final_balance", 0)
            result["btc"] = round(satoshis / 1e8, 8)
    except Exception as e:
        print(f"[Admin] BTC balance fetch failed: {e}")

    # ETH: sum balances on mainnet and Base L2 via public JSON-RPC
    eth_total_wei = 0
    rpc_payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [ETH_ADDRESS, "latest"], "id": 1}
    for label, rpc_url in [
        ("mainnet", "https://ethereum.publicnode.com"),
        ("base",    "https://mainnet.base.org"),
    ]:
        try:
            r = _requests.post(rpc_url, json=rpc_payload, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if "result" in data:
                    eth_total_wei += int(data["result"], 16)
        except Exception as e:
            print(f"[Admin] ETH balance fetch failed ({label}): {e}")
    result["eth"] = round(eth_total_wei / 1e18, 6)

    return json.dumps(result)


def handle_admin_stats(requesting_user_id, token=None):
    """Return site stats for admin users only"""
    if not _admin_ok(requesting_user_id, token):
        return json.dumps({"error": "Unauthorized"}), 403

    try:
        user_ids = s3_storage.list_users()
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

    today = datetime.utcnow().date().isoformat()
    users_out = []
    new_today = 0
    with_profile = 0

    for uid in user_ids:
        try:
            u = s3_storage.get_user(uid)
            if not u:
                continue
            created = u.get('created', '')
            profile = u.get('profile') or {}
            profile_fields = len([v for v in profile.values() if v])
            if profile_fields > 0:
                with_profile += 1
            if created.startswith(today):
                new_today += 1
            settings = u.get('settings') or {}
            users_out.append({
                'user_id': uid,
                'username': u.get('username', uid),
                'created': created,
                'profile_fields': profile_fields,
                'doc_style': settings.get('doc_style', ''),
            })
        except Exception:
            continue

    users_out.sort(key=lambda x: x.get('created', ''), reverse=True)

    return json.dumps({
        'total_users': len(users_out),
        'new_today': new_today,
        'with_profile': with_profile,
        'users': users_out,
    })


# ============ FEEDBACK ============

def handle_get_feedback():
    try:
        posts = s3_storage.get_feedback()
        return json.dumps({"posts": posts})
    except Exception as e:
        return json.dumps({"posts": [], "error": str(e)})


def handle_post_feedback(req):
    message = (req.get('message') or '').strip()
    if not message:
        return (json.dumps({"error": "Message required"}), 400)
    username = (req.get('username') or 'Guest').strip() or 'Guest'
    try:
        posts = s3_storage.get_feedback()
        post = {
            "id": str(uuid.uuid4()),
            "username": username[:40],
            "message": message[:2000],
            "created": datetime.utcnow().isoformat(),
            "status": "new",
            "replies": [],
        }
        posts.insert(0, post)
        posts = posts[:500]
        s3_storage.save_feedback(posts)
        return json.dumps({"post": post})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_reply_feedback(post_id, req):
    """Append a threaded reply to a feedback post. Open to anyone (like posting)."""
    message = (req.get('message') or '').strip()
    if not message:
        return (json.dumps({"error": "Message required"}), 400)
    username = (req.get('username') or 'Guest').strip() or 'Guest'
    try:
        posts = s3_storage.get_feedback()
        target = next((p for p in posts if p.get('id') == post_id), None)
        if target is None:
            return (json.dumps({"error": "Post not found"}), 404)
        reply = {
            "id": str(uuid.uuid4()),
            "username": username[:40],
            "message": message[:2000],
            "created": datetime.utcnow().isoformat(),
        }
        replies = target.setdefault('replies', [])
        replies.append(reply)
        target['replies'] = replies[-200:]
        s3_storage.save_feedback(posts)
        return json.dumps({"reply": reply})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def _is_mickey(user_id):
    try:
        u = s3_storage.get_user(user_id)
        return u and u.get('username', '').lower() == 'mickey'
    except Exception:
        return False


def handle_delete_feedback_post(post_id, user_id, token=None):
    if not (_is_mickey(user_id) and session_ok(user_id, token)):
        return (json.dumps({"error": "Unauthorized"}), 403)
    try:
        posts = s3_storage.get_feedback()
        posts = [p for p in posts if p.get('id') != post_id]
        s3_storage.save_feedback(posts)
        return json.dumps({"ok": True})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_update_feedback_post(post_id, req, token=None):
    user_id = req.get('user_id', '')
    if not (_is_mickey(user_id) and session_ok(user_id, token)):
        return (json.dumps({"error": "Unauthorized"}), 403)
    try:
        posts = s3_storage.get_feedback()
        for p in posts:
            if p.get('id') == post_id:
                if 'status' in req:
                    p['status'] = req['status']
                break
        s3_storage.save_feedback(posts)
        return json.dumps({"ok": True})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


# ============ BOUNTIES ============

def handle_create_bounty(req, api_key=None):
    if not demand_key_ok(api_key):
        return (json.dumps({"error": "Unauthorized — valid API key required"}), 401)
    activity = (req.get('activity') or '').strip()
    if not activity:
        return (json.dumps({"error": "activity required"}), 400)
    health_area = (req.get('health_area') or 'exercise').strip()
    price = req.get('price')
    currency = (req.get('currency') or 'ETH').strip()
    user_ids = req.get('user_ids', [])
    expires = req.get('expires', '')
    try:
        bounties = s3_storage.get_bounties()
        bounty = {
            "id": f"bty_{uuid.uuid4().hex[:12]}",
            "activity": activity[:500],
            "health_area": health_area,
            "price": price,
            "currency": currency,
            "user_ids": user_ids,
            "expires": expires,
            "created": datetime.utcnow().isoformat(),
            "status": "active"
        }
        bounties.append(bounty)
        s3_storage.save_bounties(bounties)
        return json.dumps({"bounty_id": bounty["id"], "status": "active"})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_list_bounties():
    try:
        bounties = s3_storage.get_bounties()
        return json.dumps({"bounties": bounties})
    except Exception as e:
        return json.dumps({"bounties": [], "error": str(e)})


def handle_get_bounty(bounty_id, api_key=None):
    if not demand_key_ok(api_key):
        return (json.dumps({"error": "Unauthorized — valid API key required"}), 401)
    try:
        bounties = s3_storage.get_bounties()
        for b in bounties:
            if b.get('id') == bounty_id:
                return json.dumps({"bounty": b})
        return (json.dumps({"error": "Not found"}), 404)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_delete_bounty(bounty_id, api_key=None):
    if not demand_key_ok(api_key):
        return (json.dumps({"error": "Unauthorized — valid API key required"}), 401)
    try:
        bounties = s3_storage.get_bounties()
        remaining = [b for b in bounties if b.get('id') != bounty_id]
        if len(remaining) == len(bounties):
            return (json.dumps({"error": "Not found"}), 404)
        s3_storage.save_bounties(remaining)
        return json.dumps({"ok": True})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


# ============ SUGGESTIONS ============

_SUGGESTION_AREAS = [
    ("exercise", "exercise", "Exercise Coach"),
    ("diet", "diet", "Diet Advisor"),
    ("social", "relationships", "Relationships Advisor"),
]


_ERROR_PHRASES = ("having trouble", "please try again", "i'm sorry", "i cannot", "error")

def _generate_suggestion_text(area_label, agent_name, profile):
    """Call LLM to produce one specific, actionable suggestion for the given health area."""
    prompt = (
        f"You are a {agent_name}. Based on this user's health profile, generate ONE specific, "
        f"actionable suggestion for them today in the area of {area_label}.\n\n"
        f"Health profile:\n{json.dumps(profile, indent=2) if profile else '{}'}\n\n"
        "Respond with ONLY the suggestion text (1-2 sentences, specific and actionable). "
        "No preamble, no explanation."
    )
    try:
        result = utils.completion(prompt=prompt, temperature=0.8, max_tokens=100).strip()
        if not result or len(result) < 15 or any(p in result.lower() for p in _ERROR_PHRASES):
            print(f"[Suggestions] LLM returned error/empty for {area_label}: {result[:60]!r}")
            return None
        return result
    except Exception as e:
        print(f"[Suggestions] LLM failed for {area_label}: {e}")
        return None


def _get_active_bounties_for_user(user_id):
    """Return active, non-expired bounties that list this user_id."""
    try:
        bounties = s3_storage.get_bounties()
    except Exception:
        return []
    today = datetime.utcnow().strftime('%Y-%m-%d')
    result = []
    for b in bounties:
        if b.get('status') != 'active':
            continue
        expires = b.get('expires', '')
        if expires and expires < today:
            continue
        if user_id in b.get('user_ids', []):
            result.append(b)
    return result


def generate_suggestions(user_id):
    """Generate up to 3 suggestions (bounty-backed first, then LLM-personalized)."""
    user = get_user_data(user_id)
    if not user:
        return []
    profile = user.get('profile', {})
    suggestions = []

    # Bounty-backed suggestions — skip bounties the user already accepted
    accepted_bounty_ids = {a.get('bounty_id') for a in user.get('activities', []) if a.get('bounty_id')}
    bounties = [b for b in _get_active_bounties_for_user(user_id) if b.get('id') not in accepted_bounty_ids]
    _area_to_agent = {'exercise': 'exercise', 'diet': 'diet', 'social': 'relationships'}
    for b in bounties[:3]:
        area = b.get('health_area', 'exercise')
        suggestions.append({
            "id": f"sug_{uuid.uuid4().hex[:12]}",
            "type": area,
            "agent_id": _area_to_agent.get(area, 'exercise'),
            "text": b.get('activity', ''),
            "bounty_id": b.get('id'),
            "price": b.get('price'),
            "currency": b.get('currency'),
            "created": datetime.utcnow().isoformat(),
            "status": "pending"
        })

    # Fill remaining slots with LLM suggestions — sequential to avoid simultaneous rate limits
    used_areas = {s['type'] for s in suggestions}
    slots = 3 - len(suggestions)
    areas_to_fill = [a for a in _SUGGESTION_AREAS if a[0] not in used_areas][:max(slots, 0)]
    for area_label, agent_id, agent_name in areas_to_fill:
        text = _generate_suggestion_text(area_label, agent_name, profile)
        if text:
            suggestions.append({
                "id": f"sug_{uuid.uuid4().hex[:12]}",
                "type": area_label,
                "agent_id": agent_id,
                "text": text,
                "bounty_id": None,
                "price": None,
                "currency": None,
                "created": datetime.utcnow().isoformat(),
                "status": "pending"
            })

    # Re-fetch before save: LLM generation takes seconds and another request
    # (e.g. login rotating the session token) may have written the user record
    # since we loaded it. Merge suggestions onto the fresh copy.
    try:
        fresh = s3_storage.get_user(user_id)
        if fresh:
            user = fresh
    except Exception:
        pass

    # Replace only pending suggestions; keep last 30 accepted/rejected for history
    existing = [s for s in user.get('suggestions', []) if s.get('status') != 'pending'][-30:]
    user['suggestions'] = existing + suggestions
    user['last_suggestion_gen'] = datetime.utcnow().isoformat()
    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        print(f"[Suggestions] Save failed: {e}")
    return suggestions


def generate_login_suggestions(user_id):
    """Background task: generate daily suggestions on login (24h debounce)."""
    time.sleep(2)
    user = get_user_data(user_id)
    if not user:
        return
    last_gen = user.get('last_suggestion_gen')
    if last_gen:
        try:
            last_dt = datetime.fromisoformat(last_gen.replace('Z', '+00:00'))
            if (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds() < 86400:
                # Still regenerate if stored suggestions look like error messages
                pending = [s for s in user.get('suggestions', []) if s.get('status') == 'pending']
                has_bad = any(any(p in s.get('text', '').lower() for p in _ERROR_PHRASES) for s in pending)
                if not has_bad:
                    return
        except Exception:
            pass
    generate_suggestions(user_id)


def handle_get_suggestions(user_id):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    return json.dumps({"suggestions": user.get('suggestions', [])})


def handle_generate_suggestions(user_id, force=False):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    # Without force, respect the 24h daily cadence and return the existing batch
    if not force:
        last_gen = user.get('last_suggestion_gen')
        if last_gen:
            try:
                last_dt = datetime.fromisoformat(last_gen.replace('Z', '+00:00'))
                if (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds() < 86400:
                    pending = [s for s in user.get('suggestions', []) if s.get('status') == 'pending']
                    return json.dumps({"suggestions": pending})
            except Exception:
                pass
    suggestions = generate_suggestions(user_id)
    return json.dumps({"suggestions": suggestions})


def handle_accept_suggestion(user_id, suggestion_id):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    suggestion = next((s for s in user.get('suggestions', []) if s.get('id') == suggestion_id), None)
    if not suggestion:
        return (json.dumps({"error": "Suggestion not found"}), 404)

    suggestion['status'] = 'accepted'
    activity = {
        "id": f"act_{uuid.uuid4().hex[:12]}",
        "suggestion_id": suggestion_id,
        "type": suggestion.get('type'),
        "agent_id": suggestion.get('agent_id'),
        "text": suggestion.get('text'),
        "bounty_id": suggestion.get('bounty_id'),
        "price": suggestion.get('price'),
        "currency": suggestion.get('currency'),
        "accepted_at": datetime.utcnow().isoformat(),
        "status": "active",
        "completed_at": None,
        "wallet_snapshot": None,
        "payment_pending": False
    }
    user.setdefault('activities', []).append(activity)
    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)
    return json.dumps({"activity": activity})


def handle_dismiss_suggestion(user_id, suggestion_id):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    suggestion = next((s for s in user.get('suggestions', []) if s.get('id') == suggestion_id), None)
    if not suggestion:
        return (json.dumps({"error": "Suggestion not found"}), 404)

    suggestion['status'] = 'dismissed'
    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)
    return json.dumps({"ok": True})


# ============ ACTIVITIES ============

def handle_get_activities(user_id):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    return json.dumps({"activities": user.get('activities', [])})


def handle_update_activity(user_id, activity_id, req):
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    activity = next((a for a in user.get('activities', []) if a.get('id') == activity_id), None)
    if not activity:
        return (json.dumps({"error": "Activity not found"}), 404)

    if req.get('status') == 'completed':
        activity['status'] = 'completed'
        activity['completed_at'] = datetime.utcnow().isoformat()
        wallets = user.get('wallets', {})
        activity['wallet_snapshot'] = wallets.get('eth') or wallets.get('sol') or None
        if activity.get('price'):
            activity['payment_pending'] = True
    elif req.get('status') == 'abandoned':
        if activity.get('status') != 'active':
            return (json.dumps({"error": "Only active activities can be abandoned"}), 400)
        activity['status'] = 'abandoned'
        activity['abandoned_at'] = datetime.utcnow().isoformat()

    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)
    return json.dumps({"activity": activity})


# ============ DEMAND-SIDE /generate ============

def handle_generate_demand(req, api_key=None):
    if not demand_key_ok(api_key):
        return (json.dumps({"error": "Unauthorized — valid API key required"}), 401)
    user_id = (req.get('user_id') or '').strip()
    if not user_id:
        return (json.dumps({"error": "user_id required"}), 400)

    health_area = (req.get('health_area') or '').strip()
    price = req.get('price')

    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    profile = user.get('profile', {})
    if not health_area:
        health_area = random.choice(['exercise', 'diet', 'social'])

    _area_map = {
        'exercise': ('exercise', 'Exercise Coach'),
        'diet': ('diet', 'Diet Advisor'),
        'social': ('relationships', 'Relationships Advisor'),
    }
    agent_id, agent_name = _area_map.get(health_area, ('exercise', 'Exercise Coach'))

    text = _generate_suggestion_text(health_area, agent_name, profile)
    if not text:
        return (json.dumps({"error": "Could not generate suggestion"}), 500)

    bounty_payload = {
        "activity": text,
        "health_area": health_area,
        "price": price,
        "currency": "ETH",
        "user_ids": [user_id]
    }
    return json.dumps({
        "suggestion": {"text": text, "agent_id": agent_id, "health_area": health_area},
        "bounty_payload": bounty_payload,
        "bounty_post_url": "/bounty"
    })


# ============ ADMIN PAYMENTS ============

def handle_admin_payments(requesting_user_id, token=None):
    """List all payment_pending activities across users (admin only)."""
    if not _admin_ok(requesting_user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 403)
    try:
        user_ids = s3_storage.list_users()
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    pending = []
    for uid in user_ids:
        try:
            u = s3_storage.get_user(uid)
            if not u:
                continue
            for a in u.get('activities', []):
                if a.get('payment_pending'):
                    pending.append({
                        "user_id": uid,
                        "username": u.get('username', uid),
                        "activity_id": a.get('id'),
                        "text": a.get('text'),
                        "price": a.get('price'),
                        "currency": a.get('currency'),
                        "wallet": a.get('wallet_snapshot'),
                        "completed_at": a.get('completed_at'),
                        "bounty_id": a.get('bounty_id'),
                    })
        except Exception:
            continue

    pending.sort(key=lambda x: x.get('completed_at') or '', reverse=True)
    return json.dumps({"payments": pending})


def handle_admin_mark_paid(requesting_user_id, token, target_user_id, activity_id):
    """Mark a payment_pending activity as paid (admin only)."""
    if not _admin_ok(requesting_user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 403)
    user = get_user_data(target_user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    activity = next((a for a in user.get('activities', []) if a.get('id') == activity_id), None)
    if not activity:
        return (json.dumps({"error": "Activity not found"}), 404)
    if not activity.get('payment_pending'):
        return (json.dumps({"error": "Activity is not pending payment"}), 400)

    activity['payment_pending'] = False
    activity['paid_at'] = datetime.utcnow().isoformat()
    _cache_user(target_user_id, user)
    try:
        s3_storage.save_user(target_user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)
    return json.dumps({"ok": True, "activity": activity})
