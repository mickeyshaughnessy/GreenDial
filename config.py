"""
GreenDial Configuration
All sensitive values loaded from environment variables
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

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

# LLM Configuration (OpenRouter)
LLM_API_URL = os.environ.get('LLM_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'meta-llama/llama-3.2-3b-instruct:free')
LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '800'))
