# Adapter — Deployment juhend Zone VPS-ile

## Eeldused

- Zone'i virtuaalserver (VPS) Ubuntu/Debian baasil
- SSH juurdepääs serverile (nt `root@123.45.67.89`)
- Domeen on Zone'i halduspaneelis suunatud serveri IP-aadressile (A-kirje)
- Lokaalselt on installitud: `node`, `npm`, `rsync`, `ssh`

## Kiire deployment (automaatne)

```bash
# Ilma domeenita (testiks)
./deploy/deploy.sh root@SINU-SERVER-IP

# Koos domeeniga (seadistab ka HTTPS)
./deploy/deploy.sh root@SINU-SERVER-IP sinu-domeen.ee
```

Script teeb automaatselt:
1. Ehitab frontend'i (`npm run build`)
2. Kopeerib kõik failid serverisse
3. Seadistab Python virtual environment'i
4. Seadistab systemd teenuse backend'ile
5. Seadistab Nginx reverse proxy
6. (Valikuline) Seadistab HTTPS Let's Encrypt sertifikaadiga

## Käsitsi deployment (samm-sammult)

### 1. Zone'i halduspaneel — DNS seadistamine

Mine [zone.ee halduspaneel](https://my.zone.eu) ja lisa oma domeenile A-kirje:

| Tüüp | Nimi | Väärtus |
|------|------|---------|
| A | @ | sinu-serveri-ip |
| A | www | sinu-serveri-ip |

### 2. Frontend'i ehitamine

```bash
cd frontend/vue-project
npm install
npm run build
```

Ehitatud failid tekivad kausta `frontend/vue-project/dist/`.

### 3. Failide kopeerimine serverisse

```bash
# Loo serveris kataloog
ssh root@SERVER "mkdir -p /var/www/adapter/frontend"

# Kopeeri failid
rsync -avz backend/ root@SERVER:/var/www/adapter/backend/
rsync -avz datasets/ root@SERVER:/var/www/adapter/datasets/
rsync -avz spec/ root@SERVER:/var/www/adapter/spec/
rsync -avz frontend/vue-project/dist/ root@SERVER:/var/www/adapter/frontend/
```

### 4. Serveri seadistamine (SSH kaudu)

```bash
ssh root@SERVER

# Installi tarkvara
apt update && apt install -y python3 python3-venv nginx

# Python venv
cd /var/www/adapter
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

# Testi, kas backend käivitub
./venv/bin/python -m backend.entrypoints.api
# Ctrl+C peatamiseks
```

### 5. Backend'i systemd teenus

```bash
# Kopeeri teenuse fail
cp /path/to/adapter-backend.service /etc/systemd/system/

# Aktiveeri ja käivita
systemctl daemon-reload
systemctl enable adapter-backend
systemctl start adapter-backend

# Kontrolli staatust
systemctl status adapter-backend
```

### 6. Nginx seadistamine

```bash
# Kopeeri konfig (muuda SINU_DOMEEN.ee oma domeeniks!)
cp /path/to/nginx.conf /etc/nginx/sites-available/adapter
nano /etc/nginx/sites-available/adapter

# Aktiveeri
ln -s /etc/nginx/sites-available/adapter /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Testi ja käivita
nginx -t
systemctl reload nginx
```

### 7. HTTPS (Let's Encrypt)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d sinu-domeen.ee -d www.sinu-domeen.ee
```

Sertifikaat uueneb automaatselt.

## Uuendamine (re-deploy)

Pärast koodi muudatusi käivita lihtsalt uuesti:

```bash
./deploy/deploy.sh root@SERVER sinu-domeen.ee
```

## Veaotsing

```bash
# Backend'i logid
journalctl -u adapter-backend -f

# Nginx logid
tail -f /var/log/nginx/error.log

# Kas backend töötab?
curl http://localhost:5000/api/datasets

# Kas Nginx töötab?
systemctl status nginx
```

## Serveri struktuur

```
/var/www/adapter/
├── backend/          # Python backend
├── datasets/         # Andmekogud
├── spec/             # Skeemid ja reeglid
├── frontend/         # Vue 3 ehitatud failid (dist/)
└── venv/             # Python virtual environment
```
