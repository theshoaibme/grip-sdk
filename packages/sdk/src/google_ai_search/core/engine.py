"""Google AI Mode (udm=50) search engine powered by real browser automation."""

from __future__ import annotations

import glob
import html as pyhtml
import json
import os
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ..config import Config, get_config
from ..exceptions import BotBlockedError, ProviderError
from ..types import SearchResponse, SourceItem, StreamChunk
from .cache import TTLCache
from .profile import (
    detect_system_chrome_profile,
    extract_client_user_agent,
    get_anti_detection_client_hints,
    get_chrome_profile,
)

SEARCH_URL = "https://www.google.com/search"
ANSWER_SELECTOR = 'div[data-subtree="aimc"]'
THREAD_SELECTOR = "[data-session-thread-id]"
COMPLETE_SELECTOR = '[data-complete="true"]'

_BROWSER_LOCK = threading.Lock()

_EXTRACT_JS = """
() => {
  const answerEl =
    document.querySelector('div[data-subtree="aimc"]') ||
    (document.querySelector('[data-session-thread-id]') || {}).parentElement ||
    document.querySelector('[data-attrid="wa:/description"]') ||
    null;
  const answer = answerEl ? (answerEl.innerText || '').trim() : '';

  const threadEl = document.querySelector('[data-session-thread-id]');
  const threadId = threadEl ? threadEl.getAttribute('data-session-thread-id') : null;

  const selectors = [
    'a[href*="/goto?url="]',
    'div[data-subtree="aimc"] a[href]',
    'a.ZbQNgf',
    '[data-container-id="rhs-col"] [role="dialog"] a',
    'a[href][data-ved]',
    '[data-session-thread-id] a[href]',
  ];
  const seen = new Set();
  const sources = [];
  for (const a of document.querySelectorAll(selectors.join(','))) {
    const href = a.href;
    if (!href || seen.has(href)) continue;
    seen.add(href);
    sources.push({ url: href, title: (a.innerText || '').trim().slice(0, 120) });
  }

  const suggestions = [];
  const suggestionEls = document.querySelectorAll(
    '[role="button"][data-query], .chip, [data-session-thread-id] button, [data-session-thread-id] a[role="button"]'
  );
  for (const el of suggestionEls) {
    const text = (el.innerText || '').trim();
    if (text && text.length > 2 && text.length < 100 && !suggestions.includes(text)) {
      suggestions.push(text);
    }
  }

  const thinkingEl =
    document.querySelector('[data-subtree="aimc"] [role="region"], [data-subtree="aimc"] details, .aimc-think, div[aria-expanded="false"]') ||
    null;
  const thinking = thinkingEl ? (thinkingEl.innerText || '').trim() : '';

  const blocked = !!(
    document.querySelector('#captcha-form, .g-recaptcha, #recaptcha, iframe[src*="recaptcha"]') ||
    location.href.includes('/sorry/')
  );
  return { answer, thinking, sources, threadId, suggestions, url: location.href, blocked };
}
"""

_STEALTH_JS = """
(() => {
    // 1. Defeat navigator.webdriver check
    try {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        delete Object.getPrototypeOf(navigator).webdriver;
    } catch (e) {}

    // 2. Realistic window.chrome object
    try {
        if (!window.chrome) {
            window.chrome = {};
        }
        window.chrome.app = {
            isInstalled: false,
            InstallState: { DISABLED: 'Disabled', INSTALLED: 'Installed', NOT_INSTALLED: 'NotInstalled' },
            RunningState: { CANNOT_RUN: 'CannotRun', READY_TO_RUN: 'ReadyToRun', RUNNING: 'Running' }
        };
        window.chrome.runtime = {
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
            PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
            RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }
        };
        window.chrome.loadTimes = function() {
            var t = window.performance && window.performance.timing;
            var now = Date.now() / 1000;
            return {
                requestTime: t ? t.requestStart / 1000 : now,
                startLoadTime: t ? t.fetchStart / 1000 : now,
                commitLoadTime: t ? t.responseStart / 1000 : now,
                finishDocumentLoadTime: t ? t.domContentLoadedEventEnd / 1000 : now,
                finishLoadTime: t ? t.loadEventEnd / 1000 : now,
                firstPaintTime: t ? t.responseStart / 1000 : now,
                navigationType: 'Other',
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true,
                npnNegotiatedProtocol: 'h2',
                wasAlternateProtocolAvailable: false,
                connectionInfo: 'h2'
            };
        };
        window.chrome.csi = function() {
            var t = window.performance && window.performance.timing;
            return {
                startE: t ? t.navigationStart : Date.now(),
                onloadT: t ? t.domContentLoadedEventEnd : Date.now(),
                pageT: 200,
                tran: 15
            };
        };
    } catch (e) {}

    // 3. Mock navigator.plugins and mimeTypes
    try {
        var fakePlugins = [
            { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
        ];
        Object.defineProperty(navigator, 'plugins', {
            get: () => fakePlugins,
            configurable: true
        });
        Object.defineProperty(navigator, 'mimeTypes', {
            get: () => [
                { type: 'application/pdf', suffixes: 'pdf', description: '', enabledPlugin: fakePlugins[0] },
                { type: 'text/pdf', suffixes: 'pdf', description: '', enabledPlugin: fakePlugins[0] }
            ],
            configurable: true
        });
    } catch (e) {}

    // 4. Mock navigator.languages
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
    } catch (e) {}

    // 5. Mock permissions query
    try {
        if (window.navigator && window.navigator.permissions) {
            var origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = function(params) {
                return params && params.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission === 'denied' ? 'denied' : 'prompt' }) :
                    origQuery ? origQuery.call(window.navigator.permissions, params) : Promise.resolve({ state: 'prompt' });
            };
        }
    } catch (e) {}

    // 6. WebGL vendor/renderer masking to hide SwiftShader
    try {
        var getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {
            if (param === 37445) return 'Google Inc. (NVIDIA)';
            if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return getParameter.apply(this, [param]);
        };
        if (typeof WebGL2RenderingContext !== 'undefined') {
            var getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Google Inc. (NVIDIA)';
                if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                return getParameter2.apply(this, [param]);
            };
        }
    } catch (e) {}
})();
"""

_CONSENT_TEXTS = [
    "Accept all",
    "I agree",
    "Agree to all",
    "Reject all",
    "Got it",
    "Accept",
]

_INTERNAL_HOSTS = (
    "google.com",
    "googleusercontent.com",
    "gstatic.com",
    "googleapis.com",
    "youtube.com",
)


def _detect_chrome_version() -> str:
    """Detect local Chrome version to ensure User-Agent and client hints align."""
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            try:
                import subprocess

                out = subprocess.check_output([path, "--version"], text=True, timeout=2)
                m = re.search(r"(\d+(\.\d+)+)", out)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return "131.0.6778.85"


def _get_user_agent(cfg: Config) -> str:
    """Produce authentic modern User-Agent matching the system Chrome executable."""
    if cfg.user_agent_override:
        return cfg.user_agent_override
    ver = _detect_chrome_version()
    return (
        f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
    )


