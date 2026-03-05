"""
GreenDial Configuration

This module contains hardcoded configuration values.
This file is in .gitignore and should not be committed.
"""

# Flask Configuration
SECRET_KEY = 'greendial-production-secret-key-2026'
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 8012
DEBUG = False

# Digital Ocean Spaces Configuration (S3-compatible)
# Unified credentials from Agreed
DO_SPACES_KEY = 'DO009JWM9AU4ZWNNZBCM'
DO_SPACES_SECRET = 'kteBtxY57U1jx5+RuDDXTZRayqhrRtVNYlRPrk/tVzo'
DO_SPACES_REGION = 'sfo3'
DO_SPACES_ENDPOINT = 'https://sfo3.digitaloceanspaces.com'
DO_SPACES_BUCKET = 'mithril-media'
S3_PREFIX = 'greendial/'

# LLM Configuration (OpenRouter) - Unified
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_API_KEY = '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'
# Free model (primary) - falls back to paid on rate limit
OPENROUTER_MODEL = 'meta-llama/llama-3.2-3b-instruct:free'
# Paid fallback model when free is rate-limited
OPENROUTER_FALLBACK_MODEL = 'anthropic/claude-3.5-haiku'
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 800
