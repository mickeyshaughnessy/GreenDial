#!/bin/bash
# Deployment script for GreenDial
# Usage: ./deploy.sh
#
# Also keeps the ListeningAI package in sync (reference deployment dependency).
# Expects /root/ListeningAI on the server (clone once if missing).

set -e

SERVER="root@143.110.131.237"
SSH_KEY="~/.ssh/id_ed25519"
DEPLOY_PATH="/root/GreenDial"
SERVICE_NAME="greendial.service"

echo "Deploying GreenDial to $SERVER..."

# 1. Pull latest code on server (config.py is untracked there, so git won't touch it)
echo "Pulling latest code..."
ssh -i "$SSH_KEY" "$SERVER" << 'ENDSSH'
set -e
cd /root/GreenDial
git fetch origin main
git reset --hard origin/main
echo "Code updated: $(git rev-parse --short HEAD)"

# ListeningAI package (reference dependency)
if [ -d /root/ListeningAI/.git ]; then
  echo "Updating ListeningAI..."
  cd /root/ListeningAI
  git fetch origin main
  git reset --hard origin/main
  echo "ListeningAI: $(git rev-parse --short HEAD)"
elif [ ! -d /root/ListeningAI ]; then
  echo "Cloning ListeningAI..."
  git clone https://github.com/mickeyshaughnessy/ListeningAI.git /root/ListeningAI
fi
# Install into the same env gunicorn uses (prefer venv if present)
if [ -x /root/GreenDial/venv/bin/pip ]; then
  /root/GreenDial/venv/bin/pip install -e "/root/ListeningAI[spaces]" -q
elif command -v pip3 >/dev/null 2>&1; then
  pip3 install -e "/root/ListeningAI[spaces]" -q
else
  pip install -e "/root/ListeningAI[spaces]" -q
fi
echo "listening-ai installed"

cd /root/GreenDial
# Sync web-served files to nginx webroot
cp index.html /var/www/greendial/index.html
cp stickers.html /var/www/greendial/stickers.html
cp api_server.py /var/www/greendial/api_server.py
cp handlers.py /var/www/greendial/handlers.py
# PWA assets (manifest, service worker, icons) — served statically by nginx
cp manifest.json /var/www/greendial/manifest.json
cp sw.js /var/www/greendial/sw.js
mkdir -p /var/www/greendial/icons
cp icons/*.png /var/www/greendial/icons/
echo "Static files synced to /var/www/greendial/"
ENDSSH

# 2. Sync config (after pull, so it can't be stomped)
if [ -f "config.py" ]; then
    echo "Syncing config.py..."
    scp -i "$SSH_KEY" config.py "$SERVER:$DEPLOY_PATH/config.py"
fi

# 3. Restart service
echo "Restarting $SERVICE_NAME..."
ssh -i "$SSH_KEY" "$SERVER" "systemctl restart $SERVICE_NAME && sleep 2 && systemctl is-active $SERVICE_NAME"

echo "Deployment complete."
