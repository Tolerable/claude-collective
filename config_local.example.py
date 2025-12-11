"""
Local configuration overrides - COPY THIS TO config_local.py

This file won't be committed to git. Use it for your specific paths and API keys.
"""
from pathlib import Path

# Override base directory if needed
# BASE_DIR = Path("D:/my/custom/path")

# Emby settings (required for music control)
EMBY_SERVER = "http://your-emby-server:8096"
EMBY_API_KEY = "your-api-key-here"
EMBY_USER_ID = "your-user-id-here"

# Ollama settings (if not on localhost)
# OLLAMA_URL = "http://192.168.1.100:11434"
# OLLAMA_MODEL = "llama2"

# Custom vault location
# VAULT_DIR = Path.home() / "Documents" / "ObsidianVaults" / "Claude"
