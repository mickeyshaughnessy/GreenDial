# GreenDial Health Assistant

A HIPAA-waived personal health assistant with AI chat interface, user profile management, and third-party API integration.

**Reference deployment for [ListeningAI](../ListeningAI)** — the portable conversational controller package. GreenDial mounts ListeningAI at `/listening`, routes all OpenRouter completions through `listening_ai.llm`, and runs its agentic health-tool loop through `listening_ai.ChatController` (see `listening_bridge.py` + `utils.py`).

## Features

- **Chat with Doc**: AI-powered health assistant conversations
- **User Profiles**: Store health data, goals, and preferences  
- **Authentication**: Username/passphrase login via conversation
- **Third-Party API**: External services can update user profiles
- **S3 Storage**: All data persisted to DigitalOcean Spaces (S3-compatible)
- **ListeningAI**: Portable `/listening/*` API + shared agentic tool loop
- **LLM Fallback**: Configurable OpenRouter model chain

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
pip install -e ../ListeningAI[spaces]   # reference ListeningAI package
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required settings:
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `S3_BUCKET` - Your S3 bucket name
- `LLM_API_KEY` - OpenRouter/OpenAI API key (or use Ollama)

### 3. Run the Server

```bash
python3 api_server.py
```

Open http://localhost:8012 in your browser.

### 4. (Optional) Run with Ollama Only

If you don't have an LLM API key, install [Ollama](https://ollama.ai) and run:

```bash
ollama pull llama3.2
python3 api_server.py
```

The app will automatically use Ollama when no API key is configured.

## API Endpoints

### Internal (Frontend)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve web interface |
| `/ping` | GET | Health check |
| `/auth` | POST | Login/signup |
| `/chat` | POST | Chat with Doc |
| `/user/<user_id>` | GET/PUT | User profile |
| `/conversations/<user_id>` | GET | List conversations |

### Third-Party API

External services can read/update user profiles using Basic Auth:

```bash
# Get profile
curl -u "username:passphrase" http://localhost:8012/api/v1/profile

# Update profile
curl -u "username:passphrase" -X POST http://localhost:8012/api/v1/profile \
  -H "Content-Type: application/json" \
  -d '{"profile": {"weight": "175 lbs", "blood_pressure": "120/80"}}'
```

## Architecture

```
Frontend (index.html)
    │
    ▼
API Server (Flask)
    │
    ├── handlers.py (request processing)
    ├── utils.py (LLM completion)
    └── s3_storage.py (persistence)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_URL` | OpenRouter | LLM completion endpoint |
| `LLM_API_KEY` | - | API key for LLM |
| `LLM_MODEL` | llama-3.2-3b | Model to use |
| `OLLAMA_ENABLED` | true | Enable Ollama fallback |
| `OLLAMA_URL` | localhost:11434 | Ollama server URL |
| `AWS_ACCESS_KEY_ID` | - | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | - | AWS credentials |
| `S3_BUCKET` | - | S3 bucket name |
| `S3_PREFIX` | greendial/ | S3 key prefix |
| `FLASK_PORT` | 8012 | Server port |

## Development

See `SPEC.md` for detailed technical specification and implementation phases.

## License

MIT
