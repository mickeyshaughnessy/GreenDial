# GreenDial Deployment Guide

## Local Development

### Prerequisites

```bash
# Python 3.8+
python3 --version

# Install dependencies
pip install flask redis requests boto3
```

### Configuration

Create `config.py`:

```python
# OpenRouter API
openai_api_key = "your-openrouter-api-key"
openai_url = "https://openrouter.ai/api/v1/completions"

# Redis
REDHASH_USER_DATA = "greendial:users"

# S3 (optional for local dev)
S3_BUCKET = "greendial-data"
AWS_ACCESS_KEY = "your-access-key"
AWS_SECRET_KEY = "your-secret-key"

# RSE API
RSE_API_URL = "https://rse-api.com:5003/"
```

### Start Services

```bash
# Start Redis (if using local Redis)
redis-server

# Start Flask API
python api_server.py
# Server runs on http://localhost:8012

# Open in browser
open http://localhost:8012
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8012/ping

# Chat test
curl -X POST http://localhost:8012/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "text": "hello"}'
```

---

## Production Deployment

### Server Requirements

- Ubuntu 20.04+ or similar
- Python 3.8+
- Redis
- nginx
- systemd

### Initial Setup

```bash
# SSH to production VM
ssh user@production-vm

# Clone repository
git clone https://github.com/your-org/GreenDial.git
cd GreenDial

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create config
cp config.example.py config.py
nano config.py  # Add production keys
```

### Systemd Service

Create `/etc/systemd/system/greendial.service`:

```ini
[Unit]
Description=GreenDial API Server
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/GreenDial
Environment="PATH=/path/to/GreenDial/venv/bin"
ExecStart=/path/to/GreenDial/venv/bin/python api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable greendial
sudo systemctl start greendial
```

### nginx Configuration

Update `nginx.conf` and symlink:

```bash
sudo ln -s /path/to/GreenDial/nginx.conf /etc/nginx/sites-enabled/greendial
sudo nginx -t
sudo systemctl reload nginx
```

Example nginx.conf:

```nginx
server {
    listen 80;
    server_name greendial.org www.greendial.org;

    location / {
        root /path/to/GreenDial;
        try_files $uri $uri/ /index.html;
    }

    location /chat {
        proxy_pass http://127.0.0.1:8012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /conversations {
        proxy_pass http://127.0.0.1:8012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ping {
        proxy_pass http://127.0.0.1:8012;
    }
}
```

### SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d greendial.org -d www.greendial.org
```

---

## Git Deployment Workflow

### Deploy Updates

```bash
# Local: Push changes
git add .
git commit -m "Update feature"
git push origin main

# Production: Pull and restart
ssh user@production-vm
cd /path/to/GreenDial
git pull origin main
sudo systemctl restart greendial
```

### Automated Deployment (Optional)

Create `/path/to/GreenDial/deploy.sh`:

```bash
#!/bin/bash
cd /path/to/GreenDial
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart greendial
echo "Deployment complete"
```

---

## Crontab Configuration (RCL)

Edit crontab:

```bash
crontab -e
```

Add RCL scripts:

```cron
# Morning health check-in (9 AM)
0 9 * * * /path/to/GreenDial/venv/bin/python /path/to/GreenDial/scripts/rcl_morning.py

# Evening reflection (9 PM)
0 21 * * * /path/to/GreenDial/venv/bin/python /path/to/GreenDial/scripts/rcl_evening.py

# Weekly summary (Sunday 10 AM)
0 10 * * 0 /path/to/GreenDial/venv/bin/python /path/to/GreenDial/scripts/rcl_weekly.py

# RSE bid check (every 6 hours)
0 */6 * * * /path/to/GreenDial/venv/bin/python /path/to/GreenDial/scripts/rse_bids.py
```

---

## Monitoring

### Logs

```bash
# Flask app logs
sudo journalctl -u greendial -f

# nginx access logs
sudo tail -f /var/log/nginx/access.log

# nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Health Checks

```bash
# Check service status
sudo systemctl status greendial

# Test API
curl https://greendial.org/ping
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check Flask service: `sudo systemctl status greendial` |
| Redis connection failed | Start Redis: `sudo systemctl start redis` |
| Permission denied | Check file ownership: `sudo chown -R www-data:www-data /path/to/GreenDial` |
| API key invalid | Verify config.py has correct OpenRouter key |

---

## Environment Variables

For production, consider using environment variables:

```bash
export OPENROUTER_API_KEY="your-key"
export REDIS_URL="redis://localhost:6379"
export S3_BUCKET="greendial-data"
export RSE_API_URL="https://rse-api.com:5003/"
```
