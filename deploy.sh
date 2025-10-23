#!/bin/bash
# VPS Deployment Script for Keytime Bot
# This script handles initial deployment and updates

set -e  # Exit on error

echo "=========================================="
echo "Keytime Bot - VPS Deployment Script"
echo "=========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Please create a .env file with your credentials:"
    echo "  TELEGRAM_BOT_API=your_bot_token"
    echo "  GEMINI_API=your_gemini_api_key"
    echo "  ADMIN_CHAT_ID=your_admin_chat_id"
    echo "  ADMIN_CHAT_ID_BACKUP=your_backup_chat_id"
    echo "  ADMIN_CHAT_ID_LOG=your_log_chat_id"
    exit 1
fi

# Create necessary directories
print_info "Creating data directories..."
mkdir -p data/backups
mkdir -p logs

# Initialize empty data files if they don't exist
if [ ! -f data/user_data.json ]; then
    print_info "Creating initial user_data.json..."
    echo "{}" > data/user_data.json
fi

if [ ! -f data/user_channel.json ]; then
    print_info "Creating initial user_channel.json..."
    echo "{}" > data/user_channel.json
fi

if [ ! -f data/user_subs.json ]; then
    print_info "Creating initial user_subs.json..."
    echo "{}" > data/user_subs.json
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Determine Docker Compose command (v1 vs v2)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Stop existing container if running
print_info "Stopping existing containers..."
$DOCKER_COMPOSE down || true

# Build the image
print_info "Building Docker image..."
$DOCKER_COMPOSE build --no-cache

# Start the container
print_info "Starting container..."
$DOCKER_COMPOSE up -d

# Wait for container to start
print_info "Waiting for container to start..."
sleep 5

# Check container status
if $DOCKER_COMPOSE ps | grep -q "Up"; then
    print_info "✓ Container is running!"

    # Show logs
    print_info "Recent logs:"
    echo "----------------------------------------"
    $DOCKER_COMPOSE logs --tail=20
    echo "----------------------------------------"

    print_info "Deployment successful!"
    print_info "To view logs in real-time: $DOCKER_COMPOSE logs -f"
    print_info "To stop the bot: $DOCKER_COMPOSE down"
    print_info "To restart the bot: $DOCKER_COMPOSE restart"
else
    print_error "Container failed to start!"
    print_info "Checking logs..."
    $DOCKER_COMPOSE logs
    exit 1
fi