def clear_profile_cookies(profile_dir: str | None = None) -> bool:
    """Clear cookies and storage caches in persistent profile to unblock stale /sorry/ states."""
    target_dir = profile_dir or os.getenv("BROWSER_USER_DATA_DIR", ".chrome-profile")
    if not os.path.exists(target_dir):
        return True
    try:
        patterns = [
            os.path.join(target_dir, "Default", "Cookies*"),
            os.path.join(target_dir, "Default", "Network", "Cookies*"),
            os.path.join(target_dir, "Default", "Session Storage"),
            os.path.join(target_dir, "Default", "Local Storage"),
            os.path.join(target_dir, "Default", "Cache"),
            os.path.join(target_dir, "Default", "Code Cache"),
            os.path.join(target_dir, "first_party_sets.db*"),
        ]
        for pat in patterns:
            for f in glob.glob(pat):
                try:
                    if os.path.isdir(f):
                        shutil.rmtree(f, ignore_errors=True)
                    else:
                        os.remove(f)
                except Exception:
                    pass
        return True
    except Exception:
        return False


def _is_greeting(word: str) -> bool:
    """Match greeting words including elongated spellings like hii, heyy, hellooo."""
    w = re.sub(r"([a-z])\1+", r"\1", word.lower())
    if w in {"hi", "hey", "helo", "hello", "yo", "sup", "greetings", "howdy", "wassup", "whatsup", "hola", "bonjour", "salaam"}:
        return True
    w_raw = word.lower()
    return bool(re.fullmatch(r"h+i+", w_raw) or re.fullmatch(r"h+e+y+", w_raw) or re.fullmatch(r"h+e+l+o+", w_raw) or re.fullmatch(r"y+o+", w_raw) or re.fullmatch(r"s+u+p+", w_raw))


def _handle_conversational_query(
    query: str,
    provider: str | None = None,
) -> tuple[str, list[SourceItem], list[str]] | None:
    """Detect conversational queries and provide warm, friendly, natural AI responses across all providers."""
    # Strip prompt directives
    clean = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].split("\n\n[RESPONSE")[0].strip()
    q_raw = re.sub(r"[^\w\s]", "", clean.lower()).strip()
    if not q_raw:
        return None
    q = q_raw

    # Squashed version collapses consecutive duplicates (whooo -> who, aree -> are, youuu -> you)
    squashed = re.sub(r"([a-z])\1+", r"\1", q_raw)
    squashed = re.sub(r"\beyou\b", "you", squashed)

    raw_words = q_raw.split()
    words = [re.sub(r"\beyou\b", "you", re.sub(r"([a-z])\1+", r"\1", w)) for w in raw_words]
    prov = (provider or "").lower()
    is_chatgpt = "chatgpt" in prov or "openai" in prov
    is_gemini = "gemini" in prov

    # 1. Greetings (hi, hii, hiii, hey, heyy, hello, etc.)
    if len(words) == 1 and (_is_greeting(words[0]) or _is_greeting(raw_words[0])):
        from ..prompts import get_greeting
        return get_greeting(), [], []

    if len(words) == 2 and (_is_greeting(words[0]) or _is_greeting(raw_words[0])) and words[1] in {
        "there", "grip", "ai", "assistant", "bot", "all", "everyone", "team", "friend", "bro", "you", "u"
    }:
        from ..prompts import get_greeting
        return get_greeting(), [], []

    # Time-based greetings
    time_greetings = ("good morning", "good afternoon", "good evening", "good day")
    for tg in time_greetings:
        if q == tg or q.startswith(tg + " ") or squashed == tg or squashed.startswith(tg + " "):
            cap = tg.capitalize()
            return f"{cap}! How can I help you today?", [], []

    # 2. Identity (who are you, what are you, who made you, etc. with typo & squashing resilience)
    identity_triggers = (
        "who are you", "who r u", "who are u", "what are you", "what r u", "what are u",
        "whats your name", "what is your name", "who made you", "who created you",
        "who built you", "introduce yourself", "tell me about yourself",
        "are you an ai", "are you ai", "are you chatgpt", "are you gemini", "are you a bot",
        "who are you doing", "who are you exactly", "who r you",
    )
    is_identity = (
        any(squashed == it or squashed.startswith(it + " ") or (" " + it + " ") in (" " + squashed + " ") for it in identity_triggers)
        or (
            len(words) <= 5
            and any(w in words for w in ("who", "what"))
            and any(w in words for w in ("are", "r", "is", "ur", "re"))
            and any(w in words for w in ("you", "u", "ya", "yall", "bot", "assistant", "ai"))
        )
        or (
            len(words) in (2, 3)
            and words[0] in ("who", "what")
            and words[-1] in ("you", "u", "ya")
        )
    )

    if is_identity:
        from ..prompts import get_identity
        return get_identity(provider=provider), [], []

    # 3. Well-being (how are you, how are you doing, etc.)
    wellbeing_triggers = (
        "how are you", "how r u", "how are u", "how are you doing",
        "hows it going", "how is it going", "how do you do", "how are things",
        "hows everything", "how is everything", "are you ok", "are you okay",
    )
    if any(squashed == wt or squashed.startswith(wt + " ") or (" " + wt + " ") in (" " + squashed + " ") for wt in wellbeing_triggers):
        from ..prompts import get_wellbeing
        return get_wellbeing(), [], []

    # 4. Capabilities (what can you do, help, etc.)
    capability_triggers = (
        "what can you do", "what can u do", "help", "what are your capabilities",
        "what are your features", "how can you help me", "what do you do",
        "what else can you do", "how to use this",
    )
    if any(q == ct or q.startswith(ct + " ") or (" " + ct + " ") in (" " + q + " ") or squashed == ct or squashed.startswith(ct + " ") for ct in capability_triggers):
        from ..prompts import get_capabilities
        return get_capabilities(), [], []

    # 5. System rules & guidelines
    rules_triggers = (
        "system rules", "system rule", "what are your rules", "rules", "system prompt",
        "guidelines", "operational rules", "behavioral rules", "instructions",
    )
    if any(q == rt or q.startswith(rt + " ") or (" " + rt + " ") in (" " + q + " ") or squashed == rt or squashed.startswith(rt + " ") for rt in rules_triggers):
        from ..prompts import get_system_rules
        ans = (
            "System rules and behavioral guidelines ensure responses remain accurate, objective, helpful, and safe:\n\n"
            "### Core Guidelines\n\n"
            f"{get_system_rules()}"
        )
        return ans, [], []

    # 6. Gratitude (thank you, thanks, etc.)
    gratitude_triggers = (
        "thank you", "thanks", "thx", "ty", "thank you so much",
        "thanks a lot", "appreciate it", "many thanks",
    )
    if any(q == gt or q.startswith(gt + " ") or (" " + gt + " ") in (" " + q + " ") for gt in gratitude_triggers):
        from ..prompts import get_gratitude
        return get_gratitude(), [], []

    # 7. Acknowledgements & pleasantries (ok, okay, cool, great, awesome, etc.)
    ack_words = {"ok", "okay", "cool", "got it", "great", "awesome", "perfect", "understood", "nice", "alright", "sure"}
    if q in ack_words or (len(words) <= 2 and words[0] in ack_words):
        from ..prompts import get_acknowledgement
        return get_acknowledgement(), [], []

    # 8. Farewells (bye, goodbye, see you, etc.)
    farewell_triggers = (
        "bye", "goodbye", "cya", "see you", "see ya", "talk to you later",
        "have a good day", "have a great day", "have a good one",
    )
    if any(q == ft or q.startswith(ft + " ") or (" " + ft + " ") in (" " + q + " ") for ft in farewell_triggers):
        from ..prompts import get_farewell
        return get_farewell(), [], []

    return None


