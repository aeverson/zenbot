import os
import re
import requests
import json
import logging
from slack_bolt import App
import slack_sdk
from slack_sdk.errors import SlackApiError

# Initializes app with bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

zendesk_url = os.environ.get("ZD_URL")
zendesk_token = os.environ.get("ZD_TOKEN")
zendesk_user = str(os.environ.get("ZD_EMAIL"))+"/token"
headers = {'content-type': 'application/json'}

# creates a string containing all messages in the thread, with a note at the bottom about the bot
def print_whole_thread(message, client):
    thread_ts = message.get("thread_ts", None) or message["ts"]
    conversation_id = message["channel"]
    whole_thread = ""
    try:
      result = client.conversations_replies(
          channel=conversation_id,
          inclusive=True,
          oldest=thread_ts,
          limit=10,
          ts=thread_ts
      )
    except SlackApiError as e:
        print(f"Error: {e}")

    try:
        thread_link = client.chat_getPermalink(channel=conversation_id, message_ts=thread_ts)["permalink"]
    except SlackApiError as e:
        print(f"Error: {e}")
      
    for message in result["messages"]:
        user_id = (message["user"])
        try:
            username = client.users_info(user=user_id)["user"]["real_name"]
        except SlackApiError as e:
            username = message["user"]
            print(f"Error: {e}")
        whole_thread += username+": "+str(message["text"]) + "\n"
    whole_thread += "\nThis ticket was created from Slack via Zenbot\nLink to thread: " + thread_link
    return whole_thread

# gets the text of the initial comment in the thread and removes the !zd signifier
def get_parent_text(message, client):
    thread_ts = message.get("thread_ts", None) or message["ts"]
    conversation_id = message["channel"]
    try:
      result = client.conversations_replies(
          channel=conversation_id,
          inclusive=True,
          oldest=thread_ts,
          limit=10,
          ts=thread_ts
      )
    except SlackApiError as e:
        print(f"Error: {e}")
    return result["messages"][0]["text"].replace("!zd", "")

@app.message("!zd")
def create_ticket(client, message, say):
    user = message['user']
    #the requester of the ticket is the author of the !zd command
    user_email = client.users_info(user=message["user"])["user"]["profile"]["email"]
    text = get_parent_text(message, client)
    thread_ts = message.get("thread_ts", None) or message["ts"]
    body = print_whole_thread(message, client)
    payload = {"ticket": {"subject": text, "comment": {"body": body}, "requester": user_email, "status":"open"}}
    payloadjson = json.dumps(payload)
    ticket = requests.post(zendesk_url+"/api/v2/tickets.json", data=payloadjson, auth=(zendesk_user, zendesk_token), headers=headers)
    response = ticket.status_code # get response
    #if 200 - post in channel with ticket link
    if ticket.status_code == 201:
        ticket_id=str(ticket.json()["ticket"]["id"])
        ticket_link = "<"+zendesk_url+"/agent/tickets/"+ticket_id+"|#"+ticket_id+">"
        say("Ticket was created successfully: "+ ticket_link, thread_ts=thread_ts)
    #if not 200 - post error message
    else:
        say("There was a problem creating the ticket", thread_ts=thread_ts)
    
# Start app
heroku_port=os.environ.get("PORT")
if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", heroku_port)))
