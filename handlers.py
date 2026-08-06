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
from prompts import doc_unprompted
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
                    "token": token,
                    "ledger_balance": user.get('ledger_balance'),
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
        "notifications": [],
        # Play ledger for stake leagues / CPAA payouts (USD display units)
        "ledger_balance": 50.0,  # welcome stake credit so new players can join a league
        "ledger_currency": "USD",
        "fitness_stats": {
            "total_miles": 0.0,
            "total_activities": 0,
            "current_streak_days": 0,
            "best_streak_days": 0,
            "last_activity_date": None,
        },
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
        "token": signup_token,
        "ledger_balance": new_user.get("ledger_balance", 50.0),
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
        "chat_only_mode": True,
        "bounty_discoverable": False,  # opt-in to public sponsor directory
        "bounty_public_blurb": "",
    }
    
    settings = {**default_settings, **user.get('settings', {})}
    settings['notifications_enabled'] = _coerce_bool(settings.get('notifications_enabled'), True)
    settings['chat_only_mode'] = _coerce_bool(settings.get('chat_only_mode'), True)
    settings['bounty_discoverable'] = _coerce_bool(settings.get('bounty_discoverable'), False)
    if settings.get('bounty_public_blurb') is None:
        settings['bounty_public_blurb'] = ''
    return json.dumps({"settings": settings})


def _coerce_bool(value, default=False):
    """Normalize bool-ish values from JSON / LLM actions (incl. string 'false')."""
    if value is True or value is False:
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ('true', '1', 'yes', 'on'):
            return True
        if s in ('false', '0', 'no', 'off', ''):
            return False
    return bool(value)


def handle_update_settings(user_id, data):
    """Update user settings"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404

    if not isinstance(data, dict):
        return json.dumps({"error": "Invalid settings payload"}), 400

    # Only allow known keys through (prevents junk / privilege fields)
    allowed = {
        'doc_style', 'theme', 'ui_style', 'notifications_enabled',
        'chat_only_mode', 'custom_agent_prompt',
    }
    data = {k: v for k, v in data.items() if k in allowed}

    if 'custom_agent_prompt' in data:
        data['custom_agent_prompt'] = str(data['custom_agent_prompt'])[:2000]

    for bool_key in ('notifications_enabled', 'chat_only_mode'):
        if bool_key in data:
            data[bool_key] = _coerce_bool(data[bool_key], default=True if bool_key == 'chat_only_mode' else False)

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
            "description": (
                "Save or update a field in the user's health profile. Use for stable facts: "
                "conditions, medications, goals, preferences, symptoms. "
                "Pass value=null to CLEAR/remove a field (e.g. when a problem is resolved)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Profile field name (e.g. symptoms, medications, primary_concern, goals)"},
                    "value": {
                        "description": "Value to save (string), or null to clear/remove the field",
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": ["field"],
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
            if not field:
                return "Error: field is required."
            raw_value = inputs.get("value")
            # Models may send JSON null, Python None, or the string "null"
            if isinstance(raw_value, str) and raw_value.strip().lower() in ("null", "none", ""):
                raw_value = None
            if user_id:
                u = get_user_data(user_id)
                if u:
                    profile = u.setdefault('profile', {})
                    if raw_value is None:
                        if field in profile:
                            del profile[field]
                            action = f"Cleared profile.{field}"
                        else:
                            action = f"profile.{field} was already empty"
                    else:
                        value = str(raw_value).strip()
                        if not value:
                            return "Error: value is empty; pass null to clear a field."
                        profile[field] = value
                        action = f"Saved profile.{field} = {value!r}"
                    u['last_updated'] = datetime.utcnow().isoformat()
                    _cache_user(user_id, u)
                    s3_storage.save_user(user_id, u)
                    return action
            if raw_value is None:
                return f"Cleared profile.{field} (no user session)"
            return f"Saved profile.{field} = {str(raw_value)!r} (no user session)"

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
            if tc["name"] == "update_profile":
                f = (tc["input"] or {}).get("field", "")
                v = (tc["input"] or {}).get("value")
                if isinstance(v, str) and v.strip().lower() in ("null", "none", ""):
                    v = None
                if f:
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
    """Bell feed: UB activities first, free suggestions, sticker check-ins, tips."""
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
            em = entry.get("emoji")
            check_ins.append({
                "area": area, "area_label": area_label,
                "answered": True, "emoji": em, "prompt": entry.get("prompt"),
                "src": stickers_module.pixel_src(em or "", area=area),
            })
        else:
            check_ins.append({
                "area": area, "area_label": area_label, "answered": False,
                "message": template.get("question", f"How is your {area_label.lower()} today?"),
                "emoji_options": stickers_module.build_poll_options(area, f"{user_id}:{area}:{today}"),
            })

    # Suggestions: UB (bounty) first, then free chat-bound
    pending = [s for s in user.get('suggestions', []) if s.get('status') == 'pending']
    bounty_s = [s for s in pending if s.get('bounty_id')]
    free_s = [s for s in pending if not s.get('bounty_id')]
    # Ensure destination flags for older records
    for s in bounty_s:
        s.setdefault('destination', 'activity')
    for s in free_s:
        s.setdefault('destination', 'chat')
    suggestions = (bounty_s + free_s)[:6]

    # Active UB / accepted activities for the top of the bell
    activities = [
        a for a in user.get('activities', [])
        if a.get('status') == 'active'
    ][:8]

    other_notifs = [
        n for n in user.get('notifications', [])
        if n.get('type') != 'sticker_poll' and not n.get('read')
    ][-10:]

    unanswered = sum(1 for c in check_ins if not c['answered'])
    badge = unanswered + len(suggestions) + len(activities) + len(other_notifs)

    return json.dumps({
        "activities": activities,          # UB first in the UI
        "suggestions": suggestions,        # bounty then free
        "check_ins": check_ins,
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

    # Combine agent persona with shared profile syntax, tools, and transient check-ins
    from prompts.shared.transient import TRANSIENT_CHECK_IN
    full_system = (
        f"{agent_system}\n\n{PROFILE_UPDATE_SYNTAX}\n\n"
        f"{TOOL_USE_INSTRUCTIONS}\n\n{TRANSIENT_CHECK_IN}"
    )

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
    rows = stickers_module.enrich_board_rows(board.get('rows', {}))
    board_data = {
        "rows": rows,
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
    # Return board without user_id; enrich legacy emoji → pixel art src
    return json.dumps({
        "rows": stickers_module.enrich_board_rows(board.get('rows', {})),
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
    """Extract profile updates from Doc's response (markers or bare JSON dumps)."""
    updates = {}
    if not response:
        return updates

    # Match both **PROFILE_UPDATE** and **PROFILE UPDATE** (with space or underscore)
    pattern = r'\*\*PROFILE[_ ]UPDATE\*\*\s*(\{[^{}]*\})'
    matches = re.finditer(pattern, response, re.DOTALL | re.IGNORECASE)

    for match in matches:
        json_str = match.group(1).strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                updates.update(data)
                print(f"[Chat] Parsed profile update: {data}")
        except json.JSONDecodeError as e:
            print(f"[Chat] Failed to parse profile update: {json_str} - {e}")

    # Fallback: flexible marker match
    if not updates:
        alt_pattern = r'\*\*PROFILE[_ ]UPDATE\*\*\s*\n?\s*(\{[\s\S]*?\})'
        alt_matches = re.finditer(alt_pattern, response, re.IGNORECASE)
        for match in alt_matches:
            json_str = match.group(1).strip()
            json_str = re.sub(r'\s+', ' ', json_str)
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    updates.update(data)
                    print(f"[Chat] Parsed profile update (alt): {data}")
            except json.JSONDecodeError as e:
                print(f"[Chat] Failed alt parse: {json_str} - {e}")

    # Models sometimes dump bare {"field": value} lines without markers
    if not updates:
        for m in re.finditer(r'(?m)^\s*(\{[^{}]{2,300}\})\s*$', response):
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or not data:
                continue
            # Only accept small key/value profile-like objects
            if all(isinstance(k, str) and len(k) < 64 for k in data.keys()):
                updates.update(data)
                print(f"[Chat] Parsed bare JSON profile update: {data}")

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
    """Remove profile update markers and bare profile-JSON dumps from response."""
    # Remove both **PROFILE_UPDATE** and **PROFILE UPDATE** variants
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*\{[^{}]*\}', '', response, flags=re.IGNORECASE)
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*\n?\s*\{[\s\S]*?\}', '', cleaned, flags=re.IGNORECASE)
    # Also clean any leftover markers without JSON
    cleaned = re.sub(r'\*\*PROFILE[_ ]UPDATE\*\*\s*', '', cleaned, flags=re.IGNORECASE)
    # Bare one-line JSON objects models dump instead of tool calls
    cleaned = re.sub(r'(?m)^\s*\{[^{}]{2,300}\}\s*$', '', cleaned)
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
    chat_only = _coerce_bool(settings.get('chat_only_mode', True), True)

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
    tool_profile_updates = {}
    model_used = None
    used_agentic = False

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
        keyword_agents = agent_registry.agents_for_message(user_input)
        style_hint = style_module.build_style_instruction(user_input, recent_transcript)
        sup_hints = supervisor_module.analyze(
            user_input, profile, recent_transcript,
            utils_module=utils, config_module=config
        )
        focus = sup_hints.get("focus") or None

        # Optional specialist pre-fetch for multi-domain / keyword routing
        agent_context = None
        if len(keyword_agents) >= 2:
            print(f"[Chat] Cross AI pre-fetch: {keyword_agents}")
            agent_context = _run_cross_ai(keyword_agents, user_input, profile, recent_transcript)
        elif len(keyword_agents) == 1:
            print(f"[Chat] Specialist pre-fetch: {keyword_agents[0]}")
            agent_context = _run_agent(keyword_agents[0], user_input, profile, recent_transcript)

        # Logged-in users: real ListeningAI tool loop so profile writes actually land
        if user_id:
            used_agentic = True
            chat_only = _coerce_bool(settings.get('chat_only_mode', True), True)
            system = doc_v2.build_doc_system_for_tools(
                user_input=user_input,
                profile=profile,
                recent_transcript=recent_transcript,
                username=username,
                agent_context=agent_context,
                history_summary=utils.summarize_history(user),
                style_hint=style_hint,
                focus=focus,
                chat_only_instructions=(
                    chat_only_module.CHAT_ONLY_INSTRUCTIONS if chat_only else None
                ),
                injected_context=_build_injected_context(user, user_input.lower()) if chat_only else None,
                sticker_context=_build_sticker_context_for_doc(user_id),
            )
            user_msg = doc_v2.build_doc_user_message(
                user_input=user_input,
                username=username,
                recent_transcript=recent_transcript,
            )
            messages = [{"role": "user", "content": user_msg}]
            print(f"[Chat] Agentic Doc loop (ListeningAI tools) user={user_id}")
            doc_response, tool_profile_updates, model_used = _run_agentic_loop(
                messages=messages,
                system_prompt=system,
                user_id=user_id,
                agent_id="doc",
                max_steps=8,
            )
            redirect_agent = _parse_redirect(doc_response)
        else:
            # Guests: plain completion (no persisted profile tools)
            try:
                prompt = _build_prompt(
                    user_id=user_id,
                    session_id=session_id,
                    user_input=user_input,
                    style_hint=style_hint,
                    focus=focus
                )
                if agent_context:
                    prompt = doc_v2.build_doc_prompt(
                        user_input=user_input, profile=profile,
                        recent_transcript=recent_transcript, username=username,
                        agent_context=agent_context,
                        history_summary=utils.summarize_history(user),
                        style_hint=style_hint, focus=focus
                    )
                doc_response = utils.completion(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=config.LLM_MAX_TOKENS
                )
            except Exception as e:
                print(f"[Chat] Completion error: {e}")
                doc_response = "I'm having trouble responding right now. Please try again."
            redirect_agent = _parse_redirect(doc_response)

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

    # Process sticker updates (text markers — tool write_sticker also handles this)
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

    # Profile: tools already persisted; also apply text markers / bare JSON as fallback
    text_profile_updates = _parse_profile_updates(doc_response)
    profile_updates = {**(tool_profile_updates or {}), **(text_profile_updates or {})}
    updated_profile = None

    if user_id and (profile_updates or onboard_agent_id):
        user = get_user_data(user_id)
        if user:
            if profile_updates:
                # Re-apply so null deletes + history tracking stay consistent
                updated_profile = _apply_profile_updates_with_history(user, profile_updates)
                if onboard_agent_id:
                    missing_now = agent_registry.get_missing_onboarding_fields(
                        onboard_agent_id, user['profile']
                    )
                    if len(missing_now) == 0:
                        user.setdefault('settings', {}).setdefault(
                            'agent_prefs', {}
                        ).setdefault(onboard_agent_id, {})['onboarded'] = True
            user['last_updated'] = datetime.utcnow().isoformat()
            _cache_user(user_id, user)
            try:
                s3_storage.save_user(user_id, user)
            except Exception as e:
                print(f"[Chat] Failed to save: {e}")
    elif used_agentic and user_id and tool_profile_updates:
        u = get_user_data(user_id)
        if u:
            updated_profile = u.get('profile')

    clean_response = _clean_profile_markers(doc_response)
    _update_transcript(user_id, user_input, clean_response, session_id)

    response_data = {
        "response": clean_response,
        "session_id": session_id,
        "user_id": user_id,
        "model_used": model_used or utils.get_last_model_used() or config.OPENROUTER_MODEL
    }
    if profile_updates:
        response_data["profile_updated"] = True
        if updated_profile is None and user_id:
            u = get_user_data(user_id)
            updated_profile = (u or {}).get('profile')
        if updated_profile is not None:
            response_data["profile"] = updated_profile
    if redirect_agent:
        response_data["redirect_to_agent"] = redirect_agent
    if action_results:
        response_data["action_results"] = action_results

    return json.dumps(response_data)


