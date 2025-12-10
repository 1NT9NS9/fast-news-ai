# Ubuntu Runbook — Google Cloud (GCE) Deployment for news-ai

This guide redeploys your private GitHub project on an Ubuntu GCE VM using Docker Compose. It’s tailored to:
- Repository: https://github.com/1NT9NS9/news-ai (private, cloned via token)
- Email (git identity): fedor.ivanov.agri.1985@gmail.com
- Bot uses long polling — no inbound HTTP ports needed (only SSH)

Recommended VM: e2-small (2 vCPU, 2 GB RAM) or better.

## 1) Connect and prepare the VM
```bash
# SSH (pick one)
gcloud compute ssh USER@INSTANCE_NAME --zone ZONE
# or
ssh USER@VM_EXTERNAL_IP

# Update and set timezone (optional)
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone Europe/Moscow  # or your timezone

# Tools
sudo apt install -y git ca-certificates curl gnupg
```

## 2) Install Docker + Compose (Ubuntu)
```bash
# Clean old packages (safe even if none)
sudo apt remove -y docker docker.io docker-doc docker-compose podman-docker containerd runc || true

# Keyring
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Repository (no edits needed on Ubuntu)
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable and allow docker without sudo
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

## 3) Update existing repo (directory already exists)
Use a GitHub Personal Access Token (PAT) with `repo` scope. Token is used temporarily and not saved.

```bash
# Optional: set Git identity (not required for pulls)
git config --global user.email "fedor.ivanov.agri.1985@gmail.com"
git config --global user.name "Fedor Ivanov"
read -s -p "GitHub Token: " GH_PAT; echo
#!# git clone https://$GH_PAT@github.com/1NT9NS9/news-ai.git news-ai
#!# cd news-ai
#!# git remote set-url origin https://github.com/1NT9NS9/news-ai.git
unset GH_PAT

```

## 4) Configure environment (no API secrets here)
```bash
cp -n .env.example .env  # keep existing if present
nano .env                 # fill TELEGRAM_BOT_API, GEMINI_API, ADMIN_CHAT_ID*, etc.
chmod 600 .env
```

## 5) Deploy with Docker Compose
```bash
chmod +x deploy.sh
./deploy.sh
```

Alternative:
```bash
docker compose up -d --build
```

## 6) Verify and test
```bash
docker compose ps
docker compose logs -f
```
Then open Telegram and send /start to your bot.

## 7) Updates
```bash
cd ~/news-ai
git pull
./deploy.sh   # or: docker compose up -d --build
```

## 8) Useful checks
```bash
docker compose logs -f
docker compose ps
docker run --rm hello-world
```
If network checks are needed from inside the container:
```bash
docker compose exec keytime-bot ping -c 3 api.telegram.org
```

## Notes
- Long polling: only outbound internet is needed; keep all inbound ports closed except SSH.
- Backups live under ./data/backups; download periodically for safekeeping.
