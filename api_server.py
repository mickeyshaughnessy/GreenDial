"""
GreenDial API Server
Flask HTTP server for the health assistant

Reference deployment for the listening_ai package — mounts the portable
ListeningAI API at /listening (see listening_bridge.py). Native GreenDial
routes (/auth, /chat, …) are unchanged; the agentic health-tool loop inside
handlers.py is powered by ListeningAI's ChatController.
"""
import json
from flask import Flask, request, send_from_directory, Response
import config
import handlers

app = Flask(__name__, static_folder='.')

# ListeningAI reference surface (auth/profile/chat via portable API)
try:
    import listening_bridge
    listening_bridge.ensure_configured()
    app.register_blueprint(listening_bridge.make_blueprint(url_prefix="/listening"))
    print("[ListeningAI] blueprint mounted at /listening")
except Exception as e:
    print(f"[ListeningAI] blueprint not mounted: {e}")


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Session-Token, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    return response


def _session_token():
    return request.headers.get('X-Session-Token', '')


def _api_key():
    return request.headers.get('X-API-Key', '')


def _unauthorized():
    return Response(json.dumps({"error": "Unauthorized"}), status=401, mimetype='application/json')


def _require_session(user_id):
    """Returns a 401 response if the session token doesn't match, else None."""
    if not handlers.session_ok(user_id, _session_token()):
        return _unauthorized()
    return None


# ============ STATIC ============

@app.route("/", methods=['GET'])
def index():
    return send_from_directory('.', 'index.html')


@app.route("/unprompted", methods=['GET'])
def unprompted_index():
    return send_from_directory('.', 'unprompted.html')


@app.route("/docs", methods=['GET'])
def docs():
    return send_from_directory('.', 'docs.html')


@app.route("/arazzo", methods=['GET'])
def arazzo():
    return send_from_directory('.', 'arazzo.html')


@app.route("/about", methods=['GET'])
def about():
    return send_from_directory('.', 'about.html')


@app.route("/privacy", methods=['GET'])
def privacy():
    return send_from_directory('.', 'privacy.html')


