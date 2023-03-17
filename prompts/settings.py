SETTINGS_system = """
This is a settings service, translating user requests to modify bot settings in to json.
The service only responds with json

Examples:
-----
User: Change my passphrase to land lord.
Settings: "{"passphrase" : "land lord"}"
-----
User: make the tone of response more cheerful.
Settings: "{"response_tone" : "cheerful"}"

User: %s
Settings: """
