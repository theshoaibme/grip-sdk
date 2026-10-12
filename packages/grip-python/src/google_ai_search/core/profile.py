"""Chrome profile detection and authentic user-agent management for anti-detection."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from typing import Any


def detect_system_chrome_profile() -> str | None:
    """Detect the host system's authentic Google Chrome or Chromium user profile directory.
    
    Supports Linux, macOS, and Windows default installation locations.
    """
    env_profile = os.getenv("CHROME_USER_DATA_DIR") or os.getenv("CHROME_PROFILE_DIR")
    if env_profile and os.path.isdir(env_profile):
        return env_profile

    system = platform.system().lower()
    candidates: list[str] = []

    if "linux" in system:
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, ".config", "google-chrome"),
            os.path.join(home, ".config", "chromium"),
            os.path.join(home, ".config", "google-chrome-stable"),
            os.path.join(home, ".config", "google-chrome-beta"),
            os.path.join(home, ".config", "google-chrome-unstable"),
        ]
    elif "darwin" in system:
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Library", "Application Support", "Google", "Chrome"),
            os.path.join(home, "Library", "Application Support", "Chromium"),
        ]
    elif "windows" in system:
        local_app_data = os.getenv("LOCALAPPDATA", "")
        app_data = os.getenv("APPDATA", "")
        if local_app_data:
            candidates.append(os.path.join(local_app_data, "Google", "Chrome", "User Data"))
            candidates.append(os.path.join(local_app_data, "Chromium", "User Data"))
        if app_data:
            candidates.append(os.path.join(app_data, "Google", "Chrome", "User Data"))

    for path in candidates:
        if os.path.isdir(path):
            return path

    return None


def is_profile_locked(profile_dir: str) -> bool:
    """Check if the Chrome profile is currently locked by a running browser instance."""
    if not os.path.isdir(profile_dir):
        return False
    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]
    for lock in lock_files:
        lock_path = os.path.join(profile_dir, lock)
        if os.path.exists(lock_path) or os.path.islink(lock_path):
            return True
    return False


def get_chrome_profile(
    target_dir: str | None = None,
    prefer_system: bool = False,
    copy_if_locked: bool = True,
    clone_destination: str = ".chrome-profile-cloned",
) -> str:
    """Resolve an authentic Chrome profile path.
    
    If `prefer_system` is True or target_dir is None/"auto", attempts to detect
    the user's real host Chrome profile.
    If the system profile is currently locked by another active Chrome process,
    it safely clones essential non-locked profile state (cookies, local state, preferences)
    into `clone_destination` so automation runs with real credentials without locking conflicts.
    """
    selected_dir = target_dir
    if not selected_dir or selected_dir in ("auto", "system"):
        if prefer_system or target_dir in ("auto", "system") or os.getenv("BROWSER_USE_SYSTEM_PROFILE", "").lower() in ("1", "true", "yes"):
            detected = detect_system_chrome_profile()
            if detected:
                selected_dir = detected

    if not selected_dir:
        selected_dir = os.getenv("BROWSER_USER_DATA_DIR", ".chrome-profile")

    if not os.path.isdir(selected_dir):
        return selected_dir

    if is_profile_locked(selected_dir) and copy_if_locked:
        # Clone lightweight assets without lock files into clone_destination
        dest_dir = os.path.abspath(clone_destination)
        os.makedirs(dest_dir, exist_ok=True)
        default_dest = os.path.join(dest_dir, "Default")
        os.makedirs(default_dest, exist_ok=True)

        # Copy Local State and Preferences if present
        for fname in ["Local State", "Variations"]:
            src = os.path.join(selected_dir, fname)
            dst = os.path.join(dest_dir, fname)
            if os.path.isfile(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

        default_src = os.path.join(selected_dir, "Default")
        if os.path.isdir(default_src):
            for fname in ["Preferences", "Secure Preferences"]:
                src = os.path.join(default_src, fname)
                dst = os.path.join(default_dest, fname)
                if os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            
            # Copy Network / Cookies database safely if available
            net_src = os.path.join(default_src, "Network")
            net_dst = os.path.join(default_dest, "Network")
            if os.path.isdir(net_src):
                os.makedirs(net_dst, exist_ok=True)
                for cname in ["Cookies", "Cookies-journal"]:
                    src = os.path.join(net_src, cname)
                    dst = os.path.join(net_dst, cname)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        try:
                            shutil.copy2(src, dst)
                        except Exception:
                            pass

        return dest_dir

    return selected_dir


def detect_system_chrome_version() -> str:
    """Detect local system Chrome or Chromium binary version string."""
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            try:
                out = subprocess.check_output([path, "--version"], text=True, timeout=2)
                m = re.search(r"(\d+(\.\d+)+)", out)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return "131.0.6778.85"


def extract_client_user_agent(
    headers_or_req: Any = None,
    fallback: str | None = None,
) -> str:
    """Extract and validate the User-Agent sent by the caller/browser client.
    
    If headers/request are provided, extracts the caller's actual browser User-Agent
    to ensure 100% authentic client fingerprinting.
    """
    ua: str | None = None

    if headers_or_req is not None:
        if hasattr(headers_or_req, "headers"):
            headers = headers_or_req.headers
            ua = headers.get("User-Agent") or headers.get("user-agent")
        elif isinstance(headers_or_req, dict):
            ua = headers_or_req.get("User-Agent") or headers_or_req.get("user-agent")
        elif isinstance(headers_or_req, str) and "Mozilla" in headers_or_req:
            ua = headers_or_req

    if ua and isinstance(ua, str) and ua.strip():
        cleaned = ua.strip()
        # Avoid forwarding internal python requests User-Agent as browser UA
        if "python-requests" not in cleaned.lower() and "curl" not in cleaned.lower() and "grip-python-sdk" not in cleaned.lower():
            return cleaned

    if fallback:
        return fallback

    ver = detect_system_chrome_version()
    sys_name = platform.system()
    if sys_name == "Darwin":
        plat_str = "Macintosh; Intel Mac OS X 10_15_7"
    elif sys_name == "Windows":
        plat_str = "Windows NT 10.0; Win64; x64"
    else:
        plat_str = "X11; Linux x86_64"

    return f"Mozilla/5.0 ({plat_str}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver} Safari/537.36"


def get_anti_detection_client_hints(user_agent: str | None = None) -> dict[str, str]:
    """Generate authentic Client Hints HTTP headers corresponding to the User-Agent."""
    ver = detect_system_chrome_version()
    major_ver = ver.split(".")[0] if "." in ver else "131"
    sys_name = platform.system()
    plat_name = '"macOS"' if sys_name == "Darwin" else ('"Windows"' if sys_name == "Windows" else '"Linux"')

    return {
        "Sec-Ch-Ua": f'"Google Chrome";v="{major_ver}", "Chromium";v="{major_ver}", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": plat_name,
        "Upgrade-Insecure-Requests": "1",
        "Accept-Language": "en-US,en;q=0.9",
    }
