Update - GreenDial is an AI applications harness for implementing public health data application development.

Users waive HIPAA rights during signup (hence the public moniker).

##################
Key aspects of HIPAA
Protects patient information: HIPAA establishes national standards for the privacy and security of health information, making it a federal law that prevents unauthorized disclosure of PHI without a patient's consent.
Grants patient rights: Individuals have the right to access and request corrections to their health records.
Sets standards for covered entities: The law applies to health plans, healthcare providers, and healthcare clearinghouses that transmit health information electronically.
Includes the Privacy Rule and Security Rule: The Privacy Rule sets standards for the use and disclosure of PHI, while the Security Rule sets technical, physical, and administrative safeguards for protecting electronic PHI (ePHI).
Ensures insurance portability: As the name suggests, HIPAA also addresses health insurance portability and continuity, as well as fraud and abuse in health insurance and healthcare delivery.
Mandates compliance: Covered entities must comply with HIPAA regulations, or they can face penalties, including fines and potential jail time for serious violations

#################
Revise the initial README.md and associated .md files to prepare for code development by a modular team of software engineers, known as Droids.

*You are a specific droid instance, called "<type> droid", where the type macro defines the partial droidprompt, droidname.
This section within the italics is the top-level droidprompt. A "droidprompt droid" is a droid for writing droid prompts, for example. Other droidnames might be writer droid or oracle droid or hashing droid or benefits droid or sensor droid or communications droid or janitor droid or supervisor droid or worker droid ...
Invoke droids through their droidnames and passing a JSON request with a "droidpromt" : "<some detailed text to be handled>" top-level component"* 

We'll deploy and test first as index.html and a Flask api_server.py serving on localhost
Then we'll use git to push to a production vm server, sshing onto it to pulldown code & initiate deployments.

Define the core chat functionality using openrouter /completion API over HTTP plus Amazon S3 storage for all memory and storage.

Then define the web app, including the login w/ HIPAA waiver and then a clean, modern physical health app, including chat, personal data exploration dashboard, and integration with The Services Exchange API at https://rse-api.com:5003/ (documentation available at https://theservicesexchange.com/api_docs.html) for periodic bid suggestions for diet, exercise, sleep, and entertainment services. Also include a crontab-driven unprompted speech script (RCL) for health-related conversations. 


# GreenDial
GreenDial is an open platform for personal lifestyle data assistants.

GreenDial Doc is the premier tier health and lifestyle optimizing assistant
 
## Using
You are welcome to use this software and contribute to this repository.

## Description
The core functionality is a concierge chatbot, Doc.

You can access it here: [GreenDial](https://www.greendial.org) 

My primary personal use of greendial is to have a way to:
* store data about my diet, activity, health, etc.
* set up goals and reminders

I am trying to make it flexible enough to help with a variety of other things, including
* pair programming,
* lists,
* building digital assistants 

---------------

Doc connects LLM APIs to transform unstructured user input into records, autonomously engage in conversation with people about their health, and activate external services on behalf of the person.

External services include:
* An authentication service
* Long-term memory service
* Personalization (aka settings)
* Reminders / Goals
* Suggestions
* Data analysis
* Freeform LLM chat
  


