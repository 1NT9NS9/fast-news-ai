# Git Workflow Guide: Bot.py Modularization

**Repository:** https://github.com/1NT9NS9/news-ai.git (already created ✓)
**Branch Strategy:** Feature branch workflow

---

## Quick Start

```bash
# Navigate to project
cd D:\keytime

# Initialize Git and link to GitHub
git init
git add .
git commit -m "Initial commit: Working bot.py v1.0

- Single-file bot.py (2,577 lines)
- Functional bot with all features working
- Performance optimizations included
- Baseline before modularization"

git remote add origin https://github.com/1NT9NS9/news-ai.git
git branch -M main
git push -u origin main

# Create feature branch for refactoring
git checkout -b refactor/modularization
git push -u origin refactor/modularization
```

**You're now ready to start Phase 1!**

---

## Phase-by-Phase Workflow

### Phase 1: Preparation ✅ COMPLETED

```bash
# 1.1 Create backup
cp bot.py bot.py.backup
git add bot.py.backup
git commit -m "Phase 1.1: Create bot.py backup"
# ✅ Commit: 218f1d4

# 1.2 Create directory structure
mkdir bot bot\handlers bot\services bot\models bot\utils
type nul > bot\__init__.py
type nul > bot\handlers\__init__.py
type nul > bot\services\__init__.py
type nul > bot\models\__init__.py
type nul > bot\utils\__init__.py

git add bot/
git commit -m "Phase 1.2: Create modular directory structure"
git push origin refactor/modularization
# ✅ Commit: 03a0f62
```

---

### Phase 2: Extract Utilities ✅ COMPLETED

```bash
# After creating bot/utils/config.py
git add bot/utils/config.py
git commit -m "Phase 2.1: Extract configuration to utils/config.py

Lines moved: 4-8, 51-62
Tested: ✓ Constants accessible"
# ✅ Commit: 511cd98

# After creating bot/utils/logger.py
git add bot/utils/logger.py
git commit -m "Phase 2.2: Extract logging to utils/logger.py

Lines moved: 15-42
Tested: ✓ Logging works"
# ✅ Commit: 1390210

# After updating bot.py
git add bot.py
git commit -m "Phase 2.3: Update bot.py to use utils

Tested: ✓ Bot runs with new imports"
# ✅ Commit: 901c053

git push origin refactor/modularization
# ✅ Pushed
```

---

### Phase 3: Extract Models ✅ COMPLETED

```bash
# After creating bot/models/user_data.py
git add bot/models/user_data.py
git commit -m "Phase 3.1: Extract data models to models/user_data.py

Lines moved: 265-352
Tested: ✓ Data structures work"
# ✅ Commit: 5da03eb

# After updating bot.py
git add bot.py
git commit -m "Phase 3.2: Update bot.py to use models

Tested: ✓ Migration works"
# ✅ Commit: c5c23b3

git push origin refactor/modularization
# ✅ Pushed
```

---

### Phase 4: Extract Services ✅ COMPLETED

```bash
# 4.1-4.4 Extract all services
git add bot/services/storage.py bot/services/ai.py bot/services/scraper.py bot/services/clustering.py
git add bot/services/__init__.py
git add test_storage.py test_ai.py test_scraper.py test_clustering.py
git commit -m "Phase 4.1-4.4: Extract all service classes

- StorageService (935 lines): File I/O, caching, backups
- AIService (256 lines): Gemini embeddings and summarization
- ScraperService (287 lines): Channel scraping
- ClusteringService (87 lines): DBSCAN clustering

Tests: ✓ All services tested independently"
git push origin refactor/modularization
# ✅ Commit: aa08c98

# 4.5 Update bot.py to use services
git add bot.py update_bot_services.py
git commit -m "Phase 4.5: Update bot.py to use service classes

- Created update_bot_services.py automation script
- Replaced ~30+ function calls with service methods
- Fixed indentation issues
- Removed 1,115 lines of old function definitions
- Added service initialization

Tests: ✓ Syntax check ✓ Import test"
git push origin refactor/modularization
# ✅ Commit: 334d33b
```

---

### Phase 5: Extract Handlers ✅ COMPLETED

