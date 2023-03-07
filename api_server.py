# This is the GreenDial api server
# It has a user REST API:

# POST /add_data
# request = {
#    "user_id" : <user_id>,
#    "event_data" : <event_data_json>
#    }
#
# POST /get_data
# request = {
#    "user_id" : <user_id>,
#    "data_params" : <params_json>
#    }
#
# POST /chat
# request = {
#    "user_id" : <user_id>,
#    "text" : <params_json>
#    }
import json
import redis
from flask import Flask, jsonify, request
from flask_cors import CORS
import handlers

redis = redis.StrictRedis()

app = Flask(__name__)
CORS(app)

@app.route("/ping", methods=['GET'])
def ping():
    return json.dumps({"message" : "ok"})

@app.route("/chat", methods=['POST'])
def chat():
    req = request.get_json()
    resp = handlers.chat(req)
    return resp

if __name__ == '__main__':
    app.run(ssl_context='adhoc', debug=True, host='0.0.0.0', port=8011)

