# This is the GreenDial api server

import json
import redis
from flask import Flask, jsonify, request
import handlers

redis = redis.StrictRedis()

app = Flask(__name__)

@app.route("/ping", methods=['GET'])
def ping():
    return json.dumps({"message" : "ok"})

@app.route("/conversations", methods=['POST','GET'])
def conversations():
    req = request.get_json()
    resp = handlers.handle_conversations(req)
    return resp

@app.route("/chat", methods=['POST','GET'])
def chat():
    req = request.get_json()
    resp = handlers.handle_chat(req)
    return resp

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8012)

