import redis, openai, config, requests, json, random
from prompts import auth, chat, memory, settings, external 

redis = redis.StrictRedis()

def get_history(request, user={}):
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

def parse_resp(response):
    # handle and remove all <SYMBOLS>
    # filter for alignment
    return response

def make_prompt(username, chat_history, in_text):
    return chat.CHAT_system % (
            username,
            auth.AUTH_instructions + auth.AUTH_example,
            memory.SELECT_system,
            memory.INSERT_system,
            chat_history,
            in_text) 

def handle_chat(request):
    username = request.get('username','') or "User"
    in_text = (username + ": " + request.get("text",""))
    print(in_text)
    
    chat_history = get_history(request) 
#    prompt = make_prompt(username, chat_history, in_text)

    data={
        "model": "text-davinci-003",
        "prompt": chat.CHAT_system % (
            username,
            auth.AUTH_instructions + auth.AUTH_example,
            memory.SELECT_system,
            memory.INSERT_system, 
            chat_history,
            in_text), 
        "temperature": 1.1,
        "max_tokens": 200
    }

    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    full_resp = requests.post(config.openai_url, headers=headers, json=data)
    _resp = full_resp.json().get("choices", [])[0].get('text')
    
    out_text = parse_resp(_resp)

    #if '<URD>' in out_text:
    #     out_text.replace('<URD>', '')
    #     # call URD service with out_text
    #if '<DRQ>' in out_text:
    #     out_text.replace('<DRQ>', '')
    #     # call DRQ service with out_text

    print(out_text)
    #update_history(request, in_text + '\n' + out_text) 
    return json.dumps({"response" : out_text, "username" : random.choice(["Frank", "Larry", "Angie"])})
        