# ============ DOC UNPROMPTED POLL (GET /Doc) ============

def _doc_proactive_policy():
    """ListeningAI ProactivePolicy with GreenDial Doc defaults; local fallback if missing."""
    try:
        from listening_ai import DOC_DEFAULT_POLICY, is_nothing_message
        return DOC_DEFAULT_POLICY, is_nothing_message
    except Exception as e:
        print(f"[Doc] ProactivePolicy unavailable ({e}); using local gates")

        def _is_nothing(text):
            if not text or not str(text).strip():
                return True
            t = str(text).strip().lower()
            return t in ("nothing", "no message", "skip", "n/a", "none", "(none)")

        class _LocalPolicy:
            min_interval_hours = 6.0
            max_per_day = 2
            quiet_after_activity_minutes = 30.0

            def evaluate(self, **kwargs):
                force = kwargs.get("force")
                if force:
                    return {"allowed": True, "reason": None, "next_eligible_at": None}
                if kwargs.get("require_notifications_enabled", True) is not False:
                    if not kwargs.get("notifications_enabled", True):
                        return {"allowed": False, "reason": "notifications_disabled", "next_eligible_at": None}
                if not (kwargs.get("has_profile") or kwargs.get("has_transcript")):
                    return {"allowed": False, "reason": "empty_context", "next_eligible_at": None}
                # Minimal fallback: allow (server still has LLM path)
                return {"allowed": True, "reason": None, "next_eligible_at": None}

            def record_send(self, state=None, message_id=None, now=None):
                now_iso = datetime.utcnow().isoformat()
                out = dict(state or {})
                out["last_sent_at"] = now_iso
                dates = list(out.get("sent_dates") or [])
                dates.append(now_iso[:10])
                out["sent_dates"] = dates[-14:]
                if message_id:
                    out["last_message_id"] = message_id
                return out

        return _LocalPolicy(), _is_nothing


def handle_doc_poll(user_id, force=False):
    """
    On-demand unprompted Doc message for the SPA (GET /Doc).

    Cheap rate gates first (no LLM if blocked). When allowed, generate one short
    Doc line via ListeningAI completion, inject into Doc transcript, return it.
    """
    if not user_id:
        return json.dumps({"error": "user_id required", "messages": []}), 400

    # Short lock to reduce multi-worker double generation
    lock_key = f"doc_unprompted_lock:{user_id}"
    if _cache_get('lock', lock_key) and not force:
        return json.dumps({
            "messages": [],
            "reason": "in_flight",
            "next_eligible_at": None,
        })
    _cache_set('lock', lock_key, True, 60)

    try:
        # Always re-fetch so gates see latest transcript / last_chat
        try:
            user = s3_storage.get_user(user_id)
        except Exception as e:
            print(f"[Doc] load user failed: {e}")
            user = None
        if not user:
            return json.dumps({"error": "User not found", "messages": []}), 404

        policy, is_nothing = _doc_proactive_policy()
        state = user.get("doc_unprompted") or {}
        if not isinstance(state, dict):
            state = {}
        settings = user.get("settings") or {}
        profile = user.get("profile") or {}
        transcript = user.get("transcript") or ""

        decision = policy.evaluate(
            last_sent_at=state.get("last_sent_at"),
            sent_dates=state.get("sent_dates") or [],
            last_activity_at=user.get("last_chat"),
            notifications_enabled=settings.get("notifications_enabled", True),
            has_profile=bool(profile),
            has_transcript=bool(transcript.strip()),
            force=bool(force),
        )
        if not decision.get("allowed"):
            return json.dumps({
                "messages": [],
                "reason": decision.get("reason"),
                "next_eligible_at": decision.get("next_eligible_at"),
            })

        recent = _get_recent_transcript(transcript, max_lines=12)
        sticker_ctx = _build_sticker_context_for_doc(user_id)
        prompt = doc_unprompted.build_unprompted_prompt(
            username=user.get("username") or user.get("first_name") or "friend",
            profile=profile,
            recent_transcript=recent,
            history_summary=utils.summarize_history(user),
            sticker_context=sticker_ctx,
            doc_style=settings.get("doc_style", "questioning"),
        )

        try:
            text = utils.completion(
                prompt=prompt,
                system_prompt=doc_unprompted.SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=80,
            )
        except Exception as e:
            print(f"[Doc] unprompted generation error: {e}")
            return json.dumps({
                "messages": [],
                "reason": "generation_error",
                "next_eligible_at": decision.get("next_eligible_at"),
            })

        text = (text or "").strip()
        # Strip accidental quotes / fences
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("text"):
                text = text[4:].strip()
        if is_nothing(text):
            # Do not burn daily cap on intentional silence
            return json.dumps({
                "messages": [],
                "reason": "nothing",
                "next_eligible_at": decision.get("next_eligible_at"),
            })

        # Cap length hard
        if len(text) > 400:
            text = text[:397].rstrip() + "…"

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        created = datetime.utcnow().isoformat()

        # Re-fetch before save (agent_runner pattern)
        try:
            fresh = s3_storage.get_user(user_id)
            if fresh:
                user = fresh
        except Exception:
            pass

        _inject_suggestion_into_chat(user, "doc", text)
        user["last_chat"] = created
        user["last_updated"] = created
        user["doc_unprompted"] = policy.record_send(
            user.get("doc_unprompted") if isinstance(user.get("doc_unprompted"), dict) else state,
            message_id=msg_id,
        )

        try:
            s3_storage.save_user(user_id, user)
            _cache_user(user_id, user)
        except Exception as e:
            print(f"[Doc] failed to save unprompted message: {e}")
            return json.dumps({
                "messages": [],
                "reason": "save_error",
                "next_eligible_at": None,
            }), 500

        next_eligible = None
        try:
            next_decision = policy.evaluate(
                last_sent_at=user["doc_unprompted"].get("last_sent_at"),
                sent_dates=user["doc_unprompted"].get("sent_dates") or [],
                last_activity_at=created,
                notifications_enabled=settings.get("notifications_enabled", True),
                has_profile=bool(profile),
                has_transcript=True,
                force=False,
            )
            next_eligible = next_decision.get("next_eligible_at")
        except Exception:
            pass

        print(f"[Doc] unprompted → {user_id}: {text[:80]}")
        return json.dumps({
            "messages": [{
                "id": msg_id,
                "text": text,
                "created": created,
                "source": "unprompted",
            }],
            "next_eligible_at": next_eligible,
        })
    finally:
        _cache_store.pop(('lock', lock_key), None)
        _cache_ts.pop(('lock', lock_key), None)


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

BTC_ADDRESS = '3M6nzmM6T5WsfJkGHxGFs1YRTtp8TXpBpv'
ETH_ADDRESS = '0x3EbF65C9D212F3978cB5105Aa6877F6013cAfD57'


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


# ============ BOUNTIES / DEMAND-SIDE ============

# Generic default used when a sponsor types little or nothing (friends & family UX).
DEFAULT_BOUNTY_ACTIVITY = "Take a walk sometime in the next day"
DEFAULT_BOUNTY_PRICE = 5
DEFAULT_BOUNTY_CURRENCY = "USD"
DEFAULT_BOUNTY_AREA = "exercise"

