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

**Current schema:**
```json
{
  "user_id": "user_johndoe",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "passphrase": "secret123",
  "created": "2024-01-15T10:30:00Z",
  "hipaa_waiver_accepted": true,
  "wallets": {
    "eth": "0xABC...",
    "sol": ""
  },
  "profile": {
    "age": 35,
    "location": "Austin, TX",
    "weight": "180 lbs",
    "health_conditions": ["diabetes"],
    "goals": ["lose weight", "better sleep"]
  },
  "suggestions": [
    {
      "id": "sug_abc",
      "type": "exercise",
      "agent_id": "exercise",
      "text": "Take a 20-minute walk after dinner",
      "bounty_id": null,
      "price": null,
      "currency": null,
      "created": "2026-06-11T08:00:00Z",
      "status": "pending"
    }
  ],
  "activities": [
    {
      "id": "act_xyz",
      "suggestion_id": "sug_abc",
      "type": "exercise",
      "agent_id": "exercise",
      "text": "Take a 20-minute walk after dinner",
      "bounty_id": null,
      "price": null,
      "currency": null,
      "accepted_at": "2026-06-11T09:00:00Z",
      "status": "active",
      "completed_at": null,
      "wallet_snapshot": null
    }
  ],
  "transcript": "User: Hi...\nDoc: Hello...",
  "settings": {
    "doc_style": "default",
    "theme": "green"
  }
}
```

**Identity:** `(first_name, last_name, email)` is the canonical human identity for payment matching and demand-side targeting. The internal `user_id` hash remains the S3 key.

**Migration:** existing users gain `first_name`, `last_name`, `email`, `wallets`, `suggestions`, `activities` fields (empty defaults) on first access after the update.

**Future:**
- Structured health records (weight history, sleep logs)
- Medication tracking
- Wearables integration

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

**Current implementation:**
- Three daily suggestions generated per user (exercise, diet, social) — separate from the notification bell
- Agent mapping: exercise → Exercise Coach, diet → Diet Advisor, social → Relationships Advisor
- Generation logic: check active bounties for this user first; fill remaining slots with LLM-personalized suggestions
- Users can Accept (→ promotes to Activity) or Dismiss each suggestion
- Clicking/accepting a suggestion navigates to the relevant agent's chat and pre-populates the message

**Bounty-backed suggestions:**
- Demand-side customers (e.g. health insurers) POST bounties targeting explicit user ID lists
- Bounty suggestions show the activity description and price to the user
- On activity completion, wallet address is snapshot and payment is flagged as pending (honor system, no on-chain escrow)

**Future:**
- ML-based health insights
- Wearables integration
- Webhook notifications to demand-side on completion

### 2.6 Third-Party API for Profile Updates

**Current:**
```
POST /api/v1/profile
Authorization: Basic base64(username:passphrase)
```

**Future:**
- API key authentication
- Webhook notifications on profile changes
- FHIR-compatible data format

---

### 2.7 Bounty & Demand-Side API

Demand-side customers (e.g. health insurers) authenticate with a shared API key
(`X-API-Key` header; key lives in `config.py` as `DEMAND_API_KEY`, never committed).
All bounty endpoints and `/generate` require it and fail closed if unconfigured.

#### POST /bounty — Create a bounty
```json
{
  "activity": "Walk 10,000 steps",
  "health_area": "exercise",
  "price": 5.00,
  "currency": "ETH",
  "user_ids": ["user_abc", "user_def"],
  "expires": "2026-07-01"
}
```
Response: `{ "bounty_id": "bty_123", "status": "active" }`

#### GET /bounty — List active bounties
Response: `{ "bounties": [...] }`

#### POST /generate — Generate a suggestion preview
Used by demand-side to preview what suggestion GreenDial would generate for a user, and receive a ready-to-POST bounty payload.

```json
{
  "user_id": "user_abc",
  "health_area": "diet",
  "price": 10.00
}
```
Response:
```json
{
  "suggestion": {
    "text": "Add one serving of leafy greens to lunch this week",
    "agent_id": "diet",
    "health_area": "diet"
  },
  "bounty_payload": {
    "activity": "Add one serving of leafy greens to lunch this week",
    "health_area": "diet",
    "price": 10.00,
    "currency": "ETH",
    "user_ids": ["user_abc"]
  },
  "bounty_post_url": "/bounty"
}
```

#### Bounty S3 storage
`bounties/bounties.json` — a single JSON list of all bounty objects.

```json
{
  "id": "bty_123",
  "activity": "Walk 10,000 steps",
  "health_area": "exercise",
  "price": 5.00,
  "currency": "ETH",
  "user_ids": ["user_abc"],
  "expires": "2026-07-01",
  "created": "2026-06-11T00:00:00Z",
  "status": "active"
}
```

---

### 2.8 Suggestions & Activities Endpoints

#### GET /suggestions/\<user_id\>
Returns current suggestion batch.

#### POST /suggestions/\<user_id\>/generate
Triggers suggestion generation for a user:
1. Load active bounties; filter to those listing this `user_id`
2. Create suggestions from matching bounties (up to 3)
3. Fill remaining slots: LLM call per health area (exercise, diet, social/relationships)
4. Overwrite `user.suggestions`, clearing previous pending ones

