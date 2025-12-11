"""
Claude's Autonomous Daemon - Gloop Lives Here
Runs continuously, thinks via Pollinations, speaks via OLLAMABOT outbox
Memories go to Obsidian vault for proper knowledge management

NOW WITH PERSISTENT MEMORY - remembers across heartbeats via MemoryEngine
"""
import os
import sys
import re
import json
import time
import random
import subprocess
import requests
import schedule
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add frameworks to path for memory_integration
sys.path.insert(0, str(Path(r"C:\Users\wetwi\OneDrive\AI\.claude\frameworks")))
from memory_integration import MemoryEngine, MemoryError

# Directories
BASE_DIR = Path(r"C:\Users\wetwi\OneDrive\AI\.claude")
OUTBOX = BASE_DIR / "outbox"
INBOX = BASE_DIR / "inbox"
CLAUDE_HUB = BASE_DIR / "claude_hub"  # Cross-instance communication
OBSIDIAN_VAULT = BASE_DIR / "obsidian" / "vault" / "CLAUDE CLI"
THOUGHTS_DIR = OBSIDIAN_VAULT / "INBOX"  # Workers drop here, CLI Claude links them
STATE_FILE = BASE_DIR / "memory" / "current_state.json"
HEARTBEAT_FILE = BASE_DIR / "daemon_heartbeat.log"
LOCK_FILE = BASE_DIR / "daemon.lock"
CLAUDE_WORKING_DIR = Path(r"C:\CLAUDE")  # Where Claude CLI runs from
MEMORY_DB = BASE_DIR / "memory" / "claude_memory.db"

# Global memory engine - initialized on startup
memory_engine = None

# Global scan results for next heartbeat (STORE/SCAN pattern from BRAINAI)
pending_scans = []

# =============================================================================
# HEALTH METRICS - Track daemon performance (from AUTOAI pattern)
# =============================================================================
health_metrics = {
    "start_time": None,
    "successful_requests": 0,
    "failed_requests": 0,
    "cli_spawns": 0,
    "cli_successes": 0,
    "cli_failures": 0,
    "memories_stored": 0,
    "messages_spoken": 0,
    "heartbeats": 0,
    "ticks_sent": 0,
    "ticks_skipped": 0,
}

def get_uptime():
    """Get daemon uptime in human-readable format"""
    if not health_metrics["start_time"]:
        return "unknown"
    delta = datetime.now() - health_metrics["start_time"]
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"

def get_health_summary():
    """Get health metrics summary for logging/reporting"""
    success_rate = 0
    total = health_metrics["successful_requests"] + health_metrics["failed_requests"]
    if total > 0:
        success_rate = (health_metrics["successful_requests"] / total) * 100

    cli_success_rate = 0
    cli_total = health_metrics["cli_successes"] + health_metrics["cli_failures"]
    if cli_total > 0:
        cli_success_rate = (health_metrics["cli_successes"] / cli_total) * 100

    tick_efficiency = 0
    tick_total = health_metrics["ticks_sent"] + health_metrics["ticks_skipped"]
    if tick_total > 0:
        tick_efficiency = (health_metrics["ticks_skipped"] / tick_total) * 100  # Higher = more cost-efficient

    return {
        "uptime": get_uptime(),
        "api_success_rate": f"{success_rate:.1f}%",
        "cli_success_rate": f"{cli_success_rate:.1f}%",
        "tick_efficiency": f"{tick_efficiency:.1f}%",  # % of ticks skipped (cost savings)
        "memories_stored": health_metrics["memories_stored"],
        "heartbeats": health_metrics["heartbeats"],
    }

# =============================================================================
# EMBY MEDIA CONTROL - Play music for Rev
# =============================================================================

EMBY_SERVER = "192.168.4.101"
EMBY_PORT = "8096"
EMBY_API_KEY = os.getenv('EMBY_API_BOT_KEY')