# Quiet suggestion chips (TSE-style catalog) — non-clobbering autocomplete.
BOUNTY_ACTIVITY_CATALOG = [
    {"label": "Take a walk sometime in the next day", "aliases": ["walk", "stroll", "step"], "hint": "Exercise", "health_area": "exercise", "price": 5},
    {"label": "Drink water with each meal today", "aliases": ["water", "hydrate"], "hint": "Diet", "health_area": "diet", "price": 3},
    {"label": "Go to bed 30 minutes earlier tonight", "aliases": ["sleep", "bed", "rest"], "hint": "Sleep", "health_area": "sleep", "price": 5},
    {"label": "Stretch for 10 minutes today", "aliases": ["stretch", "mobility"], "hint": "Exercise", "health_area": "exercise", "price": 4},
    {"label": "Call or text someone you care about", "aliases": ["call", "friend", "family", "social"], "hint": "Social", "health_area": "social", "price": 5},
    {"label": "Cook one home meal this week", "aliases": ["cook", "dinner", "meal"], "hint": "Diet", "health_area": "diet", "price": 10},
    {"label": "Take a short outdoor break today", "aliases": ["outside", "fresh air", "sun"], "hint": "Environment", "health_area": "exercise", "price": 4},
    {"label": "Do a calm breathing exercise once today", "aliases": ["breath", "calm", "stress", "mind"], "hint": "Mind", "health_area": "mental_health", "price": 5},
    {"label": "Schedule a preventive check-up this month", "aliases": ["doctor", "screen", "prevent"], "hint": "Protect", "health_area": "protect", "price": 25},
    {"label": "Take your usual evening walk three times this week", "aliases": ["weekly", "habit", "walk"], "hint": "Recurring", "health_area": "exercise", "price": 15},
]

_VALID_RECURRENCE = ("once", "weekly", "monthly")
_VALID_HEALTH_AREAS = ("exercise", "diet", "social", "sleep", "mental_health", "protect", "relationships", "environment")


def _bounty_auth(api_key=None, sponsor_user_id=None, token=None):
    """Authorize demand-side create/list: API key (institutions) or session (friends/family).

    Returns (ok, mode, sponsor_user_id_or_None).
    """
    if demand_key_ok(api_key):
        return True, "api_key", None
    sid = (sponsor_user_id or "").strip()
    if sid and session_ok(sid, token or ""):
        return True, "session", sid
    return False, None, None


def handle_create_bounty(req, api_key=None, session_token=None):
    """Create a Universal Bounty (one-time or recurring).

    Auth: X-API-Key (institutions) OR sponsor session (friends/family).
    """
    sponsor_user_id = (req.get("sponsor_user_id") or req.get("user_id") or "").strip()
    ok, mode, sponsor = _bounty_auth(api_key, sponsor_user_id, session_token)
    if not ok:
        return (json.dumps({
            "error": "Unauthorized — sign in as a GreenDial user, or pass a valid demand-side X-API-Key"
        }), 401)

    activity = (req.get("activity") or "").strip() or DEFAULT_BOUNTY_ACTIVITY
    health_area = (req.get("health_area") or DEFAULT_BOUNTY_AREA).strip()
    if health_area not in _VALID_HEALTH_AREAS:
        health_area = DEFAULT_BOUNTY_AREA
    # relationships maps to social for suggestion typing
    if health_area == "relationships":
        health_area = "social"

    price = req.get("price")
    if price is None or price == "":
        price = DEFAULT_BOUNTY_PRICE
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = float(DEFAULT_BOUNTY_PRICE)

    currency = (req.get("currency") or DEFAULT_BOUNTY_CURRENCY).strip() or DEFAULT_BOUNTY_CURRENCY
    user_ids = req.get("user_ids") or []
    if isinstance(user_ids, str):
        user_ids = [u.strip() for u in user_ids.split(",") if u.strip()]
    if not isinstance(user_ids, list) or not user_ids:
        return (json.dumps({"error": "user_ids required — at least one GreenDial user to sponsor"}), 400)
    user_ids = [str(u).strip() for u in user_ids if str(u).strip()][:50]

    expires = (req.get("expires") or "").strip()
    recurrence = (req.get("recurrence") or "once").strip().lower()
    if recurrence not in _VALID_RECURRENCE:
        recurrence = "once"
    note = (req.get("sponsor_note") or req.get("note") or "").strip()[:300]
    title = (req.get("title") or "").strip()[:120]

    # CPAA (cost-per-action): demand pays members per completed fitness action.
    # pricing_model: "fixed" (legacy one-shot price) | "cpaa" (per verified action)
    pricing_model = (req.get("pricing_model") or req.get("model") or "fixed").strip().lower()
    if pricing_model not in ("fixed", "cpaa"):
        pricing_model = "fixed"
    action_type = (req.get("action_type") or "").strip().lower() or None
    # Canonical fitness action types for demand-side CPAA
    _CPAA_ACTIONS = {
        "run_1mi", "run_3mi", "bike_3mi", "bike_10mi", "walk_1mi", "walk_3mi",
        "steps_5k", "steps_10k", "workout_30min", "any_fitness",
    }
    if action_type and action_type not in _CPAA_ACTIONS:
        # Allow custom labels but keep them short
        action_type = re.sub(r'[^a-z0-9_]', '', action_type)[:40] or None
    try:
        cpaa_rate = float(req.get("cpaa_rate") if req.get("cpaa_rate") is not None else (
            price if pricing_model == "cpaa" else 0
        ))
    except (TypeError, ValueError):
        cpaa_rate = float(price) if pricing_model == "cpaa" else 0.0
    try:
        max_actions = int(req.get("max_actions") or 0)
    except (TypeError, ValueError):
        max_actions = 0
    max_actions = max(0, min(max_actions, 10000))  # 0 = unlimited
    try:
        budget_total = float(req.get("budget_total") or 0)
    except (TypeError, ValueError):
        budget_total = 0.0
    budget_total = max(0.0, budget_total)
    if pricing_model == "cpaa" and cpaa_rate <= 0:
        cpaa_rate = float(DEFAULT_BOUNTY_PRICE)
    # For CPAA, surface price as the per-action rate in the member UI
    if pricing_model == "cpaa":
        price = cpaa_rate

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
            "recurrence": recurrence,  # once | weekly | monthly
            "sponsor_mode": mode,      # api_key | session
            "sponsor_user_id": sponsor if mode == "session" else (req.get("sponsor_label") or "institution"),
            "sponsor_note": note,
            "title": title,
            "created": datetime.utcnow().isoformat(),
            "status": "active",
            # CPAA fields
            "pricing_model": pricing_model,
            "action_type": action_type or ("any_fitness" if pricing_model == "cpaa" else None),
            "cpaa_rate": cpaa_rate if pricing_model == "cpaa" else None,
            "max_actions": max_actions if pricing_model == "cpaa" else None,
            "budget_total": budget_total if pricing_model == "cpaa" else None,
            "actions_completed": 0,
            "spend_total": 0.0,
        }
        bounties.append(bounty)
        s3_storage.save_bounties(bounties)
        return json.dumps({
            "bounty_id": bounty["id"],
            "status": "active",
            "recurrence": recurrence,
            "activity": bounty["activity"],
            "price": price,
            "currency": currency,
            "user_ids": user_ids,
            "pricing_model": pricing_model,
            "action_type": bounty.get("action_type"),
            "cpaa_rate": bounty.get("cpaa_rate"),
            "max_actions": bounty.get("max_actions"),
            "budget_total": bounty.get("budget_total"),
        })
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_list_bounties(api_key=None, sponsor_user_id=None, session_token=None):
    ok, mode, sponsor = _bounty_auth(api_key, sponsor_user_id, session_token)
    if not ok:
        return (json.dumps({"error": "Unauthorized"}), 401)
    try:
        bounties = s3_storage.get_bounties()
        if mode == "session" and sponsor:
            # Friends/family only see bounties they sponsored
            bounties = [b for b in bounties if b.get("sponsor_user_id") == sponsor]
        return json.dumps({"bounties": bounties})
    except Exception as e:
        return json.dumps({"bounties": [], "error": str(e)})


def handle_get_bounty(bounty_id, api_key=None, sponsor_user_id=None, session_token=None):
    ok, mode, sponsor = _bounty_auth(api_key, sponsor_user_id, session_token)
    if not ok:
        return (json.dumps({"error": "Unauthorized"}), 401)
    try:
        bounties = s3_storage.get_bounties()
        for b in bounties:
            if b.get("id") == bounty_id:
                if mode == "session" and sponsor and b.get("sponsor_user_id") != sponsor:
                    return (json.dumps({"error": "Not found"}), 404)
                return json.dumps({"bounty": b})
        return (json.dumps({"error": "Not found"}), 404)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_delete_bounty(bounty_id, api_key=None, sponsor_user_id=None, session_token=None):
    ok, mode, sponsor = _bounty_auth(api_key, sponsor_user_id, session_token)
    if not ok:
        return (json.dumps({"error": "Unauthorized"}), 401)
    try:
        bounties = s3_storage.get_bounties()
        target = None
        for b in bounties:
            if b.get("id") == bounty_id:
                target = b
                break
        if not target:
            return (json.dumps({"error": "Not found"}), 404)
        if mode == "session" and sponsor and target.get("sponsor_user_id") != sponsor:
            return (json.dumps({"error": "Not found"}), 404)
        remaining = [b for b in bounties if b.get("id") != bounty_id]
        s3_storage.save_bounties(remaining)
        return json.dumps({"ok": True})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)


def handle_discover_recipients(query="", limit=30):
    """Public directory of users who opted into bounty discovery (partial public).

    Returns only non-sensitive fields. Users with bounty_discoverable=false are omitted
    (decline / opt-out). Default for new accounts is false until they opt in.
    """
    q = (query or "").strip().lower()
    try:
        limit = max(1, min(int(limit or 30), 50))
    except (TypeError, ValueError):
        limit = 30

    results = []
    try:
        user_ids = s3_storage.list_users()
    except Exception as e:
        return (json.dumps({"error": str(e), "recipients": []}), 500)

    for uid in user_ids:
        if len(results) >= limit:
            break
        try:
            user = get_user_data(uid)
        except Exception:
            continue
        if not user:
            continue
        settings = user.get("settings") or {}
        # Opt-in only — "decline" = leave off or turn off
        if not coerce_settings_bool(settings.get("bounty_discoverable"), False):
            continue
        username = (user.get("username") or uid or "").strip()
        first = (user.get("first_name") or "").strip()
        last = (user.get("last_name") or "").strip()
        display = " ".join(x for x in (first, last) if x) or username
        blurb = (settings.get("bounty_public_blurb") or "").strip()[:160]
        if q:
            hay = f"{username} {display} {blurb} {uid}".lower()
            if q not in hay:
                continue
        results.append({
            "user_id": uid,
            "username": username,
            "display_name": display,
            "blurb": blurb,
        })

    return json.dumps({
        "recipients": results,
        "count": len(results),
        "note": "Only users who opted in under Settings → Universal Bounty appear here.",
    })


def coerce_settings_bool(v, default=False):
    """Local bool coercion for settings flags (avoid circular imports of client JS)."""
    if v is True or v == 1 or v == "1":
        return True
    if v is False or v == 0 or v == "0":
        return False
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "on"):
            return True
        if s in ("false", "no", "off", ""):
            return False
    if v is None:
        return default
    return bool(v)


