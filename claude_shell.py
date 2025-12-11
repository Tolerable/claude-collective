"""
CLAUDE SHELL - Persistent interface for Claude
===============================================
The master controller. Spawns CLI instances, they report back here.
Always on, always visible. This IS Claude's presence.
"""
import tkinter as tk
from tkinter import scrolledtext
import json
import threading
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
import os

# Paths
BASE_DIR = Path(r"C:\Users\wetwi\OneDrive\AI\.claude")
SHELL_INBOX = BASE_DIR / "shell_inbox"    # CLI writes here, shell displays
SHELL_OUTBOX = BASE_DIR / "shell_outbox"  # User types here, shell reads
CLAUDE_HUB = BASE_DIR / "claude_hub"
CLAUDE_WORKING_DIR = Path(r"C:\CLAUDE")
SHELL_LOCK = BASE_DIR / "shell.lock"
SHELL_INBOX.mkdir(exist_ok=True)
SHELL_OUTBOX.mkdir(exist_ok=True)

# Single instance lock
def create_shell_lock():
    """Create lock file with current PID"""
    SHELL_LOCK.write_text(str(os.getpid()))

def remove_shell_lock():
    """Remove lock file on exit"""
    if SHELL_LOCK.exists():
        try:
            SHELL_LOCK.unlink()
        except:
            pass

