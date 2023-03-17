
AUTH_instructions = """
A user response to a chatbot <AUTH> prompt is routed to an <AUTH> service, which replies with SUCCESS or FAIL.
The AUTH service handles new users and always returns SUCCESS or FAIL.
When the user is successfully logged, the username and user_id are specified as above.
"""

AUTH_example = """
------
"User: good morning
"Bot: Good morning! What is your name and passphrase? If you are a new user, just respond with your first name and a short memorable phrase. <AUTH>
"User" : Mickey languid camel
"Auth Service" : SUCCESS
"Bot" : Thanks, I've logged you in, Mickey.
----

"""


AUTH_system = """
This is an AUTH service, called from the main chatbot.
The service is provided an input that consists of user request data and a database response.


If nothing is provided for the database response below, the auth service responds with query for the database, like:
-----------
user_request is "Mickey donkey dan"
database_response is
auth_response: "{"username" : "Mickey", "passphrase" : "donkey dan"}"
----------
user_request is "Andy super jump"
database_response is
auth_response: "{"username" : "Andy", "passphrase" : "super jump"}"
----------

The database service will check to see if any known users match and return it's response.

If both the user request and the database response are provided above, the auth service checks to see that they are
the same and returns instead the user's name and user_id: 

----------
user_request is "andy super jump"
database_response is "{"username" : "Andy", "passphrase" : "super jump", "user_id" : "123abc"}"
auth_response: Andy 123abc 
----------

user_request is %s
database_response is %s
auth_response: 
"""

