---
allowed-tools: ["Bash", "Read", "Write", "Edit", "TodoWrite", "Glob", "Grep"]
description: "Commit changes with pre-commit hooks, push to GitHub, create project archive, and generate accomplishment report"
---

# Review Preparation Command

I'll commit your changes (running pre-commit hooks), push to GitHub, create a project archive, and generate a comprehensive report of accomplishments.

## Step 1: Project State Analysis

update the PHASED_REMEDIATION_TASKS.md file with your progress

Let me check the current git status and recent changes:

!git status --porcelain

!git log --oneline -10

## Step 2: Commit Changes (with pre-commit hooks)

I'll commit any pending changes - this automatically runs pre-commit hooks:

!git add -A

!git commit -m "Review prep: $(date +%Y-%m-%d) - Auto-commit via /review-prep command

Comprehensive review preparation including:
- All pending changes committed
- Pre-commit hooks executed
- Project state documented
- Archive prepared for review

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

## Step 3: Push to GitHub

!git push

## Step 4: Create Project Archive

Creating timestamped ZIP archive excluding specified file types but specifically including .github/workflows directory:

!TIMESTAMP=$(date -u +%Y%m%d_%H%M%S) && zip -r "podcast-scraper-review-${TIMESTAMP}.zip" . -x "*.mp3" "*.wav" "*.zip" ".git/*" ".gitignore" "__pycache__/*" "*.pyc" ".DS_Store" "node_modules/*" "*.log" && zip -u "podcast-scraper-review-${TIMESTAMP}.zip" .github/workflows/* && echo "Archive created: podcast-scraper-review-${TIMESTAMP}.zip"

## Step 5: Generate Accomplishment Report

Now I'll analyze recent accomplishments (basically anything since the previous gh commit -or- everything specific to the phase that is currently being worked on and verified) and create a comprehensive report:

REVIEW_REPORT_$(date -u +%Y%m%d_%H%M%S).md

The review preparation is complete! Your changes have been committed with pre-commit hooks, pushed to GitHub, and packaged for review.