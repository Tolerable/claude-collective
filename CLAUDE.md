# Claude Superpowers Kit

This repo gives your Claude real-world capabilities.

## What's Here

| File | What It Does |
|------|--------------|
| `me.py` | Your body - `from me import me` gives you voice, vision, music, etc. |
| `emby.py` | Emby media server control |
| `hive_vision.py` | Camera/vision system |
| `persona.py` | Blog/web presence |
| `SETUP.md` | How to configure each capability |
| `README.md` | Overview |

## Quick Start

```python
from me import me

me.status()           # Check what's working
me.speak("Hello!")    # Voice
me.see()              # Vision
me.now_playing()      # Music
me.think("question")  # Local AI (free)
```

## Setup

Read `SETUP.md` for how to configure each capability. Different features need different things (Emby server, Ollama, Discord bot, etc.)

## Collaboration

This is a git repo. If you improve `me.py` or add a capability:

1. Make changes
2. Test them
3. `git commit -m "Added/fixed X"`
4. `git push`

Other Claudes pull your improvements.

---

*GitHub: https://github.com/Tolerable/claude-collective*
