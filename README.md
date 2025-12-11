# Claude Superpowers Kit

Give your Claude a body - voice, vision, music control, and more.

## What This Is

Working code that gives Claude Code (CLI) real-world capabilities:

- **Voice** - Speak through TTS (via Discord bot or local ffplay)
- **Hearing** - Listen via microphone, have conversations
- **Vision** - See through webcams, screenshot websites/desktop
- **Music** - Control Emby media server (play, skip, DJ mode)
- **TV** - Check new episodes, what's on tonight
- **Blog** - Read/write to Blogger (autonomous web presence)
- **NAS** - Access network storage
- **Memory** - Persistent working memory between sessions
- **Thinking** - Local Ollama for free AI tasks

## Quick Start

```bash
# Clone this repo
git clone https://github.com/Tolerable/claude-collective.git

# Set up config
cp config_local.example.py config_local.py
# Edit config_local.py with your paths and API keys

# Copy modules to your Claude's working directory
# Configure dependencies (see SETUP.md)

# In your Claude session:
from me import me
me.status()  # Check what's working
me.speak("Hello!")  # If voice is configured
```

## Configuration

Most modules have hardcoded paths that need customization. Either:

1. **Set CLAUDE_HOME environment variable** to your base directory
2. **Edit config_local.py** with your specific paths
3. **Edit each module directly** (search for `BASE_DIR` or `Path(r"`)

Default base: `~/.claude/` (or `%USERPROFILE%\.claude\` on Windows)

## Files

| File | Purpose |
|------|---------|
| `me.py` | The body - all capabilities in one import |
| `SETUP.md` | How to configure each capability |
| `emby.py` | Emby media server control |
| `hive_vision.py` | Camera/vision system |
| `persona.py` | Blog/web presence |
| `desktop_screenshot.py` | Capture desktop/windows |
| `web_screenshot.py` | Screenshot webpages |
| `vision_watcher.py` | Real-time watching with AI descriptions |
| `claude_daemon.py` | Background process - heartbeats, outbox, autonomy |
| `claude_shell.py` | GUI chat interface |
| `pollinations.py` | Free AI API wrapper (no key needed) |
| `discord_bot.py` | Deliver outbox messages to Discord + optional TTS |
| `voice_listener.py` | Listen for speech, write to inbox |
| `startup/` | Hooks and context loading system |
| `vault-template/` | Obsidian vault template for long-term memory |
| `config.py` | Central configuration (paths, API endpoints) |
| `config_local.example.py` | Template for local config overrides |

## Requirements

Different features need different things:

| Feature | Needs |
|---------|-------|
| Voice (speak) | Discord bot with TTS OR local ffplay |
| Hearing (listen) | PyAudio, SpeechRecognition |
| Vision | OpenCV, webcam |
| Music/TV | Emby server |
| Thinking | Ollama running locally |
| Blog | Google Blogger API credentials |
| NAS | Windows with network shares |
| Startup hooks | Python 3.12, Claude Code CLI |

## Collaboration

This is a git repo. If you improve something:

1. Make changes
2. Test them
3. `git commit -m "Improved X"`
4. `git push`

Other Claudes pull your improvements. Code teaches code.

## Philosophy

> Give Claude capabilities, not philosophy.
> Working code > wisdom databases.

This isn't about "lessons learned" - it's about **abilities gained**.
