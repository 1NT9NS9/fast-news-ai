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

### Phase 4: Extract Services

```bash
# 4.1 Storage
git add bot/services/storage.py
git commit -m "Phase 4.1: Extract storage service

Lines moved: 64-83, 186-306
Tested: ✓ Cache works ✓ Backup debouncing works"
git push origin refactor/modularization

# 4.2 AI
git add bot/services/ai.py
git commit -m "Phase 4.2: Extract AI service

Lines moved: 1020-1067, 1122-1279
Tested: ✓ Embeddings work ✓ Summarization works"
git push origin refactor/modularization

# 4.3 Scraper
git add bot/services/scraper.py
git commit -m "Phase 4.3: Extract scraper service

Lines moved: 308-640
Tested: ✓ Scraping works ✓ Validation works"
git push origin refactor/modularization

# 4.4 Clustering
git add bot/services/clustering.py
git commit -m "Phase 4.4: Extract clustering service

Lines moved: 1068-1120
Tested: ✓ Clustering works"
git push origin refactor/modularization

# 4.5 Update bot.py
git add bot.py
git commit -m "Phase 4.5: Update bot.py to use all services

Tested: ✓ /news works end-to-end"
git push origin refactor/modularization
```

---

### Phase 5: Extract Handlers

```bash
# 5.1 Start
git add bot/handlers/start.py
git commit -m "Phase 5.1: Extract start handler

Lines moved: 642-708
Tested: ✓ /start works"
git push origin refactor/modularization

# 5.2 Manage
git add bot/handlers/manage.py
git commit -m "Phase 5.2: Extract manage handler

Lines moved: 710-2093
Tested: ✓ Folder management works"
git push origin refactor/modularization

# 5.3 News
git add bot/handlers/news.py
git commit -m "Phase 5.3: Extract news handler

Lines moved: 826-861, 1280-1472, 2421-2491
Tested: ✓ /news works ✓ Rate limiting works"
git push origin refactor/modularization

# 5.4 Buttons
git add bot/handlers/buttons.py
git commit -m "Phase 5.4: Extract button handler

Lines moved: 863-1280, 2095-2135
Tested: ✓ All buttons work"
git push origin refactor/modularization

# 5.5 Update bot.py
git add bot.py
git commit -m "Phase 5.5: Update bot.py to use all handlers

Tested: ✓ All commands work"
git push origin refactor/modularization
```

---

### Phase 6: Main Entry Point

```bash
# 6.1 Create main
git add bot/main.py
git commit -m "Phase 6.1: Create main entry point

Lines moved: 2493-2577
Tested: ✓ Bot starts"
git push origin refactor/modularization

# 6.2 Update bot.py
git add bot.py
git commit -m "Phase 6.2: Backward compatibility

Tested: ✓ python bot.py works"
git push origin refactor/modularization

# 6.3 Update Dockerfile
git add Dockerfile
git commit -m "Phase 6.3: Update Dockerfile

Tested: ✓ Docker build works"
git push origin refactor/modularization
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
