"""
Minimal Discord Bot for Claude Outbox

Watches the outbox folder and delivers messages to Discord.
This is the bridge between Claude's me.speak()/me.post_to_channel() and Discord.

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
    "voice": "Gloop" (optional, for TTS)
}
"""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

try:
    import discord
    from discord.ext import commands, tasks
except ImportError:
    print("discord.py not installed. Run: pip install discord.py")
    exit(1)

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
    """Deliver a message to Discord"""
    to = msg_data.get("to", "rev")
    message = msg_data.get("message", "")
    channel_id = msg_data.get("channel_id")

    if not message:
        print(f"Empty message in {msg_file.name}, skipping")
        msg_file.unlink()
        return

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
