import requests

while True:
    chat = input("User: ")
    resp = requests.post("http://127.0.0.1:8010/chat", json={"text" : chat})
    print("Bot: " + resp.json().get("choices", [])[0].get('text'))
