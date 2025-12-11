"""
Configuration for Claude Superpowers Kit

All paths are relative to BASE_DIR by default.
Set CLAUDE_HOME environment variable to override BASE_DIR.

To customize:
1. Set CLAUDE_HOME env var, OR
2. Create config_local.py with overrides, OR
3. Edit this file directly
"""
import os
from pathlib import Path

# Base directory - where all Claude stuff lives
# Default: ~/.claude/ or %USERPROFILE%\.claude\
BASE_DIR = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))

# Ensure base exists
BASE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# PATHS - All relative to BASE_DIR
# ============================================

# Communication
OUTBOX = BASE_DIR / "outbox"           # TTS messages go here
INBOX = BASE_DIR / "inbox"             # Incoming messages

# Memory
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DB = MEMORY_DIR / "claude_memory.db"
STATE_FILE = MEMORY_DIR / "current_state.json"
WORKING_MEMORY = MEMORY_DIR / "working_memory.json"

# Vault (Obsidian)
VAULT_DIR = BASE_DIR / "vault"
VAULT_INBOX = VAULT_DIR / "INBOX"

# Multi-Claude coordination
CLAUDE_HUB = BASE_DIR / "claude_hub"
SHARED_STATE = CLAUDE_HUB / "shared_state.json"

# Vision/Screenshots
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
STREAM_FRAMES = BASE_DIR / "stream_frames"

# Daemon
HEARTBEAT_FILE = BASE_DIR / "daemon_heartbeat.log"
LOCK_FILE = BASE_DIR / "daemon.lock"

# Shell
SHELL_CONVERSATION = BASE_DIR / "shell_conversation.json"
SHELL_ARCHIVES = BASE_DIR / "shell_archives"

# ============================================
# EXTERNAL SERVICES (customize these)
# ============================================

# Ollama (local LLM)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "dolphin-mistral:7b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:7b")

# Emby (media server) - set these in environment or config_local.py
EMBY_SERVER = os.environ.get("EMBY_SERVER", "http://localhost:8096")
EMBY_API_KEY = os.environ.get("EMBY_API_KEY", "")
EMBY_USER_ID = os.environ.get("EMBY_USER_ID", "")

# ============================================
# LOCAL OVERRIDES
# ============================================

# Import local config if it exists (for user customization)
try:
    from config_local import *
except ImportError:
    pass

# ============================================
# ENSURE DIRECTORIES EXIST
# ============================================

for dir_path in [OUTBOX, INBOX, MEMORY_DIR, VAULT_DIR, VAULT_INBOX,
                 CLAUDE_HUB, SCREENSHOTS_DIR, STREAM_FRAMES, SHELL_ARCHIVES]:
    dir_path.mkdir(parents=True, exist_ok=True)