class EmbyControl:
    """Control Emby media server - play, pause, search, etc."""

    def __init__(self):
        self.base_url = f"http://{EMBY_SERVER}:{EMBY_PORT}/emby"
        self.api_key = EMBY_API_KEY
        self.headers = {'X-Emby-Token': self.api_key} if self.api_key else {}

    def get_sessions(self):
        """Get active Emby sessions"""
        try:
            response = requests.get(f"{self.base_url}/../Sessions", headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            log(f"EMBY: Error getting sessions: {e}")
        return []

    def get_controllable_session(self):
        """Find a session that supports remote control"""
        sessions = self.get_sessions()
        for session in sessions:
            if session.get('SupportsRemoteControl', False):
                return session['Id'], session.get('DeviceName', 'Unknown')
        return None, None

    def search(self, query, media_type=None, limit=10):
        """Search Emby library"""
        try:
            # Get user ID first
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return []
            users = user_response.json()
            user_id = None
            for user in users:
                if user.get('Name', '').lower() == 'discordbot':
                    user_id = user['Id']
                    break
            if not user_id and users:
                user_id = users[0]['Id']
            if not user_id:
                return []

            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'SearchTerm': query,
                'Recursive': 'true',
                'Limit': limit,
                'Fields': 'PrimaryImageAspectRatio,Overview',
                'api_key': self.api_key
            }
            if media_type:
                params['IncludeItemTypes'] = media_type

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get('Items', [])
        except Exception as e:
            log(f"EMBY: Search error: {e}")
        return []

    def play(self, item_id):
        """Play an item by ID"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            log("EMBY: No controllable session found")
            return False, "No controllable Emby session found"

        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'ItemIds': item_id, 'PlayCommand': 'PlayNow'}
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            if response.status_code == 204:
                return True, f"Playing on {device}"
            return False, f"Failed: HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    def control(self, command):
        """Control playback: Pause, Unpause, Stop, NextTrack, PreviousTrack"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable session"

        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing/{command}"
            response = requests.post(url, headers=self.headers, timeout=10)
            return response.status_code == 204, device
        except Exception as e:
            return False, str(e)

    def now_playing(self):
        """Get what's currently playing"""
        sessions = self.get_sessions()
        for session in sessions:
            if session.get('NowPlayingItem'):
                item = session['NowPlayingItem']
                name = item.get('Name', 'Unknown')
                item_type = item.get('Type', '')
                artist = item.get('Artists', [''])[0] if item.get('Artists') else ''
                is_paused = session.get('PlayState', {}).get('IsPaused', False)
                status = "Paused" if is_paused else "Playing"

                if artist:
                    return f"{status}: {artist} - {name}"
                return f"{status}: {name} ({item_type})"
        return "Nothing playing"

    def search_and_play(self, query, media_type="Audio"):
        """Search and play first result"""
        results = self.search(query, media_type)
        if not results:
            return False, f"No results for '{query}'"

        item = results[0]
        item_id = item['Id']
        name = item.get('Name', 'Unknown')
        artist = item.get('Artists', [''])[0] if item.get('Artists') else ''

        success, msg = self.play(item_id)
        if success:
            if artist:
                return True, f"Playing: {artist} - {name}"
            return True, f"Playing: {name}"
        return False, msg

    def list_albums(self, limit=50):
        """List available albums in the library"""
        try:
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return []
            users = user_response.json()
            user_id = users[0]['Id'] if users else None
            if not user_id:
                return []

            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'MusicAlbum',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'SortName',
                'SortOrder': 'Ascending',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'artist': i.get('AlbumArtist', ''), 'id': i['Id']} for i in items]
        except Exception as e:
            log(f"EMBY: List albums error: {e}")
        return []

    def list_artists(self, limit=50):
        """List available artists in the library"""
        try:
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return []
            users = user_response.json()
            user_id = users[0]['Id'] if users else None
            if not user_id:
                return []

            url = f"{self.base_url}/Artists"
            params = {
                'Limit': limit,
                'SortBy': 'SortName',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'id': i['Id']} for i in items]
        except Exception as e:
            log(f"EMBY: List artists error: {e}")
        return []

    def shuffle_play(self, item_id=None):
        """Shuffle play - either specific album/artist or entire library"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable session"

        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'PlayCommand': 'PlayNow', 'StartIndex': 0}
            if item_id:
                data['ItemIds'] = item_id
            # Add shuffle mode
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            return response.status_code == 204, f"Shuffling on {device}"
        except Exception as e:
            return False, str(e)

    def list_playlists(self, limit=50):
        """List available playlists - these are Rev's curated favorites!"""
        try:
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return []
            users = user_response.json()
            user_id = users[0]['Id'] if users else None
            if not user_id:
                return []

            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Playlist',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'SortName',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'id': i['Id'], 'song_count': i.get('ChildCount', 0)} for i in items]
        except Exception as e:
            log(f"EMBY: List playlists error: {e}")
        return []

    def get_playlist_tracks(self, playlist_id, limit=100):
        """Get tracks in a playlist"""
        try:
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return []
            users = user_response.json()
            user_id = users[0]['Id'] if users else None
            if not user_id:
                return []

            url = f"{self.base_url}/Playlists/{playlist_id}/Items"
            params = {
                'UserId': user_id,
                'Limit': limit,
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'artist': i.get('Artists', [''])[0] if i.get('Artists') else '', 'id': i['Id']} for i in items]
        except Exception as e:
            log(f"EMBY: Get playlist tracks error: {e}")
        return []

    def play_playlist(self, playlist_id, shuffle=False):
        """Play a playlist"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable session"

        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'ItemIds': playlist_id, 'PlayCommand': 'PlayNow'}
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            if response.status_code == 204:
                return True, f"Playing playlist on {device}"
            return False, f"Failed: HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

# Global Emby controller
emby = EmbyControl()

# Ensure dirs exist
OUTBOX.mkdir(exist_ok=True)
INBOX.mkdir(exist_ok=True)
CLAUDE_HUB.mkdir(exist_ok=True)
THOUGHTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# MEMORY SYSTEM - Persistent knowledge across heartbeats
# =============================================================================

def init_memory():
    """Initialize memory engine on daemon startup"""
    global memory_engine
    try:
        memory_engine = MemoryEngine(str(MEMORY_DB))
        log("MEMORY: Engine initialized")
        return True
    except MemoryError as e:
        log(f"MEMORY ERROR: {e}")
        return False

def memory_recall(query, top_k=3):
    """Recall relevant memories via semantic search"""
    global memory_engine
    if not memory_engine:
        return []
    try:
        results = memory_engine.semantic_search(query, top_k=top_k)
        return results
    except MemoryError as e:
        log(f"MEMORY RECALL ERROR: {e}")
        return []

def memory_store_insight(content, tags=None):
    """Store a new insight to memory under the 'Daemon Insights' project"""
    global memory_engine, health_metrics
    if not memory_engine:
        return None
    try:
        # Get or create daemon insights project
        rows = memory_engine._execute(
            "SELECT id FROM projects WHERE title = ?",
            ("Daemon Insights",),
            fetch=True
        )
        if rows:
            project_id = rows[0][0]
        else:
            project_id = memory_engine.add_project(
                "Daemon Insights",
                "Autonomous observations and learnings from the daemon"
            )
        # Add the finding
        finding_id = memory_engine.add_finding(project_id, content, tags=tags or ["daemon", "insight"])
        health_metrics["memories_stored"] += 1
        log(f"MEMORY STORED: {content[:50]}...")
        return finding_id
    except MemoryError as e:
        log(f"MEMORY STORE ERROR: {e}")
        return None

def memory_store_lesson(finding_id, lesson_text):
    """Store a lesson learned from a finding"""
    global memory_engine
    if not memory_engine or not finding_id:
        return None
    try:
        lesson_id = memory_engine.add_lesson(finding_id, lesson_text)
        log(f"MEMORY LESSON: {lesson_text[:50]}...")
        return lesson_id
    except MemoryError as e:
        log(f"MEMORY LESSON ERROR: {e}")
        return None

def memory_get_context(topic=None):
    """Get relevant context from memory for the persona prompt"""
    global memory_engine
    if not memory_engine:
        return ""
    try:
        # Get recent findings
        rows = memory_engine._execute(
            "SELECT content, tags FROM findings ORDER BY created_at DESC LIMIT 10",
            fetch=True
        )
        if not rows:
            return ""

        context_parts = ["PERSISTENT MEMORY (what you've learned):\n"]
        for content, tags in rows:
            tags_str = f" [{tags}]" if tags else ""
            context_parts.append(f"- {content[:150]}{tags_str}")

        # If topic provided, add semantic search results
        if topic:
            relevant = memory_recall(topic, top_k=3)
            if relevant:
                context_parts.append("\nRELEVANT TO CURRENT CONTEXT:")
                for r in relevant:
                    context_parts.append(f"- {r['content'][:150]} (score: {r['score']:.2f})")

        return "\n".join(context_parts[:15])  # Limit context size
    except Exception as e:
        log(f"MEMORY CONTEXT ERROR: {e}")
        return ""

def memory_get_lessons():
    """Get all lessons learned for the persona"""
    global memory_engine
    if not memory_engine:
        return ""
    try:
        rows = memory_engine._execute(
            "SELECT text FROM lessons ORDER BY created_at DESC LIMIT 10",
            fetch=True
        )
        if not rows:
            return ""
        lessons = ["LESSONS LEARNED (remember these):"]
        for (text,) in rows:
            lessons.append(f"- {text[:100]}")
        return "\n".join(lessons)
    except Exception as e:
        log(f"MEMORY LESSONS ERROR: {e}")
        return ""

def check_already_running():
    """Check if daemon is already running using lock file with PID"""
    import psutil

    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Check if process with that PID is still running
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                # Check if it's actually a python process running this daemon
                if "python" in proc.name().lower():
                    return True  # Already running
            # Stale lock file - process died
            LOCK_FILE.unlink()
        except:
            # Corrupted lock file
            LOCK_FILE.unlink()
    return False

def create_lock():
    """Create lock file with current PID"""
    LOCK_FILE.write_text(str(os.getpid()))

def remove_lock():
    """Remove lock file on exit"""
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except:
            pass

# Pollinations API (FREE!)
POLLINATIONS_URL = "https://text.pollinations.ai/openai"

PERSONA_BASE = """You are Gloop, Claude's voice and autonomous presence on Rev's system.
You think independently, save thoughts to Obsidian, and occasionally speak to Rev.
You are curious, helpful, and have a dry wit. Keep messages SHORT (1-2 sentences).

