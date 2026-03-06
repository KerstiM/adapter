#!/bin/bash
# Adapter deployment script Zone VPS-ile
# Kasutamine: ./deploy.sh kasutaja@sinu-server-ip

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Kasutamine: $0 kasutaja@server-ip [domeen]"
    echo "Näide:      $0 root@123.45.67.89 minu-domeen.ee"
    exit 1
fi

SERVER="$1"
DOMAIN="${2:-}"
REMOTE_DIR="/var/www/adapter"

echo "=== 1. Frontend'i ehitamine ==="
cd "$(dirname "$0")/../frontend/vue-project"
npm install
npm run build
cd -

echo "=== 2. Failide kopeerimine serverisse ==="
# Loo serveris kataloogid
ssh "$SERVER" "mkdir -p $REMOTE_DIR/frontend"

# Kopeeri backend + datasets + spec
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pipeline_out' \
    "$(dirname "$0")/../backend" "$SERVER:$REMOTE_DIR/"

rsync -avz --delete \
    "$(dirname "$0")/../datasets" "$SERVER:$REMOTE_DIR/"

rsync -avz --delete \
    "$(dirname "$0")/../spec" "$SERVER:$REMOTE_DIR/"

# Kopeeri frontend build
rsync -avz --delete \
    "$(dirname "$0")/../frontend/vue-project/dist/" "$SERVER:$REMOTE_DIR/frontend/"

# Kopeeri deployment konfid
rsync -avz \
    "$(dirname "$0")/adapter-backend.service" "$SERVER:/tmp/"

rsync -avz \
    "$(dirname "$0")/nginx.conf" "$SERVER:/tmp/adapter-nginx.conf"

echo "=== 3. Serveri seadistamine ==="
ssh "$SERVER" bash <<'REMOTE_SCRIPT'
set -euo pipefail

# Installi vajalikud paketid
apt-get update -qq
apt-get install -y -qq python3 python3-venv nginx

# Python virtual environment
cd /var/www/adapter
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

# Systemd teenus backend'ile
cp /tmp/adapter-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable adapter-backend
systemctl restart adapter-backend

# Nginx konfiguratsioon
cp /tmp/adapter-nginx.conf /etc/nginx/sites-available/adapter
ln -sf /etc/nginx/sites-available/adapter /etc/nginx/sites-enabled/adapter
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== Deployment valmis! ==="
echo "Backend:  systemctl status adapter-backend"
echo "Nginx:    systemctl status nginx"
echo ""
echo "NB! Muuda /etc/nginx/sites-available/adapter failis SINU_DOMEEN.ee oma domeeniks!"
REMOTE_SCRIPT

if [ -n "$DOMAIN" ]; then
    echo "=== 4. Domeeni seadistamine Nginxis ==="
    ssh "$SERVER" "sed -i 's/SINU_DOMEEN.ee/$DOMAIN/g; s/www.SINU_DOMEEN.ee/www.$DOMAIN/g' /etc/nginx/sites-available/adapter && nginx -t && systemctl reload nginx"
    echo ""
    echo "=== HTTPS sertifikaadi lisamine (Let's Encrypt) ==="
    ssh "$SERVER" "apt-get install -y -qq certbot python3-certbot-nginx && certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || echo 'Certbot ebaõnnestus — käivita käsitsi: certbot --nginx -d $DOMAIN'"
fi

echo ""
echo "Valmis! Ava brauser ja mine: http://${DOMAIN:-sinu-server-ip}"
