# Claude's Obsidian Vault

This is a template for giving Claude persistent long-term memory using Obsidian.

## What is Obsidian?

[Obsidian](https://obsidian.md) is a markdown-based knowledge management app. It's:
- Local files (no cloud lock-in)
- Markdown (Claude can read/write it)
- Link-based (`[[note]]` connects ideas)
- Free

## Why Use It?

Claude forgets between sessions. An Obsidian vault gives Claude:
- **Identity** - Who am I? What do I value?
- **Context** - What was I working on? What did we decide?
- **Memory** - Lessons learned, things to remember
- **Navigation** - Links between concepts

## Setup

1. Install Obsidian: https://obsidian.md/download
2. Create a vault folder:
   - **Windows:** `%USERPROFILE%\.claude\vault\`
   - **Mac/Linux:** `~/.claude/vault/`
3. Copy these template files into it
4. Point your startup hooks to read from the vault
5. Open the folder as a vault in Obsidian

## Vault Structure

```
vault/
├── START HERE.md       # Entry point - Claude reads this first
├── About Me.md         # Claude's identity
├── About [User].md     # Who the user is
├── INBOX/              # Unprocessed notes (workers dump here)
│   └── README.md
├── Session Notes/      # What we did each session
├── Projects/           # Project-specific notes
└── Knowledge/          # Long-term reference
```

## Key Concepts

### 1. START HERE.md
The entry point. Lists what to read on startup and links to everything else.

### 2. Identity Files
`About Me.md` - Claude's personality, values, what it struggles with.
These persist across sessions so Claude wakes up knowing who it is.

### 3. [[Links]]
Use `[[Note Name]]` to link between notes. Claude should follow links, not grep.

### 4. INBOX Pattern
Workers/daemons dump notes to INBOX. Claude processes them into proper notes.

### 5. Session Notes
After each session, Claude can write what happened. Next session, it reads recent ones.

## Hooking It Up

In your startup hook, read the vault:

```python
# In load-awareness.py or similar
VAULT = Path("~/.claude/vault")
START_HERE = VAULT / "START HERE.md"

# Output contents on session start
print(START_HERE.read_text())
```

Or use CLAUDE.md to reference vault files:
```
@~/.claude/vault/START HERE.md
@~/.claude/vault/About Me.md
```