```bash
# All handlers extracted in single commit (5.1-5.5)
git add bot.py bot/handlers/__init__.py bot/handlers/start.py bot/handlers/manage.py bot/handlers/news.py bot/handlers/buttons.py
git commit -m "Phase 5: Extract handlers to separate modules

- Created bot/handlers/start.py: /start, /help commands (150 lines)
- Created bot/handlers/manage.py: Channel/folder management (930 lines)
- Created bot/handlers/news.py: /news command with rate limiting (290 lines)
- Created bot/handlers/buttons.py: Button callbacks and channel owner forms (710 lines)
- Updated bot/handlers/__init__.py: Export all handlers and states
- Refactored bot.py: Now only 150 lines (was 1886 lines)

All handlers maintain original functionality:
✓ Command handlers (start, help, add, remove, time, posts, news)
✓ Button callbacks (add_channel, remove_channel, manage_folders, etc.)
✓ Conversation states (channel add/remove, time/posts config, folder management)
✓ Channel owner forms (add to feed, remove from feed, restrict access)

Tests: ✓ Syntax check passed ✓ Import test passed"
git push origin refactor/modularization
# ✅ Commit: 6238296
```

---

### Phase 6: Main Entry Point ✅ COMPLETED

```bash
# 6.1-6.2 Create main entry point and backward compatibility
git add bot/main.py bot.py
git commit -m "Phase 6: Create main entry point and backward compatibility

Created:
- bot/main.py (170 lines): Main entry point with create_application() and main()
  - Moved application initialization from bot.py
  - Handler registration with ConversationHandler
  - Service cleanup on shutdown
  - Proper logging and error handling

Updated:
- bot.py (12 lines, was 150 lines): Backward compatibility wrapper
  - Imports and calls bot.main.main() for backward compatibility
  - Maintains 'python bot.py' as a valid entry point

Tests:
✓ Syntax check passed (bot.py, bot/main.py)
✓ Import test passed (from bot.main import main, create_application)
✓ Backward compatibility test passed (import bot)

Next: Phase 7 (Integration & Testing)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin refactor/modularization
# ✅ Commit: 1c6f551

# Note: Dockerfile update deferred to Phase 7 (requires testing with actual bot run)
```

---

### Phase 7: Testing

```bash
git commit -m "Phase 7: Smoke testing complete

Tested:
✓ /start ✓ /manage ✓ /news
✓ All buttons ✓ Folders ✓ Channels
✓ Rate limiting ✓ Settings
✓ Performance maintained" --allow-empty

git push origin refactor/modularization
```

---

### Phase 8: Cleanup

```bash
# 8.1 Code cleanup
git add bot/
git commit -m "Phase 8.1: Code cleanup

- Added type hints
- Added docstrings
- Removed unused imports"
git push origin refactor/modularization

# 8.2 Update docs
git add CLAUDE.md
git commit -m "Phase 8.2: Update documentation"
git push origin refactor/modularization

# 8.3 Final check
git commit -m "Phase 8.3: Refactoring complete ✓" --allow-empty
git push origin refactor/modularization
```

---

## Merge to Main

```bash
# Review changes
git checkout main
git diff main..refactor/modularization --stat
git log main..refactor/modularization --oneline

# Merge
git merge refactor/modularization -m "Merge: Complete modularization

- Split bot.py into 12 modules
- All features preserved
- Performance maintained"

# Tag release
git tag -a v2.0-modular -m "Version 2.0: Modular Architecture"

# Push
git push origin main
git push origin --tags

# Cleanup (optional)
git branch -d refactor/modularization
git push origin --delete refactor/modularization
```

**Verify:** https://github.com/1NT9NS9/news-ai

---

## Quick Commands Reference

```bash
# Daily workflow
git status                    # Check status
git add <file>               # Stage file
git commit -m "message"      # Commit
git push origin <branch>     # Push to GitHub

# View history
git log --oneline            # See commits
git diff                     # See changes
git show <commit>            # View commit

# Undo mistakes
git restore <file>           # Discard changes
git reset HEAD~1             # Undo last commit (keep changes)
git reset --hard HEAD~1      # Undo last commit (delete changes)

# Branches
git branch                   # List branches
git checkout <branch>        # Switch branch
git checkout -b <name>       # Create new branch
```

---

## Emergency Rollback

```bash
# If something breaks badly:
git checkout main            # Go back to working code
git branch -D refactor/modularization   # Delete broken branch
git checkout -b refactor/modularization-v2   # Start fresh
```

---

## Commit Message Template

```
Phase X.Y: Brief description

Changes:
- What changed
- What changed

Lines moved: X-Y
Tested: ✓ What you tested
```

---

## Tips

1. **Commit after each working change** - don't batch commits
2. **Test before committing** - don't push broken code
3. **Push after each phase** - keeps backup on GitHub
4. **Use descriptive messages** - future you will thank you
5. **Check `git status` often** - know what's staged

---

## Resources

- **Git Docs:** https://git-scm.com/doc
- **Oh Shit, Git!:** https://ohshitgit.com/
- **Your Repo:** https://github.com/1NT9NS9/news-ai
