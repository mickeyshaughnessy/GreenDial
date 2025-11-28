# GreenDial API Reference

Base URL: `http://localhost:8012` (dev) | `https://api.greendial.org` (prod)

## Endpoints

### Health Check

```
GET /ping
```

**Response:**
```json
{
  "message": "ok"
}
```

---

### Chat

```
POST /chat
```

Main chat interface for user interactions.

**Request:**
```json
{
  "user_id": "string",
  "text": "string"
}
```

**Response:**
```json
{
  "response": "string"
}
```

**Example:**
```bash
curl -X POST http://localhost:8012/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "text": "I walked 5000 steps today"}'
```

---

### Conversations

```
POST /conversations
GET /conversations
```

Manage conversation history.

**Request (Load):**
```json
{
  "conversationId": "string"
}
```

**Response:**
```json
{
  "conversation": [
    {
      "sender": "User",
      "message": "string"
    },
    {
      "sender": "Bot",
      "message": "string"
    }
  ]
}
```

---

### Authentication (Planned)

```
POST /auth
```

User authentication with HIPAA waiver.

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "username": "string",
  "user_id": "string",
  "token": "string"
}
```

---

## Droid Invocation (Planned)

```
POST /droid
```

Invoke a specialized droid agent.

**Request:**
```json
{
  "droidname": "<type> droid",
  "droidprompt": "string",
  "user_id": "string",
  "model": "fast|balanced|reasoning",
  "reasoning": "minimal|standard|detailed"
}
```

**Response:**
```json
{
  "response": "string",
  "droid": "string",
  "tokens_used": 123
}
```

**Example:**
```bash
curl -X POST http://localhost:8012/droid \
  -H "Content-Type: application/json" \
  -d '{
    "droidname": "oracle droid",
    "droidprompt": "Analyze my sleep patterns this week",
    "user_id": "user123"
  }'
```

---

## Data Symbols

The chat API processes responses containing symbols that trigger backend services:

### **AUTH**
Triggers authentication service.

### **SELECT**
Queries historical data from S3.

### **INSERT**
Stores new data to S3.

---

## Error Responses

```json
{
  "error": "string",
  "code": 400
}
```

| Code | Meaning |
|------|---------|
| 400 | Bad request |
| 401 | Unauthorized |
| 404 | Not found |
| 500 | Server error |

---

## External API Integration

### The Services Exchange (RSE)

Base URL: `https://rse-api.com:5003/`

Documentation: [theservicesexchange.com/api_docs.html](https://theservicesexchange.com/api_docs.html)

Used for:
- Diet service bids
- Exercise service bids
- Sleep optimization bids
- Entertainment suggestions

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/chat` | 60/min |
| `/droid` | 30/min |
| `/conversations` | 100/min |

---

## WebSocket (Planned)

Future real-time chat support:

```
WS /ws/chat
```

**Message Format:**
```json
{
  "type": "message|typing|read",
  "user_id": "string",
  "text": "string"
}
```
