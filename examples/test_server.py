#!/usr/bin/env python3
"""Grip SDK Interactive Test Server.

Demonstrates end-to-end integration of grip-sdk:
- Synchronous & Streaming AI Search
- Thinking process visualizer
- Multi-turn conversational sessions
- Dynamic multi-provider orchestration
- Grounded citations & sources

https://grip.theshoaib.me/
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from flask import Flask, Response, jsonify, render_template_string, request

# Import official Grip SDK
import grip
from grip import Grip, __version__

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("grip_test_server")

app = Flask("grip_test_server")

# Connect to running Grip Platform backend on 8000, or fall back to embedded
TARGET_BACKEND = os.getenv("GRIP_API_URL", "http://127.0.0.1:8000")
sdk = Grip(base_url=TARGET_BACKEND)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Grip AI &bull; SDK Interactive Test Server</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090a0f;
      --surface: #11131c;
      --surface-border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.35);
      --accent-grad: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-sub: #64748b;
      --card-bg: rgba(26, 29, 45, 0.65);
      --code-bg: #0d0f18;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      background-image: 
        radial-gradient(ellipse at 50% -20%, rgba(99, 102, 241, 0.22), transparent 50%),
        radial-gradient(ellipse at 80% 80%, rgba(168, 85, 247, 0.12), transparent 40%);
    }

    header {
      padding: 1.25rem 2rem;
      border-bottom: 1px solid var(--surface-border);
      backdrop-filter: blur(16px);
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      text-decoration: none;
      color: inherit;
    }

    .brand-logo {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: var(--accent-grad);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.15rem;
      box-shadow: 0 0 20px var(--accent-glow);
    }

    .brand-title {
      font-weight: 700;
      font-size: 1.25rem;
      letter-spacing: -0.02em;
    }

    .badge-sdk {
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.4);
      color: #a5b4fc;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
    }

    .badge-status {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.82rem;
      color: var(--text-muted);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.9); }
    }

    main {
      flex: 1;
      max-width: 1000px;
      width: 100%;
      margin: 0 auto;
      padding: 2.5rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }

    .hero {
      text-align: center;
      margin-bottom: 0.5rem;
    }
    .hero h1 {
      font-size: 2.5rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin-bottom: 0.6rem;
      background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p {
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 650px;
      margin: 0 auto;
    }

    .controls-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 0.75rem 1rem;
      align-items: center;
      justify-content: space-between;
    }

    .control-group {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .control-label {
      font-size: 0.8rem;
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.05em;
      color: var(--text-sub);
    }

    select, button, input[type="text"] {
      font-family: inherit;
      border-radius: 10px;
      border: 1px solid var(--surface-border);
      background: rgba(13, 15, 24, 0.8);
      color: var(--text);
      font-size: 0.88rem;
      outline: none;
      transition: all 0.2s ease;
    }
    select {
      padding: 0.5rem 1rem;
      cursor: pointer;
    }
    select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 12px var(--accent-glow);
    }

    .search-container {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 20px;
      padding: 1.25rem;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .input-row {
      display: flex;
      gap: 0.75rem;
      align-items: center;
    }

    .query-input {
      flex: 1;
      padding: 1rem 1.25rem;
      font-size: 1.05rem;
      background: rgba(8, 10, 16, 0.9);
      border: 1px solid var(--surface-border);
      color: #fff;
    }
    .query-input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 20px var(--accent-glow);
    }

    .btn-search {
      padding: 1rem 1.75rem;
      font-weight: 600;
      background: var(--accent-grad);
      color: #fff;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .btn-search:hover {
      transform: translateY(-1px);
      box-shadow: 0 0 24px var(--accent-glow);
    }
    .btn-search:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    .stream-toggle {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.85rem;
      color: var(--text-muted);
      cursor: pointer;
    }
    .stream-toggle input {
      accent-color: var(--accent);
      cursor: pointer;
    }

    /* Output Card */
    .output-card {
      background: var(--card-bg);
      border: 1px solid var(--surface-border);
      border-radius: 20px;
      padding: 2rem;
      backdrop-filter: blur(20px);
      display: none;
      flex-direction: column;
      gap: 1.5rem;
      position: relative;
    }

    .thinking-box {
      background: rgba(99, 102, 241, 0.08);
      border-left: 3px solid var(--accent);
      padding: 1rem 1.25rem;
      border-radius: 0 12px 12px 0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.86rem;
      color: #c7d2fe;
      display: none;
      line-height: 1.6;
    }
    .thinking-header {
      font-weight: 600;
      margin-bottom: 0.35rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      color: #a5b4fc;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .answer-content {
      font-size: 1.05rem;
      line-height: 1.8;
      color: #e2e8f0;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .sources-header {
      font-size: 0.85rem;
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: var(--text-sub);
      margin-top: 0.5rem;
    }
    .sources-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 0.75rem;
    }
    .source-card {
      background: rgba(13, 15, 24, 0.7);
      border: 1px solid var(--surface-border);
      border-radius: 12px;
      padding: 0.85rem 1rem;
      text-decoration: none;
      color: var(--text-muted);
      font-size: 0.85rem;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }
    .source-card:hover {
      border-color: var(--accent);
      transform: translateY(-2px);
      color: #fff;
      box-shadow: 0 6px 16px rgba(0,0,0,0.4);
    }
    .source-title {
      font-weight: 600;
      color: #f1f5f9;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .source-domain {
      font-size: 0.75rem;
      color: var(--text-sub);
    }

    .session-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.8rem;
      color: var(--text-sub);
      font-family: 'JetBrains Mono', monospace;
    }

    footer {
      margin-top: auto;
      padding: 2rem;
      text-align: center;
      font-size: 0.85rem;
      color: var(--text-sub);
      border-top: 1px solid var(--surface-border);
    }
    footer a {
      color: var(--text-muted);
      text-decoration: none;
    }
    footer a:hover { color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <a href="/" class="brand">
      <div class="brand-logo">G</div>
      <div class="brand-title">Grip AI <span style="font-weight: 300; opacity: 0.7;">Test Lab</span></div>
    </a>
    <div style="display: flex; align-items: center; gap: 1rem;">
      <span class="badge-sdk">grip-sdk v{{ version }}</span>
      <div class="badge-status">
        <span class="pulse-dot"></span>
        <span id="backend-status">Connected to {{ backend }}</span>
      </div>
    </div>
  </header>

  <main>
    <div class="hero">
      <h1>Enterprise AI Search &amp; Multi-Agent SDK</h1>
      <p>Interactive verification playground executing queries and live token streaming via the official <code>grip-sdk</code>.</p>
    </div>

    <div class="controls-bar">
      <div class="control-group">
        <span class="control-label">Search Provider</span>
        <select id="provider-select">
          <option value="google" selected>Google AI Search</option>
          <option value="google_ai">Google AI Mode</option>
          <option value="grip">Grip Native</option>
          <option value="openai">OpenAI Search</option>
        </select>
      </div>

      <div class="control-group">
        <label class="stream-toggle">
          <input type="checkbox" id="stream-checkbox" checked>
          <span>Stream Response (SSE)</span>
        </label>
      </div>

      <div class="control-group">
        <button id="btn-new-session" style="padding: 0.5rem 0.85rem; font-size: 0.8rem; cursor: pointer;">
          + New Session
        </button>
      </div>
    </div>

    <div class="search-container">
      <div class="input-row">
        <input 
          type="text" 
          id="query-input" 
          class="query-input" 
          placeholder="Ask anything (e.g. 'Explain how quantum entanglement works')..."
          value="Explain how quantum entanglement works"
        />
        <button id="btn-search" class="btn-search">
          <span>Search</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </div>
      <div id="session-info" class="session-badge">Session: Default</div>
    </div>

    <div id="output-card" class="output-card">
      <div id="thinking-box" class="thinking-box">
        <div class="thinking-header">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          Grip AI Reasoning Process
        </div>
        <div id="thinking-content"></div>
      </div>

      <div id="answer-content" class="answer-content"></div>

      <div id="sources-section" style="display: none;">
        <div class="sources-header">Grounded Sources &amp; Citations</div>
        <div id="sources-grid" class="sources-grid"></div>
      </div>
    </div>
  </main>

  <footer>
    <p>Powered by <a href="https://grip.theshoaib.me/" target="_blank">Grip AI Platform</a> &bull; Installed from PyPI: <code>pip install grip-sdk</code></p>
  </footer>

  <script>
    let activeSessionId = null;

    const queryInput = document.getElementById("query-input");
    const btnSearch = document.getElementById("btn-search");
    const btnNewSession = document.getElementById("btn-new-session");
    const providerSelect = document.getElementById("provider-select");
    const streamCheckbox = document.getElementById("stream-checkbox");
    const outputCard = document.getElementById("output-card");
    const thinkingBox = document.getElementById("thinking-box");
    const thinkingContent = document.getElementById("thinking-content");
    const answerContent = document.getElementById("answer-content");
    const sourcesSection = document.getElementById("sources-section");
    const sourcesGrid = document.getElementById("sources-grid");
    const sessionInfo = document.getElementById("session-info");

    btnNewSession.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "Session " + new Date().toLocaleTimeString() })
        });
        const data = await res.json();
        activeSessionId = data.session_id;
        sessionInfo.textContent = `Session: ${activeSessionId.substring(0, 8)}... (${data.title})`;
      } catch (err) {
        console.error("Failed to create session", err);
      }
    });

    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") btnSearch.click();
    });

    btnSearch.addEventListener("click", async () => {
      const query = queryInput.value.trim();
      if (!query) return;

      btnSearch.disabled = true;
      outputCard.style.display = "flex";
      thinkingBox.style.display = "none";
      thinkingContent.textContent = "";
      answerContent.textContent = "Analyzing query with Grip SDK...";
      sourcesSection.style.display = "none";
      sourcesGrid.innerHTML = "";

      const provider = providerSelect.value;
      const isStream = streamCheckbox.checked;

      if (isStream) {
        try {
          const res = await fetch("/api/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, provider, session_id: activeSessionId })
          });

          const reader = res.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";
          let fullAnswer = "";

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\\n");
            buffer = lines.pop();

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.event === "thinking" || data.type === "thinking") {
                    thinkingBox.style.display = "block";
                    thinkingContent.textContent += (data.thinking || data.content || "");
                  } else if (data.event === "delta" || data.type === "delta") {
                    if (fullAnswer === "") answerContent.textContent = "";
                    const chunk = data.delta || data.content || "";
                    fullAnswer += chunk;
                    answerContent.textContent = fullAnswer;
                  } else if (data.event === "done" && data.response) {
                    if (data.response.sources && data.response.sources.length) {
                      renderSources(data.response.sources);
                    }
                  }
                } catch (e) {
                  // non-json chunk or partial
                }
              }
            }
          }
          if (!fullAnswer && answerContent.textContent.includes("Analyzing")) {
            answerContent.textContent = "Search complete.";
          }
        } catch (err) {
          answerContent.textContent = "Stream error: " + err.message;
        } finally {
          btnSearch.disabled = false;
        }
      } else {
        try {
          const res = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, provider, session_id: activeSessionId })
          });
          const data = await res.json();
          if (data.error) {
            answerContent.textContent = "Error: " + data.error;
          } else {
            if (data.thinking) {
              thinkingBox.style.display = "block";
              thinkingContent.textContent = data.thinking;
            }
            answerContent.textContent = data.answer || "No text answer returned.";
            if (data.sources && data.sources.length) {
              renderSources(data.sources);
            }
          }
        } catch (err) {
          answerContent.textContent = "Request error: " + err.message;
        } finally {
          btnSearch.disabled = false;
        }
      }
    });

    function renderSources(sources) {
      sourcesSection.style.display = "block";
      sourcesGrid.innerHTML = "";
      sources.forEach(s => {
        const card = document.createElement("a");
        card.className = "source-card";
        card.href = s.link || s.url || "#";
        card.target = "_blank";
        
        const domain = (s.link || s.url || "").replace(/^https?:\\/\\//, "").split("/")[0];
        card.innerHTML = `
          <div class="source-title">${s.title || "Reference"}</div>
          <div class="source-domain">${domain || "Source"}</div>
        `;
        sourcesGrid.appendChild(card);
      });
    }
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        version=__version__,
        backend=TARGET_BACKEND,
    )


@app.route("/api/health")
def health():
    ready, reason = sdk.ready()
    return jsonify({
        "status": "ok",
        "sdk_version": __version__,
        "backend": TARGET_BACKEND,
        "ready": ready,
        "reason": reason,
        "active_sessions": sdk.sessions.count() if hasattr(sdk.sessions, "count") else len(sdk.sessions.list()),
    })


@app.route("/api/search", methods=["POST"])
def search():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    provider = payload.get("provider")
    session_id = payload.get("session_id")

    try:
        res = sdk.search.query(query, provider=provider, session_id=session_id)
        return jsonify(res.to_dict() if hasattr(res, "to_dict") else res)
    except Exception as exc:
        logger.exception("Search query error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/stream", methods=["POST"])
def stream():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    provider = payload.get("provider")
    session_id = payload.get("session_id")

    def generate():
        try:
            for chunk in sdk.search.stream(query, provider=provider, session_id=session_id):
                chunk_dict = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
                yield f"data: {json.dumps(chunk_dict)}\n\n"
        except Exception as exc:
            logger.exception("Stream error: %s", exc)
            yield f"data: {json.dumps({'event': 'error', 'error': str(exc)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/sessions", methods=["GET", "POST"])
def sessions():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        session = sdk.sessions.create(title=title)
        return jsonify(session.to_dict() if hasattr(session, "to_dict") else session)
    else:
        items = sdk.sessions.list_dicts()
        return jsonify(items)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"🚀 Grip SDK Interactive Test Server running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
