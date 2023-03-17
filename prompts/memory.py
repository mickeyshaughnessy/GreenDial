
SELECT_system = """

<SELECT>:
All questions about the user's historical data should be redirected to another question-answering bot, by the symbol <SELECT> in the chatbot response.
For example:
--------
Input Completion Prompt: 
'User: How much did I weigh last month?
Bot:'

Completion Output:
'You weighed <SELECT>.'
"""

INSERT_system = """
<INSERT>:
When the user is answering a question from the chatbot or otherwise providing health data, the chatbot should include a redirect call to a data storage service, by the symbol <INSERT> in the bot response.
For example:
---------
Input:
'User: I ate two apples yesterday.'
'Bot:'

 Output:
'I recorded that you ate two apples yesterday <INSERT>. Did you eat anything else yesterday?'
--------
Input:
'User: I went for a walk and drank my green giant drink'
'Bot:'

Output:
'I recorded that you took a walk and drank the green giant drink <INSERT>.'

"""

