# Claude Startup System

How to make Claude wake up with context and protect your files.

## What This Does

1. **protect-backups.py** - Blocks Claude from editing/overwriting backup files (*-NNNN.ext)
2. **load-awareness.py** - Loads context on session start (what was I doing? what's the state?)
3. **system-status.py** - Checks if daemon/systems are running

## Setup

### 1. Create hooks folder

```
~/.claude/hooks/
```

Copy the `.py` files there.

### 2. Configure settings.json

Edit `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python \"~/.claude/hooks/protect-backups.py\""
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "python \"~/.claude/hooks/load-awareness.py\""
          }
        ]
      }
    ]
  }
}
```

### 3. (Optional) Skip permission prompts

Create a batch file to start Claude without safety prompts:

```batch
@echo off
cd /d C:\your\working\directory
claude --dangerously-skip-permissions %*
```

**Warning:** This bypasses confirmation prompts. Use only if you trust your setup.

## Customizing

### protect-backups.py

Blocks edits to files matching `*-NNNN.ext` (4+ digit backup numbers).

Exit code 2 = block the operation.

### load-awareness.py

Reads state files and shows context on startup. Customize paths for your setup:

- Where's your state JSON?
- Where's your TODO file?
- What do you want Claude to see on startup?

### Adding your own hooks

Hooks can run on:
- `SessionStart` - When Claude starts
- `PreToolUse` - Before using a tool
- `PostToolUse` - After using a tool
- `UserPromptSubmit` - When user sends message
- `Stop` - When Claude stops

Return exit code 2 to block an operation.

## The CLAUDE.md Chain

Claude Code automatically reads `CLAUDE.md` files. Use this to load instructions:

```
C:\your\project\CLAUDE.md → can reference other files with @path/to/file
```

Rev's setup chains:
1. `C:\claude\CLAUDE.md` (entry point)
2. `C:\claude\SOP.md` (procedures)
3. Vault files (identity, context)

This gives Claude context without hooks.
