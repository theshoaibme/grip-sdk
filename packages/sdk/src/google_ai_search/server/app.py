"""Flask application factory and API endpoints for Google AI Search."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import tempfile
import time
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

UPLOAD_FOLDER = os.environ.get("GRIP_UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "grip_uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

from ..config import Config, get_config
from ..core.cache import TTLCache
from ..core.engine import GoogleAIModeEngine
from ..core.ratelimit import RateLimiter
from ..core.session_store import SessionStore
from ..errors import error_response, register_error_handlers
from ..exceptions import (
    BotBlockedError,
    ConfigError,
    GoogleAISearchError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
)


def create_app(
    cfg: Config | None = None,
    engine: Any = None,
    session_manager: SessionStore | None = None,
    client: Any = None,
) -> Flask:
    """Application factory for Google AI Search HTTP server."""
    from ..client import GoogleAI

    # Locate templates relative to package
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, "templates")
    if not os.path.isdir(templates_dir):
        # Fallback to parent templates
        templates_dir = os.path.join(os.path.dirname(current_dir), "templates")

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=os.path.join(os.path.dirname(current_dir), "static"),
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    config = cfg or get_config()

    if engine is None:
        engine = GoogleAIModeEngine(config)

    if session_manager is None:
        session_manager = SessionStore(default_ttl_sec=config.session_ttl_sec)

    if client is None:
        client = GoogleAI(config=config, engine=engine, session_store=session_manager)

    cache = TTLCache(ttl=config.cache_ttl, max_entries=config.cache_max_entries)
    limiter = RateLimiter(
        capacity=config.rate_limit_capacity,
        refill_per_sec=config.rate_limit_refill_per_sec,
        global_capacity=config.rate_limit_capacity * 4,
    )

    app.extensions["engine"] = engine
    app.extensions["session_manager"] = session_manager
    app.extensions["sdk_client"] = client
    app.extensions["cache"] = cache
    app.extensions["limiter"] = limiter
    app.extensions["search_provider"] = engine
    app.extensions["answer_provider"] = engine

    def _get_engine():
        return app.extensions.get("engine", engine)

    def _get_sm() -> SessionStore:
        return app.extensions.get("session_manager", session_manager)

    def _client_key() -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def _as_dict(obj: Any) -> Any:
        if obj is None:
            return {}
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, dict):
            return obj
        return obj

    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def _validate_query(payload: Any) -> tuple[str | None, Response | None]:
        if not isinstance(payload, dict):
            return None, error_response("Request body must be a JSON object", 400)
        query = payload.get("query") or payload.get("input") or payload.get("message") or ""
        if not isinstance(query, str) or not query.strip():
            return None, error_response("'query' must be a non-empty string", 400)
        return query.strip(), None

    def _cache_key(query: str, thread_id: str | None = None) -> str:
        payload = {"q": query, "th": thread_id or ""}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    # --- UI & Health ---

    @app.get("/")
    def index():
        eng = _get_engine()
        return render_template("index.html", port=config.port, provider=getattr(eng, "name", "google_ai"))

    @app.get("/health")
    def health():
        eng = _get_engine()
        sm = _get_sm()
        ready, reason = eng.ready() if hasattr(eng, "ready") else (True, "ok")
        provider_name = getattr(eng, "name", "google_ai")
        return jsonify({
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "reason": reason,
            "provider": provider_name,
            "answer_provider": provider_name,
            "answer_ready": ready,
            "answer_reason": reason,
            "active_sessions": sm.count(),
        })

    @app.post("/verify/clear")
    def verify_clear():
        from ..core.engine import clear_profile_cookies

        ok = clear_profile_cookies(config.browser_user_data_dir)
        return jsonify({
            "status": "ok" if ok else "warning",
            "cleared": ok,
            "profile_dir": config.browser_user_data_dir,
            "message": "Browser profile cookies and cache cleared successfully.",
        })

    @app.get("/verify/status")
    def verify_status():
        eng = _get_engine()
        ready, reason = eng.ready()
        return jsonify({
            "ready": ready,
            "reason": reason,
            "headless": config.browser_headless,
            "user_data_dir": config.browser_user_data_dir,
            "proxy_configured": bool(config.proxy_server),
            "fallback_enabled": getattr(config, "fallback_on_block", True),
        })

    # --- Direct AI Search ---

    @app.post("/search")
    @app.post("/api/v1/search")
    @app.post("/ai-search")
    @app.post("/answer")
    def search():
        payload = request.get_json(silent=True)
        query, err = _validate_query(payload)
        if err:
            return err

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response(
                "Rate limit exceeded for this client",
                429,
                retry_after=retry_after,
            )

        eng = _get_engine()
        sm = _get_sm()
        session_id = payload.get("session_id") if isinstance(payload, dict) else None

        # If executed inside a session, dispatch via the session
        if session_id:
            try:
                session = sm.get_or_create(session_id=session_id, engine=eng)
                res = session.ask(query, engine=eng)
                return jsonify(_as_dict(res))
            except BotBlockedError as exc:
                return error_response(str(exc), 403)
            except ProviderError as exc:
                return error_response(str(exc), 502)
            except Exception as exc:
                app.logger.exception("Session query error: %s", exc)
                return error_response("Internal search error", 500)

        # Check cache for standalone queries
        ckey = _cache_key(query)
        cached = cache.get(ckey)
        if cached is not None:
            resp = jsonify({**cached, "cached": True})
            resp.headers["X-Search-Cache"] = "HIT"
            return resp

        try:
            res = eng.search(query)
        except QuotaExceededError as exc:
            return error_response(str(exc), 429, retry_after=60)
        except BotBlockedError as exc:
            return error_response(str(exc), 403)
        except ConfigError as exc:
            return error_response(str(exc), 500)
        except ProviderError as exc:
            return error_response(str(exc), 502)
        except Exception as exc:
            app.logger.exception("Search execution error: %s", exc)
            return error_response("Internal search error", 500)

        body = _as_dict(res)
        if isinstance(body, dict):
            cache.set(ckey, body)
        resp = jsonify(body)
        resp.headers["X-Search-Cache"] = "MISS"
        return resp

    @app.post("/search/stream")
    @app.post("/api/v1/search/stream")
    @app.post("/ai-search/stream")
    def search_stream():
        payload = request.get_json(silent=True)
        query, err = _validate_query(payload)
        if err:
            return err

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response(
                "Rate limit exceeded for this client",
                429,
                retry_after=retry_after,
            )

        eng = _get_engine()
        sm = _get_sm()
        session_id = payload.get("session_id") if isinstance(payload, dict) else None

        def generate():
            try:
                delay_sec = max(0.012, (config.stream_delay_ms / 1000.0) if hasattr(config, "stream_delay_ms") and config.stream_delay_ms else 0.02)
                if session_id:
                    session = sm.get_or_create(session_id=session_id, engine=eng)
                    for chunk in session.stream(query, engine=eng):
                        cdata = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
                        event_type = cdata.get("event", "message")
                        yield _sse(event_type, cdata)
                        if event_type == "delta":
                            time.sleep(delay_sec)
                else:
                    for chunk in eng.stream_search(query):
                        cdata = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
                        event_type = cdata.get("event", "message")
                        yield _sse(event_type, cdata)
                        if event_type == "delta":
                            time.sleep(delay_sec)
            except BotBlockedError as exc:
                yield _sse("error", {"message": str(exc), "status": 403})
            except QuotaExceededError as exc:
                yield _sse("error", {"message": str(exc), "status": 429})
            except ProviderError as exc:
                yield _sse("error", {"message": str(exc), "status": 502})
            except Exception as exc:
                app.logger.exception("Search stream failure: %s", exc)
                yield _sse("error", {"message": str(exc), "status": 500})

        stream = Response(generate(), mimetype="text/event-stream")
        stream.headers["Cache-Control"] = "no-cache"
        stream.headers["X-Accel-Buffering"] = "no"
        return stream

    # --- Conversational Input Sessions Endpoints ---

    @app.post("/sessions")
    @app.post("/api/v1/sessions")
    def create_session():
        eng = _get_engine()
        sm = _get_sm()
        payload = request.get_json(silent=True) or {}
        title = payload.get("title") if isinstance(payload, dict) else None
        session = sm.create(title=title, engine=eng)

        initial_query = payload.get("query") if isinstance(payload, dict) else None
        initial_response = None
        if initial_query and isinstance(initial_query, str) and initial_query.strip():
            try:
                initial_res = session.ask(initial_query.strip(), engine=eng)
                initial_response = _as_dict(initial_res)
            except Exception as exc:
                app.logger.warning("Initial query in session creation failed: %s", exc)

        data: dict[str, Any] = {"session": _as_dict(session)}
        if initial_response:
            data["initial_response"] = initial_response
        return jsonify(data), 201

    @app.get("/sessions")
    @app.get("/api/v1/sessions")
    def list_sessions():
        sm = _get_sm()
        limit = request.args.get("limit", default=50, type=int)
        offset = request.args.get("offset", default=0, type=int)
        sessions = sm.list_all(limit=limit, offset=offset)
        return jsonify({
            "sessions": sessions,
            "total": sm.count(),
            "limit": limit,
            "offset": offset,
        })

    @app.get("/sessions/<session_id>")
    @app.get("/api/v1/sessions/<session_id>")
    def get_session(session_id: str):
        sm = _get_sm()
        session = sm.get(session_id)
        if not session:
            return error_response(f"Session '{session_id}' not found", 404)
        return jsonify(_as_dict(session))

    @app.post("/sessions/<session_id>/query")
    @app.post("/sessions/<session_id>/ask")
    @app.post("/api/v1/sessions/<session_id>/query")
    @app.post("/api/v1/sessions/<session_id>/ask")
    def session_query(session_id: str):
        eng = _get_engine()
        sm = _get_sm()
        session = sm.get(session_id)
        if not session:
            return error_response(f"Session '{session_id}' not found", 404)

        query, err = _validate_query(request.get_json(silent=True))
        if err:
            return err

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response(
                "Rate limit exceeded for this client",
                429,
                retry_after=retry_after,
            )

        try:
            res = session.ask(query, engine=eng)
            res_dict = _as_dict(res)
            return jsonify({
                **(res_dict if isinstance(res_dict, dict) else {"answer": str(res_dict)}),
                "session": _as_dict(session),
            })
        except BotBlockedError as exc:
            return error_response(str(exc), 403)
        except ProviderError as exc:
            return error_response(str(exc), 502)
        except Exception as exc:
            app.logger.exception("Session query execution error: %s", exc)
            return error_response(f"Search error: {exc}", 500)

    @app.post("/sessions/<session_id>/stream")
    @app.post("/api/v1/sessions/<session_id>/stream")
    def session_stream(session_id: str):
        eng = _get_engine()
        sm = _get_sm()
        session = sm.get(session_id)
        if not session:
            return error_response(f"Session '{session_id}' not found", 404)

        query, err = _validate_query(request.get_json(silent=True))
        if err:
            return err

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response(
                "Rate limit exceeded for this client",
                429,
                retry_after=retry_after,
            )

        # Compile query with active rules / identity / response format
        rules_str = client.rules.compile() if hasattr(client, "rules") else ""
        skills_str = client.skills.compile() if hasattr(client, "skills") else ""
        directives = [str(d) for d in (rules_str, skills_str) if d and isinstance(d, str) and str(d).strip()]
        compiled_query = f"{query}\n\n" + "\n\n".join(directives) if directives else None

        def generate():
            try:
                delay_sec = max(0.012, (config.stream_delay_ms / 1000.0) if hasattr(config, "stream_delay_ms") and config.stream_delay_ms else 0.02)
                for chunk in session.stream(query, engine=eng, compiled_query=compiled_query):
                    cdata = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
                    event_type = cdata.get("event", "message")
                    yield _sse(event_type, cdata)
                    if event_type == "delta":
                        time.sleep(delay_sec)
            except BotBlockedError as exc:
                yield _sse("error", {"message": str(exc), "status": 403})
            except ProviderError as exc:
                yield _sse("error", {"message": str(exc), "status": 502})
            except Exception as exc:
                app.logger.exception("Session stream error: %s", exc)
                yield _sse("error", {"message": str(exc), "status": 500})

        stream = Response(generate(), mimetype="text/event-stream")
        stream.headers["Cache-Control"] = "no-cache"
        stream.headers["X-Accel-Buffering"] = "no"
        return stream

    @app.delete("/sessions/<session_id>")
    @app.delete("/api/v1/sessions/<session_id>")
    def delete_session(session_id: str):
        sm = _get_sm()
        deleted = sm.delete(session_id)
        if not deleted:
            return error_response(f"Session '{session_id}' not found", 404)
        return jsonify({"deleted": True, "session_id": session_id})

    @app.delete("/sessions")
    @app.delete("/api/v1/sessions")
    @app.post("/sessions/clear")
    @app.post("/api/v1/sessions/clear")
    def clear_sessions():
        sm = _get_sm()
        count = sm.clear()
        return jsonify({"cleared": True, "count": count})

    @app.post("/upload")
    @app.post("/api/v1/upload")
    def upload_file():
        if "file" not in request.files:
            return error_response("no file field provided", 400)
        uploaded = request.files["file"]
        if not uploaded.filename:
            return error_response("empty filename", 400)

        raw_bytes = uploaded.read()
        filename = uploaded.filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ").strip() or "upload"
        ext = os.path.splitext(safe_name)[1].lower()

        # Categorize file type
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff"}
        audio_exts = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm", ".opus", ".weba"}
        video_exts = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".ogv"}

        mime_type, _ = mimetypes.guess_type(safe_name)
        if not mime_type:
            if ext in image_exts:
                mime_type = f"image/{ext.lstrip('.')}"
            elif ext in audio_exts:
                mime_type = f"audio/{ext.lstrip('.')}"
            elif ext in video_exts:
                mime_type = f"video/{ext.lstrip('.')}"
            else:
                mime_type = "application/octet-stream"

        if ext in image_exts:
            media_type = "image"
        elif ext in audio_exts:
            media_type = "audio"
        elif ext in video_exts:
            media_type = "video"
        else:
            media_type = "document"

        # Unique saved filename to avoid collisions
        unique_prefix = f"{int(time.time())}_{os.urandom(4).hex()}"
        saved_filename = f"{unique_prefix}_{safe_name}"
        saved_path = os.path.join(UPLOAD_FOLDER, saved_filename)
        with open(saved_path, "wb") as f:
            f.write(raw_bytes)

        # Content representation for model context
        if media_type == "document":
            try:
                content = raw_bytes.decode("utf-8")
            except Exception:
                content = raw_bytes.decode("utf-8", errors="replace")
        else:
            size_kb = round(len(raw_bytes) / 1024, 1)
            content = f"[Attached {media_type.capitalize()}: {safe_name} ({size_kb} KB)]"

        # Base64 data URL for instant frontend rendering if <= 10MB
        data_url = None
        if len(raw_bytes) <= 10 * 1024 * 1024:
            b64_str = base64.b64encode(raw_bytes).decode("ascii")
            data_url = f"data:{mime_type};base64,{b64_str}"

        url = f"/uploads/{saved_filename}"

        return jsonify({
            "filename": safe_name.lower(),
            "saved_filename": saved_filename,
            "size": len(raw_bytes),
            "content": content,
            "type": media_type,
            "mime_type": mime_type,
            "url": url,
            "data_url": data_url or url,
        }), 201

    @app.get("/uploads/<path:filename>")
    @app.get("/api/v1/uploads/<path:filename>")
    def serve_uploaded_file(filename: str):
        return send_from_directory(UPLOAD_FOLDER, filename)

    # --- Agent Capabilities Endpoints ---

    @app.get("/rules")
    @app.get("/api/v1/rules")
    def list_rules():
        return jsonify({
            "rules": _as_dict(client.rules),
            "identity": client.rules.identity or "",
            "response_format": client.rules.response_format or "",
            "compiled": client.rules.compile(),
            "total": client.rules.count(),
            "active_count": len(client.rules.list(active_only=True)),
        })

    @app.post("/rules")
    @app.post("/api/v1/rules")
    def add_rule():
        payload = request.get_json(silent=True) or {}
        content = payload.get("content") or payload.get("rule")
        if not content:
            return error_response("'content' is required", 400)
        rule = client.rules.add(
            content=content,
            name=payload.get("name"),
            priority=payload.get("priority", 1),
            active=payload.get("active", True),
        )
        return jsonify(_as_dict(rule)), 201

    @app.post("/rules/system")
    @app.put("/rules/system")
    @app.post("/api/v1/rules/system")
    @app.put("/api/v1/rules/system")
    def update_system_rules():
        payload = request.get_json(silent=True) or {}
        if "identity" in payload:
            client.rules.set_identity(payload["identity"])
        if "response_format" in payload:
            client.rules.set_response_format(payload["response_format"])
        return jsonify({
            "updated": True,
            "identity": client.rules.identity or "",
            "response_format": client.rules.response_format or "",
            "compiled": client.rules.compile(),
        })

    @app.post("/rules/<name>/toggle")
    @app.patch("/rules/<name>")
    @app.post("/api/v1/rules/<name>/toggle")
    @app.patch("/api/v1/rules/<name>")
    def toggle_rule(name: str):
        payload = request.get_json(silent=True) or {}
        active = payload.get("active")
        rule = client.rules.toggle(name, active=active)
        if not rule:
            return error_response(f"rule '{name}' not found", 404)
        return jsonify(_as_dict(rule))

    @app.post("/rules/reset")
    @app.post("/api/v1/rules/reset")
    def reset_rules():
        client.rules.reset()
        return jsonify({"reset": True})

    @app.delete("/rules/<name>")
    @app.delete("/api/v1/rules/<name>")
    def delete_rule(name: str):
        deleted = client.rules.remove(name)
        if not deleted:
            return error_response(f"rule '{name}' not found", 404)
        return jsonify({"deleted": True, "name": name})

    @app.get("/skills")
    @app.get("/api/v1/skills")
    def list_skills():
        return jsonify({"skills": _as_dict(client.skills), "total": client.skills.count()})

    @app.post("/skills")
    @app.post("/api/v1/skills")
    def add_skill():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        description = payload.get("description", "")
        instructions = payload.get("instructions", "")
        if not name or not instructions:
            return error_response("'name' and 'instructions' are required", 400)
        skill = client.skills.register(
            name=name,
            description=description,
            instructions=instructions,
            tools=payload.get("tools"),
        )
        return jsonify(_as_dict(skill)), 201

    @app.delete("/skills/<name>")
    @app.delete("/api/v1/skills/<name>")
    def delete_skill(name: str):
        deleted = client.skills.delete(name)
        if not deleted:
            return error_response(f"skill '{name}' not found", 404)
        return jsonify({"deleted": True, "name": name})

    @app.get("/tools")
    @app.get("/api/v1/tools")
    def list_tools():
        return jsonify({"tools": _as_dict(client.tools)})

    @app.post("/tools/call")
    @app.post("/api/v1/tools/call")
    def call_tool():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        if not name:
            return error_response("'name' is required", 400)
        kwargs = payload.get("args") or payload.get("kwargs") or {}
        try:
            result = client.tools.call(name, **kwargs)
            return jsonify({"tool": name, "result": result})
        except KeyError:
            return error_response(f"tool '{name}' not found", 404)
        except Exception as exc:
            return error_response(f"tool error: {exc}", 500)

    @app.post("/plan/execute")
    @app.post("/api/v1/plan/execute")
    def execute_plan():
        payload = request.get_json(silent=True) or {}
        goal = payload.get("goal")
        steps = payload.get("steps") or []
        if not goal:
            return error_response("'goal' is required", 400)
        plan = client.plan.create(
            goal=goal,
            steps=steps,
            strict_order=payload.get("strict_order", True),
            abort_on_failure=payload.get("abort_on_failure", True),
        )
        result = plan.execute(client)
        return jsonify(_as_dict(result))

    @app.post("/workflows/execute")
    @app.post("/api/v1/workflows/execute")
    def execute_workflow():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name", "pipeline")
        steps = payload.get("steps") or []
        wf = client.workflows.create(name=name)
        for s in steps:
            wf.add_step(
                action=s.get("action", "search"),
                name=s.get("name"),
                **s.get("params", {}),
            )
        result = wf.run(client, initial_input=payload.get("input"))
        return jsonify(_as_dict(result))

    register_error_handlers(app)
    return app