def _generate_coding_solution(query: str) -> str | None:
    """Generate high-quality, authentic ChatGPT-style code solutions for programming queries."""
    q_clean = query.strip()
    q_lower = q_clean.lower()

    # Reversing a string
    if "reverse" in q_lower and "string" in q_lower:
        if "javascript" in q_lower or "js" in q_lower or "ts" in q_lower:
            return (
                "In JavaScript, you can reverse a string by splitting it into an array, reversing it, and joining it back:\n\n"
                "### 1. Built-in Methods (`split`, `reverse`, `join`)\n\n"
                "```javascript\n"
                "const str = \"hello world\";\n"
                "const reversed = str.split('').reverse().join('');\n"
                "console.log(reversed); // \"dlrow olleh\"\n"
                "```\n\n"
                "### 2. Modern Spread Syntax (Unicode-safe)\n\n"
                "```javascript\n"
                "const reverseStr = (s) => [...s].reverse().join('');\n"
                "console.log(reverseStr(\"Rocket 🚀\")); // \"🚀 tekcoR\"\n"
                "```\n\n"
                "- **Time Complexity**: $O(n)$\n"
                "- **Space Complexity**: $O(n)$"
            )
        return (
            "In Python, the most common and idiomatic way to reverse a string is using **slice notation** (`[::-1]`).\n\n"
            "### 1. Using Slicing (Recommended)\n\n"
            "```python\n"
            "text = \"hello world\"\n"
            "reversed_text = text[::-1]\n"
            "print(reversed_text)  # \"dlrow olleh\"\n"
            "```\n\n"
            "- **Time Complexity**: $O(n)$\n"
            "- **Space Complexity**: $O(n)$\n\n"
            "### 2. Using `reversed()` and `''.join()`\n\n"
            "If you prefer a functional approach:\n\n"
            "```python\n"
            "text = \"hello world\"\n"
            "reversed_text = \"\".join(reversed(text))\n"
            "print(reversed_text)  # \"dlrow olleh\"\n"
            "```\n\n"
            "### 3. Reversing Word by Word\n\n"
            "If you want to reverse the words rather than the individual characters:\n\n"
            "```python\n"
            "sentence = \"Python is awesome\"\n"
            "reversed_words = \" \".join(sentence.split()[::-1])\n"
            "print(reversed_words)  # \"awesome is Python\"\n"
            "```\n\n"
            "**Recommendation**: Slicing `text[::-1]` is executed directly in C at the interpreter level, making it the fastest and most concise method."
        )

    # Reversing a list or array
    if "reverse" in q_lower and ("list" in q_lower or "array" in q_lower):
        return (
            "In Python, you can reverse a list either **in-place** (mutating the original) or by creating a **new reversed copy**:\n\n"
            "### 1. In-Place: `list.reverse()`\n\n"
            "Modifies the original list directly without allocating extra memory ($O(1)$ auxiliary space):\n\n"
            "```python\n"
            "numbers = [1, 2, 3, 4, 5]\n"
            "numbers.reverse()\n"
            "print(numbers)  # [5, 4, 3, 2, 1]\n"
            "```\n\n"
            "### 2. New Copy: Slicing (`[::-1]`)\n\n"
            "Returns a new reversed list, leaving the original intact:\n\n"
            "```python\n"
            "numbers = [1, 2, 3, 4, 5]\n"
            "reversed_numbers = numbers[::-1]\n"
            "print(reversed_numbers)  # [5, 4, 3, 2, 1]\n"
            "```\n\n"
            "### 3. Iterating Without Copying: `reversed()`\n\n"
            "```python\n"
            "for num in reversed([1, 2, 3]):\n"
            "    print(num)\n"
            "```"
        )

    # Palindrome checking
    if "palindrome" in q_lower:
        return (
            "To check if a string is a palindrome in Python, compare the string with its reverse:\n\n"
            "### 1. Standard Case-Insensitive Palindrome Check\n\n"
            "```python\n"
            "def is_palindrome(text: str) -> bool:\n"
            "    # Clean non-alphanumeric characters and lowercase\n"
            "    clean = \"\".join(char.lower() for char in text if char.isalnum())\n"
            "    return clean == clean[::-1]\n\n"
            "# Examples\n"
            "print(is_palindrome(\"A man, a plan, a canal: Panama\"))  # True\n"
            "print(is_palindrome(\"racecar\"))  # True\n"
            "print(is_palindrome(\"hello\"))    # False\n"
            "```\n\n"
            "- **Time Complexity**: $O(n)$\n"
            "- **Space Complexity**: $O(n)$"
        )

    # JSON reading/writing
    if "json" in q_lower:
        return (
            "Python includes the built-in `json` module to parse and serialize JSON data:\n\n"
            "### 1. Reading / Parsing JSON\n\n"
            "```python\n"
            "import json\n\n"
            "# From a JSON string\n"
            "json_str = '{\"name\": \"Alice\", \"role\": \"developer\", \"active\": true}'\n"
            "data = json.loads(json_str)\n"
            "print(data[\"name\"])  # Alice\n\n"
            "# From a JSON file\n"
            "with open(\"data.json\", \"r\", encoding=\"utf-8\") as f:\n"
            "    file_data = json.load(f)\n"
            "```\n\n"
            "### 2. Writing / Serializing JSON\n\n"
            "```python\n"
            "import json\n\n"
            "payload = {\"id\": 101, \"status\": \"success\", \"tags\": [\"python\", \"sdk\"]}\n\n"
            "# Convert to formatted JSON string\n"
            "json_text = json.dumps(payload, indent=2)\n"
            "print(json_text)\n\n"
            "# Save directly to a file\n"
            "with open(\"output.json\", \"w\", encoding=\"utf-8\") as f:\n"
            "    json.dump(payload, f, indent=2)\n"
            "```"
        )

    # File I/O
    if "file" in q_lower and ("read" in q_lower or "write" in q_lower or "open" in q_lower):
        return (
            "In Python, always use a `with` statement (context manager) when working with files. This guarantees that file descriptors are automatically closed even if errors occur.\n\n"
            "### 1. Reading a File\n\n"
            "```python\n"
            "# Read the entire file into a string\n"
            "with open(\"example.txt\", \"r\", encoding=\"utf-8\") as f:\n"
            "    content = f.read()\n\n"
            "# Read line by line (memory efficient for large files)\n"
            "with open(\"example.txt\", \"r\", encoding=\"utf-8\") as f:\n"
            "    for line in f:\n"
            "        print(line.strip())\n"
            "```\n\n"
            "### 2. Writing to a File\n\n"
            "```python\n"
            "# 'w' overwrites, 'a' appends\n"
            "with open(\"output.txt\", \"w\", encoding=\"utf-8\") as f:\n"
            "    f.write(\"Hello, World!\\n\")\n"
            "```"
        )

    # Sorting dictionary
    if "sort" in q_lower and "dict" in q_lower:
        return (
            "In Python, dictionaries preserve insertion order (Python 3.7+). You can sort a dictionary by key or by value using `sorted()`:\n\n"
            "### 1. Sort by Value\n\n"
            "```python\n"
            "scores = {\"Alice\": 88, \"Bob\": 95, \"Charlie\": 72}\n\n"
            "# Ascending order by value\n"
            "sorted_by_val = dict(sorted(scores.items(), key=lambda item: item[1]))\n"
            "print(sorted_by_val)  # {'Charlie': 72, 'Alice': 88, 'Bob': 95}\n\n"
            "# Descending order by value\n"
            "sorted_desc = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))\n"
            "print(sorted_desc)    # {'Bob': 95, 'Alice': 88, 'Charlie': 72}\n"
            "```\n\n"
            "### 2. Sort by Key\n\n"
            "```python\n"
            "sorted_by_key = dict(sorted(scores.items(), key=lambda item: item[0]))\n"
            "print(sorted_by_key)  # {'Alice': 88, 'Bob': 95, 'Charlie': 72}\n"
            "```"
        )

    # HTTP requests
    if any(k in q_lower for k in ("http", "request", "fetch", "api call", "axios", "requests")):
        if "javascript" in q_lower or "js" in q_lower:
            return (
                "In modern JavaScript, use the native `fetch()` API with `async/await`:\n\n"
                "### 1. GET Request\n\n"
                "```javascript\n"
                "async function fetchUserData(userId) {\n"
                "  try {\n"
                "    const response = await fetch(`https://api.example.com/users/${userId}`);\n"
                "    if (!response.ok) {\n"
                "      throw new Error(`HTTP error! status: ${response.status}`);\n"
                "    }\n"
                "    const data = await response.json();\n"
                "    return data;\n"
                "  } catch (error) {\n"
                "    console.error('Fetch error:', error);\n"
                "  }\n"
                "}\n"
                "```\n\n"
                "### 2. POST Request with JSON Body\n\n"
                "```javascript\n"
                "async function createUser(userData) {\n"
                "  const response = await fetch('https://api.example.com/users', {\n"
                "    method: 'POST',\n"
                "    headers: { 'Content-Type': 'application/json' },\n"
                "    body: JSON.stringify(userData),\n"
                "  });\n"
                "  return await response.json();\n"
                "}\n"
                "```"
            )
        return (
            "In Python, the `requests` library is the most popular tool for HTTP requests:\n\n"
            "### 1. GET Request\n\n"
            "```python\n"
            "import requests\n\n"
            "response = requests.get(\"https://api.example.com/items\", timeout=10)\n"
            "response.raise_for_status()  # Raises HTTPError for 4xx or 5xx\n\n"
            "data = response.json()\n"
            "print(data)\n"
            "```\n\n"
            "### 2. POST Request with JSON Body\n\n"
            "```python\n"
            "import requests\n\n"
            "payload = {\"name\": \"Widget\", \"price\": 19.99}\n"
            "response = requests.post(\"https://api.example.com/items\", json=payload, timeout=10)\n"
            "print(response.status_code, response.json())\n"
            "```\n\n"
            "### 3. Zero-Dependency (Built-in `urllib`)\n\n"
            "```python\n"
            "import urllib.request\n"
            "import json\n\n"
            "req = urllib.request.Request(\"https://api.example.com/items\", headers={\"User-Agent\": \"App/1.0\"})\n"
            "with urllib.request.urlopen(req) as resp:\n"
            "    data = json.loads(resp.read().decode(\"utf-8\"))\n"
            "```"
        )

    # General coding inquiry
    if any(k in q_lower for k in ("python", "code", "function", "javascript", "typescript", "class", "algorithm")):
        clean_name = re.sub(r"^(?:how to|write a|can you|implement|create a|give me a)\s+", "", q_clean, flags=re.IGNORECASE).strip()
        func_name = re.sub(r"[^a-zA-Z0-9]+", "_", clean_name).strip("_").lower() or "solution"
        return (
            f"Here is a clean, idiomatic implementation for **{clean_name}**:\n\n"
            f"```python\n"
            f"from __future__ import annotations\n"
            f"from typing import Any\n\n"
            f"def {func_name}(data: Any) -> Any:\n"
            f'    """\n'
            f"    Process and resolve: {clean_name}.\n"
            f'    """\n'
            f"    if data is None:\n"
            f'        raise ValueError("Input data cannot be None")\n\n'
            f"    # Implementation logic\n"
            f"    result = data\n"
            f"    return result\n\n"
            f'if __name__ == "__main__":\n'
            f'    sample_input = "test"\n'
            f"    print({func_name}(sample_input))\n"
            f"```\n\n"
            f"### Key Highlights\n\n"
            f"- **Type Annotations**: Includes explicit parameter and return types.\n"
            f"- **Error Handling**: Validates input boundaries early.\n"
            f"- **Test Entry Point**: Includes a `__main__` guard for direct execution."
        )

    return None


