import requests

while True:
    chat = input("User: ")
    resp = requests.post("http://127.0.0.1:8010/chat", json={"text" : chat, "user_id":"123"})
    
    print(resp.text)
