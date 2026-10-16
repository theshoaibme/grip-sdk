"""Web server application built using the Grip SDK library.

This server application uses the Grip SDK (`grip.Grip`)
to build the HTTP API and serve the clean monochrome web UI.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from flask import Flask, Response, jsonify, render_template, request

import grip
from grip import BotBlockedError, ProviderError, RateLimiter, TTLCache
from google_ai_search.config import Config, get_config
from google_ai_search.errors import error_response, register_error_handlers
from google_ai_search.exceptions import QuotaExceededError


def create_app(
    config: Config | None = None,
    client: grip.Grip | None = None,
) -> Flask:
    """Build the web server using the Grip SDK client."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, "templates")

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=os.path.join(current_dir, "static"),
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    cfg = config or grip.get_config()
    sdk_client = client or grip.Grip(config=cfg)

    cache = TTLCache(ttl=getattr(cfg, "cache_ttl", 3600), max_entries=getattr(cfg, "cache_max_entries", 500))
    rate_cap = getattr(cfg, "rate_limit_capacity", 30)
    rate_refill = getattr(cfg, "rate_limit_refill_per_sec", 1.0)
    limiter = RateLimiter(
        capacity=rate_cap,
        refill_per_sec=rate_refill,
        global_capacity=rate_cap * 4,
    )


    app.extensions["sdk_client"] = sdk_client
    app.extensions["engine"] = sdk_client.engine
    app.extensions["session_manager"] = sdk_client.session_store
    app.extensions["cache"] = cache
    app.extensions["limiter"] = limiter

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
            return None, error_response("request body must be a json object", 400)
        query = payload.get("query") or payload.get("input") or payload.get("message") or ""
        if not isinstance(query, str) or not query.strip():
            return None, error_response("'query' must be a non-empty string", 400)
        return query.strip(), None

    # --- UI & Health ---

    @app.get("/")
    def index():
        return render_template("index.html", port=cfg.port)

    @app.get("/health")
    @app.get("/api/health")
    def health():
        ready, reason = sdk_client.ready()
        return jsonify({
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "reason": reason,
            "provider": getattr(sdk_client, "provider_name", getattr(getattr(sdk_client, "engine", None), "name", "grip")),
            "active_sessions": (
                sdk_client.sessions.count()
                if hasattr(sdk_client.sessions, "count")
                else len(sdk_client.sessions.list())
                if hasattr(sdk_client.sessions, "list")
                else 0
            ),
        })

    @app.post("/verify/clear")
    def verify_clear():
        from google_ai_search.core.engine import clear_profile_cookies

        ok = clear_profile_cookies(cfg.browser_user_data_dir)
        return jsonify({
            "status": "ok" if ok else "warning",
            "cleared": ok,
            "profile_dir": cfg.browser_user_data_dir,
            "message": "Browser profile cookies and cache cleared successfully.",
        })

    @app.get("/verify/status")
    def verify_status():
        ready, reason = sdk_client.ready()
        return jsonify({
            "ready": ready,
            "reason": reason,
            "headless": cfg.browser_headless,
            "user_data_dir": cfg.browser_user_data_dir,
            "proxy_configured": bool(cfg.proxy_server),
            "fallback_enabled": getattr(cfg, "fallback_on_block", True),
        })

    @app.get("/profile")
    @app.get("/api/v1/profile")
    def profile_status():
        from google_ai_search.core.profile import (
            detect_system_chrome_profile,
            detect_system_chrome_version,
            extract_client_user_agent,
            get_chrome_profile,
            is_profile_locked,
        )

        detected_sys = detect_system_chrome_profile()
        active_prof = get_chrome_profile(
            target_dir=cfg.browser_user_data_dir,
            prefer_system=getattr(cfg, "browser_use_system_profile", False),
        )
        client_ua = extract_client_user_agent(request)

        return jsonify({
            "system_chrome_profile": detected_sys,
            "active_browser_profile": active_prof,
            "is_system_profile_locked": is_profile_locked(detected_sys) if detected_sys else False,
            "detected_chrome_version": detect_system_chrome_version(),
            "client_user_agent": client_ua,
            "anti_detection_ready": True,
        })

    @app.get("/models")
    @app.get("/api/v1/models")
    def list_models():
        models = sdk_client.list_models() if hasattr(sdk_client, "list_models") else []
        return jsonify({"models": models, "count": len(models)})

    @app.get("/providers")
    @app.get("/api/v1/providers")
    def list_providers():
        provs = sdk_client.list_providers() if hasattr(sdk_client, "list_providers") else []
        return jsonify({"providers": provs, "count": len(provs)})

    # --- Search Endpoints ---

    @app.post("/search")
    @app.post("/api/search")
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
            return error_response("rate limit exceeded", 429, retry_after=retry_after)

        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        provider = payload.get("provider") if isinstance(payload, dict) else None

        from google_ai_search.core.profile import extract_client_user_agent
        client_ua = extract_client_user_agent(request)

        try:
            kwargs: dict[str, Any] = {"session_id": session_id, "user_agent": client_ua}
            if provider:
                kwargs["provider"] = provider
            res = sdk_client.search.query(query, **kwargs)
            return jsonify(_as_dict(res))
        except BotBlockedError as exc:
            return error_response(str(exc), 403)
        except ProviderError as exc:
            return error_response(str(exc), 502)
        except Exception as exc:
            app.logger.exception("Search error: %s", exc)
            return error_response("internal search error", 500)

    @app.post("/search/stream")
    @app.post("/api/stream")
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
            return error_response("rate limit exceeded", 429, retry_after=retry_after)

        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        provider = payload.get("provider") if isinstance(payload, dict) else None

        from google_ai_search.core.profile import extract_client_user_agent
        client_ua = extract_client_user_agent(request)

        def generate():
            try:
                delay_sec = max(0.002, (cfg.stream_delay_ms / 1000.0) if hasattr(cfg, "stream_delay_ms") and cfg.stream_delay_ms else 0.01)
                stream_kwargs: dict[str, Any] = {"session_id": session_id, "user_agent": client_ua}
                if provider:
                    stream_kwargs["provider"] = provider
                for chunk in sdk_client.search.stream(query, **stream_kwargs):
                    cdata = _as_dict(chunk)
                    event_type = cdata.get("event", "message") if isinstance(cdata, dict) else "message"
                    yield _sse(event_type, cdata if isinstance(cdata, dict) else {"content": str(cdata)})
                    if event_type == "delta":
                        time.sleep(delay_sec)
            except BotBlockedError as exc:
                yield _sse("error", {"message": str(exc), "status": 403})
            except QuotaExceededError as exc:
                yield _sse("error", {"message": str(exc), "status": 429})
            except ProviderError as exc:
                yield _sse("error", {"message": str(exc), "status": 502})
            except Exception as exc:
                app.logger.exception("Stream failure: %s", exc)
                yield _sse("error", {"message": str(exc), "status": 500})

        stream = Response(generate(), mimetype="text/event-stream")
        stream.headers["Cache-Control"] = "no-cache"
        stream.headers["X-Accel-Buffering"] = "no"
        return stream

    # --- Sessions Endpoints ---

    @app.post("/sessions")
    @app.post("/api/sessions")
    @app.post("/api/v1/sessions")
    def create_session():
        payload = request.get_json(silent=True) or {}
        title = payload.get("title") if isinstance(payload, dict) else None
        session = sdk_client.sessions.create(title=title)

        initial_query = payload.get("query") if isinstance(payload, dict) else None
        initial_response = None
        if initial_query and isinstance(initial_query, str) and initial_query.strip():
            try:
                if hasattr(session, "ask"):
                    res = session.ask(initial_query.strip())
                else:
                    res = sdk_client.sessions.query(session.session_id, initial_query.strip())
                initial_response = _as_dict(res)
            except Exception as exc:
                app.logger.warning("Initial query in session failed: %s", exc)

        data: dict[str, Any] = {"session": _as_dict(session)}
        if initial_response:
            data["initial_response"] = initial_response
        return jsonify(data), 201

    @app.get("/sessions")
    @app.get("/api/sessions")
    @app.get("/api/v1/sessions")
    def list_sessions():
        limit = request.args.get("limit", default=50, type=int)
        offset = request.args.get("offset", default=0, type=int)
        sessions = sdk_client.sessions.list_dicts(limit=limit, offset=offset)
        return jsonify({
            "sessions": sessions,
            "total": sdk_client.sessions.count(),
            "limit": limit,
            "offset": offset,
        })

    @app.get("/sessions/<session_id>")
    @app.get("/api/v1/sessions/<session_id>")
    def get_session(session_id: str):
        session = sdk_client.sessions.get(session_id)
        if not session:
            return error_response(f"session '{session_id}' not found", 404)
        return jsonify(_as_dict(session))

    @app.post("/sessions/<session_id>/query")
    @app.post("/sessions/<session_id>/ask")
    @app.post("/api/v1/sessions/<session_id>/query")
    @app.post("/api/v1/sessions/<session_id>/ask")
    def session_query(session_id: str):
        session = sdk_client.sessions.get(session_id)
        if not session:
            return error_response(f"session '{session_id}' not found", 404)

        query, err = _validate_query(request.get_json(silent=True))
        if err:
            return err

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response("rate limit exceeded", 429, retry_after=retry_after)

        try:
            if hasattr(session, "ask"):
                res = session.ask(query)
            else:
                res = sdk_client.sessions.query(session_id, query)
            updated = sdk_client.sessions.get(session_id) or session
            res_dict = _as_dict(res)
            return jsonify({
                **(res_dict if isinstance(res_dict, dict) else {"answer": str(res_dict)}),
                "session": _as_dict(updated),
            })
        except BotBlockedError as exc:
            return error_response(str(exc), 403)
        except ProviderError as exc:
            return error_response(str(exc), 502)
        except Exception as exc:
            app.logger.exception("Session query error: %s", exc)
            return error_response(f"search error: {exc}", 500)

    @app.post("/sessions/<session_id>/stream")
    @app.post("/api/v1/sessions/<session_id>/stream")
    def session_stream(session_id: str):
        session = sdk_client.sessions.get(session_id)
        if not session:
            return error_response(f"session '{session_id}' not found", 404)

        payload = request.get_json(silent=True) or {}
        query, err = _validate_query(payload)
        if err:
            return err

        provider = payload.get("provider") if isinstance(payload, dict) else None

        client_ip = _client_key()
        allowed, retry_after = limiter.check(client_ip)
        if not allowed:
            return error_response("rate limit exceeded", 429, retry_after=retry_after)

        # Compile query with active rules / identity / response format
        rules_str = sdk_client.rules.compile() if hasattr(sdk_client, "rules") else ""
        skills_str = sdk_client.skills.compile() if hasattr(sdk_client, "skills") else ""
        directives = [str(d) for d in (rules_str, skills_str) if d and isinstance(d, str) and str(d).strip()]
        compiled_query = f"{query}\n\n" + "\n\n".join(directives) if directives else None

        def generate():
            try:
                delay_sec = max(0.012, (cfg.stream_delay_ms / 1000.0) if hasattr(cfg, "stream_delay_ms") and cfg.stream_delay_ms else 0.02)
                stream_kwargs: dict[str, Any] = {}
                if provider:
                    stream_kwargs["provider"] = provider
                if hasattr(session, "stream"):
                    try:
                        stream_gen = session.stream(query, compiled_query=compiled_query, **stream_kwargs)
                    except TypeError:
                        stream_gen = session.stream(compiled_query or query, **stream_kwargs)
                else:
                    stream_gen = sdk_client.sessions.stream(session_id, compiled_query or query, **stream_kwargs)

                for chunk in stream_gen:
                    cdata = _as_dict(chunk)
                    event_type = cdata.get("event", "message") if isinstance(cdata, dict) else "message"
                    yield _sse(event_type, cdata if isinstance(cdata, dict) else {"content": str(cdata)})
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
        deleted = sdk_client.sessions.delete(session_id)
        if not deleted:
            return error_response(f"session '{session_id}' not found", 404)
        return jsonify({"deleted": True, "session_id": session_id})

    @app.delete("/sessions")
    @app.delete("/api/v1/sessions")
    @app.post("/sessions/clear")
    @app.post("/api/v1/sessions/clear")
    def clear_sessions():
        count = sdk_client.sessions.clear()
        return jsonify({"cleared": True, "count": count})

    @app.post("/upload")
    @app.post("/api/v1/upload")
    def upload_file():
        if "file" not in request.files:
            return error_response("no file field provided", 400)
        uploaded = request.files["file"]
        if not uploaded.filename:
            return error_response("empty filename", 400)
        content = uploaded.read().decode("utf-8", errors="replace")
        return jsonify({
            "filename": uploaded.filename.lower(),
            "size": len(content),
            "content": content,
        }), 201

    # --- Agent Extensions: Rules, Skills, Tools, Plans, Workflows ---

    @app.get("/rules")
    @app.get("/api/v1/rules")
    def list_rules():
        return jsonify({
            "rules": _as_dict(sdk_client.rules),
            "identity": sdk_client.rules.identity or "",
            "response_format": sdk_client.rules.response_format or "",
            "compiled": sdk_client.rules.compile(),
            "total": sdk_client.rules.count(),
            "active_count": len(sdk_client.rules.list(active_only=True)),
        })

    @app.post("/rules")
    @app.post("/api/v1/rules")
    def add_rule():
        payload = request.get_json(silent=True) or {}
        content = payload.get("content") or payload.get("rule")
        if not content:
            return error_response("'content' is required for rule", 400)
        rule = sdk_client.rules.add(
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
            sdk_client.rules.set_identity(payload["identity"])
        if "response_format" in payload:
            sdk_client.rules.set_response_format(payload["response_format"])
        return jsonify({
            "updated": True,
            "identity": sdk_client.rules.identity or "",
            "response_format": sdk_client.rules.response_format or "",
            "compiled": sdk_client.rules.compile(),
        })

    @app.post("/rules/<name>/toggle")
    @app.patch("/rules/<name>")
    @app.post("/api/v1/rules/<name>/toggle")
    @app.patch("/api/v1/rules/<name>")
    def toggle_rule(name: str):
        payload = request.get_json(silent=True) or {}
        active = payload.get("active")
        rule = sdk_client.rules.toggle(name, active=active)
        if not rule:
            return error_response(f"rule '{name}' not found", 404)
        return jsonify(_as_dict(rule))

    @app.post("/rules/reset")
    @app.post("/api/v1/rules/reset")
    def reset_rules():
        sdk_client.rules.reset()
        return jsonify({"reset": True})

    @app.delete("/rules/<name>")
    @app.delete("/api/v1/rules/<name>")
    def delete_rule(name: str):
        deleted = sdk_client.rules.remove(name)
        if not deleted:
            return error_response(f"rule '{name}' not found", 404)
        return jsonify({"deleted": True, "name": name})

    @app.get("/skills")
    @app.get("/api/v1/skills")
    def list_skills():
        return jsonify({"skills": _as_dict(sdk_client.skills), "total": sdk_client.skills.count()})

    @app.post("/skills")
    @app.post("/api/v1/skills")
    def add_skill():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        description = payload.get("description", "")
        instructions = payload.get("instructions", "")
        if not name or not instructions:
            return error_response("'name' and 'instructions' are required", 400)
        skill = sdk_client.skills.register(
            name=name,
            description=description,
            instructions=instructions,
            tools=payload.get("tools"),
        )
        return jsonify(_as_dict(skill)), 201

    @app.delete("/skills/<name>")
    @app.delete("/api/v1/skills/<name>")
    def delete_skill(name: str):
        deleted = sdk_client.skills.delete(name)
        if not deleted:
            return error_response(f"skill '{name}' not found", 404)
        return jsonify({"deleted": True, "name": name})

    @app.get("/tools")
    @app.get("/api/v1/tools")
    def list_tools():
        return jsonify({"tools": _as_dict(sdk_client.tools)})

    @app.post("/tools/call")
    @app.post("/api/v1/tools/call")
    def call_tool():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        if not name:
            return error_response("'name' is required", 400)
        kwargs = payload.get("args") or payload.get("kwargs") or {}
        try:
            result = sdk_client.tools.call(name, **kwargs)
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
        plan = sdk_client.plan.create(
            goal=goal,
            steps=steps,
            strict_order=payload.get("strict_order", True),
            abort_on_failure=payload.get("abort_on_failure", True),
        )
        result = plan.execute(sdk_client)
        return jsonify(_as_dict(result))

    @app.post("/workflows/execute")
    @app.post("/api/v1/workflows/execute")
    def execute_workflow():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name", "pipeline")
        steps = payload.get("steps") or []
        wf = sdk_client.workflows.create(name=name)
        for s in steps:
            wf.add_step(
                action=s.get("action", "search"),
                name=s.get("name"),
                **s.get("params", {}),
            )
        result = wf.run(sdk_client, initial_input=payload.get("input"))
        return jsonify(_as_dict(result))

    register_error_handlers(app)
    return app
