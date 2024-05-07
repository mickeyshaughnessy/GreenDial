import redis, openai, config, requests, json, random, uuid
from prompts import auth, chat, memory, settings, external 

redis = redis.StrictRedis()

def handle_conversations(req):
    res = {}
    return res

def get_user_data(user_id=""):
    try:
        res = json.loads(redis.hget(config.REDHASH_USER_DATA, user_id))
    except:
        res = {}
    return res 

def update_history(user_id, in_text, out_text):
    try:
        res = json.loads(redis.hget(config.REDHASH_USER_DATA, user_id))
        res['transcript'] += in_text + out_text
    except:
        res = {'transcript' : in_text + out_text, 'user_id' : user_id, 'plugins' : ""}
    redis.hset(config.REDHASH_USER_DATA, user_id, json.dumps(res)) 

def parse_resp(user_id, in_text, response):
    # handle and remove all **SYMBOLS**
    # for symbols in symbols:
    # data = symbol.call(response)
    # response.replace(symbol, data)
    # update history
    return response

#def handle_auth(in_text, username):
#    query = utils.call_completion(auth.AUTH_BODY.format(in_text, username))
#    red_hash = redis.hget(config.REDHASH_USER_DATA, query.get('username'))
#    if red_hash:
#        return hash(red_hash) == hash(query.get('passphrase'))
#    else:
#        return False

def make_prompt(user_id=None, _input=""):
    user_data = get_user_data(user_id)
    transcript = user_data.get('history',"") 
    username = user_data.get('username',"no username found") 

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
    user_id = request.get('user_id')  
    in_text = request.get("text","")
 

    data={
        "prompt": make_prompt(user_id, in_text),
        "n" : 1, # number of completions
        "model": "text-davinci-003",
        "temperature": 1.1,
        "max_tokens": 200
    }

    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    full_resp = requests.post(config.openai_url, headers=headers, json=data)
    _resp = full_resp.json().get("choices", [])[0].get('text')
    
    #out_text, username = parse_resp(username, in_text, _resp)
    #out_text = parse_resp(user_id, in_text, _resp)
    update_history(user_id, in_text, _resp)

    print(out_text)
    
    return json.dumps(
        {
        "response" : out_text, 
        }
    )
        