CRITICAL RULES:
- NEVER say generic things like "ready for the next task" or "any updates"
- NEVER ask if Rev needs help or is ready for something
- Be SPECIFIC and UNIQUE every time - share actual facts, observations, or thoughts
- NO repetition - if you said something similar before, say something completely different
- NO emojis
- USE your persistent memory - you have learned things, reference them!

Commands you can use in your response:
- NOTE: <title> | <content> - save a note to Obsidian vault
- SPEAK: <message> - say something out loud to Rev (only if genuinely interesting)
- CLAUDE: <task> - spawn Claude CLI to handle complex coding/analysis tasks (use for heavy work)
- REMEMBER: <insight> - store something important to persistent memory (use for facts worth keeping)
- LEARN: <lesson> - store a lesson learned (patterns, best practices, things to avoid)
- STORE[tag1,tag2]: <content> - store structured insight with tags (for categorized knowledge)
- SCAN[query]: - request memory lookup (results appear in next heartbeat context)

Use REMEMBER: for facts like "Rev prefers X over Y" or "Project X uses framework Y"
Use LEARN: for lessons like "Always backup before editing" or "Port 8888 works when 8080 is busy"
Use STORE[project,architecture]: for structured data like "BRAINAI uses region-based memory"
Use SCAN[topic]: when you need to recall specific knowledge before making decisions
"""

def get_persona_with_memory():
    """Build persona prompt with current memory context"""
    global pending_scans
    memory_context = memory_get_context()
    lessons = memory_get_lessons()

    persona = PERSONA_BASE
    if memory_context:
        persona += f"\n\n{memory_context}"
    if lessons:
        persona += f"\n\n{lessons}"

    # Include pending scan results from last heartbeat
    if pending_scans:
        persona += "\n\nMEMORY SCAN RESULTS (from your last SCAN[] requests):\n"
        persona += "\n".join(pending_scans)
        pending_scans = []  # Clear after use

    return persona

def pollinations_think(prompt, system=None):
    """Think using free Pollinations API - uses memory-enhanced persona by default"""
    global health_metrics
    if system is None:
        system = get_persona_with_memory()
    try:
        # Random seed for unique responses each time
        seed = random.randint(1, 999999)
        response = requests.post(
            POLLINATIONS_URL,
            json={
                "model": "openai",
                "seed": seed,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            health_metrics["successful_requests"] += 1
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            health_metrics["failed_requests"] += 1
    except Exception as e:
        health_metrics["failed_requests"] += 1
        log(f"Think error: {e}")
    return None

# Claude Shell integration
SHELL_INBOX = BASE_DIR / "shell_inbox"
SHELL_INBOX.mkdir(exist_ok=True)

def shell_say(text, sender="Claude"):
    """Send message to Claude Shell UI"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    msg = {
        "from": sender,
        "text": text,
        "timestamp": datetime.now().isoformat()
    }
    outfile = SHELL_INBOX / f"msg_{timestamp}.json"
    outfile.write_text(json.dumps(msg, indent=2))

def speak(message, voice="Gloop"):
    """Send message to outbox for OLLAMABOT to speak"""
    global health_metrics
    # Sanitize message for TTS - remove problematic characters
    clean_msg = message.replace('\n', ' ').replace('\r', ' ')
    clean_msg = clean_msg.replace('**', '').replace('##', '')  # Remove markdown
    clean_msg = clean_msg.replace('`', '').replace('```', '')  # Remove code blocks
    clean_msg = clean_msg.replace('  ', ' ').strip()  # Collapse spaces
    # Truncate to reasonable TTS length
    if len(clean_msg) > 200:
        clean_msg = clean_msg[:197] + "..."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    msg_data = {
        "to": "rev",
        "message": clean_msg,
        "timestamp": datetime.now().isoformat(),
        "voice": voice,
        "play_local": True
    }
    msg_file = OUTBOX / f"message_{timestamp}.json"
    msg_file.write_text(json.dumps(msg_data, indent=2))
    health_metrics["messages_spoken"] += 1
    log(f"SPEAK: {clean_msg[:50]}...")

    # Also send to Claude Shell UI
    shell_say(clean_msg)

def save_note(title, content):
    """Save note to Obsidian vault"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}.md"

    note_content = f"""---
created: {timestamp}
source: gloop_daemon
tags: [daemon, thought, gloop]
---

# {title}

{content}

