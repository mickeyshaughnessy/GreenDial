"""
Handlers Module - Worker Droid Implementation
Request routing and processing with S3 storage integration
"""
import json
import uuid
import re
from datetime import datetime

import config
import utils
import s3_storage
from prompts import doc

# In-memory cache
_cache = {}
# Anonymous session store
_anonymous_sessions = {}

def _cache_get(key, field):
    return _cache.get(f"{key}:{field}")

def _cache_set(key, field, value):
    _cache[f"{key}:{field}"] = value

# ============ AUTH ============

def handle_auth(request):
    """Handle authentication requests"""
    username = request.get('username', '').strip()
    passphrase = request.get('password', '')
    
    if not username:
        return json.dumps({"error": "Username required"}), 400
    
    user_id = f"user_{username.lower().replace(' ', '_').replace('@', '_')}"
    
    try:
        user = s3_storage.get_user(user_id)
    except Exception as e:
        user = None
    
    if user:
        if user.get('passphrase') == passphrase:
            return json.dumps({
                "user_id": user_id, 
                "username": user.get('username', username),
                "settings": user.get('settings', {})
            })
        return json.dumps({"error": "Invalid passphrase"}), 401
    
    # New user - create account
    new_user = {
        "user_id": user_id,
        "username": username,
        "passphrase": passphrase,
        "created": datetime.utcnow().isoformat(),
        "hipaa_waiver_accepted": True,
        "transcript": "",
        "settings": {
            "doc_style": "default",
            "theme": "green",
            "notifications": True
        },
        "profile": {}
    }
    
    try:
        s3_storage.save_user(user_id, new_user)
    except Exception as e:
        print(f"S3 save error (continuing): {e}")
    
    _cache_set("users", user_id, json.dumps(new_user))
    
    return json.dumps({
        "user_id": user_id, 
        "username": username, 
        "new_user": True,
        "settings": new_user["settings"]
    })

# ============ USER ============

def get_user_data(user_id):
    """Get user data from cache or S3"""
    if not user_id:
        return {}
    
    cached = _cache_get("users", user_id)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass
    
    try:
        user = s3_storage.get_user(user_id)
        if user:
            _cache_set("users", user_id, json.dumps(user))
            return user
    except:
        pass
    
    return {}

def handle_get_user(user_id):
    """Get user profile"""
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
            if key == 'settings' and isinstance(data[key], dict):
                user.setdefault('settings', {}).update(data[key])
            elif key == 'profile' and isinstance(data[key], dict):
                user.setdefault('profile', {}).update(data[key])
            else:
                user[key] = data[key]
    
    user['last_updated'] = datetime.utcnow().isoformat()
    
    try:
        s3_storage.save_user(user_id, user)
    except:
        pass
    _cache_set("users", user_id, json.dumps(user))
    
    return json.dumps({"success": True, "user": {k: v for k, v in user.items() if k != 'passphrase'}})

# ============ SESSIONS ============

def get_or_create_session(session_id):
    """Get or create an anonymous session"""
    if session_id and session_id in _anonymous_sessions:
        return _anonymous_sessions[session_id]
    
    new_session_id = session_id or str(uuid.uuid4())
    session = {
        "session_id": new_session_id,
        "created": datetime.utcnow().isoformat(),
        "transcript": "",
        "user_id": None,
        "username": "Guest"
    }
    _anonymous_sessions[new_session_id] = session
    return session

def handle_new_session(request):
    """Create a new consultation session"""
    user_id = request.get('user_id')
    
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "user_id": user_id,
        "created": datetime.utcnow().isoformat(),
        "messages": [],
        "type": "private" if user_id else "public"
    }
    
    if user_id:
        try:
            s3_storage.save_conversation(user_id, session_id, session)
        except:
            pass
    
    _anonymous_sessions[session_id] = session
    
    return json.dumps({
        "session_id": session_id,
        "type": session["type"]
    })

def handle_list_sessions(user_id):
    """List user's consultation sessions"""
    try:
        sessions = s3_storage.list_conversations(user_id)
        return json.dumps({"sessions": sessions})
    except:
        return json.dumps({"sessions": []})

