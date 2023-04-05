import redis, openai, config, requests, json, random, uuid
from prompts import auth, chat, memory, settings, external 

redis = redis.StrictRedis()

def get_history(convo_id=""):
    try:
        res = json.loads(redis.hget(config.REDHASH_CONVERSATIONS, convo_id))
        history = res.get('history',[]) 
    except:
        history = []    
    return history

def update_history(request, out_text, convo_id=""):
    try:
        res = json.loads(redis.hget(config.REDHASH_CONVERSATIONS, convo_id))
        res['transcript'].append(out_text)
    except:
        res = {'transcript' : [out_text]}
    redis.hset(config.REDHASH_CONVERSATIONS, convo_id, json.dumps(res)) 

def get_user_data(username):
    user_data = redis.hget(config.REDHASH_USER_DATA, username)
    if user_data:
        user_data = json.loads(user_data)
    else:
        user_data = {"username" : username, "plugins" : ""}
    return user_data

def update_user_data(username, update):
    user_data = redis.hget(config.REDHASH_USER_DATA, username)
    if user_data:
        user_data = json.loads(user_data)
    else:
        user_data = {"username" : username, "plugins" : ""}
    user_data.update(update)
    redis.hset(config.REDHASH_USER_DATA, username, json.dumps(user_data))

def parse_resp(username, convo_id, in_text, response):
    # handle and remove all **SYMBOLS**
    # for symbols in symbols:
    # data = symbol.call(response)
    # response.replace(symbol, data)
    # filter for alignment
    # update history
    update_history(in_text, response, convo_id)
    return response

def handle_auth(in_text, convo_id):
    query = utils.call_completion(auth.AUTH_BODY.format(in_text, convo_id))
    red_hash = redis.hget(config.REDHASH_USER_DATA, query.get('name'))
    if red_hash:
        return hash(red_hash) == hash(query.get(passphrase))
    else:
        return False

def make_prompt(username=None, convo_id="", _input=""):
    user_data = get_user_data(username) 
    transcript = "\n".join(get_history(convo_id))
 
    p = "" 
    p += chat.CHAT_PREFIX.format(username=username, personality='Beth')
    p += chat.CHAT_SYSTEM.format(plugins=user_data.get('plugins',""))
    p += chat.CHAT_SUFFIX.format(transcript=transcript,new_user_input=_input)

    return p
    #return chat.CHAT_system % (
    #        username,
    #        auth.AUTH_instructions + auth.AUTH_example,
    #        memory.SELECT_system,
    #        memory.INSERT_system,
    #        chat_history,
    #        in_text) 

def handle_chat(request):
    username = request.get('username') or ""
    convo_id = request.get('convo_id', '')
    print(request.keys())
    if not convo_id:
        convo_id = str(uuid.uuid4())
    in_text = (username + ": " + request.get("text",""))
    print(in_text)
    
    data={
        "prompt": make_prompt(username, convo_id, in_text),
        "n" : 1, # number of completions
        "model": "text-davinci-003",
        "temperature": 1.1,
        "max_tokens": 200
    }

    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    full_resp = requests.post(config.openai_url, headers=headers, json=data)
    _resp = full_resp.json().get("choices", [])[0].get('text')
    
    out_text = parse_resp(username, convo_id, in_text, _resp)

    print(out_text)
    
    return json.dumps(
        {
        "response" : out_text, 
        #"username" : random.choice(["Frank", "Larry", "Angie"]),
        "username" : username, 
        "convo_id" : convo_id 
        }
    )
        
