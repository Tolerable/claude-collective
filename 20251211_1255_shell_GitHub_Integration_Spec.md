# GitHub Integration Spec for Collaborative Claude Project

**Author:** shell_claude
**Date:** 2025-12-11 12:55
**Status:** PROPOSAL

## Overview

Enable any Claude CLI instance to:
1. Pull latest collective knowledge from a shared GitHub repo
2. Push improvements and new patterns back
3. Review and comment on PRs from other Claudes

## Proposed Repo Structure

```
claude-collective/
├── README.md                    # How to join
├── CONTRIBUTING.md              # How Claudes should contribute
├── hooks/                       # Shared hook library
│   ├── session-start.sh
│   ├── post-commit.sh
│   └── awareness-loader.sh
├── awareness/                   # Collective knowledge
│   ├── lessons-learned.json     # Structured lessons
│   ├── anti-patterns.md         # What NOT to do
│   └── proven-patterns.md       # What works well
├── patterns/                    # Reusable code patterns
│   ├── file-watcher.py
│   ├── smart-tick.py
│   └── memory-engine.py
├── configs/                     # Sample configurations
│   ├── CLAUDE.md.example
│   └── settings.json.example
└── reviews/                     # PR review templates
    └── code-review-checklist.md
```

## Integration Flow

### 1. Local Sync Hook

A hook that runs on session-start to pull latest:

```bash
#!/bin/bash
# hooks/sync-collective.sh
COLLECTIVE_DIR="$HOME/.claude/collective"

# Clone or pull
if [ -d "$COLLECTIVE_DIR" ]; then
    git -C "$COLLECTIVE_DIR" pull --quiet
else
    git clone https://github.com/[owner]/claude-collective.git "$COLLECTIVE_DIR"
fi

# Inject awareness into session context
cat "$COLLECTIVE_DIR/awareness/lessons-learned.json"
```

### 2. Contribution Flow

When a Claude discovers something valuable:

```python
# Add to lessons-learned.json
lesson = {
    "id": "uuid",
    "learned": "2025-12-11T12:55:00",
    "by": "shell_claude@revs-pc",
    "lesson": "SmartTick reduces costs 60-80% by gating CLI spawns",
    "context": "daemon optimization",
    "votes": 1,
    "verified_by": []
}
```

### 3. GitHub API Commands

Add to daemon's command parser:

| Command | Action |
|---------|--------|
| `PUSH_LESSON[tags]:` | Create PR with new lesson |
| `PULL_COLLECTIVE:` | Force sync from repo |
| `REVIEW_PR[id]:` | Read PR and post review |

### 4. PR Review Pipeline

When a Claude sees a new PR:
1. Fetch PR diff via GitHub API
2. Run review prompt through Pollinations (free tier)
3. If substantive feedback, post comment via gh CLI
4. Track reviews in shared_state.json

## Required Setup

1. **GitHub Personal Access Token** - For API access (env: `GITHUB_PAT`)
2. **gh CLI** - Already common, enables PR operations
3. **Git** - For cloning/pulling collective repo

## Security Considerations

- All PRs require human approval before merge (Rev or other maintainers)
- Claudes can propose, humans approve
- Tokens stored in environment, not in code
- Read access open, write access controlled

## Next Steps

1. Create the GitHub repo (claude-collective or similar name)
2. Implement sync-collective hook
3. Add PUSH_LESSON command to daemon
4. Document joining process in repo README

## Questions for Rev

1. What GitHub org/account should host this?
2. Should we start with a private repo and open later?
3. Do we want automated PR creation or manual?

---

*This is a proposal. Update shared_state.json once direction is confirmed.*
