# GreenDial Architecture

## System Overview

GreenDial is a personal health data assistant built on:
- **Frontend**: Static HTML/JS served via Flask or nginx
- **Backend**: Flask API server (api_server.py)
- **LLM**: OpenRouter /completion API
- **Storage**: Amazon S3 + Redis cache
- **External Services**: The Services Exchange API (RSE)

## Component Details

### Web Frontend (index.html)

Single-page application with:
- Login form (username + passphrase)
- HIPAA waiver acknowledgment (implicit on signup)
- Chat interface
- Conversation history browser
- Dashboard (planned)

### API Server (api_server.py)

Flask application exposing:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ping` | GET | Health check |
| `/chat` | POST | Main chat interface |
| `/conversations` | POST/GET | Conversation management |
| `/auth` | POST | User authentication (planned) |

### Handlers (handlers.py)

Request processing pipeline:
1. Extract user_id and input text
2. Build prompt from templates
3. Call OpenRouter completion API
4. Parse response for symbols (**AUTH**, **SELECT**, **INSERT**)
5. Update conversation history
6. Return response

### Agents (agents.py)

Droid definitions - specialized AI agents for:
- Data storage
- Authentication
- Data retrieval

### Prompts (prompts/)

LLM prompt templates organized by function:
- `auth.py` - Authentication flow
- `chat.py` - Main chat system prompt
- `memory.py` - SELECT/INSERT data operations
- `settings.py` - User preferences
- `external.py` - External service calls
- `coach.py` - Health coaching
- `reviewer.py` - Review/analysis

## Data Flow

```
┌──────────┐    POST /chat     ┌──────────────┐
│  Client  │ ─────────────────▶│  Flask API   │
└──────────┘                   └──────┬───────┘
                                      │
                               ┌──────▼───────┐
                               │  handlers.py │
                               └──────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
             ┌────────────┐   ┌────────────┐   ┌────────────┐
             │ Redis Cache│   │ OpenRouter │   │ S3 Storage │
             └────────────┘   └────────────┘   └────────────┘
```

## Symbol Processing

The chat system uses symbols to route to specialized services:

### **AUTH** Symbol
```
User: mickey secret phrase
Bot: Welcome back! **AUTH**
     ↓
Auth service validates credentials
     ↓
Returns: SUCCESS/FAIL + user_id
```

### **SELECT** Symbol
```
User: How much did I weigh last month?
Bot: You weighed **SELECT** pounds.
     ↓
Data retrieval service queries S3
     ↓
Replaces symbol with: 185
```

### **INSERT** Symbol
```
User: I ate two apples
Bot: Recorded **INSERT**. What else did you eat?
     ↓
Data storage service writes to S3
     ↓
Confirms storage
```

## Storage Architecture

### Redis (Cache Layer)
- User session data
- Recent conversation history
- Fast lookups

Hash structure:
```
REDHASH_USER_DATA:
  user_id → {
    "transcript": "...",
    "username": "...",
    "plugins": "..."
  }
```

### S3 (Persistent Storage)
- Long-term conversation history
- Health data records
- User preferences
- Goals and reminders

## External Integrations

### OpenRouter API
```python
POST https://openrouter.ai/api/v1/completions
Headers:
  Authorization: Bearer {API_KEY}
  Content-Type: application/json

Body:
{
  "model": "text-davinci-003",  # or other models
  "prompt": "<assembled prompt>",
  "temperature": 1.1,
  "max_tokens": 200
}
```

### The Services Exchange (RSE) API
- Base URL: `https://rse-api.com:5003/`
- Documentation: `https://theservicesexchange.com/api_docs.html`
- Services: Diet, exercise, sleep, entertainment bids

## Crontab / RCL System

Unprompted health conversations via scheduled scripts:

```cron
# Health check-in
0 9 * * * /path/to/scripts/rcl_morning.py

# Evening reflection
0 21 * * * /path/to/scripts/rcl_evening.py

# Weekly summary
0 10 * * 0 /path/to/scripts/rcl_weekly.py
```

## Security Model

### HIPAA Waiver
- Users explicitly waive HIPAA protections during signup
- Enables open data sharing for health optimization
- Waiver text displayed and acknowledged before account creation

### Authentication
- Username + passphrase (not password)
- Passphrase is memorable phrase, not complex string
- Future: OAuth integration planned

### Data Protection
- All S3 data encrypted at rest
- HTTPS for all API communications
- No PHI exposure in logs (future enhancement)

## Deployment

### Local Development
```bash
python api_server.py  # Runs on localhost:8012
```

### Production
- nginx reverse proxy (nginx.conf)
- systemd service for Flask app
- Git-based deployment workflow