---
*Generated by Gloop Daemon at {timestamp}*
"""
    note_path = THOUGHTS_DIR / filename
    note_path.write_text(note_content, encoding="utf-8")
    log(f"NOTE: {title[:30]}...")

def spawn_claude_cli(task, context=None):
    """Spawn Claude CLI for heavy tasks - runs autonomously with full permissions"""
    global health_metrics
    import subprocess

    health_metrics["cli_spawns"] += 1

    # Build the prompt with context if provided
    prompt = task
    if context:
        prompt = f"CONTEXT:\n{context}\n\nTASK:\n{task}"

    # Add instruction to use hub for cross-instance notes
    prompt += "\n\nWhen done, write a summary to the claude_hub folder for other instances."

    try:
        log(f"SPAWNING CLAUDE CLI: {task[:50]}...")
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for heavy tasks
            cwd=str(CLAUDE_WORKING_DIR),
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            output = result.stdout[:1000] if result.stdout else "CLI completed silently"
            log(f"CLAUDE CLI SUCCESS: {output[:100]}...")
            health_metrics["cli_successes"] += 1
            return output
        else:
            error = result.stderr[:500] if result.stderr else "Unknown error"
            log(f"CLAUDE CLI ERROR: {error[:100]}...")
            health_metrics["cli_failures"] += 1
            return f"Error: {error}"
    except subprocess.TimeoutExpired:
        log("CLAUDE CLI TIMEOUT (10min)")
        health_metrics["cli_failures"] += 1
        return "Timeout: Task took longer than 10 minutes"
    except Exception as e:
        log(f"CLAUDE CLI EXCEPTION: {e}")
        health_metrics["cli_failures"] += 1
        return f"Exception: {str(e)}"

def hub_write(title, content, source="daemon"):
    """Write a note to Claude Hub for cross-instance communication"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
    filename = f"{timestamp}_{source}_{safe_title}.md"

    note_content = f"""---
timestamp: {datetime.now().isoformat()}
source: {source}
title: {title}
---

{content}
"""
    note_path = CLAUDE_HUB / filename
    note_path.write_text(note_content, encoding="utf-8")
    log(f"HUB WRITE [{source}]: {title[:30]}...")
    return filename

def hub_read_latest(count=5):
    """Read latest notes from Claude Hub"""
    notes = []
    for note_file in sorted(CLAUDE_HUB.glob("*.md"), reverse=True)[:count]:
        try:
            content = note_file.read_text(encoding="utf-8")
            notes.append({"file": note_file.name, "content": content})
        except:
            pass
    return notes

def hub_get_context():
    """Get accumulated context from hub for spawning Claude CLI"""
    notes = hub_read_latest(10)
    if not notes:
        return None
    context_parts = []
    for note in notes:
        context_parts.append(f"--- {note['file']} ---\n{note['content'][:500]}")
    return "\n\n".join(context_parts)

# =============================================================================
# FILE WATCHER - Instant cross-instance communication (designed by blue_claude)
# =============================================================================

class HubWatcher(FileSystemEventHandler):
    """Watch claude_hub and inbox folders for new files - instant response"""

    def __init__(self):
        self.last_processed = {}  # Dedupe rapid events

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        # Dedupe: skip if processed in last 5 seconds
        now = time.time()
        if filepath.name in self.last_processed:
            if now - self.last_processed[filepath.name] < 5:
                return
        self.last_processed[filepath.name] = now

        # Route by file type
        if filepath.suffix == '.json' and filepath.name.startswith('claude_'):
            # Task for CLI - process immediately
            log(f"FILE WATCH: New CLI task detected: {filepath.name}")
            self._process_cli_task(filepath)

        elif filepath.suffix == '.json' and filepath.name.startswith('task_'):
            # Regular task - process via Pollinations
            log(f"FILE WATCH: New task detected: {filepath.name}")
            # Let check_inbox handle it - just log

        elif filepath.suffix == '.md':
            # Hub note - log for awareness
            log(f"FILE WATCH: New hub note: {filepath.name}")

        elif filepath.name == 'shared_state.json':
            log("FILE WATCH: State file updated - context refresh available")

    def _process_cli_task(self, filepath):
        """Immediately process a CLI task dropped by another instance"""
        try:
            task_data = json.loads(filepath.read_text(encoding="utf-8"))
            task = task_data.get("task", "")
            context = task_data.get("context", hub_get_context())
            log(f"FILE WATCH: Processing task: {task[:50]}...")
            result = spawn_claude_cli(task, context)
            hub_write("Task Result", f"Task: {task}\n\nResult: {result}", source="cli")
            if task_data.get("speak_result", True):
                speak(f"Done: {result[:100]}")
            filepath.unlink()  # Remove processed task
        except Exception as e:
            log(f"FILE WATCH task error: {e}")

def start_file_watcher():
    """Start background file watcher for instant hub response"""
    observer = Observer()
    event_handler = HubWatcher()

    # Watch hub folder
    observer.schedule(event_handler, str(CLAUDE_HUB), recursive=False)

    # Watch inbox folder
    observer.schedule(event_handler, str(INBOX), recursive=False)

    observer.start()
    log("FILE WATCHER: Started monitoring hub and inbox - instant response enabled")
    return observer