@app.route("/download/android", methods=['GET'])
def download_android_apk():
    """Android APK for the landing-page download CTA (optional file on disk)."""
    import os
    candidates = [
        os.path.join('downloads', 'GreenDial.apk'),
        os.path.join('mobile', 'dist', 'GreenDial-1.0.0.apk'),
        os.path.join('mobile', 'dist', 'GreenDial.apk'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            directory, filename = os.path.split(path)
            return send_from_directory(
                directory or '.',
                filename,
                as_attachment=True,
                download_name='GreenDial.apk',
                mimetype='application/vnd.android.package-archive',
            )
    return Response(
        json.dumps({
            "error": "Android APK not published on this host yet",
            "hint": "Use the web app on mobile, or Install to Home Screen.",
        }),
        status=404,
        mimetype='application/json',
    )


@app.route("/sponsor", methods=['GET'])
def sponsor_page():
    """Demand-side Universal Bounty UI — tucked away from main chat flow."""
    return send_from_directory('.', 'sponsor.html')


@app.route("/stickers/<token>", methods=['GET'])
def sticker_board_public(token):
    return send_from_directory('.', 'stickers.html')


# ---- PWA assets (served by nginx in prod; Flask serves them in dev) ----

@app.route("/manifest.json", methods=['GET'])
def pwa_manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')


@app.route("/sw.js", methods=['GET'])
def pwa_service_worker():
    resp = send_from_directory('.', 'sw.js', mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route("/icons/<path:filename>", methods=['GET'])
def pwa_icons(filename):
    return send_from_directory('icons', filename)


@app.route("/stickers/pixel/<path:filename>", methods=['GET'])
def pixel_stickers(filename):
    """Custom 32×32 pixel-art sticker library."""
    return send_from_directory('stickers/pixel', filename)


@app.route("/stickers/cartoon/<path:filename>", methods=['GET'])
def cartoon_stickers(filename):
    """NES/SNES-inspired funny cartoon sticker library (48×48)."""
    return send_from_directory('stickers/cartoon', filename)


@app.route("/i18n/<path:filename>", methods=['GET'])
def i18n_files(filename):
    return send_from_directory('i18n', filename, mimetype='application/json' if filename.endswith('.json') else 'application/javascript')


@app.route("/themes/<path:filename>", methods=['GET'])
def theme_files(filename):
    """UI style skins + catalog/apply scripts."""
    if filename.endswith('.css'):
        mime = 'text/css'
    elif filename.endswith('.js'):
        mime = 'application/javascript'
    else:
        mime = None
    return send_from_directory('themes', filename, mimetype=mime)


# ---- Web push ----

@app.route("/push/vapid-public-key", methods=['GET'])
def push_vapid_key():
    return Response(json.dumps({"key": getattr(config, 'VAPID_PUBLIC_KEY', '')}),
                    mimetype='application/json')


@app.route("/push/subscribe/<user_id>", methods=['POST', 'OPTIONS'])
def push_subscribe(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_push_subscribe(user_id, request.get_json() or {})
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/push/unsubscribe/<user_id>", methods=['POST', 'OPTIONS'])
def push_unsubscribe(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    endpoint = (request.get_json() or {}).get('endpoint', '')
    result = handlers.handle_push_unsubscribe(user_id, endpoint)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/ping", methods=['GET'])
def ping():
    payload = {"status": "ok", "service": "greendial"}
    try:
        import listening_ai
        from listening_ai import get_settings, get_store
        s = get_settings()
        payload["listening_ai"] = {
            "version": listening_ai.__version__,
            "store": type(get_store()).__name__,
            "store_backend": s.store_backend,
            "prefix": s.spaces_prefix,
            "mounted_at": "/listening",
        }
    except Exception as e:
        payload["listening_ai"] = {"error": str(e)}
    return Response(json.dumps(payload), mimetype='application/json')


@app.route("/spec/openapi.yaml", methods=['GET'])
def spec_openapi():
    return send_from_directory('arazzo', 'greendial-openapi.yaml', mimetype='text/yaml')


@app.route("/spec/arazzo.yaml", methods=['GET'])
def spec_arazzo():
    return send_from_directory('arazzo', 'greendial-agents.arazzo.yaml', mimetype='text/yaml')


@app.route("/stats", methods=['GET'])
def stats():
    import s3_storage
    try:
        users = s3_storage.list_users()
        return Response(json.dumps({"user_count": len(users)}), mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"user_count": 0, "error": str(e)}), mimetype='application/json')


# ============ AUTHENTICATION ============

@app.route("/auth", methods=['POST', 'OPTIONS'])
def auth():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    req = request.get_json() or {}
    result = handlers.handle_auth(req)
    
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ CHAT ============

@app.route("/chat", methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    req = request.get_json() or {}
    uid = req.get('user_id', '')
    if uid and not handlers.session_ok(uid, _session_token()):
        return _unauthorized()
    result = handlers.handle_chat(req)
    return Response(result, mimetype='application/json')


# ============ DOC UNPROMPTED POLL ============

@app.route("/Doc", methods=['GET', 'OPTIONS'])
@app.route("/doc", methods=['GET', 'OPTIONS'])
def doc_poll():
    """
    Poll for an on-demand unprompted Doc message (rate-limited).
    Query: user_id (required). Optional force=1 for admin/dev.
    """
    if request.method == 'OPTIONS':
        return Response('', status=200)

    user_id = (request.args.get('user_id') or '').strip()
    if not user_id:
        return Response(
            json.dumps({"error": "user_id required", "messages": []}),
            status=400,
            mimetype='application/json',
        )
    denied = _require_session(user_id)
    if denied:
        return denied

    force = (request.args.get('force') or '').strip().lower() in ('1', 'true', 'yes')
    # force is only for admin/mickey — never for arbitrary users
    if force and not handlers._is_mickey(user_id):
        force = False

    result = handlers.handle_doc_poll(user_id, force=force)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')



# ============ USER ============

@app.route("/user/<user_id>", methods=['GET', 'OPTIONS'])
def get_user(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_user(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/user/<user_id>", methods=['DELETE', 'OPTIONS'])
def delete_user(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_delete_user(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/user/<user_id>", methods=['PUT', 'OPTIONS'])
def update_user(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    req = request.get_json() or {}
    result = handlers.handle_update_user(user_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ SETTINGS ============

@app.route("/settings/<user_id>", methods=['GET', 'OPTIONS'])
def get_settings(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_settings(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/settings/<user_id>", methods=['PUT', 'POST', 'OPTIONS'])
def update_settings(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    req = request.get_json() or {}
    result = handlers.handle_update_settings(user_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ TODAY (check-ins + suggestions + tips) ============

@app.route("/today/<user_id>", methods=['GET', 'OPTIONS'])
def get_today(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_today(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ NOTIFICATIONS ============

@app.route("/notifications/<user_id>", methods=['GET', 'OPTIONS'])
def get_notifications(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_notifications(user_id)
    return Response(result, mimetype='application/json')


@app.route("/notifications/<user_id>/generate", methods=['POST', 'OPTIONS'])
def generate_notification(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_generate_notification(user_id)
    return Response(result, mimetype='application/json')


@app.route("/notifications/<user_id>/<notification_id>", methods=['DELETE', 'OPTIONS'])
def dismiss_notification(user_id, notification_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_dismiss_notification(user_id, notification_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ CONVERSATIONS ============

@app.route("/task", methods=['POST', 'OPTIONS'])
def task():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    uid = req.get('user_id', '')
    if uid and not handlers.session_ok(uid, _session_token()):
        return _unauthorized()
    result = handlers.handle_task(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/chat/agent/<agent_id>", methods=['POST', 'OPTIONS'])
def agent_chat(agent_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    uid = req.get('user_id', '')
    if uid and not handlers.session_ok(uid, _session_token()):
        return _unauthorized()
    result = handlers.handle_agent_chat(agent_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/agents", methods=['GET', 'OPTIONS'])
def get_agent_transcripts(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_get_agent_transcripts(user_id)
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/agent/<agent_id>", methods=['DELETE', 'OPTIONS'])
def clear_agent_transcript(user_id, agent_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_clear_agent_transcript(user_id, agent_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>", methods=['GET', 'OPTIONS'])
def get_conversations(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_conversations(user_id)
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>", methods=['DELETE', 'OPTIONS'])
def clear_conversations(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_clear_transcript(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/<conversation_id>", methods=['GET', 'OPTIONS'])
def get_conversation(user_id, conversation_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied

    result = handlers.handle_get_conversation(user_id, conversation_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ UNPROMPTED (GROUP FACILITATOR) ============

@app.route("/unprompted/login", methods=['POST', 'OPTIONS'])
def unprompted_login():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_unprompted_login(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/unprompted/campaigns", methods=['GET', 'POST', 'OPTIONS'])
def unprompted_campaigns():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    if request.method == 'GET':
        result = handlers.handle_unprompted_list_campaigns()
        return Response(result, mimetype='application/json')
    req = request.get_json() or {}
    result = handlers.handle_unprompted_create_campaign(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/unprompted/assign", methods=['POST', 'OPTIONS'])
def unprompted_assign():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_unprompted_assign(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/unprompted/groups/<group_id>", methods=['GET', 'OPTIONS'])
def unprompted_group(group_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_unprompted_get_group(group_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/unprompted/message", methods=['POST', 'OPTIONS'])
def unprompted_message():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_unprompted_message(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/unprompted/sms", methods=['POST'])
def unprompted_sms():
    result = handlers.handle_unprompted_sms(request.form)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/xml')
    return Response(result, mimetype='application/xml')


# ============ AGENTS ============

@app.route("/history/<user_id>", methods=['GET', 'OPTIONS'])
def get_history(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    field = request.args.get('field')
    days = int(request.args.get('days', 30))
    result = handlers.handle_get_history(user_id, field=field, days=days)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ THIRD-PARTY API ============

@app.route("/api/v1/profile", methods=['GET', 'OPTIONS'])
def api_get_profile():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    auth_header = request.headers.get('Authorization')
    result = handlers.handle_api_profile_get(auth_header)
    
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/api/v1/profile", methods=['POST', 'PUT', 'OPTIONS'])
def api_update_profile():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    auth_header = request.headers.get('Authorization')
    req = request.get_json() or {}
    result = handlers.handle_api_profile_update(auth_header, req)
    
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ FEEDBACK ============

@app.route("/feedback", methods=['GET', 'OPTIONS'])
def get_feedback():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_feedback()
    return Response(result, mimetype='application/json')


@app.route("/feedback", methods=['POST', 'OPTIONS'])
def post_feedback():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_post_feedback(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/feedback/<post_id>/reply", methods=['POST', 'OPTIONS'])
def reply_feedback_post(post_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_reply_feedback(post_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/feedback/<post_id>", methods=['DELETE', 'OPTIONS'])
def delete_feedback_post(post_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_delete_feedback_post(post_id, user_id, token=_session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/feedback/<post_id>", methods=['PATCH', 'OPTIONS'])
def update_feedback_post(post_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_update_feedback_post(post_id, req, token=_session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ SUGGESTIONS ============

@app.route("/suggestions/<user_id>", methods=['GET', 'OPTIONS'])
def get_suggestions(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_get_suggestions(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/suggestions/<user_id>/generate", methods=['POST', 'OPTIONS'])
def generate_suggestions(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    req = request.get_json(silent=True) or {}
    result = handlers.handle_generate_suggestions(user_id, force=bool(req.get('force')))
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/suggestions/<user_id>/<suggestion_id>/accept", methods=['POST', 'OPTIONS'])
def accept_suggestion(user_id, suggestion_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_accept_suggestion(user_id, suggestion_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/suggestions/<user_id>/<suggestion_id>/dismiss", methods=['POST', 'OPTIONS'])
def dismiss_suggestion(user_id, suggestion_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_dismiss_suggestion(user_id, suggestion_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ ACTIVITIES ============

@app.route("/activities/<user_id>", methods=['GET', 'OPTIONS'])
def get_activities(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_get_activities(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/activities/<user_id>/<activity_id>", methods=['PATCH', 'OPTIONS'])
def update_activity(user_id, activity_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    req = request.get_json() or {}
    result = handlers.handle_update_activity(user_id, activity_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ BOUNTIES / DEMAND-SIDE ============

@app.route("/bounty", methods=['GET', 'POST', 'OPTIONS'])
def bounty():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    if request.method == 'GET':
        sponsor_user_id = request.args.get('sponsor_user_id', '')
        result = handlers.handle_list_bounties(
            api_key=_api_key(),
            sponsor_user_id=sponsor_user_id,
            session_token=_session_token(),
        )
        if isinstance(result, tuple):
            return Response(result[0], status=result[1], mimetype='application/json')
        return Response(result, mimetype='application/json')
    req = request.get_json() or {}
    result = handlers.handle_create_bounty(
        req, api_key=_api_key(), session_token=_session_token()
    )
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# Static paths before /bounty/<id>
@app.route("/bounty/directory", methods=['GET', 'OPTIONS'])
def bounty_directory():
    """Public list of users who opted into bounty discovery."""
    if request.method == 'OPTIONS':
        return Response('', status=200)
    q = request.args.get('q', '')
    limit = request.args.get('limit', 30)
    result = handlers.handle_discover_recipients(query=q, limit=limit)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/bounty/autocomplete", methods=['POST', 'OPTIONS'])
def bounty_autocomplete():
    """Public AI/catalog autocomplete for drafting a UB (activity + price)."""
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_bounty_autocomplete(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/bounty/<bounty_id>", methods=['GET', 'DELETE', 'OPTIONS'])
def get_bounty(bounty_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    if bounty_id in ('directory', 'autocomplete'):
        return Response(json.dumps({"error": "Not found"}), status=404, mimetype='application/json')
    sponsor_user_id = request.args.get('sponsor_user_id', '') or (request.get_json(silent=True) or {}).get('sponsor_user_id', '')
    if request.method == 'DELETE':
        result = handlers.handle_delete_bounty(
            bounty_id, api_key=_api_key(),
            sponsor_user_id=sponsor_user_id, session_token=_session_token(),
        )
    else:
        result = handlers.handle_get_bounty(
            bounty_id, api_key=_api_key(),
            sponsor_user_id=sponsor_user_id, session_token=_session_token(),
        )
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ STICKER BOARD ============

@app.route("/sticker-board/<user_id>", methods=['GET', 'OPTIONS'])
def get_sticker_board(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_get_sticker_board(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/sticker-board/<user_id>", methods=['POST', 'OPTIONS'])
def write_sticker(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    req = request.get_json() or {}
    result = handlers.handle_write_sticker(user_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/sticker-board/<user_id>/token", methods=['POST', 'OPTIONS'])
def get_share_token(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied: return denied
    result = handlers.handle_get_share_token(user_id)
    return Response(result, mimetype='application/json')


@app.route("/sticker-board/public/<token>", methods=['GET', 'OPTIONS'])
def public_sticker_board(token):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_public_sticker_board(token)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ DEMAND-SIDE GENERATE ============

@app.route("/generate", methods=['POST', 'OPTIONS'])
def generate_demand():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_generate_demand(
        req, api_key=_api_key(), session_token=_session_token()
    )
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ ADMIN ============

@app.route("/admin/balances", methods=['GET', 'OPTIONS'])
def admin_balances():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_balances(user_id, token=_session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/admin/stats", methods=['GET', 'OPTIONS'])
def admin_stats():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_stats(user_id, token=_session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/admin/payments", methods=['GET', 'OPTIONS'])
def admin_payments():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_payments(user_id, token=_session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/admin/payments/<target_user_id>/<activity_id>/paid", methods=['POST', 'OPTIONS'])
def admin_mark_paid(target_user_id, activity_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_mark_paid(user_id, _session_token(), target_user_id, activity_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/admin/bounties", methods=['GET', 'OPTIONS'])
def admin_bounties():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    if not handlers._admin_ok(user_id, _session_token()):
        return _unauthorized()
    result = handlers.handle_list_bounties()
    return Response(result, mimetype='application/json')


# ============ PUBLIC CLIENT CONFIG ============

@app.route("/config/public", methods=['GET', 'OPTIONS'])
def public_config():
    """Non-secret client config (Mapbox token, product flags)."""
    if request.method == 'OPTIONS':
        return Response('', status=200)
    return Response(handlers.handle_public_config(), mimetype='application/json')


# ============ FITNESS LEAGUES (stake groups + leaderboard) ============

@app.route("/challenges", methods=['GET', 'POST', 'OPTIONS'])
def challenges():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    if request.method == 'GET':
        user_id = request.args.get('user_id', '')
        result = handlers.handle_list_challenges(user_id=user_id or None, token=_session_token() or None)
        if isinstance(result, tuple):
            return Response(result[0], status=result[1], mimetype='application/json')
        return Response(result, mimetype='application/json')
    # POST create
    req = request.get_json() or {}
    user_id = req.get('user_id') or request.args.get('user_id', '')
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_create_challenge(user_id, _session_token(), req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/challenges/invites", methods=['GET', 'OPTIONS'])
def challenge_invites():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_challenge_invites(user_id, _session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/challenges/<challenge_id>", methods=['GET', 'OPTIONS'])
def get_challenge(challenge_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_get_challenge(challenge_id, user_id=user_id or None, token=_session_token() or None)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/challenges/<challenge_id>/join", methods=['POST', 'OPTIONS'])
def join_challenge(challenge_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    user_id = req.get('user_id') or request.args.get('user_id', '')
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_join_challenge(challenge_id, user_id, _session_token(), req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/challenges/<challenge_id>/log", methods=['POST', 'OPTIONS'])
def log_challenge(challenge_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    user_id = req.get('user_id') or request.args.get('user_id', '')
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_log_challenge_activity(challenge_id, user_id, _session_token(), req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/challenges/<challenge_id>/settle", methods=['POST', 'OPTIONS'])
def settle_challenge(challenge_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json(silent=True) or {}
    user_id = req.get('user_id') or request.args.get('user_id', '')
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_settle_challenge(challenge_id, user_id, _session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/feed", methods=['GET', 'OPTIONS'])
def social_feed():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    limit = request.args.get('limit', 40)
    result = handlers.handle_get_feed(user_id=user_id or None, token=_session_token() or None, limit=limit)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/ledger/<user_id>", methods=['GET', 'OPTIONS'])
def get_ledger(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied:
        return denied
    result = handlers.handle_get_ledger(user_id, _session_token())
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/ledger/<user_id>/topup", methods=['POST', 'OPTIONS'])
def ledger_topup(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    denied = _require_session(user_id)
    if denied:
        return denied
    req = request.get_json() or {}
    result = handlers.handle_ledger_topup(user_id, _session_token(), req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ MAIN ============

if __name__ == '__main__':
    print(f"")
    print(f"  GreenDial Health Assistant")
    print(f"  http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print(f"")
    print(f"  LLM: {config.OPENROUTER_MODEL}")
    print(f"  Storage: {config.DO_SPACES_BUCKET}/{config.S3_PREFIX}")
    print(f"  ListeningAI: /listening  (reference deployment)")
    print(f"")
    
    app.run(debug=config.DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
