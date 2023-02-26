from utils import completion

transcript = ""
while True:
    chat = input("User: ")
    transcript += "User: " + chat + "\nBot: "
    resp = completion(transcript)
    transcript += resp
    print("Bot: " + resp.replace('\n',''))