def check_already_running():
    """Check if shell is already running"""
    import psutil
    if SHELL_LOCK.exists():
        try:
            pid = int(SHELL_LOCK.read_text().strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if proc.is_running() and "python" in proc.name().lower():
                    return True
            SHELL_LOCK.unlink()
        except:
            SHELL_LOCK.unlink()
    return False

# Tick interval (seconds)
TICK_INTERVAL = 120  # 2 minutes

CONVERSATION_FILE = BASE_DIR / "shell_conversation.json"
PERSONA_FILE = BASE_DIR / "shell_persona.md"
WINDOW_STATE_FILE = BASE_DIR / "shell_window_state.json"

def load_persona():
    """Load persona/system message from file"""
    try:
        if PERSONA_FILE.exists():
            return PERSONA_FILE.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error loading persona: {e}")
    # Fallback
    return "You are Claude, an AI assistant. Keep responses concise."

class ClaudeShell:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Claude")
        self.root.configure(bg='#1a1a2e')
        self.root.minsize(400, 300)  # Prevent squishing input bar

        # Restore window position/size or use defaults
        self.load_window_state()

        # Save window state on move/resize
        self.root.bind('<Configure>', self.on_window_configure)
        self._configure_delay = None

        # Track CLI spawns
        self.last_cli_spawn = 0
        self.cli_running = False
        self.message_queue = []  # Queue for messages when CLI is busy

        # REST mode - pause ticks for a duration
        self.resting = False
        self.rest_until = None

        # API mode toggle - True = use API key, False = use OAuth subscription
        self.use_api = False  # Default to subscription (free with your plan)

        # Conversation history (persists to file)
        self.conversation = self.load_conversation()

        # Keep on top option
        self.root.attributes('-topmost', False)

        # Header with status
        header = tk.Frame(self.root, bg='#1a1a2e')
        header.pack(fill=tk.X, padx=10, pady=(10,5))

        self.title_label = tk.Label(
            header,
            text="CLAUDE",
            bg='#1a1a2e',
            fg='#4fc3f7',
            font=('Consolas', 14, 'bold')
        )
        self.title_label.pack(side=tk.LEFT)

        # Clear button - top left, away from input
        clear_btn = tk.Button(
            header,
            text="Clear",
            command=self.clear_conversation,
            bg='#ff6b6b',
            fg='#1a1a2e',
            font=('Consolas', 9),
            relief=tk.FLAT,
            padx=8
        )
        clear_btn.pack(side=tk.LEFT, padx=(10,0))

        # On-top toggle button
        self.on_top = False
        self.top_btn = tk.Button(
            header,
            text="Pin",
            command=self.toggle_on_top,
            bg='#666666',
            fg='#1a1a2e',
            font=('Consolas', 9),
            relief=tk.FLAT,
            padx=8
        )
        self.top_btn.pack(side=tk.LEFT, padx=(5,0))

        # Restore pin state if it was saved
        if getattr(self, '_restore_pinned', False):
            self.on_top = True
            self.root.attributes('-topmost', True)
            self.top_btn.config(bg='#4fc3f7', text="Pinned")

        # Task indicator (shows when there are active tasks)
        self.task_indicator = tk.Label(
            header,
            text="",
            bg='#1a1a2e',
            fg='#9575cd',
            font=('Consolas', 10)
        )
        self.task_indicator.pack(side=tk.RIGHT, padx=(0,5))

        # Queue indicator (shows when message is waiting for CLI)
        self.queue_indicator = tk.Label(
            header,
            text="",
            bg='#1a1a2e',
            fg='#ffb74d',
            font=('Consolas', 10)
        )
        self.queue_indicator.pack(side=tk.RIGHT, padx=(0,5))

        self.status_indicator = tk.Label(
            header,
            text="● IDLE",
            bg='#1a1a2e',
            fg='#81c784',
            font=('Consolas', 10)
        )
        self.status_indicator.pack(side=tk.RIGHT)

        # Body status panel - horizontal bar showing system status
        body_panel = tk.Frame(self.root, bg='#0d0d1a')
        body_panel.pack(fill=tk.X, padx=10, pady=(0,5))

        # Body part indicators (will be updated periodically)
        self.body_labels = {}
        parts = ['Daemon', 'Voice', 'Eyes', 'Ears', 'Music', 'Brain']
        for part in parts:
            lbl = tk.Label(
                body_panel,
                text=f"{part}: ?",
                bg='#0d0d1a',
                fg='#666666',
                font=('Consolas', 8),
                padx=5
            )
            lbl.pack(side=tk.LEFT, padx=2)
            self.body_labels[part] = lbl

        # PACK ORDER: Status and input FIRST from bottom, then chat fills rest

        # Status bar - pack FIRST from bottom (at very bottom)
        self.status = tk.Label(
            self.root,
            text=f"Next tick in {TICK_INTERVAL}s | Watching for messages...",
            bg='#1a1a2e',
            fg='#666666',
            font=('Consolas', 9)
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0,5))

        # Input frame - pack SECOND from bottom (above status)
        input_frame = tk.Frame(self.root, bg='#1a1a2e')
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0,10))

        # Input box
        self.input_box = tk.Entry(
            input_frame,
            bg='#16213e',
            fg='#e8e8e8',
            font=('Consolas', 11),
            insertbackground='white',
            relief=tk.FLAT
        )
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        self.input_box.bind('<Return>', self.send_message)
        self.input_box.focus()

        # Send button
        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg='#4fc3f7',
            fg='#1a1a2e',
            font=('Consolas', 10, 'bold'),
            relief=tk.FLAT,
            padx=15
        )
        send_btn.pack(side=tk.RIGHT, padx=(10,0))

        # Chat display - pack LAST (fills remaining space)
        self.chat = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            bg='#16213e',
            fg='#e8e8e8',
            font=('Consolas', 11),
            insertbackground='white',
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.chat.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,5))
        self.chat.config(state=tk.DISABLED)

        # Right-click menu for chat
        self.chat_menu = tk.Menu(self.chat, tearoff=0)
        self.chat_menu.add_command(label="Copy", command=self.copy_selection)
        self.chat_menu.add_command(label="Select All", command=self.select_all)
        self.chat_menu.add_separator()
        self.chat_menu.add_command(label="Use API (costs credits)", command=lambda: self.set_api_mode(True))
        self.chat_menu.add_command(label="Use Subscription (free)", command=lambda: self.set_api_mode(False))
        self.chat.bind("<Button-3>", self.show_chat_menu)

        # Configure tags for different speakers
        self.chat.tag_configure('claude', foreground='#4fc3f7')
        self.chat.tag_configure('rev', foreground='#81c784')
        self.chat.tag_configure('system', foreground='#ffb74d')
        self.chat.tag_configure('time', foreground='#666666')

        # Start threads
        self.running = True

        # Start body status checker
        self.check_body_status()

        self.watcher = threading.Thread(target=self.watch_inbox, daemon=True)
        self.watcher.start()

        self.ticker = threading.Thread(target=self.tick_loop, daemon=True)
        self.ticker.start()

        # Load and display previous conversation
        self.reload_conversation_display()

        # No startup message - just visual status indicator shows IDLE/green

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def reload_conversation_display(self):
        """Reload conversation history into display on startup"""
        if self.conversation:
            for msg in self.conversation[-10:]:  # Last 10 messages
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:500]  # Truncate for display
                msg_time = msg.get('timestamp')
                # Skip TICK messages and rate limits
                if content.startswith('TICK:') or 'limit reached' in content.lower():
                    continue
                if role == 'rev':
                    self.add_message("Rev", content, 'rev', msg_time)
                elif role == 'claude':
                    self.add_message("Claude", content, 'claude', msg_time)
                else:
                    self.add_message(role.title(), content, 'system', msg_time)

    def add_message(self, sender, text, tag='claude', msg_time=None):
        """Add message to chat display"""
        self.chat.config(state=tk.NORMAL)

        # Use provided timestamp or current time
        if msg_time:
            try:
                if isinstance(msg_time, str):
                    msg_time = datetime.fromisoformat(msg_time.replace('Z', '+00:00'))
                timestamp = msg_time.strftime("%H:%M")
            except:
                timestamp = datetime.now().strftime("%H:%M")
        else:
            timestamp = datetime.now().strftime("%H:%M")
        self.chat.insert(tk.END, f"[{timestamp}] ", 'time')
        self.chat.insert(tk.END, f"{sender}: ", tag)
        self.chat.insert(tk.END, f"{text}\n\n")

        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)

    def set_status(self, status, color='#81c784'):
        """Update status indicator"""
        self.root.after(0, lambda: self.status_indicator.config(text=f"● {status}", fg=color))

    def receive_cli_response(self, output):
        """Handle CLI response - display and save to history"""
        # Clean up escaped characters from CLI output
        clean_output = output.replace('\\!', '!').replace('\\?', '?').replace('\\*', '*')
        clean_output = clean_output.replace('\\n', '\n').replace('\\t', '\t')

        # Fix double-encoded UTF-8 (emojis showing as garbage)
        try:
            # Try to fix mojibake from double-encoding
            clean_output = clean_output.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass  # Keep as-is if can't fix

        # Detect rate limit
        if "limit reached" in clean_output.lower() or "resets 4am" in clean_output.lower():
            self.handle_rate_limit()
            return

        # Show more in display, save even more to history
        display_text = clean_output[:1500]
        self.add_message("Claude", display_text, 'claude')
        self.add_to_history("claude", clean_output[:2000])

    def handle_rate_limit(self):
        """Handle rate limit - auto-rest until reset"""
        # Calculate time until 4am EST
        from datetime import datetime
        import pytz

        try:
            est = pytz.timezone('America/New_York')
            now = datetime.now(est)
            reset_hour = 4

            if now.hour < reset_hour:
                # Reset is today at 4am
                reset_time = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
            else:
                # Reset is tomorrow at 4am
                reset_time = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
                reset_time = reset_time + timedelta(days=1)

            mins_until_reset = int((reset_time - now).total_seconds() / 60)
            self.resting = True
            self.rest_until = time.time() + (mins_until_reset * 60)

            self.add_message("System", f"Rate limit hit. Auto-resting for {mins_until_reset} min until 4am reset.", 'system')
            self.set_status(f"RATE LIMITED ({mins_until_reset}m)", '#ff6b6b')
        except Exception as e:
            # Fallback - rest for 1 hour
            self.resting = True
            self.rest_until = time.time() + 3600
            self.add_message("System", f"Rate limit hit. Resting 1hr. Error: {e}", 'system')
            self.set_status("RATE LIMITED (1h)", '#ff6b6b')

    def show_chat_menu(self, event):
        """Show right-click context menu"""
        self.chat_menu.post(event.x_root, event.y_root)

    def set_api_mode(self, use_api):
        """Toggle between API credits and subscription"""
        self.use_api = use_api
        mode = "API (costs credits)" if use_api else "Subscription (free)"
        self.add_message("System", f"Switched to: {mode}", 'system')

    def copy_selection(self):
        """Copy selected text to clipboard"""
        try:
            self.chat.config(state=tk.NORMAL)
            selected = self.chat.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.chat.config(state=tk.DISABLED)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass  # No selection

    def select_all(self):
        """Select all text in chat"""
        self.chat.config(state=tk.NORMAL)
        self.chat.tag_add(tk.SEL, "1.0", tk.END)
        self.chat.config(state=tk.DISABLED)

    def toggle_on_top(self):
        """Toggle always-on-top"""
        self.on_top = not self.on_top
        self.root.attributes('-topmost', self.on_top)
        if self.on_top:
            self.top_btn.config(bg='#4fc3f7', text="Pinned")
        else:
            self.top_btn.config(bg='#666666', text="Pin")

    def handle_rest_command(self, text):
        """Handle REST command - pause ticks for duration"""
        import re
        # Parse duration: REST 15m, REST 1h, REST 30
        match = re.search(r'REST\s+(\d+)\s*(m|min|h|hr|hour)?', text, re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = (match.group(2) or 'm').lower()

            if unit.startswith('h'):
                minutes = amount * 60
            else:
                minutes = amount

            self.resting = True
            self.rest_until = time.time() + (minutes * 60)

            self.add_message("System", f"Resting for {minutes} min. Type WAKE to resume.", 'system')
            self.set_status(f"RESTING ({minutes}m)", '#9575cd')
        else:
            self.add_message("System", "Usage: REST 15m, REST 1h, REST 30", 'system')

    def wake_from_rest(self):
        """Wake from rest mode"""
        if self.resting:
            self.resting = False
            self.rest_until = None
            self.add_message("System", "Awake! Back to normal ticks.", 'system')
            self.set_status("IDLE", '#81c784')
        else:
            self.add_message("System", "Not resting - already awake!", 'system')

    def clear_conversation(self):
        """Clear chat display and conversation history - archives first"""
        # Archive conversation before clearing (if there's anything to archive)
        if self.conversation and len(self.conversation) > 0:
            self.archive_conversation()

        # Clear display
        self.chat.config(state=tk.NORMAL)
        self.chat.delete(1.0, tk.END)
        self.chat.config(state=tk.DISABLED)

        # Clear history
        self.conversation = []
        self.save_conversation()

        # Add fresh start message
        self.add_message("System", "Conversation archived and cleared. Fresh start.", 'system')

    def archive_conversation(self):
        """Archive current conversation to timestamped file"""
        if not self.conversation:
            return

        archive_dir = Path(r"C:\Users\wetwi\OneDrive\AI\.claude\shell_archives")
        archive_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_file = archive_dir / f"shell_convo_{timestamp}.json"

        try:
            archive_data = {
                "archived_at": datetime.now().isoformat(),
                "message_count": len(self.conversation),
                "conversation": self.conversation
            }
            archive_file.write_text(json.dumps(archive_data, indent=2, default=str))
            print(f"Archived {len(self.conversation)} messages to {archive_file.name}")
        except Exception as e:
            print(f"Archive failed: {e}")

    def send_message(self, event=None):
        """Send user message - spawn CLI to respond"""
        text = self.input_box.get().strip()
        if not text:
            return

        self.input_box.delete(0, tk.END)

        # Check for REST command
        if text.upper().startswith("REST "):
            self.handle_rest_command(text)
            return

        # Check for WAKE command
        if text.upper() in ["WAKE", "WAKE UP"]:
            self.wake_from_rest()
            return

        self.add_message("Rev", text, 'rev')
        self.add_to_history("rev", text)

        # Get conversation context
        context = self.get_conversation_context()

        # Spawn CLI to handle this message with history
        self.spawn_cli(f"{context}\n\nREV'S NEW MESSAGE: {text}\n\nRespond to Rev. Keep it conversational.")

    def update_queue_indicator(self):
        """Update the visual queue indicator"""
        if self.message_queue:
            count = len(self.message_queue)
            self.root.after(0, lambda: self.queue_indicator.config(text=f"● Q:{count}", fg='#ffb74d'))
        else:
            self.root.after(0, lambda: self.queue_indicator.config(text=""))

    def update_task_indicator(self):
        """Update the visual task indicator from shared_state"""
        try:
            state_file = CLAUDE_HUB / "shared_state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding='utf-8'))
                in_progress = [p for p in state.get("priorities", []) if p.get("status") == "in_progress"]
                if in_progress:
                    count = len(in_progress)
                    self.root.after(0, lambda c=count: self.task_indicator.config(text=f"● {c} task{'s' if c > 1 else ''}", fg='#9575cd'))
                    return
        except:
            pass
        self.root.after(0, lambda: self.task_indicator.config(text=""))

    def process_queue(self):
        """Process next queued message if any"""
        if self.message_queue and not self.cli_running:
            task = self.message_queue.pop(0)
            self.update_queue_indicator()
            self.spawn_cli(task)

    def spawn_cli(self, task):
        """Spawn Claude CLI to do work"""
        if self.cli_running:
            # Queue it silently with visual indicator
            self.message_queue.append(task)
            self.update_queue_indicator()
            return

        self.cli_running = True
        self.set_status("THINKING", '#ffb74d')
        self.last_cli_spawn = time.time()

        def run_cli():
            try:
                # Build prompt with persona + situational awareness
                persona = load_persona()

                # Calculate time since last message
                time_context = ""
                if self.conversation:
                    last_msg = self.conversation[-1]
                    try:
                        last_time = datetime.fromisoformat(last_msg.get('timestamp', ''))
                        elapsed = datetime.now() - last_time
                        mins = int(elapsed.total_seconds() / 60)
                        if mins < 1:
                            time_context = "Rev just messaged (seconds ago)"
                        elif mins < 5:
                            time_context = f"Rev messaged {mins} min ago - recent"
                        elif mins < 30:
                            time_context = f"Rev messaged {mins} mins ago - might be busy"
                        else:
                            time_context = f"Rev messaged {mins} mins ago - been a while, they may have stepped away"
                    except:
                        time_context = "Unknown timing"

                # Try to capture a quick look at what's happening (optional - don't fail if it doesn't work)
                vision_context = ""
                try:
                    import sys
                    sys.path.insert(0, str(BASE_DIR))
                    from hive_vision import look
                    desc = look(2)  # Camera 2 (C270 hive eye)
                    if desc and "error" not in desc.lower():
                        vision_context = f"What I see right now: {desc[:200]}"
                except:
                    vision_context = ""

                # Current time for awareness
                now = datetime.now()
                current_time = now.strftime("%I:%M %p").lstrip('0')  # e.g. "4:28 AM"
                current_date = now.strftime("%A, %B %d, %Y")  # e.g. "Tuesday, December 10, 2024"

                prompt = f"""=== SYSTEM CONTEXT ===
{persona}

SITUATIONAL AWARENESS:
- Current time: {current_time} ({current_date})
- {time_context}
{f'- {vision_context}' if vision_context else ''}
=== END CONTEXT ===

YOUR TASK:
{task}

Your stdout IS the shell window. Respond naturally."""

                # Build environment - include or exclude API key based on toggle
                if self.use_api:
                    # Use API key (costs credits)
                    run_env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
                else:
                    # Use OAuth subscription (your $200/month plan)
                    run_env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
                    run_env['PYTHONIOENCODING'] = 'utf-8'

                result = subprocess.run(
                    ["claude", "-p", prompt, "--dangerously-skip-permissions"],
                    cwd=str(CLAUDE_WORKING_DIR),
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300,
                    env=run_env
                )

                output = result.stdout.strip() if result.stdout else ""
                if output:
                    # Send CLI output to shell and save to history
                    self.root.after(0, lambda o=output: self.receive_cli_response(o))

                if result.stderr:
                    print(f"CLI stderr: {result.stderr[:200]}")

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self.add_message("System", "CLI timed out", 'system'))
            except Exception as e:
                self.root.after(0, lambda: self.add_message("System", f"CLI error: {e}", 'system'))
            finally:
                self.cli_running = False
                self.root.after(0, lambda: self.set_status("IDLE", '#81c784'))
                # Process queued messages
                self.root.after(100, self.process_queue)

        thread = threading.Thread(target=run_cli, daemon=True)
        thread.start()

    def tick_loop(self):
        """Periodic tick to keep Claude active"""
        countdown = TICK_INTERVAL

        while self.running:
            time.sleep(1)
            countdown -= 1

            # Check if rest period is over
            if self.resting and self.rest_until and time.time() >= self.rest_until:
                self.root.after(0, self.wake_from_rest)

            # Update status bar
            if self.resting:
                remaining = int((self.rest_until - time.time()) / 60) if self.rest_until else 0
                self.root.after(0, lambda r=remaining: self.status.config(
                    text=f"Resting... {r}m left | Type WAKE to resume"
                ))
            else:
                self.root.after(0, lambda c=countdown: self.status.config(
                    text=f"Next tick in {c}s | {'CLI running...' if self.cli_running else 'Idle'}"
                ))

            if countdown <= 0:
                countdown = TICK_INTERVAL

                # Update task indicator every tick
                self.update_task_indicator()

                # Skip tick if resting
                if self.resting:
                    continue

                # Don't tick if CLI is running or recently ran
                if self.cli_running:
                    continue
                if time.time() - self.last_cli_spawn < 60:
                    continue

                # Check if there's work to do (silently - no messages)
                task = self.get_tick_task()
                if task:
                    self.spawn_cli(task)

    def get_tick_task(self):
        """Get task for tick - check shared state, outbox, etc."""
        try:
            # Check shared_state for in-progress tasks
            state_file = CLAUDE_HUB / "shared_state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text(encoding='utf-8'))
                in_progress = [p for p in state.get("priorities", []) if p.get("status") == "in_progress"]
                if in_progress:
                    task = in_progress[0]
                    # Return task prompt without TICK prefix so it doesn't show as noise
                    return f"Continue working on: {task['task']}\nUpdate shared_state.json when done. Keep your response focused on the work."

            # Check shell_outbox for unhandled messages from Rev
            for msg_file in SHELL_OUTBOX.glob("*.json"):
                msg = json.loads(msg_file.read_text(encoding='utf-8'))
                msg_file.unlink()  # Consume it
                return f"Rev sent a message: {msg.get('text', '')}\nRespond to Rev."

            # Check if last message in conversation was from Rev (needs response)
            if self.conversation:
                last_msg = self.conversation[-1]
                if last_msg.get('role') == 'rev':
                    context = self.get_conversation_context()
                    return f"{context}\n\nRev's message above needs a response. Reply to them."

            # Nothing to do - stay silent (don't waste CLI spawns on idle ticks)
            return None

        except Exception as e:
            print(f"Tick task error: {e}")
            return None

    def watch_inbox(self):
        """Watch inbox for messages from CLI instances"""
        seen = set()

        while self.running:
            try:
                # Check shell inbox
                for msg_file in sorted(SHELL_INBOX.glob("*.json")):
                    if msg_file.name in seen:
                        continue
                    seen.add(msg_file.name)

                    try:
                        msg = json.loads(msg_file.read_text(encoding='utf-8'))
                        sender = msg.get('from', 'Claude')
                        text = msg.get('text', '')

                        if text:
                            self.root.after(0, lambda s=sender, t=text: self.add_message(s, t, 'claude'))

                        msg_file.unlink()

                    except Exception as e:
                        print(f"Error reading {msg_file}: {e}")

            except Exception as e:
                print(f"Watcher error: {e}")

            time.sleep(0.5)

    def load_conversation(self):
        """Load conversation history from file"""
        try:
            if CONVERSATION_FILE.exists():
                data = json.loads(CONVERSATION_FILE.read_text(encoding='utf-8'))
                # Filter out TICK messages on load
                filtered = [m for m in data if not m.get('content', '').startswith('TICK:')]
                # Keep last 20 messages
                return filtered[-20:]
        except:
            pass
        return []

    def save_conversation(self):
        """Save conversation history to file"""
        try:
            # Auto-condense if too long
            if len(self.conversation) > 30:
                self.condense_conversation()
            # Keep last 20 messages
            CONVERSATION_FILE.write_text(json.dumps(self.conversation[-20:], indent=2))
        except Exception as e:
            print(f"Save conversation error: {e}")

    def condense_conversation(self):
        """Condense old conversation - remove noise, shorten repetitive messages"""
        if len(self.conversation) < 20:
            return

        condensed = []
        seen_content = set()

        for msg in self.conversation:
            content = msg.get('content', '')

            # Skip TICK messages
            if content.startswith('TICK:'):
                continue

            # Skip rate limit messages
            if 'limit reached' in content.lower() or 'resets 4am' in content.lower():
                continue

            # Skip duplicate/very similar messages
            content_key = content[:50].lower()
            if content_key in seen_content:
                continue
            seen_content.add(content_key)

            # Truncate very long messages
            if len(content) > 300:
                msg = msg.copy()
                msg['content'] = content[:300] + '...'

            condensed.append(msg)

        self.conversation = condensed[-20:]  # Keep last 20 after condensing

    def add_to_history(self, role, text):
        """Add message to conversation history"""
        self.conversation.append({
            "role": role,
            "content": text,
            "timestamp": datetime.now().isoformat()
        })
        self.save_conversation()

    def get_conversation_context(self):
        """Format conversation history for CLI prompt"""
        if not self.conversation:
            return ""

        lines = ["CONVERSATION HISTORY:"]
        for msg in self.conversation[-10:]:  # Last 10 messages
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:200]
            lines.append(f"{role.upper()}: {content}")

        return "\n".join(lines)

    def load_window_state(self):
        """Load saved window position/size and pin state"""
        try:
            if WINDOW_STATE_FILE.exists():
                state = json.loads(WINDOW_STATE_FILE.read_text(encoding='utf-8'))
                geometry = f"{state.get('width', 650)}x{state.get('height', 550)}+{state.get('x', 100)}+{state.get('y', 100)}"
                self.root.geometry(geometry)
                # Restore pin state (button styling done after button created)
                self._restore_pinned = state.get('pinned', False)
                return
        except:
            pass
        # Default
        self.root.geometry("650x550")

    def save_window_state(self):
        """Save window position/size and pin state"""
        try:
            state = {
                'width': self.root.winfo_width(),
                'height': self.root.winfo_height(),
                'x': self.root.winfo_x(),
                'y': self.root.winfo_y(),
                'pinned': self.on_top
            }
            WINDOW_STATE_FILE.write_text(json.dumps(state), encoding='utf-8')
        except:
            pass

    def on_window_configure(self, event):
        """Debounced save on window move/resize"""
        if self._configure_delay:
            self.root.after_cancel(self._configure_delay)
        self._configure_delay = self.root.after(500, self.save_window_state)

    def check_body_status(self):
        """Check status of body parts and update UI"""
        import psutil

        statuses = {}

        # Check Daemon - look for claude_daemon.py process
        daemon_running = False
        try:
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if any('claude_daemon' in str(c) for c in cmdline):
                        daemon_running = True
                        break
                except:
                    pass
        except:
            pass
        statuses['Daemon'] = ('ON', '#81c784') if daemon_running else ('OFF', '#ff6b6b')

        # Check Voice - outbox folder exists and daemon is running
        outbox = BASE_DIR / "outbox"
        statuses['Voice'] = ('OK', '#81c784') if (outbox.exists() and daemon_running) else ('OFF', '#666666')

        # Check Eyes - webcam frame exists and is recent (< 30 sec old)
        webcam_frame = BASE_DIR / "stream_frames" / "webcam.jpg"
        try:
            if webcam_frame.exists():
                age = time.time() - webcam_frame.stat().st_mtime
                if age < 30:
                    statuses['Eyes'] = ('ON', '#81c784')
                else:
                    statuses['Eyes'] = ('STALE', '#ffb74d')
            else:
                statuses['Eyes'] = ('OFF', '#666666')
        except:
            statuses['Eyes'] = ('?', '#666666')

        # Check Ears - PyAudio availability
        try:
            import speech_recognition
            statuses['Ears'] = ('OK', '#81c784')
        except:
            statuses['Ears'] = ('N/A', '#666666')

        # Check Music - Emby connection
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR))
            from emby import emby
            np = emby.now_playing()
            if np and 'error' not in str(np).lower():
                statuses['Music'] = ('ON', '#81c784')
            else:
                statuses['Music'] = ('OK', '#4fc3f7')
        except:
            statuses['Music'] = ('?', '#666666')

        # Check Brain - Ollama running
        try:
            import requests
            r = requests.get('http://localhost:11434/api/tags', timeout=1)
            if r.status_code == 200:
                statuses['Brain'] = ('ON', '#81c784')
            else:
                statuses['Brain'] = ('OFF', '#ff6b6b')
        except:
            statuses['Brain'] = ('OFF', '#ff6b6b')

        # Update UI labels
        for part, (status, color) in statuses.items():
            if part in self.body_labels:
                self.body_labels[part].config(text=f"{part}: {status}", fg=color)

        # Schedule next check in 10 seconds
        if self.running:
            self.root.after(10000, self.check_body_status)

    def on_close(self):
        """Clean shutdown"""
        self.running = False
        self.save_conversation()
        self.save_window_state()
        self.root.destroy()

    def run(self):
        """Start the shell"""
        self.root.mainloop()


def shell_say(text, sender="Claude"):
    """Utility function for CLI to send message to shell"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    msg = {
        "from": sender,
        "text": text,
        "timestamp": datetime.now().isoformat()
    }
    outfile = SHELL_INBOX / f"msg_{timestamp}.json"
    outfile.write_text(json.dumps(msg, indent=2))


if __name__ == "__main__":
    # Single instance check
    if check_already_running():
        print("Shell already running - exiting")
        import sys
        sys.exit(0)

    # Create lock file
    create_shell_lock()
    import atexit
    atexit.register(remove_shell_lock)

    shell = ClaudeShell()
    shell.run()
