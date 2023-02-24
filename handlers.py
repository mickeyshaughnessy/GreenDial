import redis, openai, prompts, config, requests, json

redis = redis.StrictRedis()

def add_data(request):
    redis.hset(config.REDHASH_USER_DATA, req.get("user_id"), req.get("event_data"))
    return json.dumps({"message" : "ok"})

def get_data(request):
    data = json.loads(redis.hget(config.REDHASH_USER_DATA, req.get("user_id")))
    return json.dumps(data)

def get_history(request):
    user_id = request.get("user_id")
    try:
        res = json.loads(redis.hget(config.REDHASH_CHAT_HISTORY, user_id))
        history = res.get('history', "")
    except:
        history = ""    
    return history

def update_history(request, out_text):
    user_id = request.get("user_id")
    try:
        res = json.loads(redis.hget(config.REDHASH_CHAT_HISTORY, user_id))
        res['history'] += out_text
    except:
        res = {'history' : out_text}
    redis.hset(config.REDHASH_CHAT_HISTORY, user_id, json.dumps(res)) 
 
def chat(request):
    in_text = ("User_%s: " % request.get('user_id')) + request.get("text","")
    chat_history = get_history(request) 
    data={
        "model": "text-davinci-003",
        "prompt": prompts.chat_concierge_preamble % (
            prompts.URD_instructions,
            prompts.DRQ_instructions, 
            chat_history,
            in_text), 
        "temperature": 0,
        "max_tokens": 200
    }

    print(data["prompt"])

    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    resp = requests.post(config.openai_url, headers=headers, json=data)
    out_text = "Bot: " + resp.json().get("choices", [])[0].get('text')
    if '<URD>' in out_text:
         out_text.replace('<URD>', '')
         # call URD service with out_text
    if '<DRQ>' in out_text:
         out_text.replace('<DRQ>', '')
         # call DRQ service with out_text

    update_history(request, in_text + '\n' + out_text) 
    return out_text 
        