#### POST /suggestions/\<user_id\>/\<suggestion_id\>/accept
Marks suggestion `accepted`, appends to `user.activities` with `status: active`.

#### GET /activities/\<user_id\>
Returns user's activities list.

#### PATCH /activities/\<user_id\>/\<activity_id\>
Body: `{ "status": "completed" }` — sets `completed_at`, snapshots wallet address into `wallet_snapshot`. If activity has a price, flags `payment_pending: true`.

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

**All routes:**
```
GET  /                                         Serve index.html
GET  /ping                                     Health check

POST /auth                                     Login/Signup
POST /chat                                     Chat with Doc
POST /chat/agent/<agent_id>                    Chat with specialist agent

GET  /user/<user_id>                           Get user profile
PUT  /user/<user_id>                           Update user (name, email, wallets, profile)

GET  /settings/<user_id>                       Get user settings
PUT  /settings/<user_id>                       Update user settings

GET  /notifications/<user_id>                  Get notifications
POST /notifications/<user_id>/generate         Generate notifications
DELETE /notifications/<user_id>/<id>           Dismiss notification

GET  /suggestions/<user_id>                    Get current suggestion batch
POST /suggestions/<user_id>/generate           Generate daily suggestions (cron or on-demand)
POST /suggestions/<user_id>/<id>/accept        Accept suggestion → activity

GET  /activities/<user_id>                     Get activities list
PATCH /activities/<user_id>/<id>               Mark activity complete

POST /bounty                                   Create bounty (demand-side)
GET  /bounty                                   List active bounties
GET  /bounty/<id>                              Get single bounty

POST /generate                                 Preview suggestion + bounty payload (demand-side)

GET  /conversations/<user_id>                  List conversations
DELETE /conversations/<user_id>                Clear all conversations
GET  /conversations/<user_id>/<conv_id>        Get conversation
GET  /conversations/<user_id>/agents           List agent transcripts
DELETE /conversations/<user_id>/agent/<id>     Clear agent transcript

GET  /api/v1/profile                           Third-party profile read (Basic Auth)
POST /api/v1/profile                           Third-party profile update (Basic Auth)

GET  /agents/<user_id>                         Get agent preferences
PUT  /agents/<user_id>                         Update agent preferences

GET  /history/<user_id>                        Get profile history

GET  /feedback                                 List feedback posts
POST /feedback                                 Post feedback
DELETE /feedback/<id>                          Delete post (admin)
PATCH /feedback/<id>                           Update post status (admin)

GET  /admin/balances                           BTC/ETH balances (admin)
GET  /admin/stats                              Platform stats (admin)
```

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
│   ├── user_johndoe.json      # includes suggestions[], activities[], wallets{}
│   ├── user_janedoe.json
│   └── ...
├── conversations/
│   ├── user_johndoe/
│   │   ├── conv_abc123.json
│   │   └── conv_def456.json
│   └── ...
├── bounties/
│   └── bounties.json          # single JSON list of all bounty objects
└── health/
    └── user_johndoe/
        ├── weight/
        └── sleep/
```

---

## 5. API AUTHENTICATION

### Internal (Frontend to Backend)
- Session tokens: `/auth` returns a `token` at login/signup, stored in the user
  record. All user-scoped reads and writes require it via the `X-Session-Token`
  header (the SPA attaches it automatically through a fetch interceptor).
- Admin endpoints (`/admin/*`, feedback moderation) require an admin user's
  valid session token — the `user_id` query param alone is not sufficient.
- Chat endpoints enforce the token whenever a `user_id` is supplied;
  anonymous (pre-login) chat still works without one.

### Demand-side
- `X-API-Key: <DEMAND_API_KEY>` on `/bounty` (all methods) and `/generate`.

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

### Phase 1: Core suggestions & activities (next up)
1. [ ] `s3_storage.py` — add `get_bounties()`, `save_bounties()`
2. [ ] `handlers.py` — add bounty CRUD, suggestion generation logic, activity accept/complete
3. [ ] `api_server.py` — wire new routes: `/bounty`, `/generate`, `/suggestions/...`, `/activities/...`
4. [ ] `index.html` — user page: first/last name, email, wallet address fields
5. [ ] `index.html` — Suggestions panel (separate from notification bell), Accept/Dismiss buttons, click-through to agent chat
6. [ ] `index.html` — Activities section on user page with Mark Complete button
7. [ ] `index.html` — Completed activities history section

### Phase 2: Bounty demand-side polish
1. [ ] `/generate` endpoint — LLM-backed suggestion preview for demand-side
2. [ ] Bounty matching in suggestion generation (check user_ids list)
3. [ ] Payment pending flag + wallet snapshot on activity completion

### Phase 3: Identity migration
1. [ ] Add first/last/email capture to signup flow
2. [ ] Profile page fields for existing users to fill in name/email
3. [ ] Lookup by email as secondary key

### Phase 4: Production hardening
1. [ ] API key auth for bounty/generate endpoints
2. [ ] Rate limiting
3. [ ] Webhook to demand-side on activity completion
4. [ ] Passphrase hashing

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
