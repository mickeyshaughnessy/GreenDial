import redis, openai, utils, config

redis = redis.StrictRedis()



def add_data(request):
    redis.hset(config.REDHASH_USER_DATA, req.get("user_id"), req.get("event_data"))
    return '{"message" : "ok"}'

def get_data(request):
    data = json.loads(redis.hget(config.REDHASH_USER_DATA, req.get("user_id")))
    return data

def chat(request):
    text = request.get("text")
    chat_history = request.get("chat_history")
    resp = requests.post(
        config.openai_url,
        headers={
            "Content-Type: application/json", 
            "Authorization: Bearer %s" % config.openai_api_key
        }
        json='{
            "model": "text-davinci-003",
            "prompt": "%s",
            "temperature": 0,
            "max_tokens": 2000}' % utils.chat_preamble % chat_history + text
    )
        