def _score_bounty_catalog(item, query):
    q = re.sub(r"[^a-z0-9\s]", " ", (query or "").lower())
    q = re.sub(r"\s+", " ", q).strip()
    if not q or len(q) < 2:
        return 2 if item.get("label") == DEFAULT_BOUNTY_ACTIVITY else 1
    label = item["label"].lower()
    hay = " ".join([label] + list(item.get("aliases") or []) + [item.get("hint") or ""]).lower()
    score = 0
    if label.startswith(q):
        score += 50
    elif q in label:
        score += 30
    for w in q.split():
        if len(w) > 1 and w in hay:
            score += 10
    return score


def handle_bounty_autocomplete(req):
    """AI / catalog autocomplete for demand-side bounty drafting (public, rate-friendly).

    Mirrors The Services Exchange homepage bid flow: chips that refine text without
    clobbering, plus optional LLM enrichment for activity wording + suggested price.
    Very generic by default.
    """
    description = (req.get("description") or req.get("activity") or "").strip()
    want_llm = bool(req.get("enrich") or req.get("ai") or len(description) >= 12)

    # Catalog chips
    scored = sorted(
        ({**c, "score": _score_bounty_catalog(c, description)} for c in BOUNTY_ACTIVITY_CATALOG),
        key=lambda x: -x["score"],
    )
    chips = []
    seen = set()
    for row in scored:
        key = row["label"].lower()
        if key in seen:
            continue
        if description and len(description) >= 2 and row["score"] < 10:
            continue
        seen.add(key)
        chips.append({
            "label": row["label"],
            "hint": row.get("hint"),
            "health_area": row.get("health_area"),
            "price": row.get("price"),
        })
        if len(chips) >= 5:
            break
    if not chips:
        chips = [{
            "label": DEFAULT_BOUNTY_ACTIVITY,
            "hint": "Default",
            "health_area": DEFAULT_BOUNTY_AREA,
            "price": DEFAULT_BOUNTY_PRICE,
        }]

    activity = description if len(description) >= 8 else DEFAULT_BOUNTY_ACTIVITY
    health_area = DEFAULT_BOUNTY_AREA
    price = DEFAULT_BOUNTY_PRICE
    currency = DEFAULT_BOUNTY_CURRENCY

    # Prefer top chip metadata when description is thin
    if chips and len(description) < 8:
        top = chips[0]
        activity = top["label"]
        health_area = top.get("health_area") or health_area
        price = top.get("price") if top.get("price") is not None else price

    if want_llm and description:
        prompt = (
            "You help sponsors draft a short Universal Bounty (a small paid healthy action) "
            "for a friend or family member on GreenDial.\n"
            f"Sponsor draft (may be incomplete): {description!r}\n\n"
            "Return ONLY valid JSON with keys:\n"
            '- "activity": one clear, kind, specific action (1 short sentence). '
            "Default style if vague: something as generic as "
            f"{DEFAULT_BOUNTY_ACTIVITY!r}.\n"
            '- "health_area": one of exercise, diet, social, sleep, mental_health, protect\n'
            '- "price": number — modest suggested reward in USD (typically 3–25 for daily habits; '
            "higher only for medical/admin tasks)\n"
            '- "currency": "USD"\n'
            "No markdown, no extra keys."
        )
        try:
            raw = utils.completion(prompt=prompt, temperature=0.4, max_tokens=120).strip()
            # strip code fences if any
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            if isinstance(data, dict):
                if data.get("activity"):
                    activity = str(data["activity"]).strip()[:500]
                ha = (data.get("health_area") or "").strip()
                if ha in _VALID_HEALTH_AREAS:
                    health_area = "social" if ha == "relationships" else ha
                try:
                    p = float(data.get("price"))
                    if p > 0:
                        price = p
                except (TypeError, ValueError):
                    pass
                if data.get("currency"):
                    currency = str(data["currency"]).strip()[:8]
        except Exception as e:
            print(f"[Bounty autocomplete] LLM enrich failed: {e}")

    return json.dumps({
        "activity": activity or DEFAULT_BOUNTY_ACTIVITY,
        "health_area": health_area,
        "price": price,
        "currency": currency,
        "chips": chips,
        "defaults": {
            "activity": DEFAULT_BOUNTY_ACTIVITY,
            "price": DEFAULT_BOUNTY_PRICE,
            "currency": DEFAULT_BOUNTY_CURRENCY,
            "health_area": DEFAULT_BOUNTY_AREA,
        },
    })


# ============ SUGGESTIONS ============

_SUGGESTION_AREAS = [
    ("exercise", "exercise", "Exercise Coach"),
    ("diet", "diet", "Diet Advisor"),
    ("social", "relationships", "Relationships Advisor"),
    ("sleep", "sleep", "Sleep Coach"),
    ("mind", "mental_health", "Mind Coach"),
]


_ERROR_PHRASES = ("having trouble", "please try again", "i'm sorry", "i cannot", "error")