# ============ CHAT ============

def detect_auth_intent(text, response):
    """Detect login/signup intent from Doc's response"""
    # Check for login detection
    login_match = re.search(r'\*\*LOGIN_DETECTED\*\*\s*username:\s*(\S+)\s*passphrase:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
    if login_match:
        return {
            "type": "login",
            "username": login_match.group(1).strip(),
            "passphrase": login_match.group(2).strip()
        }
    
    # Check for signup detection
    signup_match = re.search(r'\*\*SIGNUP_DETECTED\*\*\s*username:\s*(\S+)\s*passphrase:\s*(.+?)(?:\n|$)', response, re.IGNORECASE | re.DOTALL)
    if signup_match:
        return {
            "type": "signup",
            "username": signup_match.group(1).strip(),
            "passphrase": signup_match.group(2).strip()
        }
    
    return None

def clean_response(response):
    """Remove auth markers from response"""
    response = re.sub(r'\*\*(LOGIN|SIGNUP)_DETECTED\*\*.*?(?=\n\n|\Z)', '', response, flags=re.DOTALL)
    return response.strip()

def update_history(user_id, in_text, out_text, session_id=None):
    """Update conversation history"""
    if user_id:
        user_data = get_user_data(user_id)
        transcript = user_data.get('transcript', '')
        transcript += f"\nUser: {in_text}\nDoc: {out_text}"
        
        lines = transcript.split('\n')
        if len(lines) > 200:
            transcript = '\n'.join(lines[-200:])
        
        user_data['transcript'] = transcript
        user_data['last_updated'] = datetime.utcnow().isoformat()
        
        _cache_set("users", user_id, json.dumps(user_data))
        
        try:
            s3_storage.save_user(user_id, user_data)
        except:
            pass
    
    # Also update session
    if session_id and session_id in _anonymous_sessions:
        session = _anonymous_sessions[session_id]
        session['transcript'] = session.get('transcript', '') + f"\nUser: {in_text}\nDoc: {out_text}"

def make_prompt(user_id=None, session_id=None, _input=""):
    """Build Doc's prompt"""
    user_data = get_user_data(user_id) if user_id else {}
    session = _anonymous_sessions.get(session_id, {})
    
    transcript = user_data.get('transcript', '') or session.get('transcript', '')
    transcript = transcript[-3000:]
    
    username = user_data.get('username', 'Guest')
    is_logged_in = bool(user_id and user_data.get('username'))
    
    settings = user_data.get('settings', {})
    style_key = settings.get('doc_style', 'default')
    style_prompt = doc.DOC_STYLES.get(style_key, doc.DOC_STYLE_DEFAULT)
    
    profile = user_data.get('profile', {})
    profile_str = json.dumps(profile, indent=2) if profile else "No profile data yet."
    
    session_type = "private" if is_logged_in else "public (anonymous)"
    
    prompt = doc.DOC_SYSTEM.format(
        style_prompt=style_prompt,
        username=username,
        is_logged_in=str(is_logged_in),
        session_type=session_type,
        user_profile=profile_str,
        transcript=transcript,
        user_input=_input
    )
    
    return prompt

def handle_chat(request):
    """Handle chat requests with Doc"""
    user_id = request.get('user_id')
    session_id = request.get('session_id') or str(uuid.uuid4())
    in_text = request.get("text", "").strip()
    
    # Ensure session exists
    if session_id not in _anonymous_sessions:
        _anonymous_sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "created": datetime.utcnow().isoformat(),
            "transcript": ""
        }
    
    if not in_text:
        return json.dumps({
            "response": "I didn't catch that. What would you like to talk about?",
            "session_id": session_id,
            "user_id": user_id
        })

    prompt = make_prompt(user_id, session_id, in_text)
    
    try:
        out_text = utils.completion(prompt, temperature=0.9, max_tokens=400)
    except Exception as e:
        print(f"Completion error: {e}")
        out_text = "I apologize, I'm having trouble responding right now. Please try again."

    # Check for auth intent in response
    auth_result = detect_auth_intent(in_text, out_text)
    
    response_data = {
        "session_id": session_id,
        "user_id": user_id
    }
    
    if auth_result:
        # Process authentication
        auth_request = {
            "username": auth_result["username"],
            "password": auth_result["passphrase"]
        }
        auth_response = handle_auth(auth_request)
        
        if isinstance(auth_response, tuple):
            # Auth failed
            clean_text = clean_response(out_text)
            response_data["response"] = clean_text or "I couldn't verify those credentials. Please try again."
        else:
            auth_data = json.loads(auth_response)
            response_data["auth"] = auth_data
            response_data["user_id"] = auth_data.get("user_id")
            
            # Update session with user
            _anonymous_sessions[session_id]["user_id"] = auth_data.get("user_id")
            _anonymous_sessions[session_id]["username"] = auth_data.get("username")
            
            if auth_result["type"] == "signup":
                response_data["response"] = f"Welcome to GreenDial, {auth_data.get('username')}! I've created your account. Your health journey starts now. How are you feeling today?"
            else:
                response_data["response"] = f"Welcome back, {auth_data.get('username')}! Great to see you again. What would you like to focus on today?"
    else:
        response_data["response"] = out_text
    
    update_history(response_data.get("user_id"), in_text, response_data["response"], session_id)
    
    return json.dumps(response_data)

