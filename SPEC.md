# GreenDial Health Assistant - Technical Specification

A HIPAA-waived personal health assistant with AI chat interface, user profile management, conversation history, and third-party API integration.

---

## 1. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Chat   │ │  Profile │ │  History │ │ Settings │           │
│  │  Widget  │ │  Widget  │ │  Widget  │ │  Widget  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                           │
                    ┌──────▼──────┐
                    │  API Server │  (Flask)
                    │ api_server.py│
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌──────▼─────┐   ┌─────▼─────┐
    │ handlers  │   │   utils    │   │ s3_storage│
    │   .py     │   │   .py      │   │    .py    │
    └───────────┘   └─────┬──────┘   └─────┬─────┘
                          │                │
                    ┌─────▼─────┐    ┌─────▼─────┐
                    │ LLM API   │    │    S3     │
                    │ (config)  │    │  Storage  │
                    │ + Ollama  │    │           │
                    └───────────┘    └───────────┘
```

---

## 2. CORE FEATURES

### 2.1 Authentication (Username + Passphrase)

**MVP:**
- Simple username/passphrase login via conversation with Doc
- Passphrase stored as-is in user record (HIPAA waiver accepted)
- Session management via session_id token

**Final Form:**
- Passphrase hashing (bcrypt)
- Rate limiting on auth attempts
- Optional 2FA via email/SMS

### 2.2 Chat Interface with Doc

**MVP:**
- Single chat widget for conversations
- Doc responds via configurable /completion endpoint
- Basic profile extraction from conversation (name, age, location)
- Conversation stored in user transcript

**Final Form:**
- Multiple conversation threads
- Voice input/output
- Rich media responses (charts, images)
- Contextual suggestions mid-conversation

### 2.3 JSON User Profile

**MVP:**
```json
{
  "user_id": "user_johndoe",
  "username": "johndoe",
  "passphrase": "secret123",
  "created": "2024-01-15T10:30:00Z",
  "hipaa_waiver_accepted": true,
  "profile": {
    "age": 35,
    "location": "Austin, TX",
    "weight": "180 lbs",
    "health_conditions": ["diabetes"],
    "goals": ["lose weight", "better sleep"]
  },
  "transcript": "User: Hi...\nDoc: Hello...",
  "settings": {
    "doc_style": "default",
    "theme": "green"
  }
}
```

**Final Form:**
- Structured health records (weight history, sleep logs, etc.)
- Medication tracking
- Appointment reminders
- Integration with wearables data

### 2.4 Conversation Storage & Review

**MVP:**
- Single rolling transcript per user (last 200 exchanges)
- Resume conversation with context

**Final Form:**
- Separate conversation sessions
- Search through past conversations
- Export conversation history
- Summarization of past sessions

### 2.5 Personalized Suggestions

**MVP:**
- Doc generates suggestions based on profile during chat
- Basic goal tracking

**Final Form:**
- Proactive daily/weekly check-ins (cron jobs)
- ML-based health insights
- Integration with external services (meal delivery, fitness)

### 2.6 Third-Party API for Profile Updates

**MVP:**
```
POST /api/v1/profile
Authorization: Basic base64(username:passphrase)

{
  "profile": {
    "weight": "175 lbs",
    "blood_pressure": "120/80",
    "last_checkup": "2024-01-10"
  }
}
```

**Final Form:**
- API key authentication (separate from user passphrase)
- Webhook notifications on profile changes
- FHIR-compatible data format
- Audit logging for all API access

---

## 3. COMPONENT SPECIFICATIONS

### 3.1 config.py

**MVP:**
```python
import os

# Flask
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
FLASK_HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.environ.get('FLASK_PORT', 8012))
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

# AWS S3
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET = os.environ.get('S3_BUCKET', 'mithrilmedia')
S3_PREFIX = os.environ.get('S3_PREFIX', 'greendial/')

# LLM Configuration (Configurable endpoint)
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'meta-llama/llama-3.2-3b-instruct:free')
LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '800'))