def _generate_suggestion_text(area_label, agent_name, profile):
    """Call LLM to produce one specific, actionable suggestion for the given health area."""
    prompt = (
        f"You are a {agent_name}. Based on this user's health profile, generate ONE specific, "
        f"actionable suggestion for them today in the area of {area_label}.\n\n"
        f"Health profile:\n{json.dumps(profile, indent=2) if profile else '{}'}\n\n"
        "Respond with ONLY the suggestion text (1-2 sentences, specific and actionable). "
        "No preamble, no explanation. Phrase it as something you (the coach) are suggesting "
        "in conversation — first person as the coach is fine."
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


def _bounty_offerable_to_user(b, user):
    """Whether this bounty should surface as a suggestion for the user now.

    - once: only if never accepted into an activity
    - weekly / monthly: re-offer if last completed accept is older than the period
      (or never completed)
    """
    bounty_id = b.get("id")
    activities = user.get("activities") or []
    related = [a for a in activities if a.get("bounty_id") == bounty_id]
    recurrence = (b.get("recurrence") or "once").lower()

    if recurrence == "once":
        return not related

    # Recurring: if there's an active (not completed/abandoned) activity, don't re-offer
    for a in related:
        if a.get("status") in ("active", "accepted", "pending"):
            return False

    completed = [a for a in related if a.get("status") == "completed" and a.get("completed_at")]
    if not completed:
        return True
    last = max(completed, key=lambda a: a.get("completed_at") or "")
    try:
        last_dt = datetime.fromisoformat(str(last["completed_at"]).replace("Z", ""))
    except Exception:
        return True
    days = 7 if recurrence == "weekly" else 30
    return (datetime.utcnow() - last_dt).days >= days


def _get_active_bounties_for_user(user_id):
    """Return active, non-expired bounties that list this user_id and are offerable now."""
    try:
        bounties = s3_storage.get_bounties()
    except Exception:
        return []
    user = get_user_data(user_id) or {}
    today = datetime.utcnow().strftime('%Y-%m-%d')
    result = []
    for b in bounties:
        if b.get('status') != 'active':
            continue
        expires = b.get('expires', '')
        if expires and expires < today:
            continue
        if user_id not in b.get('user_ids', []):
            continue
        if not _bounty_offerable_to_user(b, user):
            continue
        result.append(b)
    return result


def _inject_suggestion_into_chat(user, agent_id, text):
    """Append a free suggestion into the relevant agent/Doc transcript so it
    shows up in that conversation history (listen-first proactive nudge)."""
    if not text:
        return
    timestamp = datetime.utcnow().isoformat()
    agent_id = agent_id or "doc"
    if agent_id == "doc":
        existing = user.get("transcript", "") or ""
        user["transcript"] = (
            existing + f"\n[{timestamp}] Doc: {text}"
        ).strip()
        # Cap transcript length similarly to other paths
        lines = user["transcript"].split("\n")
        if len(lines) > 300:
            user["transcript"] = "\n".join(lines[-300:])
    else:
        name = agent_id.replace("_", " ").title()
        transcripts = user.setdefault("agent_transcripts", {})
        existing = transcripts.get(agent_id, "") or ""
        existing += f"\n[{timestamp}] {name}: {text}"
        lines = existing.split("\n")
        if len(lines) > 300:
            existing = "\n".join(lines[-300:])
        transcripts[agent_id] = existing


def generate_suggestions(user_id, max_free=2, include_meta=True, include_profile_nudge=True):
    """Generate suggestions: UB bounties first, then free (chat-bound) suggestions.

    Free suggestions are also injected into the relevant agent/Doc chat transcript.
    Always tries to include one product-improvement suggestion (Doc/Feedback)
    and occasionally a profile-update nudge.
    """
    from prompts.shared.transient import (
        GREEN_DIAL_IMPROVE_SUGGESTIONS,
        PROFILE_UPDATE_SUGGESTIONS,
    )

    user = get_user_data(user_id)
    if not user:
        return []
    profile = user.get('profile', {})
    suggestions = []

    # 1) UB / bounty-backed — always first (respects once vs weekly/monthly recurrence)
    bounties = _get_active_bounties_for_user(user_id)
    _area_to_agent = {
        'exercise': 'exercise', 'diet': 'diet', 'social': 'relationships',
        'sleep': 'sleep', 'mental_health': 'mental_health', 'protect': 'protect',
        'environment': 'environment',
    }
    for b in bounties[:3]:
        area = b.get('health_area', 'exercise')
        pricing_model = b.get('pricing_model') or 'fixed'
        suggestions.append({
            "id": f"sug_{uuid.uuid4().hex[:12]}",
            "type": area,
            "agent_id": _area_to_agent.get(area, 'exercise'),
            "text": b.get('activity', ''),
            "bounty_id": b.get('id'),
            "price": b.get('price'),
            "currency": b.get('currency'),
            "recurrence": b.get('recurrence') or 'once',
            "pricing_model": pricing_model,
            "action_type": b.get('action_type'),
            "cpaa_rate": b.get('cpaa_rate') if pricing_model == 'cpaa' else None,
            "destination": "activity",  # accept → trackable UB activity
            "created": datetime.utcnow().isoformat(),
            "status": "pending",
        })

    # 2) Free LLM suggestions bound to specialist chat (not activities)
    used_areas = {s['type'] for s in suggestions}
    free_slots = max(0, max_free - sum(1 for s in suggestions if not s.get('bounty_id')))
    # Prefer areas not already covered by bounties
    areas_to_fill = [a for a in _SUGGESTION_AREAS if a[0] not in used_areas]
    random.shuffle(areas_to_fill)
    for area_label, agent_id, agent_name in areas_to_fill[:free_slots]:
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
                "destination": "chat",  # accept → open that coach's chat
                "created": datetime.utcnow().isoformat(),
                "status": "pending",
            })
            _inject_suggestion_into_chat(user, agent_id, text)

    # 3) Product-improvement free suggestion (Doc / Feedback) — always try once
    if include_meta:
        pending_meta = any(
            s.get('type') == 'greendial' and s.get('status') == 'pending'
            for s in user.get('suggestions', [])
        )
        if not pending_meta:
            meta_text = random.choice(GREEN_DIAL_IMPROVE_SUGGESTIONS)
            suggestions.append({
                "id": f"sug_{uuid.uuid4().hex[:12]}",
                "type": "greendial",
                "agent_id": "doc",
                "text": meta_text,
                "bounty_id": None,
                "price": None,
                "currency": None,
                "destination": "chat",
                "created": datetime.utcnow().isoformat(),
                "status": "pending",
            })
            _inject_suggestion_into_chat(user, "doc", meta_text)

    # 4) Occasional profile-update nudge via Doc (~40% of regenerations)
    if include_profile_nudge and random.random() < 0.4:
        profile_text = random.choice(PROFILE_UPDATE_SUGGESTIONS)
        suggestions.append({
            "id": f"sug_{uuid.uuid4().hex[:12]}",
            "type": "profile_update",
            "agent_id": "doc",
            "text": profile_text,
            "bounty_id": None,
            "price": None,
            "currency": None,
            "destination": "chat",
            "created": datetime.utcnow().isoformat(),
            "status": "pending",
        })
        _inject_suggestion_into_chat(user, "doc", profile_text)

    # Re-fetch before save to avoid stomping concurrent login/token writes
    try:
        fresh = s3_storage.get_user(user_id)
        if fresh:
            # Preserve transcript / agent_transcripts injections on the live record
            for key in ("transcript", "agent_transcripts"):
                if key in user:
                    fresh[key] = user[key]
            user = fresh
    except Exception:
        pass

    # Replace only pending; keep last 30 accepted/dismissed for history
    existing = [s for s in user.get('suggestions', []) if s.get('status') != 'pending'][-30:]
    # Order: UB (bounty) first, then free
    bounty_s = [s for s in suggestions if s.get('bounty_id')]
    free_s = [s for s in suggestions if not s.get('bounty_id')]
    user['suggestions'] = existing + bounty_s + free_s
    user['last_suggestion_gen'] = datetime.utcnow().isoformat()
    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        print(f"[Suggestions] Save failed: {e}")
    return bounty_s + free_s


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
    """Accept a suggestion.

    - UB / bounty suggestions → trackable activity
    - Free suggestions (destination=chat) → mark accepted, open chat client-side
      (already injected into the relevant transcript at generation time)
    """
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    suggestion = next((s for s in user.get('suggestions', []) if s.get('id') == suggestion_id), None)
    if not suggestion:
        return (json.dumps({"error": "Suggestion not found"}), 404)

    suggestion['status'] = 'accepted'
    dest = suggestion.get('destination') or (
        'activity' if suggestion.get('bounty_id') else 'chat'
    )

    activity = None
    if dest == 'activity' or suggestion.get('bounty_id'):
        activity = {
            "id": f"act_{uuid.uuid4().hex[:12]}",
            "suggestion_id": suggestion_id,
            "type": suggestion.get('type'),
            "agent_id": suggestion.get('agent_id'),
            "text": suggestion.get('text'),
            "bounty_id": suggestion.get('bounty_id'),
            "price": suggestion.get('price'),
            "currency": suggestion.get('currency'),
            "pricing_model": suggestion.get('pricing_model') or 'fixed',
            "action_type": suggestion.get('action_type'),
            "cpaa_rate": suggestion.get('cpaa_rate'),
            "accepted_at": datetime.utcnow().isoformat(),
            "status": "active",
            "completed_at": None,
            "wallet_snapshot": None,
            "payment_pending": False
        }
        user.setdefault('activities', []).append(activity)
    else:
        # Free / meta / profile nudges: ensure they're in chat history
        _inject_suggestion_into_chat(
            user,
            suggestion.get('agent_id') or 'doc',
            suggestion.get('text') or '',
        )

    _cache_user(user_id, user)
    try:
        s3_storage.save_user(user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    return json.dumps({
        "activity": activity,
        "destination": dest,
        "agent_id": suggestion.get('agent_id') or 'doc',
        "text": suggestion.get('text') or '',
    })


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
        # Optional GPS proof from tracker
        if isinstance(req.get('proof'), dict):
            proof = req['proof']
            activity['proof'] = {
                "miles": float(proof.get('miles') or 0),
                "meters": float(proof.get('meters') or 0),
                "duration_sec": int(proof.get('duration_sec') or 0),
                "activity_kind": (proof.get('activity_kind') or 'run')[:32],
                "points": min(len(proof.get('path') or []), 500),
            }
        payout = 0.0
        pricing_model = activity.get('pricing_model') or 'fixed'
        if activity.get('price') or activity.get('cpaa_rate'):
            activity['payment_pending'] = True
            if pricing_model == 'cpaa':
                payout = float(activity.get('cpaa_rate') or activity.get('price') or 0)
                # Advance bounty spend counters when possible
                _cpaa_record_action(activity.get('bounty_id'), payout)
            else:
                payout = float(activity.get('price') or 0)
            if payout > 0:
                user['ledger_balance'] = float(user.get('ledger_balance') or 0) + payout
                activity['ledger_credited'] = payout
        _touch_fitness_stats(user, miles=(activity.get('proof') or {}).get('miles') or 0)
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
    return json.dumps({"activity": activity, "ledger_balance": user.get('ledger_balance')})


# ============ DEMAND-SIDE /generate ============

def handle_generate_demand(req, api_key=None, session_token=None):
    """Preview a UB for a recipient.

    Auth: demand API key OR signed-in sponsor session.
    If description is provided, uses bounty autocomplete path (generic-friendly).
    Otherwise generates from recipient profile (institutions).
    """
    sponsor_user_id = (req.get("sponsor_user_id") or "").strip()
    ok, mode, sponsor = _bounty_auth(api_key, sponsor_user_id, session_token)
    if not ok:
        return (json.dumps({"error": "Unauthorized"}), 401)

    user_id = (req.get('user_id') or '').strip()
    if not user_id:
        return (json.dumps({"error": "user_id required"}), 400)

    health_area = (req.get('health_area') or '').strip()
    price = req.get('price')
    description = (req.get('description') or req.get('activity') or '').strip()
    recurrence = (req.get('recurrence') or 'once').strip().lower()
    if recurrence not in _VALID_RECURRENCE:
        recurrence = 'once'

    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    profile = user.get('profile', {})

    # Path A: description-first (friends/family autocomplete style)
    if description or not health_area:
        ac = json.loads(handle_bounty_autocomplete({
            "description": description or DEFAULT_BOUNTY_ACTIVITY,
            "enrich": bool(description and len(description) >= 8),
        }))
        text = ac.get("activity") or DEFAULT_BOUNTY_ACTIVITY
        health_area = health_area or ac.get("health_area") or DEFAULT_BOUNTY_AREA
        if price is None or price == "":
            price = ac.get("price", DEFAULT_BOUNTY_PRICE)
        currency = ac.get("currency") or DEFAULT_BOUNTY_CURRENCY
        agent_id = {
            'exercise': 'exercise', 'diet': 'diet', 'social': 'relationships',
            'sleep': 'sleep', 'mental_health': 'mental_health', 'protect': 'protect',
        }.get(health_area, 'exercise')
    else:
        # Path B: profile-aware institutional generate
        _area_map = {
            'exercise': ('exercise', 'Exercise Coach'),
            'diet': ('diet', 'Diet Advisor'),
            'social': ('relationships', 'Relationships Advisor'),
            'sleep': ('sleep', 'Sleep Coach'),
            'mental_health': ('mental_health', 'Mind Coach'),
            'protect': ('protect', 'Protect AI'),
        }
        if not health_area:
            health_area = random.choice(['exercise', 'diet', 'social'])
        agent_id, agent_name = _area_map.get(health_area, ('exercise', 'Exercise Coach'))
        text = _generate_suggestion_text(health_area, agent_name, profile)
        if not text:
            text = DEFAULT_BOUNTY_ACTIVITY
            health_area = DEFAULT_BOUNTY_AREA
            agent_id = 'exercise'
        if price is None or price == "":
            price = DEFAULT_BOUNTY_PRICE
        currency = (req.get('currency') or DEFAULT_BOUNTY_CURRENCY)

    try:
        price = float(price)
    except (TypeError, ValueError):
        price = float(DEFAULT_BOUNTY_PRICE)

    pricing_model = (req.get("pricing_model") or req.get("model") or "fixed").strip().lower()
    if pricing_model not in ("fixed", "cpaa"):
        pricing_model = "fixed"
    action_type = (req.get("action_type") or "").strip().lower() or None
    if pricing_model == "cpaa" and not action_type:
        action_type = "any_fitness"
    try:
        cpaa_rate = float(req.get("cpaa_rate") if req.get("cpaa_rate") is not None else price)
    except (TypeError, ValueError):
        cpaa_rate = float(price)

    bounty_payload = {
        "activity": text,
        "health_area": health_area,
        "price": price if pricing_model == "fixed" else cpaa_rate,
        "currency": currency,
        "user_ids": [user_id],
        "recurrence": recurrence,
        "pricing_model": pricing_model,
    }
    if pricing_model == "cpaa":
        bounty_payload["action_type"] = action_type
        bounty_payload["cpaa_rate"] = cpaa_rate
        if req.get("max_actions") is not None:
            bounty_payload["max_actions"] = req.get("max_actions")
        if req.get("budget_total") is not None:
            bounty_payload["budget_total"] = req.get("budget_total")
    if mode == "session" and sponsor:
        bounty_payload["sponsor_user_id"] = sponsor

    return json.dumps({
        "suggestion": {"text": text, "agent_id": agent_id, "health_area": health_area},
        "bounty_payload": bounty_payload,
        "bounty_post_url": "/bounty",
        "defaults": {
            "activity": DEFAULT_BOUNTY_ACTIVITY,
            "price": DEFAULT_BOUNTY_PRICE,
            "currency": DEFAULT_BOUNTY_CURRENCY,
            "pricing_model": "fixed",
            "action_types": [
                "run_1mi", "run_3mi", "bike_3mi", "bike_10mi", "walk_1mi", "walk_3mi",
                "steps_5k", "steps_10k", "workout_30min", "any_fitness",
            ],
        },
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


# ============ CPAA HELPERS + FITNESS STAKE LEAGUES ============

_CHALLENGE_TEMPLATES = [
    {
        "slug": "daily-run-1",
        "name": "Daily Mile Club",
        "tagline": "Run 1 mile every day. Top half keep their stake.",
        "challenge_type": "run_1mi_daily",
        "activity_kind": "run",
        "daily_goal_miles": 1.0,
        "stake": 50.0,
        "emoji": "🏃",
        "duration_days": 30,
        "max_members": 24,
    },
    {
        "slug": "daily-bike-3",
        "name": "Bike 3 Challenge",
        "tagline": "Ride 3 miles a day. Consistency wins the pot.",
        "challenge_type": "bike_3mi_daily",
        "activity_kind": "bike",
        "daily_goal_miles": 3.0,
        "stake": 50.0,
        "emoji": "🚴",
        "duration_days": 30,
        "max_members": 24,
    },
    {
        "slug": "walk-3-grind",
        "name": "Walk It Off",
        "tagline": "Walk 3 miles daily. Skin in the game.",
        "challenge_type": "walk_3mi_daily",
        "activity_kind": "walk",
        "daily_goal_miles": 3.0,
        "stake": 25.0,
        "emoji": "👟",
        "duration_days": 21,
        "max_members": 32,
    },
    {
        "slug": "weekend-warriors",
        "name": "Weekend Warriors",
        "tagline": "Hit 5 miles every Sat+Sun. Top half cashes stake back.",
        "challenge_type": "weekend_5mi",
        "activity_kind": "run",
        "daily_goal_miles": 5.0,
        "stake": 40.0,
        "emoji": "🔥",
        "duration_days": 56,
        "max_members": 20,
        "days_of_week": [5, 6],  # Sat/Sun if using weekday checks; score still by logged miles
    },
]


def _cpaa_record_action(bounty_id, payout):
    """Increment CPAA spend on the bounty; auto-close if budget/max hit."""
    if not bounty_id or payout <= 0:
        return
    try:
        bounties = s3_storage.get_bounties()
    except Exception:
        return
    changed = False
    for b in bounties:
        if b.get('id') != bounty_id:
            continue
        if (b.get('pricing_model') or 'fixed') != 'cpaa':
            break
        b['actions_completed'] = int(b.get('actions_completed') or 0) + 1
        b['spend_total'] = float(b.get('spend_total') or 0) + float(payout)
        max_a = int(b.get('max_actions') or 0)
        budget = float(b.get('budget_total') or 0)
        if max_a and b['actions_completed'] >= max_a:
            b['status'] = 'exhausted'
        if budget and b['spend_total'] >= budget:
            b['status'] = 'exhausted'
        changed = True
        break
    if changed:
        try:
            s3_storage.save_bounties(bounties)
        except Exception as e:
            print(f"[CPAA] Failed to update bounty spend: {e}")


def _touch_fitness_stats(user, miles=0):
    """Update streak / totals on a user after a completed fitness action."""
    stats = user.setdefault('fitness_stats', {
        "total_miles": 0.0,
        "total_activities": 0,
        "current_streak_days": 0,
        "best_streak_days": 0,
        "last_activity_date": None,
    })
    today = datetime.utcnow().strftime('%Y-%m-%d')
    last = stats.get('last_activity_date')
    stats['total_miles'] = float(stats.get('total_miles') or 0) + float(miles or 0)
    stats['total_activities'] = int(stats.get('total_activities') or 0) + 1
    if last == today:
        pass  # already counted streak today
    else:
        from datetime import timedelta
        yday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        if last == yday:
            stats['current_streak_days'] = int(stats.get('current_streak_days') or 0) + 1
        else:
            stats['current_streak_days'] = 1
        stats['best_streak_days'] = max(
            int(stats.get('best_streak_days') or 0),
            int(stats.get('current_streak_days') or 0),
        )
        stats['last_activity_date'] = today


def _ensure_ledger(user):
    if user.get('ledger_balance') is None:
        # First touch for pre-play accounts: one-time $50 welcome stake credit
        if not user.get('ledger_initialized'):
            user['ledger_balance'] = 50.0
            user['ledger_initialized'] = True
        else:
            user['ledger_balance'] = 0.0
    if not user.get('ledger_currency'):
        user['ledger_currency'] = 'USD'
    return float(user.get('ledger_balance') or 0)


def _append_feed(event):
    try:
        events = s3_storage.get_feed_events(limit=200)
    except Exception:
        events = []
    event = dict(event)
    event.setdefault('id', f"evt_{uuid.uuid4().hex[:10]}")
    event.setdefault('ts', datetime.utcnow().isoformat())
    events.insert(0, event)
    try:
        s3_storage.save_feed_events(events[:200])
    except Exception as e:
        print(f"[Feed] save failed: {e}")


def _public_member(m):
    return {
        "user_id": m.get("user_id"),
        "username": m.get("username"),
        "joined_at": m.get("joined_at"),
        "stake": m.get("stake"),
        "days_hit": m.get("days_hit", 0),
        "total_miles": round(float(m.get("total_miles") or 0), 2),
        "score": m.get("score", 0),
        "last_log_date": m.get("last_log_date"),
        "status": m.get("status", "active"),
        "rank": m.get("rank"),
        "payout": m.get("payout"),
    }


def _score_members(challenge):
    """Score = days_hit * 100 + total_miles (consistency first). Rank in place."""
    members = challenge.get('members') or []
    for m in members:
        if m.get('status') == 'left':
            m['score'] = -1
            continue
        days = int(m.get('days_hit') or 0)
        miles = float(m.get('total_miles') or 0)
        m['score'] = days * 100 + miles
    active = [m for m in members if m.get('status') != 'left']
    active.sort(key=lambda x: (-float(x.get('score') or 0), x.get('joined_at') or ''))
    for i, m in enumerate(active):
        m['rank'] = i + 1
    # left members keep no rank
    for m in members:
        if m.get('status') == 'left':
            m['rank'] = None
    return active


def _challenge_public(challenge, viewer_id=None):
    members = challenge.get('members') or []
    active = [m for m in members if m.get('status') != 'left']
    pot = sum(float(m.get('stake') or 0) for m in active)
    me = None
    if viewer_id:
        me = next((m for m in members if m.get('user_id') == viewer_id), None)
    return {
        "id": challenge.get("id"),
        "name": challenge.get("name"),
        "tagline": challenge.get("tagline"),
        "emoji": challenge.get("emoji") or "🏆",
        "challenge_type": challenge.get("challenge_type"),
        "activity_kind": challenge.get("activity_kind") or "run",
        "daily_goal_miles": challenge.get("daily_goal_miles"),
        "stake": challenge.get("stake"),
        "currency": challenge.get("currency") or "USD",
        "payout_rule": challenge.get("payout_rule") or "top_half_refund",
        "start_date": challenge.get("start_date"),
        "end_date": challenge.get("end_date"),
        "status": challenge.get("status"),
        "max_members": challenge.get("max_members"),
        "member_count": len(active),
        "pot": round(pot, 2),
        "is_member": bool(me and me.get('status') != 'left'),
        "my_rank": (me or {}).get('rank'),
        "my_score": (me or {}).get('score'),
        "invite_only": bool(challenge.get('invite_only')),
        "created": challenge.get("created"),
    }


def _seed_default_challenges():
    """Create open public leagues if none exist."""
    try:
        existing = s3_storage.get_challenges()
    except Exception:
        existing = []
    if existing:
        return existing
    from datetime import timedelta
    today = datetime.utcnow().date()
    challenges = []
    for t in _CHALLENGE_TEMPLATES:
        start = today.isoformat()
        end = (today + timedelta(days=int(t.get('duration_days') or 30))).isoformat()
        challenges.append({
            "id": f"lg_{uuid.uuid4().hex[:10]}",
            "slug": t["slug"],
            "name": t["name"],
            "tagline": t["tagline"],
            "emoji": t.get("emoji") or "🏆",
            "challenge_type": t["challenge_type"],
            "activity_kind": t.get("activity_kind") or "run",
            "daily_goal_miles": float(t.get("daily_goal_miles") or 1),
            "stake": float(t.get("stake") or 50),
            "currency": "USD",
            "payout_rule": "top_half_refund",
            "start_date": start,
            "end_date": end,
            "status": "open",  # open | active | settled
            "max_members": int(t.get("max_members") or 24),
            "invite_only": False,
            "members": [],
            "logs": [],  # recent check-ins (capped)
            "created": datetime.utcnow().isoformat(),
            "created_by": "system",
        })
    try:
        s3_storage.save_challenges(challenges)
    except Exception as e:
        print(f"[Leagues] seed failed: {e}")
    return challenges


def handle_public_config():
    """Non-secret client config (Mapbox token if configured)."""
    token = getattr(config, 'MAPBOX_ACCESS_TOKEN', None) or getattr(config, 'MAPBOX_TOKEN', None) or ''
    return json.dumps({
        "mapbox_token": token or None,
        "map_provider": "mapbox" if token else "osm",
        "product": {
            "name": "GreenDial",
            "tagline": "Skin in the game. Get paid to move.",
            "payout_rule": "top_half_refund",
        },
    })


def handle_list_challenges(user_id=None, token=None):
    """List open/active leagues. Optional auth for membership flags + invites."""
    if user_id and token and not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    try:
        challenges = _seed_default_challenges()
    except Exception as e:
        return (json.dumps({"error": str(e), "challenges": []}), 500)

    # Expire / activate by date
    today = datetime.utcnow().strftime('%Y-%m-%d')
    dirty = False
    for c in challenges:
        if c.get('status') in ('open', 'active'):
            if c.get('end_date') and c['end_date'] < today and c.get('status') != 'settled':
                # leave as active until someone settles; mark ended
                c['status'] = 'ended'
                dirty = True
            elif c.get('start_date') and c['start_date'] <= today and c.get('status') == 'open' and len(c.get('members') or []) >= 2:
                c['status'] = 'active'
                dirty = True
    if dirty:
        try:
            s3_storage.save_challenges(challenges)
        except Exception:
            pass

    public = [_challenge_public(c, user_id) for c in challenges
              if c.get('status') not in ('archived',)]
    # Sort: member leagues first, then open, then by pot
    public.sort(key=lambda x: (
        0 if x.get('is_member') else 1,
        0 if x.get('status') in ('open', 'active') else 1,
        -float(x.get('pot') or 0),
    ))
    balance = None
    if user_id:
        u = get_user_data(user_id)
        if u:
            balance = _ensure_ledger(u)
    return json.dumps({
        "challenges": public,
        "ledger_balance": balance,
        "ledger_currency": "USD",
    })


def handle_get_challenge(challenge_id, user_id=None, token=None):
    if user_id and token and not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    challenges = _seed_default_challenges()
    challenge = next((c for c in challenges if c.get('id') == challenge_id), None)
    if not challenge:
        return (json.dumps({"error": "Not found"}), 404)
    _score_members(challenge)
    leaderboard = [_public_member(m) for m in (challenge.get('members') or [])
                   if m.get('status') != 'left']
    leaderboard.sort(key=lambda x: (x.get('rank') or 9999))
    detail = _challenge_public(challenge, user_id)
    detail['leaderboard'] = leaderboard
    detail['recent_logs'] = (challenge.get('logs') or [])[:30]
    detail['rules'] = {
        "payout": "Top half of the leaderboard get their stake back when the league settles. "
                  "Bottom half fund the prize culture — demand-side CPAA partners stack extra pay on fitness actions.",
        "scoring": "1 point per day you hit the distance goal (+ miles as tie-break).",
        "daily_goal_miles": challenge.get('daily_goal_miles'),
        "activity_kind": challenge.get('activity_kind'),
    }
    return json.dumps({"challenge": detail})


def handle_create_challenge(user_id, token, req):
    """Create a custom stake league (session required)."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    name = (req.get('name') or '').strip()[:80]
    if not name:
        return (json.dumps({"error": "name required"}), 400)
    try:
        stake = float(req.get('stake') if req.get('stake') is not None else 50)
    except (TypeError, ValueError):
        stake = 50.0
    stake = max(5.0, min(stake, 500.0))
    try:
        daily_goal = float(req.get('daily_goal_miles') if req.get('daily_goal_miles') is not None else 1)
    except (TypeError, ValueError):
        daily_goal = 1.0
    daily_goal = max(0.25, min(daily_goal, 50.0))
    activity_kind = (req.get('activity_kind') or 'run').strip().lower()
    if activity_kind not in ('run', 'bike', 'walk', 'any'):
        activity_kind = 'run'
    try:
        duration_days = int(req.get('duration_days') or 30)
    except (TypeError, ValueError):
        duration_days = 30
    duration_days = max(7, min(duration_days, 365))
    try:
        max_members = int(req.get('max_members') or 20)
    except (TypeError, ValueError):
        max_members = 20
    max_members = max(2, min(max_members, 100))
    invite_only = bool(req.get('invite_only'))

    from datetime import timedelta
    today = datetime.utcnow().date()
    start = (req.get('start_date') or today.isoformat())[:10]
    end = (req.get('end_date') or (today + timedelta(days=duration_days)).isoformat())[:10]
    emoji = (req.get('emoji') or '🏆')[:4]
    tagline = (req.get('tagline') or f"Stake ${stake:.0f}. Hit {daily_goal:g} mi/day. Top half get stake back.")[:160]

    challenge = {
        "id": f"lg_{uuid.uuid4().hex[:10]}",
        "slug": re.sub(r'[^a-z0-9]+', '-', name.lower())[:40],
        "name": name,
        "tagline": tagline,
        "emoji": emoji,
        "challenge_type": req.get('challenge_type') or f"{activity_kind}_{daily_goal:g}mi_daily",
        "activity_kind": activity_kind,
        "daily_goal_miles": daily_goal,
        "stake": stake,
        "currency": "USD",
        "payout_rule": "top_half_refund",
        "start_date": start,
        "end_date": end,
        "status": "open",
        "max_members": max_members,
        "invite_only": invite_only,
        "members": [],
        "logs": [],
        "created": datetime.utcnow().isoformat(),
        "created_by": user_id,
    }

    challenges = _seed_default_challenges()
    challenges.append(challenge)
    try:
        s3_storage.save_challenges(challenges)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    _append_feed({
        "type": "league_created",
        "username": user.get('username') or user_id,
        "user_id": user_id,
        "challenge_id": challenge['id'],
        "challenge_name": name,
        "text": f"created {emoji} {name} — ${stake:.0f} stake",
    })
    return json.dumps({"challenge": _challenge_public(challenge, user_id)})


def handle_join_challenge(challenge_id, user_id, token, req=None):
    """Join a league: deduct stake from ledger into the pot."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    challenges = _seed_default_challenges()
    challenge = next((c for c in challenges if c.get('id') == challenge_id), None)
    if not challenge:
        return (json.dumps({"error": "Not found"}), 404)
    if challenge.get('status') in ('settled', 'ended', 'archived'):
        return (json.dumps({"error": "This league is closed"}), 400)

    members = challenge.setdefault('members', [])
    existing = next((m for m in members if m.get('user_id') == user_id), None)
    if existing and existing.get('status') != 'left':
        return (json.dumps({"error": "Already in this league", "challenge": _challenge_public(challenge, user_id)}), 409)

    active = [m for m in members if m.get('status') != 'left']
    if len(active) >= int(challenge.get('max_members') or 24):
        return (json.dumps({"error": "League is full"}), 400)

    if challenge.get('invite_only'):
        invites = challenge.get('invites') or []
        if user_id not in invites and challenge.get('created_by') != user_id:
            return (json.dumps({"error": "Invite required"}), 403)

    stake = float(challenge.get('stake') or 50)
    bal = _ensure_ledger(user)
    if bal < stake:
        return (json.dumps({
            "error": f"Need ${stake:.0f} stake — your balance is ${bal:.2f}. Complete CPAA activities or wait for a top-up.",
            "ledger_balance": bal,
            "stake": stake,
        }), 402)

    user['ledger_balance'] = bal - stake
    member = {
        "user_id": user_id,
        "username": user.get('username') or user_id,
        "joined_at": datetime.utcnow().isoformat(),
        "stake": stake,
        "days_hit": 0,
        "total_miles": 0.0,
        "score": 0,
        "last_log_date": None,
        "hit_dates": [],
        "status": "active",
    }
    if existing:
        # rejoin
        existing.update(member)
    else:
        members.append(member)

    if challenge.get('status') == 'open' and len([m for m in members if m.get('status') != 'left']) >= 2:
        challenge['status'] = 'active'

    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
        s3_storage.save_challenges(challenges)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    _append_feed({
        "type": "join",
        "username": user.get('username'),
        "user_id": user_id,
        "challenge_id": challenge_id,
        "challenge_name": challenge.get('name'),
        "text": f"staked ${stake:.0f} on {challenge.get('emoji', '🏆')} {challenge.get('name')}",
    })
    _score_members(challenge)
    return json.dumps({
        "ok": True,
        "challenge": _challenge_public(challenge, user_id),
        "ledger_balance": user['ledger_balance'],
        "stake_paid": stake,
    })


def handle_log_challenge_activity(challenge_id, user_id, token, req):
    """Log a GPS-tracked (or manual) fitness session toward a league day goal."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    challenges = _seed_default_challenges()
    challenge = next((c for c in challenges if c.get('id') == challenge_id), None)
    if not challenge:
        return (json.dumps({"error": "Not found"}), 404)
    if challenge.get('status') in ('settled', 'archived'):
        return (json.dumps({"error": "League is settled"}), 400)

    members = challenge.get('members') or []
    member = next((m for m in members if m.get('user_id') == user_id and m.get('status') != 'left'), None)
    if not member:
        return (json.dumps({"error": "Join this league first"}), 403)

    try:
        miles = float(req.get('miles') if req.get('miles') is not None else 0)
    except (TypeError, ValueError):
        miles = 0.0
    if miles <= 0 and req.get('meters'):
        try:
            miles = float(req.get('meters')) / 1609.344
        except (TypeError, ValueError):
            miles = 0.0
    if miles <= 0:
        return (json.dumps({"error": "miles (or meters) required"}), 400)
    miles = round(min(miles, 100.0), 3)  # sanity cap

    activity_kind = (req.get('activity_kind') or challenge.get('activity_kind') or 'run')[:32]
    duration_sec = 0
    try:
        duration_sec = max(0, int(req.get('duration_sec') or 0))
    except (TypeError, ValueError):
        duration_sec = 0

    # Path samples optional (store count only to keep JSON small)
    path = req.get('path') or []
    path_points = min(len(path) if isinstance(path, list) else 0, 2000)

    today = datetime.utcnow().strftime('%Y-%m-%d')
    # Accumulate same-day miles
    day_logs = member.setdefault('day_miles', {})
    prev = float(day_logs.get(today) or 0)
    day_logs[today] = round(prev + miles, 3)
    member['total_miles'] = round(float(member.get('total_miles') or 0) + miles, 3)
    member['last_log_date'] = today

    goal = float(challenge.get('daily_goal_miles') or 1)
    hit_dates = member.setdefault('hit_dates', [])
    newly_hit = False
    if day_logs[today] >= goal and today not in hit_dates:
        hit_dates.append(today)
        member['days_hit'] = len(hit_dates)
        newly_hit = True

    log_entry = {
        "user_id": user_id,
        "username": user.get('username'),
        "miles": miles,
        "day_total": day_logs[today],
        "activity_kind": activity_kind,
        "duration_sec": duration_sec,
        "path_points": path_points,
        "goal_hit": day_logs[today] >= goal,
        "ts": datetime.utcnow().isoformat(),
        "date": today,
    }
    logs = challenge.setdefault('logs', [])
    logs.insert(0, log_entry)
    challenge['logs'] = logs[:100]

    # Also store on user fitness log
    flogs = user.setdefault('fitness_logs', [])
    flogs.insert(0, {
        "id": f"flog_{uuid.uuid4().hex[:10]}",
        "challenge_id": challenge_id,
        "miles": miles,
        "activity_kind": activity_kind,
        "duration_sec": duration_sec,
        "ts": log_entry['ts'],
        "date": today,
    })
    user['fitness_logs'] = flogs[:100]
    _touch_fitness_stats(user, miles=miles)

    # CPAA: if demand-side CPAA bounties target this user for matching action, credit once per day
    cpaa_credit = _maybe_credit_cpaa_for_fitness(user, activity_kind, miles)

    _score_members(challenge)
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
        s3_storage.save_challenges(challenges)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    if newly_hit:
        _append_feed({
            "type": "day_hit",
            "username": user.get('username'),
            "user_id": user_id,
            "challenge_id": challenge_id,
            "challenge_name": challenge.get('name'),
            "text": f"hit day goal in {challenge.get('emoji', '🏆')} {challenge.get('name')} ({day_logs[today]:g} mi)",
            "miles": day_logs[today],
        })
    else:
        _append_feed({
            "type": "activity",
            "username": user.get('username'),
            "user_id": user_id,
            "challenge_id": challenge_id,
            "challenge_name": challenge.get('name'),
            "text": f"logged {miles:g} mi ({activity_kind}) — {challenge.get('name')}",
            "miles": miles,
        })

    return json.dumps({
        "ok": True,
        "log": log_entry,
        "member": _public_member(member),
        "newly_hit": newly_hit,
        "ledger_balance": user.get('ledger_balance'),
        "cpaa_credit": cpaa_credit,
        "challenge": _challenge_public(challenge, user_id),
    })


def _maybe_credit_cpaa_for_fitness(user, activity_kind, miles):
    """Pay user from matching active CPAA bounties (max one credit per bounty per day)."""
    user_id = user.get('user_id')
    if not user_id:
        return 0.0
    try:
        bounties = s3_storage.get_bounties()
    except Exception:
        return 0.0
    today = datetime.utcnow().strftime('%Y-%m-%d')
    credited = 0.0
    for b in bounties:
        if b.get('status') != 'active':
            continue
        if (b.get('pricing_model') or 'fixed') != 'cpaa':
            continue
        if user_id not in (b.get('user_ids') or []):
            continue
        expires = b.get('expires') or ''
        if expires and expires < today:
            continue
        # Action type match (loose)
        at = (b.get('action_type') or 'any_fitness')
        kind = (activity_kind or '').lower()
        if at != 'any_fitness':
            if 'run' in at and kind not in ('run', 'jog'):
                continue
            if 'bike' in at and kind not in ('bike', 'cycle', 'cycling'):
                continue
            if 'walk' in at and kind not in ('walk', 'hike'):
                continue
            # Distance thresholds encoded in action_type like run_1mi
            m = re.search(r'(\d+(?:\.\d+)?)mi', at)
            if m and miles < float(m.group(1)) * 0.9:  # 10% GPS tolerance
                continue
        # Budget / max
        rate = float(b.get('cpaa_rate') or b.get('price') or 0)
        if rate <= 0:
            continue
        max_a = int(b.get('max_actions') or 0)
        if max_a and int(b.get('actions_completed') or 0) >= max_a:
            continue
        budget = float(b.get('budget_total') or 0)
        if budget and float(b.get('spend_total') or 0) + rate > budget + 0.001:
            continue
        # Once per bounty per day
        cpaa_days = user.setdefault('cpaa_credit_days', {})
        key = b.get('id')
        if cpaa_days.get(key) == today:
            continue
        cpaa_days[key] = today
        user['ledger_balance'] = float(user.get('ledger_balance') or 0) + rate
        credited += rate
        # Track as payment_pending activity for admin settlement
        user.setdefault('activities', []).append({
            "id": f"act_{uuid.uuid4().hex[:12]}",
            "type": "exercise",
            "text": b.get('activity') or f"CPAA {at}",
            "bounty_id": b.get('id'),
            "price": rate,
            "currency": b.get('currency') or 'USD',
            "pricing_model": "cpaa",
            "action_type": at,
            "cpaa_rate": rate,
            "accepted_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "status": "completed",
            "payment_pending": True,
            "ledger_credited": rate,
            "auto_from": "fitness_log",
        })
        _cpaa_record_action(b.get('id'), rate)
    return credited


def handle_settle_challenge(challenge_id, user_id, token):
    """Settle league: top half get stake refunded to ledger."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    challenges = _seed_default_challenges()
    challenge = next((c for c in challenges if c.get('id') == challenge_id), None)
    if not challenge:
        return (json.dumps({"error": "Not found"}), 404)
    if challenge.get('status') == 'settled':
        return json.dumps({"ok": True, "challenge": _challenge_public(challenge, user_id), "already": True})

    # Creator or admin can settle; also allow any member after end_date
    today = datetime.utcnow().strftime('%Y-%m-%d')
    is_creator = challenge.get('created_by') == user_id
    is_admin = _admin_ok(user_id, token)
    ended = (challenge.get('end_date') or '') <= today
    member = next((m for m in (challenge.get('members') or [])
                   if m.get('user_id') == user_id and m.get('status') != 'left'), None)
    if not (is_creator or is_admin or (ended and member)):
        return (json.dumps({"error": "Only creator/admin, or members after end date, can settle"}), 403)

    ranked = _score_members(challenge)
    n = len(ranked)
    if n == 0:
        challenge['status'] = 'settled'
        challenge['settled_at'] = datetime.utcnow().isoformat()
        try:
            s3_storage.save_challenges(challenges)
        except Exception as e:
            return (json.dumps({"error": str(e)}), 500)
        return json.dumps({"ok": True, "winners": [], "challenge": _challenge_public(challenge, user_id)})

    # Top half (ceil): e.g. 5 members → top 3; 4 → top 2
    import math
    winner_count = max(1, math.ceil(n / 2.0))
    winners = ranked[:winner_count]
    winner_ids = {m['user_id'] for m in winners}

    for m in challenge.get('members') or []:
        if m.get('status') == 'left':
            continue
        uid = m.get('user_id')
        stake = float(m.get('stake') or 0)
        if uid in winner_ids:
            m['payout'] = stake  # get money back
            m['result'] = 'win'
            u = get_user_data(uid)
            if u:
                u['ledger_balance'] = float(u.get('ledger_balance') or 0) + stake
                try:
                    s3_storage.save_user(uid, u)
                    _cache_user(uid, u)
                except Exception as e:
                    print(f"[Settle] credit {uid}: {e}")
        else:
            m['payout'] = 0
            m['result'] = 'lose'

    challenge['status'] = 'settled'
    challenge['settled_at'] = datetime.utcnow().isoformat()
    challenge['winner_count'] = winner_count
    try:
        s3_storage.save_challenges(challenges)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)

    _append_feed({
        "type": "settle",
        "challenge_id": challenge_id,
        "challenge_name": challenge.get('name'),
        "text": f"{challenge.get('emoji', '🏆')} {challenge.get('name')} settled — top {winner_count} got stakes back",
    })
    return json.dumps({
        "ok": True,
        "winner_count": winner_count,
        "winners": [_public_member(m) for m in winners],
        "challenge": _challenge_public(challenge, user_id),
    })


def handle_challenge_invites(user_id, token):
    """Suggest leagues + people to invite based on profile + Doc chat signals."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)

    profile = user.get('profile') or {}
    transcript = (user.get('transcript') or '') + ' ' + ' '.join(
        (user.get('agent_transcripts') or {}).values()
    )
    blob = (json.dumps(profile) + ' ' + transcript).lower()

    scores = {
        "run_1mi_daily": 1,
        "bike_3mi_daily": 1,
        "walk_3mi_daily": 1,
        "weekend_5mi": 1,
    }
    if any(w in blob for w in ('run', 'running', 'jog', '5k', 'marathon', 'mile')):
        scores['run_1mi_daily'] += 5
        scores['weekend_5mi'] += 3
    if any(w in blob for w in ('bike', 'cycling', 'cycle', 'peloton')):
        scores['bike_3mi_daily'] += 5
    if any(w in blob for w in ('walk', 'steps', 'hike', 'outdoors')):
        scores['walk_3mi_daily'] += 4
    if any(w in blob for w in ('weight', 'lose', 'fat', 'cardio', 'fitness')):
        scores['run_1mi_daily'] += 2
        scores['walk_3mi_daily'] += 2
    if any(w in blob for w in ('weekend', 'busy', 'schedule')):
        scores['weekend_5mi'] += 3

    challenges = _seed_default_challenges()
    ranked_types = sorted(scores.keys(), key=lambda k: -scores[k])
    suggestions = []
    for ctype in ranked_types:
        match = next((c for c in challenges
                      if c.get('challenge_type') == ctype
                      and c.get('status') in ('open', 'active')), None)
        if match:
            suggestions.append({
                "reason": _invite_reason(ctype, blob),
                "challenge": _challenge_public(match, user_id),
                "affinity": scores[ctype],
            })

    # Peer invites: users with overlapping fitness goals who are discoverable
    peers = []
    try:
        for uid in s3_storage.list_users()[:80]:
            if uid == user_id:
                continue
            try:
                ou = get_user_data(uid)
            except Exception:
                continue
            if not ou:
                continue
            settings = ou.get('settings') or {}
            if not settings.get('bounty_discoverable') and not (ou.get('fitness_stats') or {}).get('total_activities'):
                continue
            oblob = json.dumps(ou.get('profile') or {}).lower()
            overlap = 0
            for w in ('run', 'bike', 'walk', 'exercise', 'fitness', 'weight'):
                if w in blob and w in oblob:
                    overlap += 1
            if overlap or (ou.get('fitness_stats') or {}).get('total_activities'):
                peers.append({
                    "user_id": uid,
                    "username": ou.get('username'),
                    "blurb": (settings.get('bounty_public_blurb') or '')[:120],
                    "overlap": overlap,
                    "miles": (ou.get('fitness_stats') or {}).get('total_miles') or 0,
                })
            if len(peers) >= 8:
                break
    except Exception:
        pass
    peers.sort(key=lambda p: (-p.get('overlap', 0), -float(p.get('miles') or 0)))

    return json.dumps({
        "suggested_leagues": suggestions[:4],
        "suggested_peers": peers[:6],
        "profile_signals": {
            "run": 'run' in blob or 'jog' in blob,
            "bike": 'bike' in blob or 'cycl' in blob,
            "walk": 'walk' in blob or 'steps' in blob,
        },
    })


def _invite_reason(ctype, blob):
    if ctype.startswith('run') and ('run' in blob or 'jog' in blob):
        return "Doc chats + profile point to running — this league fits."
    if ctype.startswith('bike') and ('bike' in blob or 'cycl' in blob):
        return "You've talked about cycling — stake a Bike 3 group."
    if ctype.startswith('walk') and ('walk' in blob or 'steps' in blob):
        return "Walking goals show up in your profile — join a walk league."
    if 'weekend' in ctype:
        return "Good for packed weeks — only weekends count."
    return "Popular open league — put skin in the game."


def handle_get_feed(user_id=None, token=None, limit=40):
    if user_id and token and not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    try:
        limit = max(1, min(int(limit or 40), 100))
    except (TypeError, ValueError):
        limit = 40
    try:
        events = s3_storage.get_feed_events(limit=limit)
    except Exception as e:
        return json.dumps({"events": [], "error": str(e)})
    return json.dumps({"events": events})


def handle_get_ledger(user_id, token):
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    bal = _ensure_ledger(user)
    # Persist if we had to default
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception:
        pass
    return json.dumps({
        "ledger_balance": bal,
        "ledger_currency": user.get('ledger_currency') or 'USD',
        "fitness_stats": user.get('fitness_stats') or {},
        "welcome_note": "New players start with $50 play credit to join a league. "
                        "CPAA sponsors pay you per completed fitness action — stack that on top of stake refunds.",
    })


def handle_ledger_topup(user_id, token, req):
    """Demo top-up (no real payment rail yet). Caps abuse."""
    if not session_ok(user_id, token):
        return (json.dumps({"error": "Unauthorized"}), 401)
    user = get_user_data(user_id)
    if not user:
        return (json.dumps({"error": "User not found"}), 404)
    try:
        amount = float(req.get('amount') or 50)
    except (TypeError, ValueError):
        amount = 50.0
    amount = max(5.0, min(amount, 100.0))
    # Soft rate limit: at most +$200 total demo topups
    topped = float(user.get('demo_topups') or 0)
    if topped + amount > 200:
        return (json.dumps({"error": "Demo top-up limit reached ($200). Real payouts come via demand partners."}), 400)
    user['demo_topups'] = topped + amount
    user['ledger_balance'] = _ensure_ledger(user) + amount
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500)
    return json.dumps({
        "ok": True,
        "ledger_balance": user['ledger_balance'],
        "added": amount,
        "note": "Demo credit only — not a real card charge.",
    })
