"""
Handlers Module - Core request processing
"""
import json
import uuid
import re
import base64
import random
from datetime import datetime

import config
import utils
import s3_storage
from prompts import doc

# In-memory session cache
_sessions = {}
_user_cache = {}


def _cache_user(user_id, data):
    _user_cache[user_id] = data


def _get_cached_user(user_id):
    return _user_cache.get(user_id)


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
                return json.dumps({
                    "user_id": user_id,
                    "username": user.get('username', username),
                    "settings": user.get('settings', {}),
                    "profile": user.get('profile', {})
                })
            return json.dumps({"error": "Invalid passphrase"}), 401
        return json.dumps({"error": "User not found"}), 404
    
    # SIGNUP mode
    if user:
        return json.dumps({"error": "User already exists"}), 409
    
    if not request.get('hipaa_waiver_accepted'):
        return json.dumps({"error": "HIPAA waiver must be accepted"}), 400
    
    profile = request.get('profile', {})
    new_user = {
        "user_id": user_id,
        "username": username,
        "passphrase": passphrase,
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
    except Exception as e:
        print(f"[Auth] Failed to save user: {e}")
        return json.dumps({"error": "Failed to create account"}), 500
    
    return json.dumps({
        "user_id": user_id,
        "username": username,
        "new_user": True,
        "settings": new_user["settings"],
        "profile": new_user["profile"]
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


def handle_get_user(user_id):
    """Get user profile (excludes passphrase)"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    safe_user = {k: v for k, v in user.items() if k != 'passphrase'}
    return json.dumps(safe_user)


def handle_update_user(user_id, data):
    """Update user profile"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    allowed = ['username', 'settings', 'profile']
    for key in allowed:
        if key in data:
            if key in ('settings', 'profile') and isinstance(data[key], dict):
                user.setdefault(key, {}).update(data[key])
            else:
                user[key] = data[key]
    
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[User] Failed to update: {e}")
    
    safe_user = {k: v for k, v in user.items() if k != 'passphrase'}
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
        "notifications_enabled": True
    }
    
    settings = {**default_settings, **user.get('settings', {})}
    return json.dumps({"settings": settings})


def handle_update_settings(user_id, data):
    """Update user settings"""
    user = get_user_data(user_id)
    if not user:
        return json.dumps({"error": "User not found"}), 404
    
    user.setdefault('settings', {}).update(data)
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
        _cache_user(user_id, user)
    except Exception as e:
        print(f"[Settings] Failed to update: {e}")
        return json.dumps({"error": "Failed to save settings"}), 500
    
    return json.dumps({"success": True, "settings": user['settings']})


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
        tip = random.choice(doc.HEALTH_TIPS)
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


def _build_prompt(user_id=None, session_id=None, user_input=""):
    """Build Doc's prompt dynamically using modular components"""
    user = get_user_data(user_id) if user_id else {}
    session = _sessions.get(session_id, {})
    
    # Get transcript
    transcript = user.get('transcript', '') or session.get('transcript', '')
    
    # Split into recent and summary
    recent_transcript = _get_recent_transcript(transcript, max_lines=8)
    summary = _get_summary(transcript)
    
    # Get user info
    username = user.get('username', 'Guest')
    profile = user.get('profile', {})
    settings = user.get('settings', {})
    
    # Use the new modular prompt builder
    return doc.build_prompt(
        user_input=user_input,
        username=username,
        profile=profile,
        recent_transcript=recent_transcript,
        summary=summary,
        settings=settings
    )


def handle_chat(request):
    """Handle chat with Doc"""
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
    
    prompt = _build_prompt(user_id, session_id, user_input)
    
    try:
        doc_response = utils.completion(prompt, temperature=0.8, max_tokens=300)
    except Exception as e:
        print(f"[Chat] Completion error: {e}")
        doc_response = "I'm having trouble responding right now. Please try again."
    
    # Extract and apply profile updates
    profile_updates = _parse_profile_updates(doc_response)
    updated_profile = None
    
    if profile_updates and user_id:
        user = get_user_data(user_id)
        if user:
            user.setdefault('profile', {})
            _apply_profile_updates(user['profile'], profile_updates)
            user['last_updated'] = datetime.utcnow().isoformat()
            _cache_user(user_id, user)
            try:
                s3_storage.save_user(user_id, user)
                updated_profile = user['profile']
            except Exception as e:
                print(f"[Chat] Failed to save profile update: {e}")
    
    clean_response = _clean_profile_markers(doc_response)
    _update_transcript(user_id, user_input, clean_response, session_id)
    
    response_data = {
        "response": clean_response,
        "session_id": session_id,
        "user_id": user_id
    }
    
    if updated_profile:
        response_data["profile_updated"] = True
        response_data["profile"] = updated_profile
    
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