# ============ USER MESSAGING ============

def handle_send_message(request):
    """Send a message to another user"""
    from_user_id = request.get('from_user_id')
    to_user_id = request.get('to_user_id')
    message_text = request.get('message', '').strip()
    
    if not all([from_user_id, to_user_id, message_text]):
        return json.dumps({"error": "Missing required fields"}), 400
    
    message = {
        "id": str(uuid.uuid4()),
        "from": from_user_id,
        "to": to_user_id,
        "message": message_text,
        "timestamp": datetime.utcnow().isoformat(),
        "read": False
    }
    
    # Store message for both users
    try:
        # Get existing messages for recipient
        messages_key = f"messages/{to_user_id}.json"
        try:
            existing = s3_storage.s3_client.get_object(
                Bucket=config.S3_BUCKET,
                Key=f"{config.S3_PREFIX}{messages_key}"
            )
            messages = json.loads(existing['Body'].read().decode('utf-8'))
        except:
            messages = {"inbox": []}
        
        messages["inbox"].append(message)
        
        s3_storage.s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=f"{config.S3_PREFIX}{messages_key}",
            Body=json.dumps(messages),
            ContentType='application/json'
        )
        
        return json.dumps({"success": True, "message_id": message["id"]})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

def handle_get_messages(user_id):
    """Get user's messages"""
    try:
        messages_key = f"messages/{user_id}.json"
        existing = s3_storage.s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=f"{config.S3_PREFIX}{messages_key}"
        )
        messages = json.loads(existing['Body'].read().decode('utf-8'))
        return json.dumps(messages)
    except:
        return json.dumps({"inbox": []})

# ============ DOC'S AD-HOC MESSAGES ============

def handle_doc_message(request):
    """Send an ad-hoc message from Doc to a user"""
    user_id = request.get('user_id')
    message_type = request.get('type', 'custom')
    custom_message = request.get('message')
    
    if not user_id:
        return json.dumps({"error": "user_id required"}), 400
    
    # Get message template or use custom
    if custom_message:
        message_text = custom_message
    else:
        message_text = doc.RCL_TEMPLATES.get(message_type, doc.RCL_MORNING)
    
    # Store as a Doc message
    doc_message = {
        "id": str(uuid.uuid4()),
        "type": "doc_message",
        "message": message_text,
        "timestamp": datetime.utcnow().isoformat(),
        "read": False
    }
    
    try:
        messages_key = f"doc_messages/{user_id}.json"
        try:
            existing = s3_storage.s3_client.get_object(
                Bucket=config.S3_BUCKET,
                Key=f"{config.S3_PREFIX}{messages_key}"
            )
            messages = json.loads(existing['Body'].read().decode('utf-8'))
        except:
            messages = {"messages": []}
        
        messages["messages"].append(doc_message)
        
        s3_storage.s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=f"{config.S3_PREFIX}{messages_key}",
            Body=json.dumps(messages),
            ContentType='application/json'
        )
        
        return json.dumps({"success": True, "message": doc_message})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

