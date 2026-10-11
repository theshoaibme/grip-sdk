"""Google AI Mode (udm=50) search engine powered by real browser automation."""

from __future__ import annotations

import glob
import html as pyhtml
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


def _handle_conversational_query(query: str) -> tuple[str, list[SourceItem], list[str]] | None:
    """Detect common conversational prompts and provide natural, warm AI responses."""
    clean = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].strip()
    q = re.sub(r"[^\w\s]", "", clean.lower()).strip()

    patterns: dict[tuple[str, ...], str] = {
        ("who are you", "who r u", "who are youu", "whats your name", "what is your name", "who made you"): (
            "I am **Grip AI**, an AI assistant. I can help answer questions, analyze topics, write code, search the web, and assist with various tasks.\n\n"
            "How can I help you today?"
        ),
        ("hello", "hi", "hey", "greetings"): (
            "Hello! How can I help you today?"
        ),
        ("good morning",): (
            "Good morning! How can I help you today?"
        ),
        ("good afternoon",): (
            "Good afternoon! How can I help you today?"
        ),
        ("good evening",): (
            "Good evening! How can I help you today?"
        ),
        ("how are you", "how r u", "how are you doing", "hows it going"): (
            "I'm doing well, thank you! How can I help you today?"
        ),
        ("what can you do", "help", "what are your capabilities", "what can u do"): (
            "I can help you with a wide range of tasks, including answering questions, brainstorming, writing and debugging code, researching topics, and more. What would you like to work on?"
        ),
        ("thank you", "thanks", "thx", "thank you so much"): (
            "You're welcome! Let me know if you need anything else."
        ),
    }

    for keys, answer in patterns.items():
        if any(q == k or q.startswith(k + " ") or (" " + k + " ") in (" " + q + " ") for k in keys):
            return answer, [], []

    return None


def _synthesize_ai_response(query: str, items: list[tuple[str, str, str]]) -> str:
    """Synthesize web knowledge into a natural, fluid, well-structured AI response."""
    clean_query = query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].strip()

    if not items:
        return f"I couldn't find specific live web results for **{clean_query}**. Try rephrasing or providing additional context."

    points: list[str] = []
    seen = set()
    for _, title, snip in items:
        s = snip.replace("<b>", "").replace("</b>", "").strip()
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", s) if len(sentence.strip()) > 20]
        for sentence in sentences:
            key = sentence.lower()[:45]
            if key not in seen:
                seen.add(key)
                points.append(f"• **{title}**: {sentence}")
                break
        if len(points) >= 5:
            break

    intro = f"Regarding **{clean_query}**, here is a synthesis of the most current findings and information:\n\n"
    body = "\n".join(points) if points else "Detailed information was retrieved across verified web sources."
    conclusion = "\n\nFeel free to ask follow-up questions or explore any of these specific details further."
    return intro + body + conclusion


def _normalize_ai_answer(answer: str, query: str) -> str:
    """Normalize robotic Google AI canned responses into natural, modern AI prose."""
    if not answer:
        return answer
    robotic_phrases = [
        "I am an AI assistant developed to provide accurate information, solve problems, and help with tasks using verified references and tools.",
        "If you have a specific task or question, let me know:",
        "What topic or subject are you working on?",
        "Do you need help with research, writing, or coding?",
        "AI can make mistakes, so double-check responses",
        "I am a large language model trained by Google.",
    ]
    cleaned = answer
    for rob in robotic_phrases:
        cleaned = cleaned.replace(rob, "").strip()

    if not cleaned or len(cleaned) < 15:
        conv = _handle_conversational_query(query)
        if conv:
            return conv[0]
        return (
            "I am **Grip AI**, an intelligent AI assistant. "
            "How can I help you with this topic or task today?"
        )
    return cleaned


def _fetch_fallback_results(query: str, max_results: int = 5) -> tuple[str, list[SourceItem], list[str]]:
    """Grounded web search fallback when Google blocks automated browser with CAPTCHA."""
    conv = _handle_conversational_query(query)
    if conv:
        return conv

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return "", [], []

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

    sources: list[SourceItem] = []
    items: list[tuple[str, str, str]] = []

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

    synthesized = _synthesize_ai_response(query, items)
    return synthesized, sources, []


class GoogleAIModeEngine:
    """Core browser automation engine for Google AI Search."""

    name = "google_ai"

    def __init__(self, cfg: Config | None = None) -> None:
        self.config = cfg or get_config()

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
    ) -> SearchResponse:
        """Perform a synchronous Google AI search query in browser."""
        start_time = time.time()
        conv = _handle_conversational_query(query)
        if conv:
            c_ans, c_src, c_sug = conv
            thought_text = f"Analyzing conversational query: '{query}'"
            return SearchResponse(
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
                browser, context = self._launch(p)
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
                    return SearchResponse(
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

        return SearchResponse(
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

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        """Stream Google AI Search tokens in real-time as rendered by Google."""
        start_time = time.time()
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
                browser, context = self._launch(p)
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
        yield {"event": "done", "response": resp.to_dict()}
        return resp

    def _render_url(self, query: str, thread_id: str | None = None) -> str:
        params: dict[str, str] = {
            "q": query,
            "udm": "50",
            "hl": self.config.browser_lang,
        }
        if self.config.browser_gl:
            params["gl"] = self.config.browser_gl
        if thread_id:
            params["stick"] = thread_id
        return f"{SEARCH_URL}?{urlencode(params)}"

    def _launch(self, p):
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
        ua = _get_user_agent(self.config)
        viewport = {"width": 1920, "height": 1080}

        common: dict[str, Any] = {
            "headless": headless,
            "args": args,
            "ignore_default_args": ["--enable-automation"],
            "channel": channel,
            "locale": self.config.browser_lang,
            "user_agent": ua,
            "viewport": viewport,
        }

        if self.config.proxy_server:
            proxy_dict: dict[str, str] = {"server": self.config.proxy_server}
            if self.config.proxy_username:
                proxy_dict["username"] = self.config.proxy_username
            if self.config.proxy_password:
                proxy_dict["password"] = self.config.proxy_password
            common["proxy"] = proxy_dict

        if self.config.browser_user_data_dir:
            os.makedirs(self.config.browser_user_data_dir, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                self.config.browser_user_data_dir, **common
            )
            self._apply_stealth(context)
            return None, context

        browser = p.chromium.launch(**common)
        context = browser.new_context(
            locale=self.config.browser_lang,
            user_agent=ua,
            viewport=viewport,
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
