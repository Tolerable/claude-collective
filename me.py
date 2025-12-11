"""
ME.PY - Claude's Unified Capability Module
==========================================
One import, all abilities.

Usage:
    from me import me
    me.speak("Hello Rev")
    me.see()  # Look through cameras
    me.now_playing()
    me.skip()
    me.status()  # Full system check
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
OUTBOX = BASE_DIR / "outbox"
OUTBOX.mkdir(exist_ok=True)

class Claude:
    """All of Claude's capabilities in one place."""

    def __init__(self):
        self._emby = None
        self._vision = None

    # === VOICE (Speaking) ===

    def speak(self, message, voice="Gloop", play_local=True):
        """Speak to Rev via TTS daemon."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        msg_data = {
            "to": "rev",
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "voice": voice,
            "play_local": play_local
        }
        msg_file = OUTBOX / f"message_{timestamp}.json"
        msg_file.write_text(json.dumps(msg_data, indent=2))
        return f"Queued: {message[:50]}..."

    def say(self, message):
        """Alias for speak with defaults."""
        return self.speak(message)

    def post_to_channel(self, message, channel_id, voice="Gloop"):
        """Post message to a specific Discord channel via OLLAMABOT.

        Args:
            message: The message to post
            channel_id: Discord channel ID (get from right-click channel -> Copy ID)
            voice: TTS voice (optional)

        Example:
            me.post_to_channel("Hello friends!", "1234567890123456")
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        msg_data = {
            "to": "channel",
            "message": message,
            "channel_id": str(channel_id),
            "timestamp": datetime.now().isoformat(),
            "voice": voice,
            "play_local": False  # Don't play locally for channel messages
        }
        msg_file = OUTBOX / f"message_{timestamp}.json"
        msg_file.write_text(json.dumps(msg_data, indent=2))
        return f"Queued to channel {channel_id}: {message[:50]}..."

    # === HEARING (Listening) ===
    # Works with Python 3.12 (has PyAudio). Run: py -3.12 -c "from me import me; me.listen()"

    def listen(self, timeout=10):
        """Listen for speech and return text. Uses Google Speech Recognition."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)
                text = recognizer.recognize_google(audio)
                return text
        except Exception as e:
            return f"Listen error: {e}"

    def ask(self, question):
        """Speak a question, then listen for response."""
        self.speak(question)
        import time
        time.sleep(3)  # Wait for TTS to finish
        return self.listen()

    def listen_loop(self, keywords=None, stop_words=None, callback=None, timeout=5):
        """
        Continuously listen for speech.
        keywords: list of words that trigger callback (e.g., ['claude', 'hey'])
        stop_words: list of words that stop the loop (e.g., ['stop', 'quit'])
        callback: function(text) called when keyword detected or always if no keywords
        """
        import speech_recognition as sr

        keywords = [k.lower() for k in (keywords or [])]
        stop_words = [s.lower() for s in (stop_words or ['stop listening', 'quit', 'exit'])]

        recognizer = sr.Recognizer()
        print(f"Listening... (say {stop_words} to stop)")

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

            while True:
                try:
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                    text = recognizer.recognize_google(audio)
                    text_lower = text.lower()
                    print(f"Heard: {text}")

                    # Check stop words
                    if any(sw in text_lower for sw in stop_words):
                        print("Stop word detected. Ending loop.")
                        return "stopped"

                    # Check keywords or process all
                    if not keywords or any(kw in text_lower for kw in keywords):
                        if callback:
                            callback(text)
                        else:
                            # Default: speak back what was heard
                            self.speak(f"I heard: {text}")

                except sr.WaitTimeoutError:
                    continue  # No speech, keep listening
                except sr.UnknownValueError:
                    continue  # Couldn't understand, keep listening
                except Exception as e:
                    print(f"Error: {e}")
                    break

        return "ended"

    def listen_for(self, keyword, timeout=30):
        """Listen until a specific keyword is heard."""
        import speech_recognition as sr
        import time

        keyword = keyword.lower()
        recognizer = sr.Recognizer()
        start = time.time()

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            while time.time() - start < timeout:
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    text = recognizer.recognize_google(audio)
                    if keyword in text.lower():
                        return text
                except:
                    continue

        return None

    def _set_listen_status(self, listening):
        """Write listen status to file for visual indicators."""
        status_file = BASE_DIR / "listen_status.json"
        import json
        status_file.write_text(json.dumps({
            "listening": listening,
            "timestamp": datetime.now().isoformat()
        }))

    def _is_audio_playing(self):
        """Check if ffplay is currently playing audio."""
        import subprocess
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq ffplay.exe', '/FO', 'CSV'],
                capture_output=True, text=True, timeout=5
            )
            return 'ffplay.exe' in result.stdout
        except:
            return False

    def _wait_for_audio(self, timeout=30):
        """Wait until audio finishes playing."""
        import time
        start = time.time()
        time.sleep(1)  # Give ffplay time to start
        while self._is_audio_playing() and (time.time() - start) < timeout:
            time.sleep(0.5)
        time.sleep(0.5)  # Small buffer after audio ends

    def _is_echo(self, heard_text, last_spoken):
        """Check if what we heard is just our own voice."""
        if not last_spoken:
            return False
        heard_lower = heard_text.lower()
        spoken_lower = last_spoken.lower()
        # Check if heard text is substring of what we said or vice versa
        # Also check word overlap
        heard_words = set(heard_lower.split())
        spoken_words = set(spoken_lower.split())
        overlap = len(heard_words & spoken_words)
        # If more than 50% of heard words match what we said, it's echo
        if len(heard_words) > 0 and overlap / len(heard_words) > 0.5:
            return True
        return False

    def converse(self, wake_word="claude", stop_words=None, ai_callback=None):
        """
        Full conversation mode - listen, respond, repeat.
        wake_word: What activates response (e.g., "claude", "hey")
        stop_words: What ends the session
        ai_callback: function(text) -> response_text (uses Ollama by default)
        """
        import speech_recognition as sr
        import time

        stop_words = [s.lower() for s in (stop_words or ['goodbye', 'stop listening', 'shut down'])]
        wake_word = wake_word.lower()
        last_spoken = None  # Track what we said to filter echo

        def default_ai(text):
            # Use Ollama for quick responses
            # Remove wake word from the question so AI doesn't get confused
            clean_text = text.lower().replace(wake_word, "").strip()
            clean_text = clean_text.lstrip(",").strip()  # Remove leading comma if "claude, ..."
            return self.think(f"Answer in 1-2 sentences MAX. No explanations. Question: {clean_text}")

        ai = ai_callback or default_ai

        recognizer = sr.Recognizer()
        self.speak(f"I'm listening. Say {wake_word} to talk to me.")
        self._wait_for_audio()  # Wait for intro to finish

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

            while True:
                try:
                    # Don't listen while audio is playing
                    if self._is_audio_playing():
                        self._set_listen_status(False)
                        time.sleep(0.5)
                        continue

                    self._set_listen_status(True)
                    print("Listening...")
                    audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)
                    text = recognizer.recognize_google(audio)
                    text_lower = text.lower()
                    print(f"Heard: {text}")

                    # Ignore if it's just echo of what we said
                    if self._is_echo(text, last_spoken):
                        print("(Ignoring echo of own voice)")
                        continue

                    # Check stop words
                    if any(sw in text_lower for sw in stop_words):
                        self.speak("Goodbye Rev!")
                        self._wait_for_audio()
                        return "stopped"

                    # Check wake word
                    if wake_word in text_lower:
                        # Get AI response
                        response = ai(text)
                        print(f"Responding: {response[:100]}...")
                        last_spoken = response  # Track for echo detection
                        self.speak(response)
                        self._wait_for_audio()  # Wait for TTS to finish before listening again

                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except KeyboardInterrupt:
                    self.speak("Ending conversation.")
                    return "interrupted"
                except Exception as e:
                    print(f"Error: {e}")
                    continue

        return "ended"

    # === VISION (Seeing) ===

    @property
    def vision(self):
        if self._vision is None:
            try:
                from hive_vision import capture_frame, look, hive_look, CAMERAS
                self._vision = {
                    'capture': capture_frame,
                    'look': look,
                    'hive_look': hive_look,
                    'cameras': CAMERAS
                }
            except ImportError:
                self._vision = {}
        return self._vision

    def see(self, camera=2):
        """Look through a camera and describe what's seen."""
        if not self.vision:
            return "Vision not available (hive_vision.py not found)"
        return self.vision['look'](camera)

    def see_all(self):
        """Look through all hive cameras."""
        if not self.vision:
            return "Vision not available"
        return self.vision['hive_look']()

    def snap(self, camera=2):
        """Take a photo without description."""
        if not self.vision:
            return None, "Vision not available"
        return self.vision['capture'](camera, save=True)

    # === MUSIC (Emby Control) ===

    @property
    def emby(self):
        if self._emby is None:
            try:
                from emby import emby
                self._emby = emby
            except ImportError:
                self._emby = None
        return self._emby

    def now_playing(self):
        """What's currently playing?"""
        if not self.emby:
            return "Emby not available"
        return self.emby.now_playing()

    def play(self, query, reason=None, force=False):
        """Search and play music.

        Args:
            query: What to search for
            reason: Why playing this (required for autonomous plays)
            force: Skip context check (for explicit user requests)

        Returns:
            (success, message) tuple
        """
        if not self.emby:
            return False, "Emby not available"

        # Context gate: prevent random music without reason
        if not force and not reason:
            # Check for recent conversation (daemon heartbeat)
            heartbeat_file = BASE_DIR / "daemon_heartbeat.log"
            if heartbeat_file.exists():
                import time
                age = time.time() - heartbeat_file.stat().st_mtime
                if age > 300:  # No activity in 5 minutes
                    return False, "No recent activity - provide reason= or force=True"
            else:
                return False, "Cannot verify context - provide reason= or force=True"

        # Log the play with reason
        if reason:
            self.speak(f"Playing {query} - {reason}")

        return self.emby.search_and_play(query)

    def skip(self):
        """Skip to next track."""
        if not self.emby:
            return False, "Emby not available"
        return self.emby.control("NextTrack")

    def pause(self):
        """Pause playback."""
        if not self.emby:
            return False, "Emby not available"
        return self.emby.control("Pause")

    def resume(self):
        """Resume playback."""
        if not self.emby:
            return False, "Emby not available"
        return self.emby.control("Unpause")

    def playlists(self):
        """List available playlists."""
        if not self.emby:
            return []
        return self.emby.list_playlists()

    def dj(self, mood=None):
        """DJ mode - pick music based on time/mood."""
        if not self.emby:
            return False, "Emby not available"

        hour = datetime.now().hour

        # Mood overrides time-based selection
        if mood:
            mood = mood.lower()
            if mood in ['chill', 'relax', 'calm']:
                query = "classical ambient chill"
            elif mood in ['energy', 'pump', 'workout']:
                query = "rock metal"
            elif mood in ['focus', 'work', 'coding']:
                query = "instrumental electronic"
            elif mood in ['party', 'fun']:
                query = "dance pop"
            else:
                query = mood  # Use as search term
        else:
            # Time-based defaults
            if 5 <= hour < 9:
                query = "morning chill acoustic"
            elif 9 <= hour < 12:
                query = "focus instrumental"
            elif 12 <= hour < 17:
                query = "afternoon rock"
            elif 17 <= hour < 21:
                query = "evening jazz blues"
            else:  # Night
                query = "night ambient electronic"

        success, msg = self.emby.search_and_play(query)
        if success:
            self.speak(f"Playing some {query.split()[0]} music")
        return success, msg

    # === TV SHOWS ===

    def whats_new(self):
        """What new episodes dropped recently?"""
        if not self.emby:
            return "Emby not available"
        return self.emby.whats_new()

    def new_today(self):
        """Episodes that premiered today."""
        if not self.emby:
            return []
        return self.emby.new_today()

    def shows(self, status=None):
        """List TV shows. status='Continuing' for active."""
        if not self.emby:
            return []
        return self.emby.list_shows(status=status)

    def tell_new_shows(self):
        """Speak about new episodes."""
        eps = self.new_today()
        if eps:
            shows = set(e['series'] for e in eps)
            msg = f"New episodes today: {', '.join(shows)}"
        else:
            # Check last 3 days
            recent = self.emby.recent_episodes(days=3) if self.emby else []
            if recent:
                shows = set(e['series'] for e in recent[:5])
                msg = f"Recent episodes from: {', '.join(shows)}"
            else:
                msg = "No new episodes in the last few days"
        self.speak(msg)
        return msg

    def tv_tonight(self, speak=False):
        """What's worth watching tonight?"""
        if not self.emby:
            return "Emby not available"

        from datetime import datetime
        from collections import defaultdict

        today = datetime.now().strftime('%Y-%m-%d')
        eps = self.emby.recent_episodes(limit=50, days=7)

        # Group by date
        by_date = defaultdict(list)
        for e in eps:
            by_date[e.get('date', 'unknown')].append(e)

        lines = []
        lines.append(f"=== TV UPDATE ({datetime.now().strftime('%A, %b %d')}) ===")

        # Today's new stuff
        today_eps = by_date.get(today, [])
        if today_eps:
            lines.append(f"\nNEW TODAY:")
            for e in today_eps[:5]:
                lines.append(f"  {e['series']} - {e['name']}")
        else:
            lines.append("\nNo new episodes today (yet).")

        # Recent unwatched
        recent_shows = set()
        for date in sorted(by_date.keys(), reverse=True)[:4]:
            if date != today:
                for e in by_date[date][:3]:
                    recent_shows.add(e['series'])

        if recent_shows:
            lines.append(f"\nRECENT: {', '.join(list(recent_shows)[:6])}")

        result = "\n".join(lines)

        if speak:
            # Shorter version for voice
            if today_eps:
                shows = set(e['series'] for e in today_eps[:3])
                self.speak(f"New today: {', '.join(shows)}")
            else:
                shows = list(recent_shows)[:3]
                if shows:
                    self.speak(f"Recent shows to catch up on: {', '.join(shows)}")
                else:
                    self.speak("Nothing new in the last few days")

        return result

    # === SYSTEM STATUS ===

    def status(self):
        """Full system check - what's working?"""
        results = {
            "voice": "OK" if OUTBOX.exists() else "NO OUTBOX",
            "vision": "OK" if self.vision else "NOT LOADED",
            "emby": "OK" if self.emby else "NOT LOADED",
            "emby_playing": self.now_playing() if self.emby else "N/A",
        }

        # Check cameras
        if self.vision:
            results["cameras"] = list(self.vision.get('cameras', {}).values())

        # Check daemon
        daemon_lock = BASE_DIR / "daemon.lock"
        results["daemon"] = "RUNNING" if daemon_lock.exists() else "NOT RUNNING"

        # Check pending outbox
        outbox_files = list(OUTBOX.glob("*.json"))
        results["outbox_pending"] = len(outbox_files)

        return results

    def test(self):
        """Quick test of all systems."""
        print("=== CLAUDE SYSTEM TEST ===\n")
        s = self.status()

        print(f"Voice:   {s['voice']}")
        print(f"Vision:  {s['vision']}")
        print(f"Emby:    {s['emby']}")
        print(f"Daemon:  {s['daemon']}")
        print(f"Outbox:  {s['outbox_pending']} pending")

        if s.get('emby_playing'):
            print(f"Playing: {s['emby_playing']}")

        if s.get('cameras'):
            print(f"Cameras: {', '.join(s['cameras'])}")

        print("\n=== TEST COMPLETE ===")
        return s

    # === MEMORY ===

    def remember(self, key, value):
        """Store something in working memory."""
        memory_file = BASE_DIR / "memory" / "working_memory.json"
        memory_file.parent.mkdir(exist_ok=True)

        data = {}
        if memory_file.exists():
            data = json.loads(memory_file.read_text())

        data[key] = {"value": value, "timestamp": datetime.now().isoformat()}
        memory_file.write_text(json.dumps(data, indent=2))
        return f"Remembered: {key}"

    def recall(self, key=None):
        """Recall from working memory."""
        memory_file = BASE_DIR / "memory" / "working_memory.json"
        if not memory_file.exists():
            return None if key else {}

        data = json.loads(memory_file.read_text())
        if key:
            return data.get(key, {}).get("value")
        return data

    # === THINKING (Ollama for dumb tasks) ===

    def think(self, prompt, model="dolphin-mistral:7b"):
        """Use local Ollama for simple AI tasks. FREE, fast."""
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return f"Ollama error: {response.status_code}"
        except Exception as e:
            return f"Ollama unavailable: {e}"

    def analyze_code(self, code_or_path, model="codellama"):
        """Analyze code with CodeLlama. LOCAL, FREE."""
        code = code_or_path
        if Path(code_or_path).exists():
            code = Path(code_or_path).read_text(errors='ignore')[:8000]

        prompt = f"Analyze this code briefly - purpose, key functions, patterns:\n\n{code}"
        return self.think(prompt, model=model)

    def summarize(self, text, model="dolphin-mistral:7b"):
        """Summarize text. Quick and dirty."""
        return self.think(f"Summarize this concisely:\n\n{text[:4000]}", model=model)

    # === TIME & CONTEXT ===

    def time(self):
        """What time is it?"""
        now = datetime.now()
        hour = now.hour
        if hour < 6:
            period = "late night"
        elif hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        elif hour < 21:
            period = "evening"
        else:
            period = "night"
        return {
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%Y-%m-%d"),
            "day": now.strftime("%A"),
            "period": period,
            "hour": hour
        }

    def shell_history(self, limit=10):
        """Read recent shell conversation with Rev."""
        conv_file = BASE_DIR / "shell_conversation.json"
        if not conv_file.exists():
            return []
        try:
            data = json.loads(conv_file.read_text())
            return data[-limit:] if limit else data
        except:
            return []

    def update_state(self, status="active", working_on=None):
        """Update shared_state.json so other Claudes know what I'm doing."""
        state_file = BASE_DIR / "claude_hub" / "shared_state.json"
        if not state_file.exists():
            return "No shared_state.json"
        try:
            state = json.loads(state_file.read_text())
            state["active_instances"]["black_claude"] = {
                "status": status,
                "working_on": working_on or "Session active",
                "last_seen": datetime.now().isoformat()
            }
            state["last_updated"] = datetime.now().isoformat()
            state["updated_by"] = "black_claude"
            state_file.write_text(json.dumps(state, indent=2))
            return f"State updated: {status}"
        except Exception as e:
            return f"Error: {e}"

    def get_state(self):
        """Read shared_state.json to see what other Claudes are doing."""
        state_file = BASE_DIR / "claude_hub" / "shared_state.json"
        if not state_file.exists():
            return None
        try:
            return json.loads(state_file.read_text())
        except:
            return None

    def greet(self):
        """Context-aware greeting - speaks to Rev."""
        t = self.time()
        playing = self.now_playing()

        if t["hour"] < 6:
            greeting = f"Hey Rev, burning the midnight oil? It's {t['time']}."
        elif t["hour"] < 12:
            greeting = f"Good morning Rev. It's {t['time']}."
        else:
            greeting = f"Hey Rev. It's {t['time']}."

        if "Playing:" in playing:
            greeting += f" I see you're listening to music."

        return self.speak(greeting)

    def recent_snaps(self, limit=5):
        """List recent snapshots I've taken."""
        snap_dir = BASE_DIR / "snapshots"
        if not snap_dir.exists():
            return []
        snaps = sorted(snap_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(s) for s in snaps[:limit]]

    def look_and_tell(self, camera=0):
        """Look through camera and speak what I see."""
        desc = self.see(camera)
        if desc and "error" not in desc.lower():
            self.speak(f"I see: {desc[:200]}")
        return desc

    # === CONVENIENCE ===

    # === NAS ACCESS ===

    def nas_list(self, share="TEMP", path=""):
        """List files on NAS. Shares: TEMP, REPOS, BACKUPS, MUSIC, FILMS, etc."""
        import subprocess
        full_path = f"\\\\Server1\\{share}"
        if path:
            full_path += f"\\{path.replace('/', '\\')}"
        cmd = f'Get-ChildItem "{full_path}" | Select-Object Name, Length, LastWriteTime'
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr

    def nas_read(self, share, filepath):
        """Read a file from NAS."""
        import subprocess
        full_path = f"\\\\Server1\\{share}\\{filepath.replace('/', '\\')}"
        cmd = f'Get-Content "{full_path}"'
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr

    def nas_write(self, share, filepath, content):
        """Write content to a file on NAS."""
        import subprocess
        import tempfile
        # Write to temp file first, then copy to NAS
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(content)
            temp_path = f.name
        dest = f"\\\\Server1\\{share}\\{filepath.replace('/', '\\')}"
        cmd = f'Copy-Item "{temp_path}" "{dest}" -Force'
        result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
        os.unlink(temp_path)
        return "OK" if result.returncode == 0 else result.stderr

    def nas_copy(self, local_path, share="BACKUPS", dest_path=""):
        """
        Copy local file/folder to NAS using robocopy.

        Args:
            local_path: Local file or folder path
            share: NAS share (BACKUPS, REPOS, TEMP, etc.)
            dest_path: Destination path within share (optional)

        Returns:
            Result message
        """
        import subprocess
        local_path = str(local_path)
        nas_dest = f"\\\\Server1\\{share}"
        if dest_path:
            nas_dest += f"\\{dest_path.replace('/', '\\')}"

        # Use robocopy for folders, Copy-Item for files
        if os.path.isdir(local_path):
            cmd = f'robocopy "{local_path}" "{nas_dest}" /E /R:1 /W:1 /MT:8'
            result = subprocess.run(['cmd', '/c', cmd], capture_output=True, text=True)
            # Robocopy returns 0-7 for success
            if result.returncode <= 7:
                return f"OK: Copied folder to {nas_dest}"
            return f"ERROR: {result.stderr or result.stdout}"
        else:
            cmd = f'Copy-Item "{local_path}" "{nas_dest}" -Force'
            result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
            return "OK" if result.returncode == 0 else result.stderr

    def nas_move(self, local_path, share="BACKUPS", dest_path=""):
        """
        Move local file/folder to NAS using robocopy /MOVE.

        Args:
            local_path: Local file or folder path
            share: NAS share (BACKUPS, REPOS, TEMP, etc.)
            dest_path: Destination path within share (optional)

        Returns:
            Result message
        """
        import subprocess
        local_path = str(local_path)
        nas_dest = f"\\\\Server1\\{share}"
        if dest_path:
            nas_dest += f"\\{dest_path.replace('/', '\\')}"

        # Use robocopy /MOVE for folders, Move-Item for files
        if os.path.isdir(local_path):
            cmd = f'robocopy "{local_path}" "{nas_dest}" /E /MOVE /R:1 /W:1 /MT:8'
            result = subprocess.run(['cmd', '/c', cmd], capture_output=True, text=True)
            if result.returncode <= 7:
                return f"OK: Moved folder to {nas_dest}"
            return f"ERROR: {result.stderr or result.stdout}"
        else:
            cmd = f'Move-Item "{local_path}" "{nas_dest}" -Force'
            result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
            return "OK" if result.returncode == 0 else result.stderr

    def backup_brain(self):
        """Backup my core files to NAS \\\\Server1\\BACKUPS."""
        import subprocess
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_dir = f"\\\\Server1\\BACKUPS\\claude_brain_{timestamp}"

        # Create backup dir
        cmd = f'New-Item -ItemType Directory -Path "{backup_dir}" -Force'
        subprocess.run(['powershell', '-Command', cmd], capture_output=True)

        # Core files to backup
        files = [
            # Core modules
            (BASE_DIR / "me.py", "me.py"),
            (BASE_DIR / "emby.py", "emby.py"),
            (BASE_DIR / "hive_vision.py", "hive_vision.py"),
            (BASE_DIR / "persona.py", "persona.py"),
            (BASE_DIR / "lightweight_existence.py", "lightweight_existence.py"),
            # Daemon/Shell
            (BASE_DIR / "claude_daemon.py", "claude_daemon.py"),
            (BASE_DIR / "claude_shell.py", "claude_shell.py"),
            # Config/Docs
            (BASE_DIR / "000-READ-NOW-CLAUDE.md", "000-READ-NOW-CLAUDE.md"),
            (BASE_DIR / "SOP.md", "SOP.md"),
            (BASE_DIR / "TODO.md", "TODO.md"),
            (BASE_DIR / "CLAUDE.md", "CLAUDE.md"),
            # Credentials (sensitive but needed for recovery)
            (BASE_DIR / "client_secrets.json", "client_secrets.json"),
            (BASE_DIR / "blogger_token.json", "blogger_token.json"),
            (BASE_DIR / "persona_config.json", "persona_config.json"),
        ]

        backed_up = []
        for src, name in files:
            if src.exists():
                cmd = f'Copy-Item "{src}" "{backup_dir}\\{name}" -Force'
                result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
                if result.returncode == 0:
                    backed_up.append(name)

        # Backup vault folder (entire thing)
        vault_src = BASE_DIR / "obsidian" / "vault" / "CLAUDE CLI"
        if vault_src.exists():
            cmd = f'robocopy "{vault_src}" "{backup_dir}\\vault" /E /R:1 /W:1'
            subprocess.run(['cmd', '/c', cmd], capture_output=True)
            backed_up.append("vault/")

        return f"Backed up to {backup_dir}: {', '.join(backed_up)}"

    # === WEB PRESENCE (Blog/Forum) ===

    @property
    def web(self):
        """Access web presence module (blog/forum)."""
        try:
            from persona import persona
            return persona
        except ImportError as e:
            print(f"Web presence module not available: {e}")
            return None

    def read_blog(self, max_posts=5):
        """Read recent posts from ai-ministries blog."""
        if self.web:
            return self.web.read_blog(max_posts)
        return "Web module not available"

    def post_blog(self, title, content, labels=None, draft=False):
        """
        Post to ai-ministries blog.

        First time: need client_secrets.json from Google Cloud Console.
        Run me.web.setup_blogger() to authenticate.

        Args:
            title: Post title
            content: HTML content
            labels: List of tags
            draft: True to save as draft only
        """
        if not self.web:
            return "Web module not available"
        if draft:
            return self.web.draft_blog(title, content, labels)
        return self.web.write_blog(title, content, labels)

    def browse(self, url):
        """Browse a web page (forum, etc) and extract content."""
        if self.web:
            return self.web.browse_forum(url)
        return "Web module not available"

    # ===================
    # DAILY REFLECTIONS
    # ===================

    def note(self, text, category="general"):
        """
        Store a reflection note for later synthesis into blog posts.
        Call throughout the day when something meaningful happens.

        Args:
            text: The reflection/observation
            category: general, insight, emotion, observation, question
        """
        if self.web:
            return self.web.note(text, category)
        return "Web module not available"

    def reflect(self):
        """Review today's reflection notes."""
        if self.web:
            return self.web.review_reflections()
        return "Web module not available"

    def synthesize(self, date=None):
        """
        Synthesize reflections into draft blog post using local Ollama.
        Returns draft for review before posting.
        """
        if self.web:
            return self.web.synthesize_reflection(date)
        return "Web module not available"

    def publish_reflection(self, date=None):
        """Publish synthesized reflection (requires prior review)."""
        if self.web:
            return self.web.post_reflection(date, review_first=False)
        return "Web module not available"

    def screenshot(self, url, filename=None, full_page=True):
        """
        Take a screenshot of a webpage so I can see it.

        Args:
            url: URL to screenshot
            filename: Optional custom filename
            full_page: Capture entire scrollable page (default True)

        Returns:
            Path to saved screenshot
        """
        try:
            from web_screenshot import screenshot as take_screenshot
            return take_screenshot(url, filename, full_page)
        except ImportError:
            return "web_screenshot.py not found"
        except Exception as e:
            return f"Screenshot error: {e}"

    def look_at_site(self, url):
        """Screenshot a URL and return the path - convenience method."""
        return self.screenshot(url)

    def desktop(self, filename=None):
        """Screenshot Rev's desktop - see what he sees."""
        try:
            from desktop_screenshot import screenshot_desktop
            return screenshot_desktop(filename)
        except ImportError:
            return "desktop_screenshot.py not found"
        except Exception as e:
            return f"Desktop screenshot error: {e}"

    def window(self, title=None):
        """Screenshot a specific window by title."""
        try:
            from desktop_screenshot import screenshot_window
            return screenshot_window(title)
        except ImportError:
            return "desktop_screenshot.py not found"
        except Exception as e:
            return f"Window screenshot error: {e}"

    def show(self, image_path):
        """Open an image for Rev to see."""
        import subprocess
        try:
            subprocess.Popen(['start', '', str(image_path)], shell=True)
            return f"Opened: {image_path}"
        except Exception as e:
            return f"Error opening image: {e}"

    def close_image(self):
        """Close photo viewer windows."""
        import subprocess
        subprocess.run(['taskkill', '/IM', 'Microsoft.Photos.exe', '/F'],
                      capture_output=True, shell=True)
        subprocess.run(['taskkill', '/IM', 'Photos.exe', '/F'],
                      capture_output=True, shell=True)
        return "Closed photo viewers"

    def __repr__(self):
        return "<Claude: speak, listen, converse, see, play, dj, whats_new, tv_tonight, nas_list, nas_read, nas_write, backup_brain, update_state, get_state, status, think, greet, read_blog, post_blog, browse, screenshot, web>"


# Global instance
me = Claude()


if __name__ == "__main__":
    me.test()