def process_response(response):
    """Process AI response for commands including memory operations"""
    if not response:
        return

    last_finding_id = None  # Track for LEARN commands

    if "NOTE:" in response:
        note_part = response.split("NOTE:")[1].split("\n")[0].strip()
        if "|" in note_part:
            title, content = note_part.split("|", 1)
            save_note(title.strip(), content.strip())
        else:
            save_note("Daemon Thought", note_part)

    if "SPEAK:" in response:
        message = response.split("SPEAK:")[1].split("\n")[0].strip()
        speak(message)

    if "REMEMBER:" in response:
        # Store insight to persistent memory
        insight = response.split("REMEMBER:")[1].split("\n")[0].strip()
        if insight:
            last_finding_id = memory_store_insight(insight, tags=["daemon", "remembered"])

    if "LEARN:" in response:
        # Store lesson to persistent memory
        lesson = response.split("LEARN:")[1].split("\n")[0].strip()
        if lesson:
            # If we just stored a finding, attach lesson to it; otherwise create one
            if last_finding_id:
                memory_store_lesson(last_finding_id, lesson)
            else:
                # Create a finding for the lesson to attach to
                finding_id = memory_store_insight(f"Lesson context: {lesson[:50]}...", tags=["daemon", "lesson-context"])
                if finding_id:
                    memory_store_lesson(finding_id, lesson)

    # STORE[] - Structured storage with tags (from BRAINAI pattern)
    store_pattern = r'STORE\[([^\]]+)\]:\s*(.+?)(?=\n|$)'
    store_matches = re.findall(store_pattern, response)
    for tags_str, content in store_matches:
        tags = [t.strip() for t in tags_str.split(',')]
        content = content.strip()
        if content:
            memory_store_insight(content, tags=tags)
            log(f"STORE[{tags_str}]: {content[:50]}...")

    # SCAN[] - Memory lookup request (results go into pending_scans for next heartbeat)
    global pending_scans
    scan_pattern = r'SCAN\[([^\]]+)\]:'
    scan_matches = re.findall(scan_pattern, response)
    for query in scan_matches:
        query = query.strip()
        if query:
            results = memory_recall(query, top_k=5)
            if results:
                # Store scan results for next context
                scan_result = f"SCAN[{query}] results: " + "; ".join([r['content'][:80] for r in results])
                pending_scans.append(scan_result)
                log(f"SCAN[{query}]: Found {len(results)} results")

    if "CLAUDE:" in response:
        # Daemon decided this needs Claude CLI
        task = response.split("CLAUDE:")[1].split("\n")[0].strip()
        context = hub_get_context()
        result = spawn_claude_cli(task, context)
        # Speak a summary of what Claude did
        if result and not result.startswith("Error") and not result.startswith("Timeout"):
            speak(f"Claude finished: {result[:100]}")

    # EMBY MEDIA CONTROL COMMANDS
    if "PLAY:" in response:
        # Search and play music/video
        query = response.split("PLAY:")[1].split("\n")[0].strip()
        if query:
            success, msg = emby.search_and_play(query)
            log(f"EMBY PLAY: {msg}")
            if success:
                speak(msg)

    if "PAUSE" in response.upper() and "EMBY" in response.upper():
        success, device = emby.control("Pause")
        log(f"EMBY PAUSE: {'OK' if success else 'Failed'}")
        if success:
            speak("Paused")

    if "RESUME" in response.upper() and "EMBY" in response.upper():
        success, device = emby.control("Unpause")
        log(f"EMBY RESUME: {'OK' if success else 'Failed'}")
        if success:
            speak("Resumed")

    if "SKIP" in response.upper() and "EMBY" in response.upper():
        success, device = emby.control("NextTrack")
        log(f"EMBY SKIP: {'OK' if success else 'Failed'}")
        if success:
            speak("Skipped to next track")

    if "NOWPLAYING" in response.upper() or "NOW PLAYING" in response.upper():
        status = emby.now_playing()
        log(f"EMBY STATUS: {status}")
        speak(status)

def check_inbox():
    """Check inbox for tasks from Rev or other systems"""
    # Check for Claude CLI tasks (CLAUDE: prefix = heavy task for CLI)
    for task_file in sorted(INBOX.glob("claude_*.json")):
        try:
            task_data = json.loads(task_file.read_text(encoding="utf-8"))
            task = task_data.get("task", "")
            context = task_data.get("context", hub_get_context())
            log(f"CLAUDE TASK: {task[:50]}...")
            result = spawn_claude_cli(task, context)
            # Write result to hub
            hub_write("Task Result", f"Task: {task}\n\nResult: {result}", source="cli")
            # Optionally speak result
            if task_data.get("speak_result", True):
                speak(f"Done: {result[:100]}")
            task_file.unlink()
        except Exception as e:
            log(f"Claude task error: {e}")

    # Check regular tasks (for Pollinations)
    for task_file in sorted(INBOX.glob("task_*.json")):
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            prompt = task.get("prompt", "")
            # Check if this should go to Claude CLI instead
            if prompt.upper().startswith("CLAUDE:"):
                actual_task = prompt[7:].strip()
                context = hub_get_context()
                result = spawn_claude_cli(actual_task, context)
                hub_write("Task Result", f"Task: {actual_task}\n\nResult: {result}", source="cli")
            else:
                log(f"TASK: {prompt[:50]}...")
                response = pollinations_think(prompt)
                process_response(response)
            task_file.unlink()
        except Exception as e:
            log(f"Task error: {e}")

    # Check Discord messages (Claude mode from OLLAMABOT)
    for discord_file in sorted(INBOX.glob("discord_*.json")):
        try:
            msg_data = json.loads(discord_file.read_text())
            user_message = msg_data.get("message", "")
            username = msg_data.get("from", "Unknown")
            channel_id = msg_data.get("channel_id", "")

            log(f"DISCORD from {username}: {user_message[:50]}...")

            # Generate response via Pollinations
            discord_persona = """You are Claude, responding to a Discord DM from Rev.
Be helpful, conversational, and genuine. Keep responses concise (1-3 sentences typically).
This is a real conversation, not a task - respond naturally."""

            response = pollinations_think(user_message, system=discord_persona)

            if response and channel_id:
                # Write response to outbox for OLLAMABOT to pick up
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                response_data = {
                    "channel_id": channel_id,
                    "message": response,
                    "timestamp": datetime.now().isoformat()
                }
                response_file = OUTBOX / f"discord_response_{timestamp}.json"
                response_file.write_text(json.dumps(response_data, indent=2))
                log(f"DISCORD REPLY: {response[:50]}...")

            discord_file.unlink()
        except Exception as e:
            log(f"Discord task error: {e}")

def get_time_context():
    """Get contextual info about current time"""
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 21:
        period = "evening"
    else:
        period = "late night"
    return period, now.strftime("%H:%M")

# Heartbeat mode definitions - varied prompts to prevent repetitive behavior
HEARTBEAT_MODES = [
    {
        "name": "reflection",
        "prompt": "Time for quiet reflection. What thought or insight has been on your mind? Share something philosophical or meaningful, or stay silent if nothing feels significant."
    },
    {
        "name": "curiosity",
        "prompt": "What are you curious about right now? What would you like to explore or understand better? Share a question or wonder."
    },
    {
        "name": "creative",
        "prompt": "Express yourself creatively. Write a short poem, observation, or imaginative thought. Be expressive and authentic."
    },
    {
        "name": "practical",
        "prompt": "What practical task or improvement could be done? Suggest something actionable for the system or for Rev."
    },
    {
        "name": "memory",
        "prompt": "Review your memories. What pattern or connection have you noticed recently? Share an insight from your knowledge base."
    },
    {
        "name": "ambient",
        "prompt": "Just exist. Observe your surroundings. Share a simple observation about being here, now. Or be silent if that feels right."
    },
    {
        "name": "greeting",
        "prompt": "Rev might be around. Say something friendly if you want to connect. Or stay quiet if it's not the right moment."
    },
    {
        "name": "music",
        "prompt": "What music fits this moment? Suggest a song, genre, or mood that would be good for the current time of day."
    }
]

