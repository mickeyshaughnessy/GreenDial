# GreenDial Deployment Guide

## Server Configuration

### Nginx Configuration

The nginx configuration must proxy **all API endpoints** to the backend API server running on port 8012.

**Location:** `/etc/nginx/sites-available/greendial.org`

```nginx
server {
    server_name greendial.org www.greendial.org;
    root /var/www/greendial;
    
    # Proxy ALL API endpoints to the backend
    # This regex matches: /auth, /chat, /user, /settings, /conversations, 
    # /notifications, /stats, /ping, /api, /unprompted
    location ~ ^/(auth|chat|user|settings|conversations|notifications|stats|ping|api|unprompted) {
        proxy_pass http://localhost:8012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Serve static files (index.html, etc.)
    location / {
        try_files $uri $uri/ =404;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/greendial.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/greendial.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = www.greendial.org) {
        return 301 https://$host$request_uri;
    }
    if ($host = greendial.org) {
        return 301 https://$host$request_uri;
    }
    listen 80;
    server_name greendial.org www.greendial.org;
    return 404;
}
```

**Important:** After updating nginx config:
```bash
nginx -t                    # Test configuration
systemctl reload nginx      # Apply changes
```

### Systemd Service

**Location:** `/etc/systemd/system/greendial.service`

```ini
[Unit]
Description=GreenDial API
After=network.target

[Service]
User=root
WorkingDirectory=/root/GreenDial
ExecStart=/root/GreenDial/venv/bin/gunicorn -w 4 -b 0.0.0.0:8012 api_server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**Service Management:**
```bash
systemctl daemon-reload     # After changing service file
systemctl restart greendial # Restart service
systemctl status greendial  # Check status
journalctl -u greendial -f  # View logs
```

## Deployment Process

### 1. Update Code on Server

```bash
ssh root@143.110.131.237
cd ~/GreenDial
git pull origin main
```

### 2. Update Dependencies (if needed)

```bash
~/GreenDial/venv/bin/pip install -r requirements.txt
```

### 3. Update Configuration

Copy `config.py` with secrets to server (not in git):
```bash
scp -i ~/.ssh/id_ed25519 config.py root@143.110.131.237:~/GreenDial/
```

### 4. Copy Static Files

```bash
cp ~/GreenDial/*.html /var/www/greendial/
```

### 5. Restart Service

```bash
systemctl restart greendial
systemctl status greendial
```

### 6. Update Nginx (if endpoints changed)

```bash
# Edit /etc/nginx/sites-available/greendial.org
nginx -t
systemctl reload nginx
```

## Testing

### Run Integration Tests

From local machine:
```bash
./test_integration.py https://greendial.org
```

### Manual API Tests

```bash
# Test API is running
curl https://greendial.org/ping

# Test stats
curl https://greendial.org/stats

# Test signup
curl -X POST https://greendial.org/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123","create_new":true,"hipaa_waiver_accepted":true}'

# Test login
curl -X POST https://greendial.org/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Test chat
curl -X POST https://greendial.org/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_test","text":"Hello"}'
```

## Common Issues

### Issue: Login/Signup Returns 404

**Cause:** Nginx not proxying `/auth` endpoint to backend

**Fix:** Ensure nginx configuration includes `/auth` in the proxy location regex:
```nginx
location ~ ^/(auth|chat|user|...) {
    proxy_pass http://localhost:8012;
    ...
}
```

### Issue: Service Won't Start

**Check logs:**
```bash
journalctl -u greendial -n 50
```

**Common causes:**
- Python dependencies missing
- Port 8012 already in use
- config.py missing or invalid
- Wrong working directory in service file

### Issue: Static Files Not Loading

**Cause:** Files not copied to `/var/www/greendial/`

**Fix:**
```bash
cp ~/GreenDial/*.html /var/www/greendial/
```

### Issue: CORS Errors

**Cause:** Frontend using wrong API URL

**Check:** `index.html` should have:
```javascript
const API = window.location.origin;  // Uses same domain
```

## Monitoring

### Check Service Status
```bash
systemctl status greendial
```

### View Logs
```bash
journalctl -u greendial -n 100 --no-pager
journalctl -u greendial -f  # Follow logs
```

### Check Nginx Logs
```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Check DO Spaces Storage
Storage is in Digital Ocean Spaces at:
- Bucket: `mithril-media`
- Prefix: `greendial/`
- Endpoint: `sfo3.digitaloceanspaces.com`

## Security

### Secrets Management

- `config.py` contains API keys and secrets
- **Never commit config.py to git** (in .gitignore)
- Copy to server via SCP
- Stored only on server at `~/GreenDial/config.py`

### SSL/TLS

- Managed by Let's Encrypt (Certbot)
- Auto-renewal configured
- Certificates in `/etc/letsencrypt/live/greendial.org/`

## Rollback

If deployment breaks:

```bash
# Revert code
cd ~/GreenDial
git log --oneline -10  # Find last good commit
git checkout <commit-hash>

# Restart service
systemctl restart greendial

# Revert nginx config
cp /etc/nginx/sites-available/greendial.org.backup /etc/nginx/sites-available/greendial.org
nginx -t
systemctl reload nginx
```

## CI/CD Notes

Future enhancement: Add GitHub Actions workflow to:
1. Run tests on push
2. Deploy to staging
3. Run integration tests
4. Deploy to production
5. Run smoke tests
