# Keytime Bot

A Telegram bot for aggregating and summarizing news from multiple Telegram channels using Google Gemini AI.
[Bot](t.me/FAST_NEWS_Al_BOT)
<img width="412" height="589" alt="image" src="https://github.com/user-attachments/assets/11a00ed4-471f-4426-91e0-8c061914bde9" /> 
[Channel tg](https://t.me/FAST_NEWS_AI)
<img width="410" height="492" alt="image" src="https://github.com/user-attachments/assets/21e1640e-642b-465c-b656-0cff449d7435" />
[Channel youtube](https://www.youtube.com/@FAST_NEWS_Al)
<img width="1272" height="700" alt="image" src="https://github.com/user-attachments/assets/de0c2313-05c2-44d8-bbfb-0febf3ad4ddf" />




## Features

- Subscribe to multiple Telegram channels
- AI-powered news clustering and summarization
- Smart content deduplication using embeddings
- Customizable news digest schedules
- Admin controls for content moderation
- Automatic backups and data persistence
- Rate limiting for Telegram API compliance

## Quick Start

### Local Development

1. Clone the repository:
```bash
git clone <your-repo-url>
cd keytime
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Run the bot:
```bash
python bot.py
```

### VPS Deployment (Recommended for 24/7 Operation)

**Quick Deploy:**

1. Upload code to VPS
2. Copy `.env.example` to `.env` and configure
3. Run deployment script:
```bash
chmod +x deploy.sh
./deploy.sh
```

## Configuration

### Required Environment Variables

Create a `.env` file with the following:

```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_API=your_bot_token

# Google Gemini API Key
GEMINI_API=your_gemini_api_key

# Admin Chat IDs (from @userinfobot)
ADMIN_CHAT_ID=your_admin_chat_id
ADMIN_CHAT_ID_BACKUP=your_backup_chat_id
ADMIN_CHAT_ID_LOG=your_log_chat_id
```

See `.env.example` for all available configuration options.

## Bot Commands

### User Commands
- `/start` - Start the bot and see main menu
- `/help` - Show help information
- `/news` - Get latest news digest
- `/list` - List subscribed channels
- `/add` - Add a new channel
- `/remove` - Remove a channel
- `/time` - Set news digest interval
- `/posts` - Set number of posts to summarize

### Admin Commands
- `/restore_backup` - Restore from backup
- `/log` - View system logs and statistics

## Architecture

```
keytime/
├── bot/
│   ├── handlers/       # Telegram command and message handlers
│   ├── services/       # Business logic (AI, storage, scraping)
│   ├── models/         # Data models
│   └── utils/          # Configuration and logging
├── data/               # Persistent data (created on deployment)
├── logs/               # Application logs (created on deployment)
├── bot.py             # Entry point
├── Dockerfile         # Docker configuration
├── docker-compose.yml # Docker Compose orchestration
└── deploy.sh          # Deployment script
```

## Development

### Running Tests

```bash
pytest
```

### Project Structure

- **handlers/** - Telegram bot command handlers and conversation flows
- **services/** - Core business logic
  - `ai.py` - Gemini AI integration for summaries and embeddings
  - `clustering.py` - News deduplication and clustering
  - `storage.py` - Data persistence and backups
  - `scraper.py` - Telegram channel scraping
  - `messenger.py` - Message sending with rate limiting
- **models/** - Data structures and validation
- **utils/** - Configuration, logging, validators

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot 21.6** - Telegram Bot API
- **Google Gemini AI** - Text generation and embeddings
- **Docker** - Containerization
- **aiofiles** - Async file I/O
- **httpx** - Modern async HTTP client
- **scikit-learn** - Cosine similarity calculations

## Data Persistence

The bot stores data in JSON files inside the `data/` directory (override via `DATA_DIR` env var if needed):

- `data/user_data.json` - User subscriptions and settings
- `data/user_channel.json` - Channel feed metadata
- `data/user_subs.json` - Subscription plans
- `backups/` - Automatic backups (max 20, 7-day retention)

In Docker deployment, these are stored in the `data/` directory with volume mounts for persistence.

## Security

- API credentials stored in `.env` (never committed)
- Automatic security updates on VPS
- Rate limiting to prevent API abuse
- Admin-only commands with chat ID verification
- Firewall configuration for VPS deployment

## Monitoring

### Docker Logs
```bash
docker compose logs -f
```

### System Resources
```bash
docker stats keytime-bot
```

### Bot Statistics
Use the `/log` command in your admin Telegram chat.

# ⭐️Important
bot/services folder is empty!
I removed the code from this folder. Message me on Telegram if you need it.

