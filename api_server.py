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

import json, redis
from flask import Flask, jsonify, request
from handlers import h_add_data, h_get_data, h_chat 
import handlers
redis = redis.StrictRedis()

app = Flask(__name__)

@app.route("/ping", methods=['GET'])
def ping():
    return json.dumps({"message" : "ok"})

@app.route("/get_data", methods=['POST'])
def ():
    req = request.get_json()

    # here fire off the ad campaign
    # import geopy
    # extract targeting criteria
    
    targeting = make_targeting(req)
    res = run_demand(targeting)

    print(req, req.keys())
    return json.dumps({"message" : "ok"})

@app.route("/configure", methods=['POST'])
def configure():
    req = request.get_json()
    print(req.keys())
    return json.dumps({"message" : "ok"})

@app.route("/report", methods=['GET'])
def report():
    req = request.get_json()
    return json.dumps({"report" : "report"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8010)
