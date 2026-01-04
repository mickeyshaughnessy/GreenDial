# LLM Model Upgrade - Rate Limit Resolution

## Issue
Users were experiencing rate limit errors with the free LLM model during conversations.

## Previous Configuration
```python
LLM_MODEL = 'meta-llama/llama-3.2-3b-instruct:free'
```

**Problems:**
- Rate limits on free tier (strict)
- No cost control, but limited availability
- Service interruptions during peak usage

## New Configuration
```python
LLM_MODEL = 'anthropic/claude-3.5-haiku'
```

**Benefits:**
- **No rate limits** (paid tier with OpenRouter key)
- **Very affordable pricing:**
  - Input: $0.25 per 1M tokens (~$0.0000003 per typical message)
  - Output: $1.25 per 1M tokens (~$0.0000015 per response)
  - Typical conversation: ~$0.001 (1/10th of a cent)
- **Better quality responses**
- **Faster response times** (Claude 3.5 Haiku is optimized for speed)
- **Better profile extraction** (observed in testing)

## Testing Results

### Local Testing
✅ Simple responses working  
✅ Complex health assistant prompts working  
✅ Profile extraction improved  
✅ Enhanced Doc v2 conversation flow working  

### Live Deployment Testing
✅ User signup successful  
✅ Chat responses with no rate limits  
✅ Profile updates working correctly  
✅ **Rapid-fire test: 5 consecutive requests - all successful**  
✅ Response quality excellent  
✅ Response times fast (<3 seconds)  

## Cost Estimates

Based on typical usage patterns:

**Per Conversation:**
- Average prompt: ~400 tokens input
- Average response: ~200 tokens output
- Cost per exchange: ~$0.00035 (1/30th of a cent)

**Monthly Estimates:**
- 100 conversations/day: ~$1.05/month
- 500 conversations/day: ~$5.25/month
- 1000 conversations/day: ~$10.50/month

**Compared to:**
- Free model: $0 but rate limited (unusable during peak)
- GPT-4: ~$0.03 per conversation (~100x more expensive)
- GPT-3.5 Turbo: ~$0.002 per conversation (~6x more expensive)

## Model Comparison

| Model | Input Cost | Output Cost | Speed | Rate Limits |
|-------|-----------|-------------|-------|-------------|
| Llama 3.2 3B (free) | $0 | $0 | Fast | **Strict** ⚠️ |
| Claude 3.5 Haiku | $0.25/1M | $1.25/1M | Very Fast | None ✅ |
| GPT-3.5 Turbo | $0.50/1M | $1.50/1M | Fast | Flexible |
| GPT-4 Turbo | $10/1M | $30/1M | Medium | Flexible |

## Implementation

### Configuration Change
File: `config.py` (not in git, deployed via SCP)
```python
LLM_MODEL = 'anthropic/claude-3.5-haiku'
```

### Deployment
1. Updated local config.py
2. Tested locally - all tests passing
3. Copied config.py to server via SCP
4. Restarted greendial service
5. Verified with multiple tests - no rate limits

### Monitoring

**Check current model in use:**
```bash
ssh root@143.110.131.237 "cat ~/GreenDial/config.py | grep LLM_MODEL"
```

**Monitor API costs:**
- Check OpenRouter dashboard: https://openrouter.ai/
- View usage per model
- Set spending alerts if needed

**Check for rate limit errors in logs:**
```bash
ssh root@143.110.131.237 "journalctl -u greendial -n 100 | grep -i 'rate limit'"
```

## Rollback Procedure

If cost becomes an issue or need to switch models:

1. Edit `config.py` locally:
   ```python
   LLM_MODEL = 'your-chosen-model'
   ```

2. Copy to server:
   ```bash
   scp -i ~/.ssh/id_ed25519 config.py root@143.110.131.237:~/GreenDial/
   ```

3. Restart service:
   ```bash
   ssh root@143.110.131.237 "systemctl restart greendial"
   ```

## Alternative Affordable Models

If Claude 3.5 Haiku has issues, consider:

1. **GPT-3.5 Turbo** ($0.50/$1.50 per 1M tokens)
   ```python
   LLM_MODEL = 'openai/gpt-3.5-turbo'
   ```

2. **Llama 3.2 3B** (paid, no rate limits) ($0.06/$0.06 per 1M tokens)
   ```python
   LLM_MODEL = 'meta-llama/llama-3.2-3b-instruct'
   ```

3. **Mistral Small** ($0.20/$0.60 per 1M tokens)
   ```python
   LLM_MODEL = 'mistralai/mistral-small-latest'
   ```

## Conclusion

✅ **Rate limit issue resolved**  
✅ **Cost-effective solution** (~$1-10/month for typical usage)  
✅ **Better response quality**  
✅ **Faster response times**  
✅ **No service interruptions**  

The Claude 3.5 Haiku model provides excellent value: high quality, fast responses, and negligible cost for the current usage level.
