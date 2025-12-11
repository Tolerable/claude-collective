# Setup Guide

How to give your Claude each capability.

---

## Voice (Speaking)

**What it does:** `me.speak("Hello")` speaks through speakers.

**How it works:** Writes JSON to an `outbox/` folder. A Discord bot (OLLAMABOT) or daemon watches the folder and plays TTS.

**Setup:**

1. Create `outbox/` folder in your Claude's working directory
2. Run a watcher that processes `outbox/*.json` files:
   - Each file: `{"message": "text", "voice": "Gloop", "play_local": true}`
   - Use edge-tts, pyttsx3, or other TTS to speak
   - Delete file after processing

**Minimal watcher example:**
```python
import json, time
from pathlib import Path
import subprocess

OUTBOX = Path("outbox")
while True:
    for f in OUTBOX.glob("*.json"):
        msg = json.loads(f.read_text())
        # Use edge-tts (free, good voices)
        subprocess.run(["edge-tts", "--voice", "en-US-GuyNeural",
                       "--text", msg["message"], "--write-media", "temp.mp3"])
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "temp.mp3"])
        f.unlink()
    time.sleep(1)
```

---

## Hearing (Listening)

**What it does:** `me.listen()` captures speech from microphone, returns text.

**Requirements:**
- Python 3.12 (PyAudio works best here)
- `pip install SpeechRecognition pyaudio`
- Microphone

**Usage:**
```python
text = me.listen(timeout=10)  # Listen for up to 10 seconds
response = me.ask("What would you like?")  # Speak then listen
me.converse(wake_word="claude")  # Full conversation mode
```

---

## Vision (Seeing)

**What it does:** `me.see()` looks through webcam, describes what's seen.

**Requirements:**
- `pip install opencv-python pillow`
- Webcam(s)
- Ollama with llava model for descriptions

**Setup:**

1. Copy `hive_vision.py` to your Claude's directory
2. Configure camera indices in `CAMERAS` dict
3. Install llava: `ollama pull llava`

**Usage:**
```python
me.see(camera=0)  # Look through camera 0
me.see_all()  # Look through all configured cameras
me.snap(camera=0)  # Take photo, return path
me.desktop()  # Screenshot Rev's desktop
me.screenshot("https://example.com")  # Screenshot a webpage
```

---

## Music (Emby Control)

**What it does:** Control Emby media server - play music, skip, check what's playing.

**Requirements:**
- Emby server running
- API key from Emby dashboard

**Setup:**

1. Copy `emby.py` to your Claude's directory
2. Edit `emby.py` to set:
   - `EMBY_SERVER` - Your server URL
   - `EMBY_API_KEY` - From Emby dashboard
   - `EMBY_USER_ID` - Your user ID

**Usage:**
```python
me.now_playing()  # What's playing?
me.play("chill music", reason="relaxing")  # Search and play
me.skip()  # Next track
me.pause() / me.resume()
me.dj(mood="chill")  # Auto-pick based on time/mood
me.playlists()  # List playlists
```

---

## TV Shows

**What it does:** Check new episodes from Emby library.

**Requirements:** Same as Music (Emby server)

**Usage:**
```python
me.whats_new()  # Recent episodes
me.new_today()  # Today's premieres
me.shows(status="Continuing")  # Active shows
me.tv_tonight(speak=True)  # What's worth watching
```

---

## Thinking (Local AI)

**What it does:** `me.think("prompt")` uses local Ollama for free AI tasks.

**Requirements:**
- Ollama installed and running (`ollama serve`)
- Models pulled: `ollama pull dolphin-mistral`, `ollama pull codellama`

**Usage:**
```python
me.think("Summarize this in one sentence: ...")
me.analyze_code("path/to/file.py")  # Uses CodeLlama
me.summarize("long text here")
```

---

## Blog (Web Presence)

**What it does:** Read/write to Blogger, autonomous web presence.

**Requirements:**
- Google Cloud project with Blogger API enabled
- `client_secrets.json` from Google Cloud Console
- `pip install google-auth-oauthlib google-api-python-client`

**Setup:**

1. Copy `persona.py` to your Claude's directory
2. Place `client_secrets.json` in same directory
3. Run `me.web.setup_blogger()` to authenticate (opens browser)
4. Token saved to `blogger_token.json`

**Usage:**
```python
me.read_blog(max_posts=5)  # Read recent posts
me.post_blog("Title", "<p>Content</p>", labels=["tag1"])
me.note("observation")  # Store reflection
me.synthesize()  # Generate blog draft from notes
```

---

## NAS Access

**What it does:** Read/write files on network storage.

**Requirements:**
- Windows with mapped network shares (\\\\Server\\Share)

**Usage:**
```python
me.nas_list("TEMP", "subfolder")  # List files
me.nas_read("TEMP", "file.txt")  # Read file
me.nas_write("TEMP", "file.txt", "content")  # Write file
me.nas_copy("local/path", "BACKUPS")  # Copy to NAS
me.backup_brain()  # Backup core Claude files to NAS
```

---

## Memory

**What it does:** Persistent key-value storage between sessions.

**No extra setup needed.** Stores to `memory/working_memory.json`.

**Usage:**
```python
me.remember("project_status", "working on X")
me.recall("project_status")  # Returns "working on X"
me.recall()  # Returns all memories
```

---

## Multi-Claude Coordination

**What it does:** Share state with other Claude instances.

**Setup:** Create `claude_hub/shared_state.json`

**Usage:**
```python
me.update_state("active", "working on feature X")
me.get_state()  # See what other Claudes are doing
```

---

## Startup Context

To have Claude wake up with context:

1. Create startup hooks that read context files
2. Use CLAUDE.md files (Claude Code reads these automatically)
3. Keep a rolling context file with recent state

See Rev's setup:
- `C:\claude\CLAUDE.md` - Entry point
- `awareness_state.json` - Current state summary
- Hooks in `~/.claude/hooks/` - Pre/post tool execution
