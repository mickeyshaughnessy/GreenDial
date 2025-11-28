"""
GreenDial API Server - Worker Droid Implementation
Flask HTTP server for the GreenDial health assistant
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

@app.route("/", methods=['GET'])
def index():
    return send_from_directory('.', 'index.html')

@app.route("/ping", methods=['GET'])
def ping():
    return Response(json.dumps({"message": "ok", "service": "greendial"}), mimetype='application/json')

# Auth
@app.route("/auth", methods=['POST', 'OPTIONS'])
def auth():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_auth(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')

# Chat
@app.route("/chat", methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_chat(req)
    return Response(result, mimetype='application/json')

# Sessions
@app.route("/session", methods=['POST', 'OPTIONS'])
def new_session():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_new_session(req)
    return Response(result, mimetype='application/json')

@app.route("/sessions/<user_id>", methods=['GET', 'OPTIONS'])
def list_sessions(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_list_sessions(user_id)
    return Response(result, mimetype='application/json')

# Conversations
@app.route("/conversations", methods=['GET', 'POST', 'OPTIONS'])
def conversations():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_conversations(req)
    return Response(result, mimetype='application/json')

# User profile
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
    return Response(result, mimetype='application/json')

# User Messaging
@app.route("/messages/<user_id>", methods=['GET', 'OPTIONS'])
def get_messages(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_messages(user_id)
    return Response(result, mimetype='application/json')

@app.route("/messages", methods=['POST', 'OPTIONS'])
def send_message():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_send_message(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')

# Doc's Messages (RCL)
@app.route("/doc/messages/<user_id>", methods=['GET', 'OPTIONS'])
def get_doc_messages(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_doc_messages(user_id)
    return Response(result, mimetype='application/json')

@app.route("/doc/message", methods=['POST', 'OPTIONS'])
def send_doc_message():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_doc_message(req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')

# Goals
@app.route("/goals/<user_id>", methods=['GET', 'OPTIONS'])
def get_goals(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_goals(user_id)
    return Response(result, mimetype='application/json')

@app.route("/goals/<user_id>", methods=['POST', 'OPTIONS'])
def save_goals(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_save_goals(user_id, req)
    return Response(result, mimetype='application/json')

# Settings
@app.route("/settings/<user_id>", methods=['GET', 'OPTIONS'])
def get_settings(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_settings(user_id)
    return Response(result, mimetype='application/json')

@app.route("/settings/<user_id>", methods=['PUT', 'OPTIONS'])
def save_settings(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_save_settings(user_id, req)
    if isinstance(result, tuple):
        return Response(result[0], status=result[1], mimetype='application/json')
    return Response(result, mimetype='application/json')

# Health records
@app.route("/health/<user_id>", methods=['GET', 'OPTIONS'])
def get_health_records(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    record_type = request.args.get('type')
    result = handlers.handle_get_health_records(user_id, record_type)
    return Response(result, mimetype='application/json')

@app.route("/health/<user_id>", methods=['POST', 'OPTIONS'])
def save_health_record(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_save_health_record(user_id, req)
    return Response(result, mimetype='application/json')

# Droid invocation
@app.route("/droid", methods=['POST', 'OPTIONS'])
def invoke_droid():
    if request.method == 'OPTIONS':
        return Response('', status=200)
    req = request.get_json() or {}
    result = handlers.handle_droid(req)
    return Response(result, mimetype='application/json')

# Dashboard stats
@app.route("/stats/<user_id>", methods=['GET', 'OPTIONS'])
def get_stats(user_id):
    if request.method == 'OPTIONS':
        return Response('', status=200)
    result = handlers.handle_get_stats(user_id)
    return Response(result, mimetype='application/json')

if __name__ == '__main__':
    print(f"Starting GreenDial API on http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(debug=config.DEBUG, host=config.FLASK_HOST, port=config.FLASK_PORT)
