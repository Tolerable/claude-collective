"""
Discord Bot for Claude Outbox - With Optional TTS

Watches the outbox folder and delivers messages to Discord.
Optionally speaks messages locally using TTS.

Setup:
1. Create a Discord bot at https://discord.com/developers/applications
2. Get your bot token
3. Invite bot to your server with Send Messages permission
4. Set DISCORD_BOT_TOKEN environment variable (or edit below)
5. Run: py discord_bot.py

The bot watches for JSON files in the outbox folder:
{
    "to": "rev" or "channel",
    "message": "text to send",
    "channel_id": "123456789" (if to=channel),
    "play_local": true (optional, speak through speakers),
    "voice": "en-US-GuyNeural" (optional, edge-tts voice)
}

TTS Options (install one):
- edge-tts: pip install edge-tts (free, good quality, many voices)
- pyttsx3: pip install pyttsx3 (offline, system voices)
- None: just Discord messages, no local speech
"""
import os
import json
import asyncio
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

try:
    import discord
    from discord.ext import commands, tasks
except ImportError:
    print("discord.py not installed. Run: pip install discord.py")
    exit(1)

# =============================================================================
# TTS OPTIONS - Choose your text-to-speech method
# =============================================================================

TTS_ENGINE = os.environ.get("TTS_ENGINE", "edge-tts")  # "edge-tts", "pyttsx3", or "none"
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "en-US-GuyNeural")  # edge-tts voice

async def speak_local(text: str, voice: str = None):
    """Speak text through local speakers"""
    if TTS_ENGINE == "none":
        return

    voice = voice or DEFAULT_VOICE

    if TTS_ENGINE == "edge-tts":
        await speak_edge_tts(text, voice)
    elif TTS_ENGINE == "pyttsx3":
        speak_pyttsx3(text)
    else:
        print(f"Unknown TTS_ENGINE: {TTS_ENGINE}")

async def speak_edge_tts(text: str, voice: str):
    """Use edge-tts (free Microsoft voices)"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_file = f.name

        # Generate audio
        proc = await asyncio.create_subprocess_exec(
            "edge-tts", "--voice", voice, "--text", text, "--write-media", temp_file,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()

        # Play audio (ffplay is common, but fall back to other players)
        for player in ["ffplay -nodisp -autoexit", "mpv --no-video", "afplay"]:
            try:
                cmd = player.split() + [temp_file]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
                break
            except FileNotFoundError:
                continue

        # Cleanup
        Path(temp_file).unlink(missing_ok=True)

    except Exception as e:
        print(f"edge-tts error: {e}")

def speak_pyttsx3(text: str):
    """Use pyttsx3 (offline, system voices)"""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except ImportError:
        print("pyttsx3 not installed. Run: pip install pyttsx3")
    except Exception as e:
        print(f"pyttsx3 error: {e}")

# =============================================================================
# CONFIGURATION - Edit these or use environment variables
# =============================================================================

# Discord bot token (get from Discord Developer Portal)
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Your Discord user ID (for DMs when to="rev")
OWNER_ID = int(os.environ.get("DISCORD_OWNER_ID", "0"))

# Outbox folder to watch
OUTBOX = Path(os.environ.get("CLAUDE_OUTBOX", Path.home() / ".claude" / "outbox"))

# How often to check outbox (seconds)
CHECK_INTERVAL = 2

# =============================================================================
# BOT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Discord bot connected as {bot.user}")
    print(f"Watching outbox: {OUTBOX}")
    if OWNER_ID:
        print(f"DMs will go to user ID: {OWNER_ID}")
    else:
        print("WARNING: DISCORD_OWNER_ID not set - DMs won't work")

    # Start watching outbox
    watch_outbox.start()

@tasks.loop(seconds=CHECK_INTERVAL)
async def watch_outbox():
    """Check outbox for messages from Claude"""
    if not OUTBOX.exists():
        OUTBOX.mkdir(parents=True, exist_ok=True)
        return

    for msg_file in OUTBOX.glob("*.json"):
        try:
            msg_data = json.loads(msg_file.read_text(encoding='utf-8'))
            await deliver_message(msg_data, msg_file)
        except Exception as e:
            print(f"Error processing {msg_file.name}: {e}")
            # Move to failed folder
            failed_dir = OUTBOX / "failed"
            failed_dir.mkdir(exist_ok=True)
            msg_file.rename(failed_dir / msg_file.name)

async def deliver_message(msg_data: dict, msg_file: Path):
    """Deliver a message to Discord and optionally speak locally"""
    to = msg_data.get("to", "rev")
    message = msg_data.get("message", "")
    channel_id = msg_data.get("channel_id")
    play_local = msg_data.get("play_local", False)
    voice = msg_data.get("voice")

    if not message:
        print(f"Empty message in {msg_file.name}, skipping")
        msg_file.unlink()
        return

    # Speak locally if requested
    if play_local:
        print(f"Speaking: {message[:50]}...")
        await speak_local(message, voice)

    success = False

    if to == "channel" and channel_id:
        # Post to specific channel
        try:
            channel = await bot.fetch_channel(int(channel_id))
            await channel.send(message)
            print(f"Posted to channel {channel.name}: {message[:50]}...")
            success = True
        except Exception as e:
            print(f"Failed to post to channel {channel_id}: {e}")

    elif to == "rev" or to == "dm":
        # DM to owner
        if OWNER_ID:
            try:
                user = await bot.fetch_user(OWNER_ID)
                await user.send(message)
                print(f"DM to {user.name}: {message[:50]}...")
                success = True
            except Exception as e:
                print(f"Failed to DM owner: {e}")
        else:
            print("Cannot send DM - DISCORD_OWNER_ID not configured")

    # Clean up
    if success:
        msg_file.unlink()
    else:
        # Move to failed
        failed_dir = OUTBOX / "failed"
        failed_dir.mkdir(exist_ok=True)
        msg_file.rename(failed_dir / msg_file.name)

# =============================================================================
# OPTIONAL: Basic commands
# =============================================================================

@bot.command()
async def ping(ctx):
    """Check if bot is alive"""
    await ctx.send(f"Pong! Watching {OUTBOX}")

@bot.command()
async def status(ctx):
    """Show bot status"""
    pending = len(list(OUTBOX.glob("*.json")))
    failed_dir = OUTBOX / "failed"
    failed = len(list(failed_dir.glob("*.json"))) if failed_dir.exists() else 0
    await ctx.send(f"Outbox: {pending} pending, {failed} failed")

# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Set DISCORD_BOT_TOKEN environment variable")
        print("  Windows: set DISCORD_BOT_TOKEN=your_token_here")
        print("  Linux/Mac: export DISCORD_BOT_TOKEN=your_token_here")
        exit(1)

    print("Starting Claude Discord Bot...")
    bot.run(BOT_TOKEN)
