"""
Desktop Screenshot Tool - Capture what's on Rev's screen
Usage:
    from desktop_screenshot import screenshot_desktop
    screenshot_desktop()  # Full screen
    screenshot_desktop(region=(0, 0, 800, 600))  # Region
"""
import os
from pathlib import Path
from datetime import datetime

SCREENSHOT_DIR = Path(r"C:\Users\wetwi\OneDrive\AI\.claude\screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

def screenshot_desktop(filename=None, region=None):
    """
    Take a screenshot of the desktop.

    Args:
        filename: Optional custom filename
        region: Optional tuple (x, y, width, height) for partial screenshot

    Returns:
        Path to saved screenshot
    """
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Pillow not installed. Run: py -3.12 -m pip install Pillow"

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"desktop_{timestamp}.png"

    output_path = SCREENSHOT_DIR / filename

    if region:
        # Region screenshot: (left, top, right, bottom)
        x, y, w, h = region
        img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
    else:
        # Full screen
        img = ImageGrab.grab()

    img.save(str(output_path))
    print(f"Desktop screenshot saved: {output_path}")
    return str(output_path)


def screenshot_window(window_title=None):
    """
    Screenshot a specific window by title.

    Args:
        window_title: Part of window title to match (case insensitive)

    Returns:
        Path to saved screenshot or error message
    """
    try:
        import pygetwindow as gw
        from PIL import ImageGrab
    except ImportError:
        return "Missing deps. Run: py -3.12 -m pip install Pillow pygetwindow"

    if window_title:
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            return f"No window found matching '{window_title}'"
        win = windows[0]
        # Bring to front
        try:
            win.activate()
        except:
            pass
        import time
        time.sleep(0.3)
        region = (win.left, win.top, win.right, win.bottom)
        img = ImageGrab.grab(bbox=region)
    else:
        # Active window
        try:
            win = gw.getActiveWindow()
            region = (win.left, win.top, win.right, win.bottom)
            img = ImageGrab.grab(bbox=region)
        except:
            img = ImageGrab.grab()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in (window_title or "active") if c.isalnum())[:20]
    filename = f"window_{safe_title}_{timestamp}.png"
    output_path = SCREENSHOT_DIR / filename

    img.save(str(output_path))
    print(f"Window screenshot saved: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = screenshot_window(sys.argv[1])
    else:
        path = screenshot_desktop()
    print(f"Done: {path}")