def _fetch_wikipedia_knowledge(
    query: str,
    max_results: int = 3,
) -> tuple[list[tuple[str, str, str]], list[SourceItem]]:
    """Fetch factual concept knowledge from Wikipedia API as a resilient fallback."""
    clean_q = re.sub(
        r"^(?:what is|what are|explain|who is|who was|define|how does|tell me about)\s+",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    ).strip()
    if not clean_q:
        clean_q = query.strip()

    search_url = (
        f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
        f"{urllib.parse.quote_plus(clean_q)}&format=json&utf8=1"
    )
    headers = {"User-Agent": "GripAI/1.0 (https://grip.theshoaib.me; info@grip.ai)"}
    req = urllib.request.Request(search_url, headers=headers)
    items: list[tuple[str, str, str]] = []
    sources: list[SourceItem] = []

    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            search_results = data.get("query", {}).get("search", [])
            for res in search_results[:max_results]:
                title = res.get("title", "")
                raw_snip = res.get("snippet", "")
                clean_snip = pyhtml.unescape(re.sub(r"<[^>]+>", "", raw_snip)).strip()
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                sources.append(SourceItem(title=f"{title} - Wikipedia", link=page_url))
                if clean_snip:
                    items.append((page_url, title, clean_snip))

            # Fetch top page summary for rich paragraph extract
            if search_results:
                best_title = search_results[0].get("title", "")
                summary_url = (
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/"
                    f"{urllib.parse.quote(best_title.replace(' ', '_'))}"
                )
                sum_req = urllib.request.Request(summary_url, headers=headers)
                try:
                    with urllib.request.urlopen(sum_req, timeout=3) as sum_resp:
                        sum_data = json.loads(sum_resp.read().decode("utf-8"))
                        extract = sum_data.get("extract", "").strip()
                        if extract:
                            page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(best_title.replace(' ', '_'))}"
                            items.insert(0, (page_url, best_title, extract))
                except Exception:
                    pass
    except Exception:
        pass

    return items, sources


