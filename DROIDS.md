# Droid Development Guide

Droids are modular AI agents that handle specific tasks within GreenDial. Each droid is specialized for a particular domain and can be invoked via a standardized JSON interface.

## Droid Invocation

Invoke any droid by passing a JSON request:

```json
{
  "droidprompt": "<detailed instruction text to be handled>",
  "droidname": "<type> droid"
}
```

### Example Invocations

```json
// Writer droid for documentation
{
  "droidprompt": "Generate user-facing documentation for the health dashboard feature",
  "droidname": "writer droid"
}

// Oracle droid for data analysis
{
  "droidprompt": "Analyze user sleep patterns over the last 30 days and identify trends",
  "droidname": "oracle droid"
}

// Hashing droid for security
{
  "droidprompt": "Generate secure passphrase validation for user authentication",
  "droidname": "hashing droid"
}
```

## Available Droids

### Core Droids

| Droid | Type | Responsibility |
|-------|------|----------------|
| **Writer Droid** | Content | Documentation, prompts, user messages |
| **Oracle Droid** | Data | Queries, analysis, insights |
| **Hashing Droid** | Security | Auth, encryption, validation |
| **Worker Droid** | General | Task execution, processing |

### Domain Droids

| Droid | Type | Responsibility |
|-------|------|----------------|
| **Benefits Droid** | Health | Health optimization recommendations |
| **Sensor Droid** | Input | Data collection, monitoring |
| **Communications Droid** | Output | Notifications, reminders, RCL |

### System Droids

| Droid | Type | Responsibility |
|-------|------|----------------|
| **Supervisor Droid** | Control | Orchestration, task routing |
| **Janitor Droid** | Maintenance | Cleanup, archival, optimization |
| **Droidprompt Droid** | Meta | Writing prompts for other droids |

## Creating a New Droid

### 1. Define the Droid Agent

Add to `agents.py`:

```python
health_coach_droid = """
You are a health coach droid specialized in:
- Diet optimization
- Exercise recommendations
- Sleep hygiene
- Stress management

When invoked, analyze the user context and provide actionable health advice.
"""
```

### 2. Create Prompt Templates

Add to `prompts/`:

```python
# prompts/health_coach.py

COACH_SYSTEM = """
You are a certified health coach assistant.
User profile: {user_profile}
Health goals: {goals}
Recent data: {recent_data}

Provide specific, actionable recommendations.
"""

COACH_DIET = """
Based on the user's dietary history:
{diet_history}

Suggest improvements for: {focus_area}
"""
```

### 3. Register Handler

Add to `handlers.py`:

```python
def handle_health_coach(request):
    droidprompt = request.get('droidprompt')
    user_id = request.get('user_id')
    
    # Build context
    user_data = get_user_data(user_id)
    prompt = build_coach_prompt(droidprompt, user_data)
    
    # Call completion API
    response = utils.completion(prompt)
    
    return json.dumps({"response": response})
```

## Droid Communication Pattern

Droids communicate through the symbol system:

```
User Input
    │
    ▼
┌─────────────────┐
│ Supervisor Droid │ ─── Routes to appropriate droid
└────────┬────────┘
         │
    ┌────┴────┬─────────┐
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│Oracle │ │Writer │ │Worker │
│Droid  │ │Droid  │ │Droid  │
└───────┘ └───────┘ └───────┘
    │         │         │
    └────┬────┴─────────┘
         ▼
   ┌───────────┐
   │  Response │
   └───────────┘
```

## Best Practices

1. **Single Responsibility**: Each droid should have one clear purpose
2. **Stateless**: Droids should not maintain internal state; use S3 for persistence
3. **Composable**: Droids can invoke other droids via the supervisor
4. **Traceable**: Log all droid invocations for debugging
5. **Efficient**: Use reasoning and model arguments to reduce token cost

## Testing Droids

```bash
# Test droid invocation locally
curl -X POST http://localhost:8012/droid \
  -H "Content-Type: application/json" \
  -d '{"droidname": "oracle droid", "droidprompt": "test query"}'
```

## Token Optimization

When invoking droids, use the `reasoning` and `model` parameters to control costs:

```json
{
  "droidprompt": "Simple task description",
  "droidname": "worker droid",
  "model": "fast",
  "reasoning": "minimal"
}
```
