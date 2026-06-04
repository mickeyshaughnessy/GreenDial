"""
GreenDial API Server
Flask HTTP server for the health assistant
"""
import json
from flask import Flask, request, send_from_directory, Response
import config
import handlers

app = Flask(__name__, static_folder='.')


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


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


@app.route("/ping", methods=['GET'])
def ping():
    return Response(json.dumps({"status": "ok", "service": "greendial"}), mimetype='application/json')


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
    result = handlers.handle_chat(req)
    return Response(result, mimetype='application/json')


# ============ USER ============

@app.route("/user/<user_id>", methods=['GET', 'OPTIONS'])
def get_user(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_get_user(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/user/<user_id>", methods=['PUT', 'OPTIONS'])
def update_user(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
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
    
    result = handlers.handle_get_settings(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/settings/<user_id>", methods=['PUT', 'POST', 'OPTIONS'])
def update_settings(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    req = request.get_json() or {}
    result = handlers.handle_update_settings(user_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ NOTIFICATIONS ============

@app.route("/notifications/<user_id>", methods=['GET', 'OPTIONS'])
def get_notifications(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_get_notifications(user_id)
    return Response(result, mimetype='application/json')


@app.route("/notifications/<user_id>/generate", methods=['POST', 'OPTIONS'])
def generate_notification(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_generate_notification(user_id)
    return Response(result, mimetype='application/json')


@app.route("/notifications/<user_id>/<notification_id>", methods=['DELETE', 'OPTIONS'])
def dismiss_notification(user_id, notification_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_dismiss_notification(user_id, notification_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


# ============ CONVERSATIONS ============

@app.route("/chat/agent/<agent_id>", methods=['POST', 'OPTIONS'])
def agent_chat(agent_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_agent_chat(agent_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/agents", methods=['GET', 'OPTIONS'])
def get_agent_transcripts(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_agent_transcripts(user_id)
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/agent/<agent_id>", methods=['DELETE', 'OPTIONS'])
def clear_agent_transcript(user_id, agent_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_clear_agent_transcript(user_id, agent_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>", methods=['GET', 'OPTIONS'])
def get_conversations(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_get_conversations(user_id)
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>", methods=['DELETE', 'OPTIONS'])
def clear_conversations(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
    result = handlers.handle_clear_transcript(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/conversations/<user_id>/<conversation_id>", methods=['GET', 'OPTIONS'])
def get_conversation(user_id, conversation_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    
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
    field = request.args.get('field')
    days = int(request.args.get('days', 30))
    result = handlers.handle_get_history(user_id, field=field, days=days)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/agents/<user_id>", methods=['GET', 'OPTIONS'])
def get_agent_subscriptions(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_agent_subscriptions(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/agents/<user_id>", methods=['PUT', 'POST', 'OPTIONS'])
def update_agent_subscriptions(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_update_agent_subscriptions(user_id, req)
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


# ============ ADMIN ============

@app.route("/admin/balances", methods=['GET', 'OPTIONS'])
def admin_balances():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_balances(user_id)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')


@app.route("/admin/stats", methods=['GET', 'OPTIONS'])
def admin_stats():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    user_id = request.args.get('user_id', '')
    result = handlers.handle_admin_stats(user_id)
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
    print(f"")
    
    app.run(debug=config.DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
