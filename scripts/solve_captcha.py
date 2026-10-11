#!/usr/bin/env python3
"""One-time visible browser verification script to clear Google CAPTCHA."""

import os
import sys
import time
from playwright.sync_api import sync_playwright

from google_ai_search.config import get_config
from google_ai_search.core.engine import _STEALTH_JS, _get_user_agent

cfg = get_config()
USER_DATA_DIR = cfg.browser_user_data_dir or ".chrome-profile"
TARGET_URL = "https://www.google.com/search?q=AI&udm=50"


def main():
    print(f"🚀 Launching visible Google Chrome with profile: '{USER_DATA_DIR}'...")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    ua = _get_user_agent(cfg)

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--window-size=1920,1080",
        "--start-maximized",
    ]

    with sync_playwright() as p:
        common = {
            "headless": False,
            "channel": cfg.browser_channel or "chrome",
            "args": launch_args,
            "ignore_default_args": ["--enable-automation"],
            "locale": cfg.browser_lang or "en-US",
            "user_agent": ua,
            "viewport": {"width": 1920, "height": 1080},
        }
        if cfg.proxy_server:
            p_dict = {"server": cfg.proxy_server}
            if cfg.proxy_username:
                p_dict["username"] = cfg.proxy_username
            if cfg.proxy_password:
                p_dict["password"] = cfg.proxy_password
            common["proxy"] = p_dict

        context = p.chromium.launch_persistent_context(USER_DATA_DIR, **common)
        context.add_init_script(_STEALTH_JS)

        page = context.pages[0] if context.pages else context.new_page()
        print(f"🌐 Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")

        # Try auto-clicking consent
        for btn_text in ["Accept all", "I agree", "Agree to all", "Accept", "Got it"]:
            try:
                b = page.get_by_role("button", name=btn_text, exact=False)
                if b.count() > 0:
                    b.first.click(timeout=1500)
                    print(f"Clicked '{btn_text}' consent button.")
                    break
            except Exception:
                pass

        time.sleep(2)

        # Check if blocked by CAPTCHA
        blocked = (
            "google.com/sorry" in page.url
            or page.locator("#captcha-form, .g-recaptcha, #recaptcha").count() > 0
        )

        if blocked:
            print("\n" + "=" * 65)
            print("⚠️  CAPTCHA DETECTED ON SCREEN")
            print("Please complete the Google verification puzzle in the Chrome window.")
            print("This script will automatically detect when you finish.")
            print("=" * 65 + "\n")

            start = time.time()
            while time.time() - start < 180:
                time.sleep(1.5)
                if (
                    "google.com/sorry" not in page.url
                    and page.locator("#captcha-form, .g-recaptcha, #recaptcha").count() == 0
                ):
                    print("✅ Verification solved successfully!")
                    break
            else:
                print("❌ Timed out waiting for CAPTCHA resolution.")
                context.close()
                sys.exit(1)
        else:
            print("✅ No CAPTCHA encountered! Profile is clean.")

        time.sleep(2)
        context.close()
        print(f"💾 Persistent cookies saved to '{USER_DATA_DIR}'.")
        print("You can now run in headless mode (BROWSER_HEADLESS=1) without blocks.\n")


if __name__ == "__main__":
    main()
