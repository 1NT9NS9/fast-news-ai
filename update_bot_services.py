# -*- coding: utf-8 -*-
"""
Script to update bot.py to use service classes instead of global functions.
This performs systematic replacements of function calls throughout the file.
"""

import re

# Read the current bot.py
with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

original_length = len(content)

# ============================================================================
# Step 1: Remove old function definitions that are now in services
# ============================================================================

# Find and remove storage functions (lines 68-616)
# Remove from _cleanup_old_backups() to just before create_persistent_keyboard()
pattern_storage_funcs = r'def _cleanup_old_backups\(\):.*?(?=def create_persistent_keyboard\(\):)'
content = re.sub(pattern_storage_funcs, '', content, flags=re.DOTALL)

# Find and remove scraper functions
pattern_scraper_funcs = r'def parse_subscriber_count\(text: str\).*?(?=async def get_embeddings\(texts: list\))'
content = re.sub(pattern_scraper_funcs, '', content, flags=re.DOTALL)

# Find and remove AI and clustering functions
pattern_ai_clustering = r'async def get_embeddings\(texts: list\).*?(?=async def button_callback\(update: Update)'
content = re.sub(pattern_ai_clustering, '', content, flags=re.DOTALL)

# ============================================================================
# Step 2: Replace function calls with service method calls
# ============================================================================

# Storage service replacements
replacements = [
    # Core storage operations
    (r'\bload_user_data\(\)', 'storage.load_user_data()'),
    (r'\bsave_user_data\(', 'storage.save_user_data('),
    (r'\bbackup_user_data\(\)', 'storage.backup_user_data()'),
    (r'\blist_user_data_backups\(\)', 'storage.list_user_data_backups()'),
    (r'\brestore_user_data_from_backup\(', 'storage.restore_user_data_from_backup('),

    # Channel operations
    (r'\bget_user_channels\(', 'storage.get_user_channels('),
    (r'\bset_user_channels\(', 'storage.set_user_channels('),
    (r'\bget_all_user_channels\(', 'storage.get_all_user_channels('),
    (r'\bget_active_folder_name\(', 'storage.get_active_folder_name('),

    # Settings operations
    (r'\bget_user_time_limit\(', 'storage.get_user_time_limit('),
    (r'\bset_user_time_limit\(', 'storage.set_user_time_limit('),
    (r'\bget_user_max_posts\(', 'storage.get_user_max_posts('),
    (r'\bset_user_max_posts\(', 'storage.set_user_max_posts('),

    # Folder operations
    (r'\bget_user_folders\(', 'storage.get_user_folders('),
    (r'\bcreate_folder\(', 'storage.create_folder('),
    (r'\bdelete_folder\(', 'storage.delete_folder('),
    (r'\bswitch_active_folder\(', 'storage.switch_active_folder('),

    # Rate limiting
    (r'\bcheck_news_rate_limit\(', 'storage.check_news_rate_limit('),
    (r'\bincrement_news_request\(', 'storage.increment_news_request('),

    # Channel feed operations
    (r'\bload_channel_feed\(\)', 'storage.load_channel_feed()'),
    (r'\bsave_channel_feed\(', 'storage.save_channel_feed('),
    (r'\bcheck_channel_in_feed\(', 'storage.check_channel_in_feed('),

    # Scraper service replacements
    (r'\bscrape_channel\(', 'scraper.scrape_channel('),
    (r'\bvalidate_channel_access\(', 'scraper.validate_channel_access('),
    (r'\bparse_subscriber_count\(', 'scraper.parse_subscriber_count('),
    (r'\bget_http_client\(\)', 'scraper.get_http_client()'),
    (r'\bclose_http_client\(', 'scraper.close_http_client('),

    # AI service replacements
    (r'\bget_embeddings\(', 'ai_service.get_embeddings('),
    (r'\bsummarize_cluster\(', 'ai_service.summarize_cluster('),
    (r'\bget_gemini_model\(\)', 'ai_service.get_gemini_model()'),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# ============================================================================
# Step 3: Special case - cluster_posts() needs to be split into two calls
# ============================================================================

# Find all calls to cluster_posts and replace with combined embeddings + clustering
# Pattern: clusters = await cluster_posts(posts)
# Replace with:
#   texts = [post['text'] for post in posts]
#   embeddings = await ai_service.get_embeddings(texts)
#   clusters = clustering.cluster_posts(embeddings, posts)

cluster_pattern = r'clusters = await cluster_posts\((\w+)\)'
cluster_replacement = r'''texts = [post['text'] for post in \1]
    embeddings = await ai_service.get_embeddings(texts)
    clusters = clustering.cluster_posts(embeddings, \1)'''
content = re.sub(cluster_pattern, cluster_replacement, content)

# ============================================================================
# Step 4: Remove unused imports
# ============================================================================

# Remove imports that are now only used in services
# (Keep them for now to avoid breaking anything - can clean up later)

# ============================================================================
# Save the updated file
# ============================================================================

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

new_length = len(content)
removed_chars = original_length - new_length

print(f"✓ bot.py updated successfully!")
print(f"  Original: {original_length:,} characters")
print(f"  New: {new_length:,} characters")
print(f"  Removed: {removed_chars:,} characters ({removed_chars/original_length*100:.1f}%)")
print(f"\nNext steps:")
print(f"  1. Test syntax: python -m py_compile bot.py")
print(f"  2. Test imports: python -c 'import bot'")
print(f"  3. Review changes: git diff bot.py")
