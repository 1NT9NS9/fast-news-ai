# DOMAIN.md

## Domain Model

This document describes the core domain model for the Telegram news aggregation bot.

## Overview

The system aggregates news from multiple Telegram channels, identifies duplicate stories using AI embeddings and clustering, and delivers consolidated summaries to users. Users organize channels into folders and configure preferences for time ranges and summary counts.

## Key Entities

### User
Represents a Telegram bot user with their preferences and subscriptions.

**Attributes:**
- `user_id` (string) - Telegram user identifier (primary key)
- `folders` (dict) - Named collections of channel subscriptions
- `active_folder` (string) - Currently selected folder for operations
- `time_limit` (integer) - Hours of history to scan (default: 24, max: 720)
- `max_posts` (integer) - Maximum summaries per request (default: 10, max: 30)
- `news_request_count` (integer) - Daily usage counter for rate limiting
- `last_news_date` (string, ISO date) - Last request date for rate limit reset

**Constraints:**
- Maximum 10 channels total across all folders
- Maximum 5 news requests per day (UTC)
- At least one folder must exist ("Папка1" is default)

### Folder
Named collection of channel subscriptions within a user's account.

**Attributes:**
- `name` (string) - Folder identifier (unique per user)
- `channels` (list of strings) - Telegram channel names starting with `@`

**Constraints:**
- Default folder "Папка1" cannot be deleted if it's the only folder
- Channel names must start with `@`
- Folders cannot share names within a user account

### Channel
Public Telegram channel that publishes news content.

**Attributes:**
- `name` (string) - Channel handle (e.g., `@channel_name`)

**Constraints:**
- Must be public (accessible via `https://t.me/s/{channel}`)
- Each channel can appear in multiple folders

### Post
Individual news item scraped from a channel.

**Attributes:**
- `text` (string) - Post content
- `timestamp` (datetime, UTC) - Publication time
- `channel` (string) - Source channel name
- `link` (string) - Telegram post URL

**Constraints:**
- Minimum length: 50 characters
- Must have valid timestamp (posts without timestamps are dropped)
- Only Telegram URLs (`t.me`) preserved in summaries

### Cluster
Group of similar posts identified by AI embeddings and DBSCAN algorithm.

**Attributes:**
- `posts` (list) - Posts with cosine similarity ≥ 0.9
- `size` (integer) - Number of posts in cluster
- `embedding` (vector) - Representative embedding for the cluster

**Behavior:**
- Clusters ranked by size (most covered stories first)
- Outliers (posts without matches) treated as single-post clusters

### Summary
AI-generated digest consolidating a cluster of similar posts.

**Attributes:**
- `text` (string) - Consolidated summary in Russian
- `source_posts` (list) - Original posts that were summarized
- `channel_names` (list) - Unique channels that covered the story

**Constraints:**
- Maximum 500 tokens per summary
- Generated using Gemini Flash Lite model
- Non-Telegram URLs removed from output

### ChannelFeed
Channel owner submission form (optional feature).

**Attributes:**
- `channel_name` (string) - Channel identifier
- `description` (string) - Owner-provided description
- `category` (string) - Content category
- `submission_timestamp` (datetime) - Form submission time

## Entity Relationships

```
User (1) ──< has >── (N) Folder
  │
  └─< subscribes to >── (N) Channel

Folder (1) ──< contains >── (N) Channel

Channel (1) ──< publishes >── (N) Post

Post (N) ──< belongs to >── (1) Cluster

Cluster (1) ──< generates >── (1) Summary
```

## Data Schema

### user_data.json
```json
{
  "<user_id>": {
    "folders": {
      "<folder_name>": ["@channel1", "@channel2"],
      "<folder_name2>": ["@channel3"]
    },
    "active_folder": "<folder_name>",
    "time_limit": 24,
    "max_posts": 10,
    "news_request_count": 3,
    "last_news_date": "2025-10-15"
  }
}
```

### channel_feed.json
```json
{
  "@channel_name": {
    "description": "Channel description",
    "category": "News category",
    "submitted_at": "2025-10-15T12:00:00Z"
  }
}
```

## Domain Operations

### Core Workflows

**News Aggregation (`/news` command):**
1. Rate limit check (5 requests/day per user)
2. Retrieve channels from active folder
3. Scrape posts (parallel, max 20 posts/channel)
4. Generate embeddings (batched, 100 at a time)
5. Cluster posts (DBSCAN, 0.9 similarity threshold)
6. Rank clusters by size
7. Generate summaries (parallel)
8. Deliver formatted summaries
9. Increment rate limit counter

**Channel Management:**
- Add/remove channels from folders (validation required)
- Create/delete folders (maintains "Папка1" invariant)
- Switch active folder for operations

**Settings Management:**
- Configure time_limit (1-720 hours)
- Configure max_posts (1-30 summaries)

**Rate Limiting:**
- Daily counter resets at UTC midnight
- Tracks date and count per user
- Enforces 5 requests/day limit

## Validation Rules

**User Data:**
- User ID must be string
- Folders must be dictionary of string→list mappings
- Active folder must exist in folders dictionary
- Channel names must start with `@`
- Time limit: 1 ≤ hours ≤ 720
- Max posts: 1 ≤ count ≤ 30
- News request date keys match `YYYY-MM-DD` format
- News request counts are non-negative integers

**Post Filtering:**
- Length ≥ 50 characters
- Valid UTC timestamp present
- Within user's configured time window

**Channel Validation:**
- Accessible via HTTPS at `https://t.me/s/{channel}`
- Returns valid HTML content

## Migration Path

The system supports backward compatibility from legacy schema:
- Legacy `channels` list → `folders.Папка1` array
- Missing `active_folder` → set to "Папка1"
- Preserves old structure for read-only access during transition
