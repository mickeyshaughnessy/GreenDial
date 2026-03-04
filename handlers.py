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
from prompts import doc, doc_v2, notifications, facilitator
import threading

# In-memory TTL cache
_cache_store = {}
_cache_ts = {}

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
                # Generate notifications in background on login
                threading.Thread(target=generate_login_notifications, args=(user_id,)).start()
                
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
        
        # Generate initial notifications in background
        threading.Thread(target=generate_login_notifications, args=(user_id,)).start()
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
    """Build Doc's prompt using Unprompted-style guided conversation"""
    user = get_user_data(user_id) if user_id else {}
    session = _sessions.get(session_id, {})
    
    # Get transcript
    transcript = user.get('transcript', '') or session.get('transcript', '')
    
    # Split into recent
    recent_transcript = _get_recent_transcript(transcript, max_lines=10)
    
    # Get user info
    username = user.get('username', 'Guest')
    profile = user.get('profile', {})
    
    # Use the new Unprompted-style prompt builder
    return doc_v2.build_doc_prompt(
        user_input=user_input,
        profile=profile,
        recent_transcript=recent_transcript,
        username=username
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
    
    try:
        # Build Unprompted-style guided prompt
        prompt = _build_prompt(
            user_id=user_id,
            session_id=session_id,
            user_input=user_input
        )
        
        # Single-stage completion with enhanced prompt
        doc_response = utils.completion(
            prompt=prompt,
            temperature=0.7,
            max_tokens=config.LLM_MAX_TOKENS
        )
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