def handle_get_doc_messages(user_id):
    """Get Doc's messages for a user"""
    try:
        messages_key = f"doc_messages/{user_id}.json"
        existing = s3_storage.s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=f"{config.S3_PREFIX}{messages_key}"
        )
        messages = json.loads(existing['Body'].read().decode('utf-8'))
        return json.dumps(messages)
    except:
        return json.dumps({"messages": []})

# ============ SETTINGS ============

def handle_get_settings(user_id):
    try:
        user = get_user_data(user_id)
        return json.dumps(user.get('settings', {
            "doc_style": "default",
            "theme": "green",
            "notifications": True
        }))
    except:
        return json.dumps({})

def handle_save_settings(user_id, data):
    try:
        user = get_user_data(user_id)
        if not user:
            return json.dumps({"error": "User not found"}), 404
        
        user.setdefault('settings', {}).update(data)
        user['last_updated'] = datetime.utcnow().isoformat()
        
        s3_storage.save_user(user_id, user)
        _cache_set("users", user_id, json.dumps(user))
        
        return json.dumps({"success": True, "settings": user['settings']})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ============ GOALS ============

def handle_get_goals(user_id):
    try:
        goals = s3_storage.get_goals(user_id)
        return json.dumps(goals)
    except:
        return json.dumps({"goals": []})

def handle_save_goals(user_id, data):
    try:
        s3_storage.save_goals(user_id, data)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ============ CONVERSATIONS ============

def handle_conversations(req):
    user_id = req.get('user_id')
    conversation_id = req.get('conversationId')
    
    if conversation_id and user_id:
        try:
            conv = s3_storage.get_conversation(user_id, conversation_id)
            return json.dumps({"conversation": conv.get("messages", []) if conv else []})
        except:
            return json.dumps({"conversation": []})
    
    if user_id:
        try:
            conversations = s3_storage.list_conversations(user_id)
            return json.dumps({"conversations": conversations})
        except:
            pass
    
    return json.dumps({"conversations": []})

# ============ HEALTH RECORDS ============

def handle_get_health_records(user_id, record_type=None):
    try:
        records = s3_storage.query_health_records(user_id, record_type)
        return json.dumps({"records": records})
    except:
        return json.dumps({"records": []})

def handle_save_health_record(user_id, data):
    record_type = data.get('type', 'general')
    timestamp = data.get('timestamp', datetime.utcnow().isoformat())
    record_data = data.get('data', {})
    
    try:
        s3_storage.save_health_record(user_id, record_type, timestamp, record_data)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ============ DROID ============

def handle_droid(request):
    droidname = request.get('droidname', 'worker droid')
    droidprompt = request.get('droidprompt', '')
    user_id = request.get('user_id')
    model = request.get('model', config.DEFAULT_MODEL)
    
    if not droidprompt:
        return json.dumps({"error": "droidprompt required"}), 400
    
    prompt = f"""You are a {droidname} for the GreenDial health application.

Your task: {droidprompt}

User context: {user_id or 'anonymous'}

Respond concisely and helpfully."""

    try:
        response = utils.completion(prompt, model=model, temperature=0.7)
        return json.dumps({"response": response, "droid": droidname})
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ============ STATS ============

def handle_get_stats(user_id):
    stats = {
        "conversations": 0,
        "records": 0,
        "goals": 0,
        "days_active": 1
    }
    
    try:
        convos = s3_storage.list_conversations(user_id)
        stats["conversations"] = len(convos)
    except:
        pass
    
    try:
        records = s3_storage.query_health_records(user_id)
        stats["records"] = len(records)
    except:
        pass
    
    try:
        goals_data = s3_storage.get_goals(user_id)
        stats["goals"] = len(goals_data.get("goals", []))
    except:
        pass
    
    try:
        user = get_user_data(user_id)
        if user.get('created'):
            created = datetime.fromisoformat(user['created'].replace('Z', '+00:00'))
            days = (datetime.utcnow() - created.replace(tzinfo=None)).days + 1
            stats["days_active"] = max(1, days)
    except:
        pass
    
    return json.dumps(stats)
