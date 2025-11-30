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


@app.route("/ping", methods=['GET'])
def ping():
    return Response(json.dumps({"status": "ok", "service": "greendial"}), mimetype='application/json')


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


# ============ MAIN ============

if __name__ == '__main__':
    print(f"")
    print(f"  GreenDial Health Assistant")
    print(f"  http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print(f"")
    print(f"  LLM: {config.LLM_API_URL}")
    print(f"  Ollama fallback: {'enabled' if config.OLLAMA_ENABLED else 'disabled'}")
    print(f"  S3: s3://{config.S3_BUCKET}/{config.S3_PREFIX}")
    print(f"")
    
    app.run(debug=config.DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
