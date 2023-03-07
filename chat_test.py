from utils import completion
import requests

user_id = '123'

while True:
    chat = input("User_%s: " % user_id)
    #resp = requests.post("http://127.0.0.1:8011/chat", json={"text" : chat, "user_id":user_id})
    resp = requests.post("http://3.89.10.143:8011/chat", json={"text" : chat, "user_id":user_id})
    print(resp.text)