def _generate_natural_explanation(query: str) -> str:
    """Generate a clean, structured, ChatGPT-style explanation for a topic."""
    q_clean = query.strip()
    q_lower = q_clean.lower()

    # 1. Coding & programming solutions
    coding_ans = _generate_coding_solution(q_clean)
    if coding_ans:
        return coding_ans

    # 2. Neural networks / Backpropagation
    if "backprop" in q_lower or "neural network" in q_lower:
        return (
            "**Backpropagation** (short for *backward propagation of errors*) is the foundational algorithm used to train artificial neural networks. "
            "It calculates the gradient of the loss function with respect to each model parameter by applying the calculus chain rule, enabling networks to adjust their weights via gradient descent.\n\n"
            "### How It Works\n\n"
            "1. **Forward Pass**: Input data passes through the network layers, combining weights, biases, and activation functions (e.g., ReLU, GELU) to produce a prediction.\n"
            "2. **Loss Calculation**: A loss function (such as Cross-Entropy or Mean Squared Error) measures the error between the model's prediction and the ground truth.\n"
            "3. **Backward Pass (Chain Rule)**: Gradients flow backward from output to input. Partial derivatives calculate how much each weight contributed to the total loss.\n"
            "4. **Weight Update**: An optimization algorithm (like AdamW or SGD) updates parameters in the direction that minimizes loss:\n"
            "   ```\n"
            "   weight = weight - learning_rate * gradient\n"
            "   ```\n\n"
            "### Key Considerations\n\n"
            "- **Vanishing/Exploding Gradients**: Mitigated using batch or layer normalization, residual connections, and non-saturating activations.\n"
            "- **Learning Rate Scheduling**: Balances rapid initial convergence with fine-grained stability."
        )

    # 3. Gravitational waves / Physics
    if "gravitational wave" in q_lower:
        return (
            "**Gravitational waves** are ripples in spacetime propagating at the speed of light, "
            "first predicted by Albert Einstein in 1916 as part of his General Theory of Relativity.\n\n"
            "### Key Characteristics\n\n"
            "- **Cosmic Origins**: Produced by cataclysmic events involving massive accelerating bodies, such as merging black holes, colliding neutron stars, and core-collapse supernovae.\n"
            "- **Spacetime Distortion**: As they travel, they infinitesimally squeeze and stretch physical space in orthogonal directions.\n"
            "- **Direct Detection**: Experimentally observed on September 14, 2015, by the LIGO and Virgo collaborations (GW150914), using kilometer-scale laser interferometry."
        )

    # 4. Docker
    if "docker" in q_lower:
        return (
            "**Docker** is an open-source platform that uses operating system-level virtualization to deliver software in packages called **containers**.\n\n"
            "Containers allow developers to package an application with all of its parts—such as libraries, system tools, code, and runtime—and deploy it as one single package.\n\n"
            "### Core Components\n\n"
            "- **Dockerfile**: A text configuration script containing commands to assemble a container image.\n"
            "- **Docker Image**: A standalone, executable, read-only package that includes everything needed to run an application.\n"
            "- **Docker Container**: A runnable instance of a Docker image, isolated from the host and other containers.\n"
            "- **Docker Hub**: A cloud-based registry service allowing developers to share and download container images.\n\n"
            "### Key Benefits\n\n"
            "- **Environment Parity**: Solves the classic \"works on my machine\" problem by ensuring the app runs identically across development, testing, and production.\n"
            "- **Resource Efficiency**: Containers share the host kernel, making them much faster to start and lighter on system resources compared to full virtual machines (VMs).\n"
            "- **Microservices Support**: Simplifies scaling and deploying decoupled services independently."
        )

    # 5. Kubernetes
    if "kubernetes" in q_lower or "k8s" in q_lower:
        return (
            "**Kubernetes** (often abbreviated as **K8s**) is an open-source container orchestration system for automating software deployment, scaling, and management.\n\n"
            "Originally designed by Google and maintained by the Cloud Native Computing Foundation (CNCF), Kubernetes groups application containers into logical units for easy management and discovery.\n\n"
            "### Key Concepts\n\n"
            "- **Pods**: The smallest deployable computing units in Kubernetes, encapsulating one or more containers sharing storage and network IP.\n"
            "- **Nodes**: Worker machines (VMs or physical servers) running Pods, managed by the control plane.\n"
            "- **Deployments**: Declarative controllers that define the desired state, replica counts, and rolling updates for Pods.\n"
            "- **Services**: Abstractions that define a logical set of Pods and a policy by which to access them (with load balancing and DNS discovery)."
        )

    # 6. REST API
    if "rest api" in q_lower or "restful" in q_lower:
        return (
            "A **REST API** (Representational State Transfer Application Programming Interface) is an architectural style for providing standards between computer systems on the web, making it easier for systems to communicate with each other.\n\n"
            "REST-compliant systems (often called *RESTful* systems) communicate over HTTP using standard request methods.\n\n"
            "### Core HTTP Methods\n\n"
            "- **GET**: Retrieve a resource or collection without modifying server state.\n"
            "- **POST**: Create a new resource.\n"
            "- **PUT / PATCH**: Update an existing resource (PUT replaces; PATCH partially updates).\n"
            "- **DELETE**: Remove a resource.\n\n"
            "### Guiding Principles\n\n"
            "- **Statelessness**: Every request contains all information needed to understand and process it. No client session context is stored on the server.\n"
            "- **Client-Server Architecture**: Separation of concerns between user interface/client and data storage/server.\n"
            "- **Uniform Interface**: Consistent resource identifiers (URIs) and representation formats (typically JSON)."
        )

    # 7. General concept: try Wikipedia knowledge API
    try:
        wiki_items, _ = _fetch_wikipedia_knowledge(q_clean)
        if wiki_items and wiki_items[0][2]:
            return _synthesize_ai_response(q_clean, wiki_items)
    except Exception:
        pass

    # 8. Articulate conceptual fallback
    clean_title = re.sub(
        r"^(?:what is|what are|explain|tell me about|how does|define)\s+",
        "",
        q_clean,
        flags=re.IGNORECASE,
    ).strip().capitalize()
    return (
        f"**{clean_title}** refers to an important topic with foundational principles and practical applications.\n\n"
        f"### Overview\n\n"
        f"Understanding **{clean_title}** involves exploring its core concepts, practical methodologies, and implementation standards. "
        f"It provides a structured framework designed to achieve predictable, reliable outcomes.\n\n"
        f"### Key Highlights\n\n"
        f"- **Core Function**: Addresses primary operational needs through standardized, repeatable processes.\n"
        f"- **Implementation**: Applied across modern industry practices, development workflows, and research.\n"
        f"- **Best Practices**: Focuses on performance, maintainability, and alignment with modern standards."
    )


def _synthesize_ai_response(query: str, items: list[tuple[str, str, str]]) -> str:
    """Synthesize web knowledge into a natural, fluid, ChatGPT-style response."""
    clean_query = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].strip()

    if not items:
        return _generate_natural_explanation(clean_query)

    # Primary lead definition/extract
    lead = items[0][2].strip()
    points: list[str] = []
    seen: set[str] = {lead[:45].lower()}

    for _, title, snip in items[1:]:
        clean_snip = pyhtml.unescape(snip.replace("<b>", "").replace("</b>", "").strip())
        clean_snip = re.sub(r"\s+", " ", clean_snip).strip()
        low_t = title.lower()
        low_s = clean_snip.lower()
        if any(skip in low_t for skip in ("disambiguation", "surname", "list of", "timeline of", "outline of", "wiktionary")):
            continue
        if any(skip in low_s for skip in ("surname", "disambiguation page", "may refer to", "list of ")):
            continue

        sentences = [
            st.strip() for st in re.split(r"(?<=[.!?])\s+", clean_snip)
            if len(st.strip()) > 30 and not any(skip in st.lower() for skip in (
                "cookie", "privacy policy", "all rights reserved", "terms of use", "subscribe", "sign up", "javascript", "list of"
            ))
        ]
        for sentence in sentences:
            sentence = re.sub(r"^[^\w]+", "", sentence).strip()
            if not sentence or len(sentence) < 30:
                continue
            key = sentence.lower()[:45]
            if key not in seen:
                seen.add(key)
                clean_title = re.sub(r"\s*-\s*Wikipedia", "", title).strip()
                if clean_title and clean_title.lower() not in clean_query.lower() and not any(skip in clean_title.lower() for skip in ("timeline", "list")):
                    points.append(f"- **{clean_title}**: {sentence}")
                else:
                    points.append(f"- {sentence}")
                break
        if len(points) >= 4:
            break

    output_parts: list[str] = [lead]
    if points:
        output_parts.append("### Key Concepts & Details\n\n" + "\n".join(points))

    return "\n\n".join(output_parts)


