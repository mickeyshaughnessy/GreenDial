import redis, openai, utils, config, requests, json

redis = redis.StrictRedis()

def add_data(request):
    redis.hset(config.REDHASH_USER_DATA, req.get("user_id"), req.get("event_data"))
    return '{"message" : "ok"}'

def get_data(request):
    data = json.loads(redis.hget(config.REDHASH_USER_DATA, req.get("user_id")))
    return json.dumps(data)

def chat(request):
    text = request.get("text","")
    chat_history = request.get("chat_history", "")
    data={
    "model": "text-davinci-003",
    "prompt": "%s" % utils.chat_preamble % (chat_history, text),
    "temperature": 0,
    "max_tokens": 200}

    print(data.get('prompt'))
    print(data)
    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    resp = requests.post(config.openai_url, headers=headers, json=data)
    print(resp.json())
    return resp.json() 
        
