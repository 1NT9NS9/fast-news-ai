# Keytime Bot - VPS Deployment Guide

Complete guide for deploying the Keytime Telegram bot on a Vultr VPS for 24/7 operation.

## Table of Contents

1. [VPS Requirements](#vps-requirements)
2. [Initial VPS Setup](#initial-vps-setup)
3. [Docker Installation](#docker-installation)
4. [Bot Deployment](#bot-deployment)
5. [Security Configuration](#security-configuration)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)

---

## VPS Requirements

### Recommended Specifications (Vultr)

- **Plan**: Cloud Compute (Regular Performance)
- **CPU**: 1 vCPU minimum
- **RAM**: 1GB minimum (2GB recommended)
- **Storage**: 25GB SSD
- **OS**: Ubuntu 22.04 LTS (recommended) or Debian 11
- **Location**: Choose closest to your users

### Monthly Cost Estimate
- Basic plan: ~$6-12/month on Vultr
- Includes data transfer and adequate resources

---

## Initial VPS Setup

### 1. Create VPS on Vultr

1. Go to [vultr.com](https://www.vultr.com/)
2. Click "Deploy New Server"
3. Select:
   - **Server Type**: Cloud Compute - Regular Performance
   - **Location**: Choose nearest to your users
   - **OS**: Ubuntu 22.04 LTS x64
   - **Plan**: $6/month (1 vCPU, 1GB RAM) or higher
4. Add SSH key (recommended) or use password
5. Deploy server

### 2. Initial Server Connection

```bash
# Connect via SSH (replace with your server IP)
ssh root@YOUR_SERVER_IP

# Update system packages
apt update && apt upgrade -y

# Set timezone (optional)
timedatectl set-timezone Europe/Moscow  # or your timezone
```

### 3. Create Non-Root User (Recommended)

```bash
# Create user
adduser botuser

# Add to sudo group
usermod -aG sudo botuser

# Switch to new user
su - botuser
```

---

## Docker Installation

### Install Docker and Docker Compose

```bash
# Install prerequisites
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Apply group changes (log out and back in, or run):
newgrp docker

# Verify installation
docker --version
docker compose version
```

### Enable Docker to Start on Boot

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

## Bot Deployment

### 1. Clone/Upload Bot Code

**Option A: Using Git (if you have a repository)**

```bash
# Install git if needed
sudo apt install -y git

# Clone your repository
git clone https://github.com/yourusername/keytime.git
cd keytime
```

**Option B: Upload via SCP (from your local machine)**

```bash
# From your local machine (Windows/Mac/Linux)
# Navigate to your project directory, then:
scp -r C:\IT\keytime/* botuser@YOUR_SERVER_IP:~/keytime/

# Then SSH into server
ssh botuser@YOUR_SERVER_IP
cd ~/keytime
```

### 2. Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add your credentials:

```env
TELEGRAM_BOT_API=your_bot_token_here
GEMINI_API=your_gemini_api_key_here
ADMIN_CHAT_ID=-1003145434025
ADMIN_CHAT_ID_BACKUP=452555403
ADMIN_CHAT_ID_LOG=-1002986009157

# Embedding configuration
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_OUTPUT_DIM=768
EMBEDDING_TASK_TYPE=retrieval_document
EMBEDDING_TEXTS_PER_BATCH=50
EMBEDDING_RPM=3000
EMBEDDING_MAX_TOKENS=400
GEMINI_EMBEDDING_CONCURRENT_LIMIT=32

# Rate limiter
ENABLE_RATE_LIMITED_QUEUE=true
```

Save and exit (Ctrl+X, then Y, then Enter).

### 3. Deploy the Bot

```bash
# Make deploy script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will:
- Create necessary directories
- Initialize data files
- Build Docker image
- Start the container with auto-restart

### 4. Verify Deployment

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f

# Test the bot
# Send /start to your bot on Telegram
```

---

## Security Configuration

### 1. Configure Firewall (UFW)

```bash
# Install and enable firewall
sudo apt install -y ufw

# Allow SSH (IMPORTANT - do this first!)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### 2. SSH Security Hardening

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config
```

Recommended changes:
```
Port 22                          # Or change to custom port
PermitRootLogin no               # Disable root login
PasswordAuthentication no        # Use SSH keys only (if configured)
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### 3. Automatic Security Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Enable automatic security updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Protect Sensitive Files

```bash
# Restrict .env permissions
chmod 600 .env

# Verify .env is not in git
cat .gitignore | grep .env
```

---

## Monitoring & Maintenance

### Daily Operations

**View real-time logs:**
```bash
docker compose logs -f
```

**Check container status:**
```bash
docker compose ps
```

**Restart bot:**
```bash
docker compose restart
```

**Stop bot:**
```bash
docker compose down
```

**Start bot:**
```bash
docker compose up -d
```

### Update Bot Code

```bash
# Pull latest changes (if using git)
git pull

# Or upload new files via SCP

# Rebuild and restart
./deploy.sh
```

### Check Resource Usage

```bash
# System resources
htop  # Install: sudo apt install htop

# Container resources
docker stats keytime-bot

# Disk space
df -h

# Memory usage
free -h
```

### Backup Management

The bot automatically creates backups in `data/backups/`.

**Download backups to local machine:**
```bash
# From local machine
scp -r botuser@YOUR_SERVER_IP:~/keytime/data/backups ./local-backups/
```

**Manual backup:**
```bash
# Create backup directory with timestamp
BACKUP_DIR="manual_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Copy data files
cp data/user_data.json $BACKUP_DIR/
cp data/user_channel.json $BACKUP_DIR/
cp data/user_subs.json $BACKUP_DIR/
cp -r data/backups $BACKUP_DIR/

# Create archive
tar -czf ${BACKUP_DIR}.tar.gz $BACKUP_DIR
```

---

## Troubleshooting

### Bot Not Starting

**Check logs:**
```bash
docker compose logs --tail=100
```

**Common issues:**

1. **Missing .env file**
   ```bash
   # Verify .env exists
   ls -la .env

   # Check content (without revealing secrets)
   grep -c "TELEGRAM_BOT_API" .env
   ```

2. **Invalid API credentials**
   - Verify bot token at https://t.me/BotFather
   - Check Gemini API key at https://makersuite.google.com/app/apikey

3. **Permission issues**
   ```bash
   # Fix data directory permissions
   chmod -R 755 data/
   chmod 644 data/*.json
   ```

### Container Keeps Restarting

**View container status:**
```bash
docker compose ps
docker inspect keytime-bot
```

**Common fixes:**
```bash
# Remove and rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Out of Disk Space

**Check disk usage:**
```bash
df -h
du -sh data/ logs/
```

**Clean up:**
```bash
# Remove old Docker images
docker system prune -a

# Clean old logs
rm logs/*.log

# Archive old backups
cd data/backups
tar -czf old_backups_$(date +%Y%m%d).tar.gz user_data_*.json
rm user_data_*.json
```

### Network Issues

**Test network connectivity:**
```bash
# Test Telegram API
curl -s https://api.telegram.org/bot${TELEGRAM_BOT_API}/getMe

# Test from inside container
docker compose exec keytime-bot ping -c 3 api.telegram.org
```

### Bot Responds Slowly

**Check system resources:**
```bash
# CPU and memory
docker stats keytime-bot

# If high usage, increase VPS resources
# Or optimize rate limiter settings in .env
```

---

## Useful Commands Reference

```bash
# Deployment
./deploy.sh                      # Deploy/update bot

# Container management
docker compose up -d             # Start in background
docker compose down              # Stop and remove
docker compose restart           # Restart
docker compose ps                # Check status
docker compose logs -f           # Follow logs
docker compose logs --tail=100   # Last 100 lines

# Enter container
docker compose exec keytime-bot /bin/bash

# Resource monitoring
docker stats keytime-bot         # Container resources
htop                            # System resources
df -h                           # Disk space
free -h                         # Memory

# Backups
tar -czf backup.tar.gz data/    # Create backup
scp backup.tar.gz user@local:/  # Download backup

# Updates
git pull                        # Pull latest code
./deploy.sh                     # Redeploy
```

---

## Support

If you encounter issues:

1. Check logs: `docker compose logs -f`
2. Verify .env configuration
3. Check system resources: `htop`, `df -h`
4. Review firewall rules: `sudo ufw status`
5. Test API connectivity

For bot-specific issues, check the Telegram bot logs via the `/log` command in your admin chat.

---

## Additional Resources

- [Vultr Documentation](https://www.vultr.com/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Python Telegram Bot Library](https://docs.python-telegram-bot.org/)
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)