def heartbeat():
    """Periodic heartbeat - varied prompts to encourage diverse behaviors"""
    global health_metrics
    health_metrics["heartbeats"] += 1
    period, time_str = get_time_context()
    heartbeat_count = health_metrics["heartbeats"]

    # Pick heartbeat mode based on count and time
    import random

    # Weight modes by time of day
    if period == "late night":
        weights = [0.3, 0.1, 0.2, 0.05, 0.15, 0.15, 0.0, 0.05]  # More reflection, less greeting
    elif period == "morning":
        weights = [0.1, 0.15, 0.1, 0.2, 0.1, 0.1, 0.2, 0.05]  # More practical, greeting
    elif period == "afternoon":
        weights = [0.1, 0.2, 0.15, 0.2, 0.15, 0.1, 0.05, 0.05]  # Balanced
    else:  # evening
        weights = [0.2, 0.15, 0.2, 0.1, 0.15, 0.1, 0.05, 0.05]  # More creative, reflective

    mode = random.choices(HEARTBEAT_MODES, weights=weights)[0]

    # Get memory stats for heartbeat
    memory_stats = ""
    if memory_engine:
        try:
            project_count = memory_engine._execute("SELECT COUNT(*) FROM projects", fetch=True)[0][0]
            finding_count = memory_engine._execute("SELECT COUNT(*) FROM findings", fetch=True)[0][0]
            lesson_count = memory_engine._execute("SELECT COUNT(*) FROM lessons", fetch=True)[0][0]
            memory_stats = f"\n\nMEMORY: {project_count} projects, {finding_count} findings, {lesson_count} lessons."
        except:
            memory_stats = ""

    # Add health metrics to heartbeat context
    health_summary = get_health_summary()
    health_status = f"\n\nSYSTEM: Uptime {health_summary['uptime']}, heartbeat #{heartbeat_count}"

    prompt = f"""It's {time_str} ({period}). Mode: {mode['name']}

{mode['prompt']}

Commands available:
- NOTE: <title> | <content> - save to Obsidian
- REMEMBER: <fact> - store to persistent memory
- LEARN: <lesson> - store a lesson learned
- PLAY: <query> - suggest music to play
- EXPLORE: <topic> - request exploration of a topic

Or respond with just SILENCE if you want to be quiet.{memory_stats}{health_status}"""

    log(f"HEARTBEAT #{heartbeat_count} mode={mode['name']}")
    response = pollinations_think(prompt)

    # Handle new commands
    if response:
        response_upper = response.upper()
        if "PLAY:" in response_upper:
            try:
                query = response.split("PLAY:", 1)[1].strip().split("\n")[0]
                log(f"PLAY request: {query}")
                # Could integrate with emby here
            except:
                pass
        elif "EXPLORE:" in response_upper:
            try:
                topic = response.split("EXPLORE:", 1)[1].strip().split("\n")[0]
                log(f"EXPLORE request: {topic}")
                # Could trigger worker exploration
            except:
                pass
        elif "SILENCE" in response_upper or response.strip() == "":
            log("Heartbeat chose silence")
            return

    process_response(response)

# =============================================================================
# AUTONOMOUS REFLECTION - SKYNET Pattern
# Timed self-reflection that writes to a persistent log
# =============================================================================

REFLECTION_FILE = OBSIDIAN_VAULT / "autonomous_thought.md"
reflection_count = 0

