"""
GreenDial Configuration
All sensitive values loaded from environment variables
"""
import os

# Flask
SECRET_KEY = os.environ.get('SECRET_KEY', 'greendial-dev-secret-key')
FLASK_HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.environ.get('FLASK_PORT', '8012'))
DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET = os.environ.get('S3_BUCKET', 'mithrilmedia')
S3_PREFIX = os.environ.get('S3_PREFIX', 'greendial/')

# LLM Configuration (configurable /completion endpoint)
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'meta-llama/llama-3.2-3b-instruct:free')
LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '800'))

# Ollama Fallback Configuration
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/chat')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2')
OLLAMA_ENABLED = os.environ.get('OLLAMA_ENABLED', 'true').lower() == 'true'

# Legacy compatibility aliases
OPENROUTER_API_KEY = LLM_API_KEY
OPENROUTER_API_URL = LLM_API_URL
OPENROUTER_MODEL = LLM_MODEL
DEFAULT_MODEL = LLM_MODEL
