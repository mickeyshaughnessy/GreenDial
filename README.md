# GreenDial

GreenDial is an AI applications harness for personal health data assistants. Users waive HIPAA rights during signup, enabling open data sharing for health optimization.

**Live:** [greendial.org](https://www.greendial.org)

## Overview

GreenDial Doc is the premier tier health and lifestyle optimizing assistant - a concierge chatbot that:
- Transforms unstructured user input into structured health records
- Engages in autonomous health-related conversations
- Activates external services on behalf of the user
- Provides periodic bid suggestions via The Services Exchange API

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         index.html                               │
│                    (Web App + HIPAA Waiver)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      api_server.py (Flask)                       │
│                    localhost:8012 / nginx                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   handlers.py │ │   agents.py   │ │   prompts/    │
│  (Routing)    │ │   (Droids)    │ │  (Templates)  │
└───────┬───────┘ └───────────────┘ └───────────────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  OpenRouter   │  │   Amazon S3   │  │  RSE API      │
│  /completion  │  │   (Storage)   │  │  (Services)   │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Droid Architecture

GreenDial uses a modular "Droid" system for development. Each droid is a specialized AI agent invoked via JSON:

```json
{
  "droidprompt": "<detailed instruction text>",
  "droidname": "<type> droid"
}
```

**Available Droid Types:**
| Droid | Purpose |
|-------|---------|
| `writer droid` | Content and documentation generation |
| `oracle droid` | Data retrieval and analysis |
| `hashing droid` | Authentication and security |
| `benefits droid` | Health benefits optimization |
| `sensor droid` | Data collection and monitoring |
| `communications droid` | Notifications and messaging |
| `janitor droid` | Cleanup and maintenance |
| `supervisor droid` | Orchestration and oversight |
| `worker droid` | General task execution |
| `droidprompt droid` | Writing droid prompts |

See [DROIDS.md](./DROIDS.md) for detailed droid development guide.

## Core Services

| Service | Description |
|---------|-------------|
| **Authentication** | Login with HIPAA waiver acknowledgment |
| **Long-term Memory** | S3-backed conversation and data storage |
| **Personalization** | User settings and preferences |
| **Reminders/Goals** | Health goal tracking and notifications |
| **Suggestions** | RSE API integration for service bids |
| **Data Analysis** | Historical health data queries |
| **LLM Chat** | OpenRouter completion API |

## Quick Start

### Local Development

```bash
# Install dependencies
pip install flask redis requests

# Start the API server
python api_server.py

# Open in browser
open http://localhost:8012
```

### Production Deployment

```bash
# Push to production VM
git push origin main

# SSH and deploy
ssh user@production-vm
cd /path/to/GreenDial
git pull origin main
sudo systemctl restart greendial
```

## External Integrations

- **OpenRouter API**: `/completion` endpoint for LLM inference
- **Amazon S3**: All memory and persistent storage
- **The Services Exchange API**: `https://rse-api.com:5003/`
  - [API Documentation](https://theservicesexchange.com/api_docs.html)
  - Periodic bid suggestions for diet, exercise, sleep, entertainment

## Crontab (RCL - Unprompted Speech)

Health-related proactive conversations are scheduled via crontab:

```cron
# Example: Daily health check-in at 9am
0 9 * * * /path/to/greendial/scripts/rcl_health_checkin.py
```

## File Structure

```
GreenDial/
├── api_server.py      # Flask HTTP server
├── handlers.py        # Request routing and processing
├── agents.py          # Droid agent definitions
├── utils.py           # Shared utilities (completion API)
├── index.html         # Web frontend with login/chat
├── prompts/           # LLM prompt templates
│   ├── auth.py        # Authentication prompts
│   ├── chat.py        # Chat system prompts
│   ├── memory.py      # SELECT/INSERT data prompts
│   ├── settings.py    # User settings prompts
│   ├── external.py    # External service prompts
│   ├── coach.py       # Health coaching prompts
│   └── reviewer.py    # Review/analysis prompts
└── nginx.conf         # Production nginx config
```

## Symbol System

The chat system uses **SYMBOL** notation to route to specialized services:

| Symbol | Purpose |
|--------|---------|
| `**AUTH**` | User authentication |
| `**SELECT**` | Query historical data |
| `**INSERT**` | Store new health data |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Invoke appropriate droid for your task type
4. Submit a pull request

## Documentation

- [DROIDS.md](./DROIDS.md) - Droid development and invocation
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Technical architecture details
- [API.md](./API.md) - API endpoint reference
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment procedures

## License

Open source - contributions welcome.