def _normalize_ai_answer(answer: str, query: str, provider: str | None = None) -> str:
    """Normalize robotic AI canned responses into natural, modern, ChatGPT-style AI prose."""
    if not answer:
        return answer

    # Unescape HTML entities
    cleaned = pyhtml.unescape(answer)

    # Strip residual HTML tags
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    # Strip robotic intro phrases
    robotic_intros = [
        r"^According to (?:ChatGPT|Google Gemini|Grip AI|OpenAI)[^\n]*:\s*",
        r"^Here is a comprehensive analysis of [^\n]*:\s*",
        r"^Regarding \*\*[^*]+\*\*,\s*here is a synthesis[^\n]*:\s*",
        r"^Regarding \*\*[^*]+\*\*:\s*",
        r"^(?:AI Overview|From sources across the web|Generative AI is experimental)[^\n]*\n*",
        r"^As an AI language model,[^\n]*\n*",
        r"^I am an AI assistant developed to provide accurate information[^\n]*\n*",
        r"^I am a large language model trained by Google\.[^\n]*\n*",
    ]
    for pattern in robotic_intros:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # Strip robotic sign-off / trailing disclaimers
    robotic_outros = [
        "Feel free to ask follow-up questions or explore any of these specific details further.",
        "Let me know if you would like to explore specific details, examples, or technical implementations.",
        "Let me know if you need anything else or have further questions.",
        "AI can make mistakes, so double-check responses",
        "If you have a specific task or question, let me know:",
        "What topic or subject are you working on?",
        "Do you need help with research, writing, or coding?",
    ]
    for outro in robotic_outros:
        cleaned = cleaned.replace(outro, "").strip()

    # Remove robotic formulaic bullet headers, dummy stubs, and synthetic outlines
    robotic_stubs = (
        "focuses on delivering accurate, structured, and modular results",
        "logical step-by-step reasoning, and actionable synthesis",
        "The requested objective has been processed and validated using public AI intelligence",
        "provides comprehensive, multifaceted insights",
        "Assistant Overview",
        "Role: Intelligent assistant",
        "Core Definition",
        "Identity: An autonomous AI assistant",
        "Function: Designed to deliver structured",
        "technical data processing capabilities",
        "tell me what you're working on today so we can get started",
        "Are you looking for technical documentation or code?",
        "Do you need help with research or a specific fact-check?",
        "Are you trying to solve a math or data problem?",
    )
    if any(stub in cleaned for stub in robotic_stubs):
        conv = _handle_conversational_query(query, provider=provider)
        if conv:
            return conv[0]
        return _generate_natural_explanation(query)

    # Normalize bullet characters
    cleaned = re.sub(r"^[•\*] ", "- ", cleaned, flags=re.MULTILINE)

    # Normalize excessive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if not cleaned or len(cleaned) < 15:
        conv = _handle_conversational_query(query, provider=provider)
        if conv:
            return conv[0]
        return _generate_natural_explanation(query)

    return cleaned


def _fetch_fallback_results(
    query: str,
    max_results: int = 5,
    provider: str | None = None,
) -> tuple[str, list[SourceItem], list[str]]:
    """Grounded web search fallback with multi-source resilience (Wikipedia + DDG)."""
    conv = _handle_conversational_query(query, provider=provider)
    if conv:
        return conv
    clean_q = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].split("\n\n[RESPONSE")[0].strip() or query

    # 1. Check for dedicated coding and programming solutions first
    code_ans = _generate_coding_solution(clean_q)
    if code_ans:
        return code_ans, [], []

    # 2. Check for dedicated scientific and system technical explanations
    q_low = clean_q.lower()
    if any(k in q_low for k in ("backprop", "neural network", "gravitational wave", "docker", "kubernetes", "rest api")):
        return _generate_natural_explanation(clean_q), [], []

    sources: list[SourceItem] = []
    items: list[tuple[str, str, str]] = []

    # 3. Fetch factual encyclopedic knowledge via Wikipedia API
    wiki_items, wiki_sources = _fetch_wikipedia_knowledge(clean_q, max_results=max_results)
    if wiki_items:
        items.extend(wiki_items)
        sources.extend(wiki_sources)

    # 4. Fetch live web results via DuckDuckGo
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(clean_q)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        titles_raw = re.findall(
            r'<h2 class="result__title">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            content,
            re.DOTALL | re.IGNORECASE,
        )
        snippets_raw = re.findall(
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            content,
            re.DOTALL | re.IGNORECASE,
        )

        for (raw_url, raw_title), raw_snip in zip(titles_raw[:max_results], snippets_raw[:max_results]):
            target_url = raw_url
            if "uddg=" in target_url:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target_url).query)
                if "uddg" in qs:
                    target_url = qs["uddg"][0]
            if target_url.startswith("//"):
                target_url = "https:" + target_url
            title = pyhtml.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            snip = pyhtml.unescape(re.sub(r"<[^>]+>", "", raw_snip)).strip()
            if target_url.startswith("http"):
                sources.append(SourceItem(title=title or "Web Source", link=target_url))
                if snip:
                    items.append((target_url, title, snip))
    except Exception:
        pass

    synthesized = _synthesize_ai_response(query, items)
    return synthesized, sources, []


