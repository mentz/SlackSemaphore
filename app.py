from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import json
import config

app = App(token=config.SLACK_BOT_TOKEN)

users = {}  # key: user_id, value: emoji
subscriptions = {}  # key: emoji, value: set of user_id
semaphores = (
    {}
)  # key: emoji, value: { queue: [user_id], holders: [user_id], seats: Integer }


def init_semaphores(file_path):
    file = open(file_path)
    data = json.load(file)
    for obj in data:
        resource = obj["resource"]
        emoji = obj["emoji"]
        seats = obj["seats"]

        semaphores[emoji] = {}
        semaphores[emoji]["queue"] = []
        semaphores[emoji]["holders"] = []
        semaphores[emoji]["resource"] = resource
        semaphores[emoji]["seats"] = seats

    print("Done initializing semaphores:", semaphores)


def init_subscriptions():
    for emoji in semaphores.keys():
        subscriptions[emoji] = set()

    print("Done initializing subscriptions:", subscriptions)


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
    if emoji in semaphores.keys():
        semaphore = semaphores[emoji]

        if user_id in subscriptions[emoji]:
            return f"You're already part of {emoji}."

        subscriptions[emoji].add(user_id)
        return (
            f"Right-o! You've joined the {emoji} semaphore that manages access "
            + f"to {semaphore['resource']}.\nSet {emoji} as your Slack Status Emoji "
            + "whenever you want to secure access to that resource. After you're "
            + "done using that resource, just clear your Status and I'll notify the "
            + "next person waiting for it that they can use it now."
        )
    else:
        return f"Sorry, there is no semaphore for {emoji}."


def semaphore_list():
    message = (
        "These are the available semaphores, what resource they manage and "
        + "how many may use it simultaneously:\n"
    )

    for emoji in semaphores.keys():
        semaphore = semaphores[emoji]
        resource = semaphore["resource"]
        seats = semaphore["seats"]
        message += (
            f"\n - {emoji} - {resource} ({seats} seat{'s' if seats != 1 else ''})"
        )

    return message


@app.message()
def say_hello(message, say):
    user = message["user"]
    say(f"Hello, <@{user}>!")
    # Not working. Are we missing OAuth scopes?


@app.command("/semaphore_list")
def cmd_semaphore_list(ack, say):
    ack()
    say(semaphore_list())


@app.command("/semaphore_join")
def cmd_semaphore_join(ack, body, say):
    user_id = body["user_id"]
    emoji = body["text"]
    ack()
    say(semaphore_join(user_id, emoji))


@app.command("/semaphore_leave")
def cmd_semaphore_leave(ack, body, say):
    user_id = body["user_id"]
    emoji = body["text"]
    print("Implement /semaphore_leave")
    # ack()
    # say("Sorry to see you go. Feel free to join again any time :)")


@app.event("user_status_changed")
def receive_status_update(client, event, say):
    user = event["user"]
    emoji = event["user"]["profile"]["status_emoji"]
    ftime = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    print(f"[{ftime}] {user['name']} ({user['id']}) has {emoji}")

    user_update(user["id"], emoji)


if __name__ == "__main__":
    init_semaphores(config.SEMAPHORE_CONFIG_FILE)
    init_subscriptions()

    handler = SocketModeHandler(app, config.SLACK_SOCKET_MODE_TOKEN)
    handler.start()  # use this to have an event listener
    # handler.connect() # use this to just connect without blocking the thread