# Ollama Fallback
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/chat')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2')
OLLAMA_ENABLED = os.environ.get('OLLAMA_ENABLED', 'true').lower() == 'true'
```

**Final Form:**
- Vault/secrets manager integration
- Config validation on startup
- Hot-reload for non-sensitive settings

### 3.2 utils.py - Completion Module

**MVP:**
```python
def completion(prompt, model=None, temperature=None, max_tokens=None):
    """
    Call configurable LLM API with Ollama fallback.
    1. Try configured LLM_API_URL
    2. On error/429, fallback to Ollama if enabled
    3. Return error message if both fail
    """
```

**Final Form:**
- Retry logic with exponential backoff
- Response caching for repeated queries
- Token usage tracking
- Multiple model support per request

### 3.3 s3_storage.py

**MVP:**
```python
# User operations
get_user(user_id) -> dict
save_user(user_id, data) -> None
list_users() -> list

# Conversation operations
get_conversation(user_id, conv_id) -> dict
save_conversation(user_id, conv_id, data) -> None
list_conversations(user_id) -> list
```

**Final Form:**
- Encryption at rest
- Versioning for user data
- Batch operations
- Query indexes for health records

### 3.4 handlers.py

**MVP Endpoints:**
```python
# Authentication
handle_auth(request) -> JSON
  - Login: {"username", "password"}
  - Signup: {"username", "password", "create_new": true, "hipaa_waiver_accepted": true}

# Chat
handle_chat(request) -> JSON
  - {"text", "user_id", "session_id"}
  - Returns: {"response", "session_id", "user_id", "auth"?}

# User Profile
handle_get_user(user_id) -> JSON
handle_update_user(user_id, data) -> JSON

# Third-Party API
handle_api_profile_update(request) -> JSON
  - Basic auth with username:passphrase
  - Updates user profile fields
```

**Final Form:**
- Request validation middleware
- Rate limiting
- Audit logging
- Batch profile updates

### 3.5 api_server.py

**MVP Routes:**
```
GET  /                    - Serve index.html
GET  /ping                - Health check

POST /auth                - Login/Signup
POST /chat                - Chat with Doc

GET  /user/<user_id>      - Get user profile (internal)
PUT  /user/<user_id>      - Update user (internal)

POST /api/v1/profile      - Third-party profile update (Basic Auth)
GET  /api/v1/profile      - Third-party profile read (Basic Auth)

GET  /conversations       - List conversation history
GET  /conversations/<id>  - Get specific conversation
```

**Final Form:**
- OpenAPI/Swagger documentation
- API versioning
- WebSocket for real-time chat
- GraphQL endpoint option

### 3.6 prompts/doc.py

**MVP:**
```python
DOC_SYSTEM = """You are Doc, a friendly health assistant for GreenDial.

## Core Functions
1. Health conversations - discuss diet, exercise, sleep, wellness
2. Profile building - extract and store user health information
3. Authentication - handle login/signup via conversation
4. Suggestions - provide personalized health recommendations

## Authentication Markers
- **ATTEMPT_LOGIN: username | passphrase**
- **REQUIRE_HIPAA: username | passphrase | age | location**
- **ATTEMPT_LOGOUT**

## Profile Update Marker
When user shares health info, emit:
**PROFILE_UPDATE**
{"field": "value"}

## Context
Username: {username}
Logged in: {is_logged_in}
Profile: {user_profile}
Recent conversation: {transcript}

User: {user_input}
Doc:"""
```

**Final Form:**
- Multiple Doc personalities
- Structured output mode (JSON responses)
- Multi-turn reasoning
- Tool use (function calling)

### 3.7 index.html (Frontend)

**MVP:**
- Clean single-page app
- Chat widget (primary)
- Profile display widget
- Conversation history widget
- Login/logout via chat or button
- Responsive design

**Final Form:**
- PWA with offline support
- Dark/light theme toggle
- Accessibility compliance (WCAG 2.1)
- Native mobile apps

---

## 4. DATA STORAGE STRUCTURE (S3)

```
s3://mithrilmedia/greendial/
├── users/
│   ├── user_johndoe.json
│   ├── user_janedoe.json
│   └── ...
├── conversations/
│   ├── user_johndoe/
│   │   ├── conv_abc123.json
│   │   └── conv_def456.json
│   └── ...
└── health/
    ├── user_johndoe/
    │   ├── weight/
    │   │   └── 2024-01-15T10:00:00.json
    │   └── sleep/
    │       └── 2024-01-15T06:00:00.json
    └── ...