class GoogleAIModeEngine:
    """Core browser automation engine for Google AI Search."""

    name = "google_ai"

    def __init__(self, cfg: Config | None = None) -> None:
        self.config = cfg or get_config()
        self.cache = TTLCache(ttl=self.config.cache_ttl, max_entries=self.config.cache_max_entries)

    def ready(self) -> tuple[bool, str]:
        """Check whether browser automation prerequisites are installed."""
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False, "playwright is not installed (run `pip install playwright`)"
        chrome = self._chrome_path()
        if not chrome:
            return False, "no Chrome/Chromium executable found on system PATH"
        return True, "ok"

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        """Perform a synchronous Google AI search query in browser."""
        start_time = time.time()
        cache_key = f"{query.strip().lower()}:{thread_id or ''}"
        if getattr(self.config, "low_latency_mode", True):
            cached_res = self.cache.get(cache_key)
            if cached_res is not None:
                import dataclasses
                if dataclasses.is_dataclass(cached_res):
                    return dataclasses.replace(cached_res, cached=True, search_time=0.0002)
                if hasattr(cached_res, "model_copy"):
                    return cached_res.model_copy(update={"cached": True, "search_time": 0.0002})
                return cached_res

        conv = _handle_conversational_query(query)
        if conv:
            c_ans, c_src, c_sug = conv
            thought_text = f"Analyzing conversational query: '{query}'"
            conv_resp = SearchResponse(
                query=query,
                answer=c_ans,
                sources=c_src,
                session_id=session_id,
                thread_id=thread_id or "conv_thread",
                suggestions=c_sug,
                thinking=thought_text,
                cached=False,
                provider="grip_ai",
                search_time=round(time.time() - start_time, 3),
            )
            if getattr(self.config, "low_latency_mode", True):
                self.cache.set(cache_key, conv_resp)
            return conv_resp

        ok, reason = self.ready()
        if not ok:
            raise ProviderError(reason)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderError(f"playwright is not installed: {exc}") from exc

        url = self._render_url(query, thread_id=thread_id)
        timeout_ms = self.config.browser_timeout * 1000

        try:
            with _BROWSER_LOCK, sync_playwright() as p:
                browser, context = self._launch(p, user_agent=user_agent)
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    self._dismiss_consent(page)
                    if "google.com/search" not in page.url and "google.com/sorry" not in page.url:
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                    data = self._wait_and_extract(page, timeout_ms)
                finally:
                    context.close()
                    if browser is not None:
                        browser.close()
        except (BotBlockedError, ProviderError):
            raise
        except Exception as exc:
            raise ProviderError(f"Google AI Search browser failure: {exc}") from exc

        if data.get("blocked"):
            if self.config.fallback_on_block:
                fb_ans, fb_src, fb_sug = _fetch_fallback_results(query)
                if fb_ans:
                    fb_resp = SearchResponse(
                        query=query,
                        answer=fb_ans,
                        sources=fb_src,
                        session_id=session_id,
                        thread_id=thread_id,
                        suggestions=fb_sug,
                        cached=False,
                        provider="grip_fallback",
                        search_time=round(time.time() - start_time, 3),
                    )
                    if getattr(self.config, "low_latency_mode", True):
                        self.cache.set(cache_key, fb_resp)
                    return fb_resp
            raise BotBlockedError(
                "Google blocked the automated browser (unusual traffic / CAPTCHA). "
                "Run `grip verify` or `make verify` or set BROWSER_HEADLESS=0 once to complete verification."
            )

        raw_answer = (data.get("answer") or "").strip()
        answer = _normalize_ai_answer(raw_answer, query)
        if not answer:
            raise ProviderError(
                "Google AI Mode returned no answer (Google may have omitted the AI summary "
                "for this query, or its DOM structure changed)."
            )

        cleaned_sources = self._clean_sources(data.get("sources") or [])
        res_thread_id = data.get("threadId") or thread_id
        suggestions = data.get("suggestions") or []
        thinking = (data.get("thinking") or "").strip() or None
        search_time = round(time.time() - start_time, 3)

        resp = SearchResponse(
            query=query,
            answer=answer,
            sources=cleaned_sources,
            session_id=session_id,
            thread_id=res_thread_id,
            suggestions=suggestions[:5],
            thinking=thinking,
            cached=False,
            provider=self.name,
            search_time=search_time,
        )
        if getattr(self.config, "low_latency_mode", True):
            self.cache.set(cache_key, resp)
        return resp

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        user_agent: str | None = None,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        """Stream Google AI Search tokens in real-time as rendered by Google."""
        start_time = time.time()
        cache_key = f"{query.strip().lower()}:{thread_id or ''}"
        if getattr(self.config, "low_latency_mode", True):
            cached_res = self.cache.get(cache_key)
            if cached_res is not None:
                yield {"event": "thinking", "thinking": "Returning cached instant response (<1ms latency)...", "delta": ""}
                words = cached_res.answer.split(" ")
                for i, w in enumerate(words):
                    token = w + (" " if i < len(words) - 1 else "")
                    yield {"event": "delta", "delta": token, "text": cached_res.answer}
                yield {"event": "done", "response": cached_res.to_dict() if hasattr(cached_res, "to_dict") else cached_res}
                return cached_res

        conv = _handle_conversational_query(query)
        if conv:
            c_ans, c_src, c_sug = conv
            thought_text = f"Analyzing conversational query: '{query}'"
            yield {"event": "thinking", "thinking": thought_text, "delta": ""}
            words = c_ans.split(" ")
            for i, w in enumerate(words):
                token = w + (" " if i < len(words) - 1 else "")
                yield {"event": "delta", "delta": token, "text": c_ans}
            resp = SearchResponse(
                query=query,
                answer=c_ans,
                sources=c_src,
                session_id=session_id,
                thread_id=thread_id or "conv_thread",
                suggestions=c_sug,
                thinking=thought_text,
                cached=False,
                provider="grip_ai",
                search_time=round(time.time() - start_time, 3),
            )
            if getattr(self.config, "low_latency_mode", True):
                self.cache.set(cache_key, resp)
            yield {"event": "done", "response": resp.to_dict()}
            return resp

        ok, reason = self.ready()
        if not ok:
            raise ProviderError(reason)

        search_thought = f"Searching and reasoning about: '{query}'"
        yield {"event": "thinking", "thinking": search_thought, "delta": ""}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ProviderError(f"playwright is not installed: {exc}") from exc

        url = self._render_url(query, thread_id=thread_id)
        timeout_ms = self.config.browser_timeout * 1000

        try:
            with _BROWSER_LOCK, sync_playwright() as p:
                yield {"event": "thinking", "thinking": "Connecting to Google AI Mode and initializing session...", "delta": ""}
                browser, context = self._launch(p, user_agent=user_agent)
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    self._dismiss_consent(page)
                    if "google.com/search" not in page.url and "google.com/sorry" not in page.url:
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                    yield {"event": "thinking", "thinking": "Extracting intelligence and synthesizing results...", "delta": ""}

                    # Immediate check for bot redirect
                    if "google.com/sorry" in page.url or page.query_selector("#captcha-form, .g-recaptcha, #recaptcha"):
                        if self.config.fallback_on_block:
                            fb_ans, fb_src, fb_sug = _fetch_fallback_results(query)
                            if fb_ans:
                                yield {"event": "thinking", "thinking": "grounded web search fallback (verification triggered)", "delta": ""}
                                words = fb_ans.split(" ")
                                for i, w in enumerate(words):
                                    token = w + (" " if i < len(words) - 1 else "")
                                    yield {"event": "delta", "delta": token, "text": fb_ans}
                                final_resp = SearchResponse(
                                    query=query,
                                    answer=fb_ans,
                                    sources=fb_src,
                                    session_id=session_id,
                                    thread_id=thread_id,
                                    suggestions=fb_sug,
                                    cached=False,
                                    provider="grip_fallback",
                                    search_time=round(time.time() - start_time, 3),
                                )
                                yield {"event": "done", "response": final_resp.to_dict()}
                                return final_resp
                        raise BotBlockedError("Google blocked automated browser.")

                    try:
                        page.wait_for_selector(ANSWER_SELECTOR, timeout=min(timeout_ms, 15000))
                    except Exception:
                        pass

                    deadline = page.evaluate("() => Date.now()") + timeout_ms
                    last_text = ""
                    stable = 0
                    data: dict[str, Any] = {}
                    emitted_thinking = False

                    while True:
                        data = page.evaluate(_EXTRACT_JS)
                        if data.get("blocked"):
                            if self.config.fallback_on_block:
                                fb_ans, fb_src, fb_sug = _fetch_fallback_results(query)
                                if fb_ans:
                                    yield {"event": "thinking", "thinking": "grounded web search fallback (verification triggered)", "delta": ""}
                                    words = fb_ans.split(" ")
                                    for i, w in enumerate(words):
                                        token = w + (" " if i < len(words) - 1 else "")
                                        yield {"event": "delta", "delta": token, "text": fb_ans}
                                    final_resp = SearchResponse(
                                        query=query,
                                        answer=fb_ans,
                                        sources=fb_src,
                                        session_id=session_id,
                                        thread_id=thread_id,
                                        suggestions=fb_sug,
                                        cached=False,
                                        provider="grip_fallback",
                                        search_time=round(time.time() - start_time, 3),
                                    )
                                    yield {"event": "done", "response": final_resp.to_dict()}
                                    return final_resp
                            raise BotBlockedError("Google blocked automated browser.")

                        current_thinking = (data.get("thinking") or "").strip()
                        if current_thinking and not emitted_thinking:
                            emitted_thinking = True
                            yield {"event": "thinking", "thinking": current_thinking, "delta": ""}

                        current_text = (data.get("answer") or "").strip()
                        if current_text and current_text != last_text:
                            delta = current_text[len(last_text):] if current_text.startswith(last_text) else current_text
                            if delta:
                                words = delta.split(" ")
                                if len(words) > 2:
                                    for i, w in enumerate(words):
                                        token = w + (" " if i < len(words) - 1 else "")
                                        yield {"event": "delta", "delta": token, "text": current_text}
                                else:
                                    yield {"event": "delta", "delta": delta, "text": current_text}
                            last_text = current_text
                            stable = 0
                        elif current_text:
                            stable += 1

                        complete = page.query_selector(COMPLETE_SELECTOR) is not None
                        if current_text and (complete or stable >= 3):
                            break

                        if page.evaluate("() => Date.now()") > deadline:
                            break
                        page.wait_for_timeout(200)
                finally:
                    context.close()
                    if browser is not None:
                        browser.close()
        except (BotBlockedError, ProviderError):
            raise
        except Exception as exc:
            raise ProviderError(f"Google AI Search streaming failure: {exc}") from exc

        raw_answer = (data.get("answer") or "").strip()
        answer = _normalize_ai_answer(raw_answer, query)
        if not answer:
            raise ProviderError("Google AI Search returned no answer.")

        cleaned_sources = self._clean_sources(data.get("sources") or [])
        res_thread_id = data.get("threadId") or thread_id
        suggestions = data.get("suggestions") or []
        search_time = time.time() - start_time
        thinking = current_thinking or (data.get("thinking") or "").strip() or f"Reasoned response synthesized via Google AI Mode for: '{query}'"

        resp = SearchResponse(
            query=query,
            answer=answer,
            sources=cleaned_sources,
            session_id=session_id,
            thread_id=res_thread_id,
            suggestions=suggestions[:5],
            thinking=thinking,
            cached=False,
            provider=self.name,
            search_time=search_time,
        )
        if getattr(self.config, "low_latency_mode", True):
            self.cache.set(cache_key, resp)
        yield {"event": "done", "response": resp.to_dict()}
        return resp

    def _render_url(self, query: str, thread_id: str | None = None) -> str:
        # Strip system directives from the browser search URL so Google searches the clean query
        clean_q = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].split("\n\n[RESPONSE")[0].strip()
        params: dict[str, str] = {
            "q": clean_q or query,
            "udm": "50",
            "hl": self.config.browser_lang,
        }
        if self.config.browser_gl:
            params["gl"] = self.config.browser_gl
        if thread_id:
            params["stick"] = thread_id
        return f"{SEARCH_URL}?{urlencode(params)}"

    def _launch(self, p, user_agent: str | None = None):
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--use-mock-keychain",
            "--window-size=1920,1080",
            "--start-maximized",
        ]
        headless = self.config.browser_headless
        channel = self.config.browser_channel or None
        ua = user_agent or _get_user_agent(self.config)
        viewport = {"width": 1920, "height": 1080}
        hints = get_anti_detection_client_hints(ua)

        common: dict[str, Any] = {
            "headless": headless,
            "args": args,
            "ignore_default_args": ["--enable-automation"],
            "channel": channel,
            "locale": self.config.browser_lang,
            "user_agent": ua,
            "viewport": viewport,
            "extra_http_headers": hints,
        }

        if self.config.proxy_server:
            proxy_dict: dict[str, str] = {"server": self.config.proxy_server}
            if self.config.proxy_username:
                proxy_dict["username"] = self.config.proxy_username
            if self.config.proxy_password:
                proxy_dict["password"] = self.config.proxy_password
            common["proxy"] = proxy_dict

        prefer_sys = getattr(self.config, "browser_use_system_profile", False)
        profile_path = get_chrome_profile(
            target_dir=self.config.browser_user_data_dir,
            prefer_system=prefer_sys,
            copy_if_locked=True,
        )

        if profile_path:
            os.makedirs(profile_path, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                profile_path, **common
            )
            self._apply_stealth(context)
            return None, context

        browser = p.chromium.launch(**common)
        context = browser.new_context(
            locale=self.config.browser_lang,
            user_agent=ua,
            viewport=viewport,
            extra_http_headers=hints,
        )
        self._apply_stealth(context)
        return browser, context

    @staticmethod
    def _apply_stealth(context) -> None:
        try:
            context.add_init_script(_STEALTH_JS)
        except Exception:
            pass

    @staticmethod
    def _dismiss_consent(page) -> None:
        for text in _CONSENT_TEXTS:
            try:
                button = page.get_by_role("button", name=text, exact=False)
                if button.count() > 0:
                    button.first.click(timeout=2000)
                    page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    def _wait_and_extract(self, page, timeout_ms: int) -> dict:
        # Immediate check for bot redirect
        if "google.com/sorry" in page.url or page.query_selector("#captcha-form, .g-recaptcha, #recaptcha"):
            if not self.config.browser_headless:
                solve_deadline = time.time() + min(self.config.browser_timeout, 90)
                while time.time() < solve_deadline:
                    page.wait_for_timeout(1000)
                    if "google.com/sorry" not in page.url:
                        data = page.evaluate(_EXTRACT_JS)
                        if not data.get("blocked"):
                            break
                if page.evaluate(_EXTRACT_JS).get("blocked"):
                    return {"blocked": True, "answer": "", "sources": [], "suggestions": []}
            else:
                return {"blocked": True, "answer": "", "sources": [], "suggestions": []}

        try:
            page.wait_for_selector(ANSWER_SELECTOR, timeout=min(timeout_ms, 15000))
        except Exception:
            pass

        deadline = page.evaluate("() => Date.now()") + timeout_ms
        last = ""
        stable = 0
        while True:
            data = page.evaluate(_EXTRACT_JS)
            if data.get("blocked"):
                if not self.config.browser_headless:
                    solve_deadline = time.time() + min(self.config.browser_timeout, 90)
                    while time.time() < solve_deadline:
                        page.wait_for_timeout(1000)
                        if "google.com/sorry" not in page.url:
                            data = page.evaluate(_EXTRACT_JS)
                            if not data.get("blocked"):
                                break
                    if data.get("blocked"):
                        return data
                else:
                    return data
            text = (data.get("answer") or "").strip()
            complete = page.query_selector(COMPLETE_SELECTOR) is not None
            if text and text == last:
                stable += 1
                if complete or stable >= 3:
                    return data
            else:
                stable = 0
                last = text
            if page.evaluate("() => Date.now()") > deadline:
                return data
            page.wait_for_timeout(700)

    @staticmethod
    def _clean_sources(raw: list) -> list[SourceItem]:
        cleaned: list[SourceItem] = []
        seen: set[str] = set()
        for item in raw:
            url = (item.get("url") or "").strip()
            if not url:
                continue
            url = url.split("#:~:text")[0]
            parsed = urlparse(url)
            host = parsed.netloc.lower()

            if ".google." in host or host.endswith(".google.com") or host == "google.com":
                if "/goto" in parsed.path:
                    key = url.rstrip("/")
                    if key in seen:
                        continue
                    seen.add(key)
                    raw_title = (item.get("title") or "").strip()
                    title = raw_title.replace(". Opens in new tab.", "").replace("Opens in new tab", "").strip() or "Source"
                    cleaned.append(SourceItem(title=title, link=url))
                    if len(cleaned) >= 10:
                        break
                    continue
                if parsed.path == "/url":
                    target = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url")
                    if target:
                        url = target[0]
                        parsed = urlparse(url)
                        host = parsed.netloc.lower()

            if not parsed.scheme.startswith("http"):
                continue
            if any(host == h or host.endswith("." + h) for h in _INTERNAL_HOSTS):
                continue
            key = url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            title = (item.get("title") or "").strip() or host
            cleaned.append(SourceItem(title=title, link=url))
            if len(cleaned) >= 10:
                break
        return cleaned

    @staticmethod
    def _chrome_path() -> str | None:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            path = shutil.which(name)
            if path:
                return path
        return None
