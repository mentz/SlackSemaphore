import os
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import config

app = App(token=config.SLACK_BOT_TOKEN)

users = {} # key: user_id, value: emoji
subscribed = {} # key: emoji
semaphores = {} # key: emoji, value: { queue: [user_id], holders: [user_id], limit: Integer }

def user_update(user_id, emoji):
    previous_emoji = users.get(user_id)
    users[user_id] = emoji

    # If user is subscribed to a queue on the previous or new emoji,
    # update the semaphores.

    print(users)
    print("Finish user_update")


def semaphore_update(user_id, emoji):
    print("Implement semaphore_update")


def semaphore_join(user_id, emoji):
    print("Implement semaphore_join")


@app.message()
def say_hello(message, say):
    user = message["user"]
    say(f"Hello, <@{user}>!")
    # Not working. Are we missing OAuth scopes?


@app.command("/semaphore_list")
def cmd_semaphore_list(ack, say):
    ack()
    say("These are the available semaphores:\n" + 
        "- :hackerman: - `:hackerman:` - There can only be one hackerman at a time\n" +
        "- :babypatrick: - `:babypatrick:` - Access to Union's API Symplr Schedule Grid\n" +
        "\nJoin any of these by messaging me `/semaphore_join emoji`.")


@app.command("/semaphore_join")
def cmd_semaphore_join(ack, body, say):
    user_id = body['user_id']
    emoji = body['text']
    ack()
    #if emoji in semaphores.keys():
    say(f"Right-o! You're now participating the {emoji} semaphore.")
    #else
    #    say(f"Sorry, there is no semaphore with the {emoji} emoji")


@app.command("/semaphore_leave")
def cmd_semaphore_leave(ack, body, say):
    user_id = body['user_id']
    emoji = body['text']
    ack()
    say("Sorry to see you go. Feel free to join again any time :)")


@app.event("user_status_changed")
def receive_status_update(event, say):
    user = event['user']
    emoji = event['user']['profile']['status_emoji']
    ftime = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    print(f"[{ftime}] {user['name']} ({user['id']}) has {emoji}")

    user_update(user['id'], emoji)


if __name__ == "__main__":
    handler = SocketModeHandler(app, config.SLACK_SOCKET_MODE_TOKEN)
    handler.start() # use this to have an event listener
    # handler.connect() # use this to just connect without blocking the thread