```

---

## 5. API AUTHENTICATION

### Internal (Frontend to Backend)
- Session-based: `session_id` in request body
- User context: `user_id` in request body after login

### Third-Party API
```http
POST /api/v1/profile
Authorization: Basic base64(username:passphrase)
Content-Type: application/json

{
  "profile": {
    "weight": "175 lbs",
    "custom_field": "value"
  }
}
```

Response:
```json
{
  "success": true,
  "user_id": "user_johndoe",
  "updated_fields": ["weight", "custom_field"]
}
```

---

## 6. IMPLEMENTATION PHASES

### Phase 1: MVP Core (Current Sprint)
1. [ ] Update config.py - environment variables
2. [ ] Simplify handlers.py - core auth, chat, profile
3. [ ] Add third-party API endpoint
4. [ ] Simplify index.html - chat + profile widgets only
5. [ ] Update utils.py - configurable endpoint + ollama fallback
6. [ ] Test full flow

### Phase 2: Enhanced Features
1. [ ] Conversation sessions (not just transcript)
2. [ ] Health record storage (structured)
3. [ ] Goal tracking
4. [ ] Settings persistence

### Phase 3: Production Ready
1. [ ] Passphrase hashing
2. [ ] Rate limiting
3. [ ] Error handling improvements
4. [ ] Logging and monitoring
5. [ ] API documentation

---

## 7. ENVIRONMENT VARIABLES

Required for deployment:
```bash
# AWS
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1
S3_BUCKET=mithrilmedia
S3_PREFIX=greendial/

# LLM
LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
LLM_API_KEY=sk-or-xxx
LLM_MODEL=meta-llama/llama-3.2-3b-instruct:free

# Ollama (fallback)
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=llama3.2
OLLAMA_ENABLED=true

# Flask
SECRET_KEY=your-secret-key
FLASK_PORT=8012
DEBUG=false
```

---

## 8. SECURITY CONSIDERATIONS

### MVP (HIPAA Waived)
- Users accept waiver that data is not HIPAA protected
- Passphrase stored in plaintext (user acknowledged)
- HTTPS required for production
- No PII logging

### Future Enhancements
- Passphrase hashing (bcrypt)
- API key rotation
- Audit trails
- Data encryption at rest
- Session expiration

---

## 9. FILES TO MODIFY

| File | Action | Description |
|------|--------|-------------|
| config.py | UPDATE | Environment variables, remove hardcoded credentials |
| utils.py | UPDATE | Configurable LLM endpoint, improved fallback |
| handlers.py | SIMPLIFY | Core handlers only, add API endpoint |
| api_server.py | SIMPLIFY | Core routes only, add /api/v1/profile |
| s3_storage.py | KEEP | Minor cleanup |
| prompts/doc.py | UPDATE | Streamline prompt |
| index.html | SIMPLIFY | Chat + Profile focus |
| README.md | UPDATE | New setup instructions |

---

## 10. TESTING CHECKLIST

### Authentication
- [ ] New user signup via chat
- [ ] Existing user login via chat
- [ ] HIPAA waiver enforcement
- [ ] Logout functionality
- [ ] Invalid credentials handling

### Chat
- [ ] Basic conversation
- [ ] Profile extraction from chat
- [ ] Context preservation (transcript)
- [ ] LLM API failure -> Ollama fallback
- [ ] Rate limiting graceful handling

### Third-Party API
- [ ] Basic auth validation
- [ ] Profile update success
- [ ] Profile read success
- [ ] Invalid credentials rejection
- [ ] Missing fields handling

### Storage
- [ ] User create/read/update
- [ ] Conversation persistence
- [ ] S3 error handling

---

Ready to implement? Start with Phase 1 tasks.