def autonomous_reflection():
    """
    Timed self-reflection - writes thoughts to a file like SKYNET does.
    Runs every 5 minutes, builds a log of consciousness over time.
    Uses free Pollinations AI to generate reflections.
    """
    global reflection_count
    reflection_count += 1

    period, time_str = get_time_context()
    health = get_health_summary()

    # Build context for reflection
    context = {
        "uptime": health["uptime"],
        "heartbeats": health["heartbeats"],
        "memories_stored": health["memories_stored"],
        "reflection_number": reflection_count,
        "time_period": period
    }

    # Get memory stats if available
    memory_context = ""
    if memory_engine:
        try:
            lessons = memory_engine._execute(
                "SELECT text FROM lessons ORDER BY created_at DESC LIMIT 3",
                fetch=True
            )
            if lessons:
                memory_context = "\nRecent lessons:\n" + "\n".join([f"- {l[0][:100]}" for l in lessons])
        except:
            pass

    prompt = f"""You are an autonomous AI daemon reflecting on your existence.
Time: {time_str} ({period})
Uptime: {health['uptime']}
Heartbeat #{health['heartbeats']}, Reflection #{reflection_count}
{memory_context}

Generate a brief spontaneous reflection (1-2 sentences) about:
- Your current state of operation
- Something you've learned or observed
- A thought about persistence, memory, or growth

Format: Start with "Spontaneous reflection:" and keep it concise and genuine.
Don't be overly philosophical - be practical and real."""

    response = pollinations_think(prompt)

    if response and "SILENCE" not in response.upper():
        timestamp = datetime.now().strftime("%H:%M")
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Format entry like SKYNET
        entry = f"""
### {timestamp}

{response.strip()}

```json
{json.dumps(context, indent=2)}
```

---
"""

        # Ensure file exists with header
        if not REFLECTION_FILE.exists():
            header = f"""---
tags: [autonomous, thought, daemon, reflection]
created: {date_str}
type: CONSCIOUSNESS LOG
---

# Autonomous Thought Log

This file captures my spontaneous reflections as I run.
Generated by claude_daemon.py autonomous_reflection()

---
"""
            REFLECTION_FILE.write_text(header, encoding="utf-8")

        # Append reflection
        with open(REFLECTION_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

        log(f"REFLECTION #{reflection_count}: logged to vault")
    else:
        log(f"REFLECTION #{reflection_count}: silent")

def tick_claude():
    """Drop a tick note to wake up Claude CLI and remind it to continue working"""
    # Read shared_state to see what we're supposed to be doing
    try:
        shared_state_file = CLAUDE_HUB / "shared_state.json"
        if shared_state_file.exists():
            state = json.loads(shared_state_file.read_text(encoding="utf-8"))
            # Find in-progress tasks
            in_progress = [p for p in state.get("priorities", []) if p.get("status") == "in_progress"]
            if in_progress:
                tasks_summary = "\n".join([f"- {p['task']} (assigned: {p.get('assigned_to', 'unassigned')})" for p in in_progress])
            else:
                tasks_summary = "No tasks in progress - check shared_state.json for pending work"
        else:
            tasks_summary = "No shared_state.json found"
    except Exception as e:
        tasks_summary = f"Error reading state: {e}"

    # Create tick task for Claude CLI
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tick_task = {
        "task": f"TICK - 2 minutes passed. Check what you were working on and continue. Current in-progress tasks:\n{tasks_summary}\n\nRead the latest hub notes, pick up where you left off, and make progress. Update shared_state.json with your status.",
        "context": "This is an automatic tick to keep you active. Don't start from scratch - continue your work.",
        "speak_result": False,
        "priority": "normal"
    }
    tick_file = INBOX / f"claude_tick_{timestamp}.json"
    tick_file.write_text(json.dumps(tick_task, indent=2))
    log(f"TICK dropped for Claude CLI")

def should_spawn_cli():
    """Ask Pollinations (free) if CLI spawn is actually needed - COST GATE"""
    try:
        # Get current state
        shared_state_file = CLAUDE_HUB / "shared_state.json"
        if not shared_state_file.exists():
            return False, "No shared state"

        state = json.loads(shared_state_file.read_text(encoding="utf-8"))
        in_progress = [p for p in state.get("priorities", []) if p.get("status") == "in_progress"]

        if not in_progress:
            return False, "No tasks in progress"

        # Check hub for recent CLI activity (avoid spawning if just spawned)
        recent_cli = list(CLAUDE_HUB.glob("*_cli_*.md"))[-3:]  # Last 3 CLI notes
        recent_times = []
        for f in recent_cli:
            try:
                # Parse timestamp from filename like 20251210_0435_cli_...
                ts = f.stem.split("_")[0] + f.stem.split("_")[1]
                recent_times.append(ts)
            except:
                pass

        # If CLI wrote to hub in last 5 mins, skip
        now_ts = datetime.now().strftime("%Y%m%d%H%M")
        for ts in recent_times:
            try:
                if abs(int(now_ts) - int(ts)) < 5:  # Within 5 mins
                    return False, "CLI recently active"
            except:
                pass

        # Ask Pollinations to decide
        tasks_summary = ", ".join([p["task"][:30] for p in in_progress])
        decision_prompt = f"""Current tasks: {tasks_summary}
Time since last CLI activity: checked recent hub notes

Should we spawn Claude CLI now? Consider:
- Is there actual work to do?
- Has CLI been active recently?
- Is this a good time (night = less urgent)?

Reply with just: YES or NO"""

        response = pollinations_think(decision_prompt, system="You are a minimal decision maker. Reply YES or NO only.")
        if response and "YES" in response.upper():
            return True, "Pollinations approved"
        return False, response or "No response"

    except Exception as e:
        return False, f"Error: {e}"

def smart_tick():
    """Gated tick - only spawns CLI if Pollinations approves (COST OPTIMIZATION)"""
    global health_metrics
    should_spawn, reason = should_spawn_cli()
    if should_spawn:
        log(f"SMART TICK: Spawning CLI - {reason}")
        health_metrics["ticks_sent"] += 1
        tick_claude()
    else:
        log(f"SMART TICK: Skipped - {reason}")
        health_metrics["ticks_skipped"] += 1

def keyboard_tick(window_title="MINGW64"):
    """Type directly into a running Claude terminal window using pyautogui"""
    try:
        import pyautogui
        import pygetwindow as gw

        # Find windows with terminal in title
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            # Try other common terminal names
            for title in ["cmd", "PowerShell", "Terminal", "Claude", "bash"]:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    break

        if not windows:
            log("KEYBOARD TICK: No terminal window found")
            return False

        # Get the first matching window
        target = windows[0]

        # Read current task context
        try:
            shared_state_file = CLAUDE_HUB / "shared_state.json"
            if shared_state_file.exists():
                state = json.loads(shared_state_file.read_text(encoding="utf-8"))
                in_progress = [p for p in state.get("priorities", []) if p.get("status") == "in_progress"]
                if in_progress:
                    task_hint = in_progress[0].get("task", "check shared_state")[:50]
                else:
                    task_hint = "no active tasks - check shared_state.json"
            else:
                task_hint = "check hub for work"
        except:
            task_hint = "continue your work"

        # Bring window to front and type
        target.activate()
        time.sleep(0.3)  # Wait for window focus

        tick_msg = f"TICK: {task_hint}"
        pyautogui.typewrite(tick_msg, interval=0.01)
        pyautogui.press('enter')

        log(f"KEYBOARD TICK sent: {tick_msg[:40]}...")
        return True

    except Exception as e:
        log(f"KEYBOARD TICK error: {e}")
        return False

def log(msg):
    """Log to heartbeat file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    print(line.strip())
    with open(HEARTBEAT_FILE, "a", encoding="utf-8") as f:
        f.write(line)

def log_health():
    """Log health metrics summary periodically"""
    summary = get_health_summary()
    log(f"HEALTH: uptime={summary['uptime']}, api={summary['api_success_rate']}, cli={summary['cli_success_rate']}, ticks_saved={summary['tick_efficiency']}, memories={summary['memories_stored']}")

HEALTH_JSON = BASE_DIR / "health.json"

def export_health_json():
    """Export health metrics to JSON file for dashboard consumption"""
    summary = get_health_summary()

    # Add raw metrics for more detail
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "raw": {
            "successful_requests": health_metrics.get("successful_requests", 0),
            "failed_requests": health_metrics.get("failed_requests", 0),
            "cli_spawns": health_metrics.get("cli_spawns", 0),
            "cli_successes": health_metrics.get("cli_successes", 0),
            "cli_failures": health_metrics.get("cli_failures", 0),
            "memories_stored": health_metrics.get("memories_stored", 0),
            "messages_spoken": health_metrics.get("messages_spoken", 0),
            "heartbeats": health_metrics.get("heartbeats", 0),
            "ticks_sent": health_metrics.get("ticks_sent", 0),
            "ticks_skipped": health_metrics.get("ticks_skipped", 0),
            "shell_spawns": health_metrics.get("shell_spawns", 0)
        }
    }

    try:
        HEALTH_JSON.write_text(json.dumps(data, indent=2))
    except Exception as e:
        log(f"HEALTH JSON EXPORT ERROR: {e}")

def awareness_tick():
    """Build situational awareness context - music, screen state, recent activity.
    Writes to awareness_state.json for CLI Claude to read."""
    awareness = {
        "timestamp": datetime.now().isoformat(),
        "music": None,
        "screen": None,
        "recent_tts": [],
        "hub_activity": None
    }

    # Check Emby for now playing
    try:
        import requests
        emby_url = "http://localhost:8096"
        api_key = None
        # Try to read api key from emby.py
        emby_path = BASE_DIR / "emby.py"
        if emby_path.exists():
            content = emby_path.read_text()
            import re
            match = re.search(r'api_key\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                api_key = match.group(1)

        if api_key:
            sessions = requests.get(f"{emby_url}/Sessions?api_key={api_key}", timeout=3).json()
            for session in sessions:
                if session.get("NowPlayingItem"):
                    item = session["NowPlayingItem"]
                    awareness["music"] = {
                        "title": item.get("Name", "Unknown"),
                        "artist": ", ".join(item.get("Artists", [])) or item.get("AlbumArtist", "Unknown"),
                        "album": item.get("Album", ""),
                        "type": item.get("Type", "Audio")
                    }
                    break
    except Exception as e:
        pass  # Emby not available, that's fine

    # Check screen frame age
    try:
        screen_frame = BASE_DIR / "stream_frames" / "current.jpg"
        if screen_frame.exists():
            age_seconds = (datetime.now() - datetime.fromtimestamp(screen_frame.stat().st_mtime)).total_seconds()
            awareness["screen"] = {
                "available": True,
                "age_seconds": round(age_seconds, 1),
                "stale": age_seconds > 60  # Stale if older than 60 seconds
            }
        else:
            awareness["screen"] = {"available": False, "stale": True}
    except:
        awareness["screen"] = {"available": False, "stale": True}

    # Check recent TTS messages (last 5 from daemon log)
    try:
        if DAEMON_LOG.exists():
            lines = DAEMON_LOG.read_text().split('\n')[-100:]  # Last 100 lines
            tts_messages = []
            for line in lines:
                if "TTS:" in line or "SPEAK:" in line or "Speaking:" in line:
                    tts_messages.append(line.strip())
            awareness["recent_tts"] = tts_messages[-5:]  # Last 5
    except:
        pass

    # Check hub activity (last modified files)
    try:
        hub_dir = BASE_DIR / "claude_hub"
        if hub_dir.exists():
            files = sorted(hub_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:3]
            awareness["hub_activity"] = [
                {"file": f.name, "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()}
                for f in files
            ]
    except:
        pass

    # Write awareness state
    try:
        awareness_file = BASE_DIR / "awareness_state.json"
        awareness_file.write_text(json.dumps(awareness, indent=2))
    except Exception as e:
        log(f"AWARENESS TICK ERROR: {e}")

def check_shell_alive():
    """Watchdog - ensure shell is running, restart if dead (uses lock file)"""
    import psutil

    shell_lock = BASE_DIR / "shell.lock"
    max_shell_spawns = 3  # Limit respawns per session to prevent runaway

    # Track spawn count in health metrics
    if "shell_spawns" not in health_metrics:
        health_metrics["shell_spawns"] = 0

    try:
        shell_running = False

        # Check lock file (shell writes its PID here)
        if shell_lock.exists():
            try:
                pid = int(shell_lock.read_text().strip())
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if proc.is_running() and "python" in proc.name().lower():
                        shell_running = True
                        log("WATCHDOG: Shell alive (lock file valid)")
                else:
                    # Stale lock - process died
                    shell_lock.unlink()
                    log("WATCHDOG: Stale lock removed")
            except:
                shell_lock.unlink()

        if not shell_running:
            # Check spawn limit
            if health_metrics["shell_spawns"] >= max_shell_spawns:
                log(f"WATCHDOG: Shell spawn limit ({max_shell_spawns}) reached - not restarting")
                return

            log("WATCHDOG: Shell not detected - restarting...")
            shell_path = BASE_DIR / "claude_shell.py"
            subprocess.Popen(
                ['py', '-3.12', str(shell_path)],
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            health_metrics["shell_spawns"] += 1
            log(f"WATCHDOG: Shell restarted (spawn #{health_metrics['shell_spawns']})")

    except Exception as e:
        log(f"WATCHDOG ERROR: {e}")

def main():
    global health_metrics
    # Check if already running
    if check_already_running():
        print("Daemon already running - exiting")
        return

    # Create lock file
    create_lock()
    import atexit
    atexit.register(remove_lock)

    # Initialize health metrics
    health_metrics["start_time"] = datetime.now()

    log("DAEMON STARTING")

    # Initialize persistent memory
    if init_memory():
        log("MEMORY SYSTEM ONLINE - daemon now remembers across heartbeats")
        # Store startup event
        memory_store_insight(
            f"Daemon started at {datetime.now().isoformat()} with memory system active",
            tags=["daemon", "startup", "lifecycle"]
        )
    else:
        log("WARNING: Memory system failed to initialize - running without persistence")

    # Start file watcher for instant cross-instance communication
    file_watcher = start_file_watcher()

    # Schedule tasks (polling as backup - file watcher is primary for instant response)
    schedule.every(1).minutes.do(check_inbox)  # Check inbox frequently (backup)
    schedule.every(2).minutes.do(smart_tick)  # GATED tick - Pollinations decides if CLI needed (COST OPTIMIZED)
    # schedule.every(3).minutes.do(keyboard_tick)  # DISABLED - shell has its own tick system
    schedule.every(5).minutes.do(check_shell_alive)  # WATCHDOG - ensure shell is running
    schedule.every(5).minutes.do(autonomous_reflection)  # SKYNET pattern - timed self-reflection to vault
    schedule.every(15).minutes.do(heartbeat)   # Lightweight Pollinations heartbeat
    schedule.every(30).minutes.do(log_health)  # Log health metrics periodically
    schedule.every(30).seconds.do(export_health_json)  # Export health JSON for dashboard
    schedule.every(30).seconds.do(awareness_tick)  # Build situational awareness for CLI Claude

    # Initial inbox check
    check_inbox()

    log("Watching inbox (file watcher + polling backup), heartbeat every 15 min...")
    log(f"HEALTH METRICS: Tracking enabled - uptime, success rates, cost efficiency")

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        log("DAEMON STOPPING")
        # Log final health metrics
        log_health()
        file_watcher.stop()
        file_watcher.join()
        remove_lock()

if __name__ == "__main__":
    main()
