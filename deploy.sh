#!/bin/bash
# Deployment script for GreenDial
# Usage: ./deploy.sh

set -e

SERVER="root@143.110.131.237"
SSH_KEY="~/.ssh/id_ed25519"
DEPLOY_PATH="/root/GreenDial"
SERVICE_NAME="greendial.service"

echo "Deploying GreenDial to $SERVER..."

# 1. Sync config
if [ -f "config.py" ]; then
    echo "Syncing config.py..."
    scp -i "$SSH_KEY" config.py "$SERVER:$DEPLOY_PATH/config.py"
fi

# 2. Push local commits then pull on server
echo "Pulling latest code..."
ssh -i "$SSH_KEY" "$SERVER" << 'ENDSSH'
set -e
cd /root/GreenDial
git stash 2>/dev/null || true
git pull origin main
git stash pop 2>/dev/null || true
echo "Code updated: $(git rev-parse --short HEAD)"
# Sync web-served files to nginx webroot
cp index.html /var/www/greendial/index.html
cp api_server.py /var/www/greendial/api_server.py
cp handlers.py /var/www/greendial/handlers.py
echo "Static files synced to /var/www/greendial/"
ENDSSH

# 3. Restart service
echo "Restarting $SERVICE_NAME..."
ssh -i "$SSH_KEY" "$SERVER" "systemctl restart $SERVICE_NAME && sleep 2 && systemctl is-active $SERVICE_NAME"

echo "Deployment complete."
