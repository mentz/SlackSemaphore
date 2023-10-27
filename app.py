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


def is_user_subscribed(user_id, emoji):
    if emoji not in semaphores.keys():
        return False

    return user_id in subscriptions[emoji]


def try_advance_semaphore(client, emoji):
    semaphore = semaphores[emoji]
    user_waiting = len(semaphore["queue"]) > 0
    seat_available = len(semaphore["holders"]) < semaphore["seats"]

    if user_waiting and seat_available:
        new_holder = semaphore["queue"].pop()
        semaphore["holders"].append(new_holder)
        notify_user_of_acquiring(client, new_holder, emoji)
        notify_enqueued_users(client, emoji)
        return True

    return False


def pop_user_from_semaphore(client, user_id, emoji):
    if emoji not in semaphores.keys():
        return

    semaphore = semaphores[emoji]
    message = ""
    if user_id in semaphore["queue"]:
        message = f"You just left the queue for {emoji}."
        position = semaphore["queue"].index(user_id)
        semaphore["queue"].remove(user_id)
        notify_enqueued_users(client, emoji, starting_from=position)

    if user_id in semaphore["holders"]:
        resource = semaphore["resource"]
        message = f"Thank you for returning {resource} :patrickprayge:!"
        semaphore["holders"].remove(user_id)
        try_advance_semaphore(client, emoji)

    if len(message) > 0:
        client.chat_postMessage(channel=user_id, text=message)


def push_user_to_semaphore(client, user_id, emoji):
    # message is sent by try_advance_semaphore
    semaphore = semaphores[emoji]

    if user_id in semaphore["holders"]:
        return

    if user_id in semaphore["queue"]:
        return

    semaphore["queue"].append(user_id)
    acquired = try_advance_semaphore(client, emoji)
    notify_holders(client, emoji)

    if not acquired:
        index = semaphore["queue"].index(user_id)
        message = f"I see you're interested in {emoji}. You didn't get access just yet, though.\nYou're "
        if index == 0:
            message += "next in line. Be prepared, it's coming soon!"
        else:
            message += f"behind {index} others waiting for the resource."
        client.chat_postMessage(channel=user_id, text=message)


def notify_user_of_acquiring(client, user_id, emoji):
    resource = semaphores[emoji]["resource"]
    client.chat_postMessage(
        channel=user_id,
        text=(
            f"You're now authorized to access {resource}.\n"
            + f"Please remember to release the resource by removing {emoji} from your "
            + "status when you're done.\nHave fun :party_parrot:!"
        ),
    )


def notify_enqueued_users(client, emoji, starting_from=0):
    semaphore = semaphores[emoji]
    for idx, user_id in enumerate(semaphore["queue"]):
        if idx < starting_from:
            continue

        message = f"News on {emoji}: You're "
        if idx == 0:
            message += "next in line. Be prepared, it's coming soon!"
        else:
            message += f"behind {idx} others waiting for the resource."

        client.chat_postMessage(channel=user_id, text=message)


def notify_holders(client, emoji):
    semaphore = semaphores[emoji]
    queue_size = len(semaphore["queue"])

    if queue_size == 0:
        return

    if queue_size == 1:
        people_substr = "is 1 person"
    else:
        people_substr = f"are {queue_size} people"

    message = (
        "Hey friend! Not to pressure you, but just so you know, there "
        + f"{people_substr} waiting on {emoji}. :slightly_smiling_face:"
    )

    for user_id in semaphore["holders"]:
        client.chat_postMessage(channel=user_id, text=message)


def user_update(client, user_id, emoji):
    previous_emoji = users.get(user_id)
    users[user_id] = emoji

    # Updates might not be related to status emoji changes
    if previous_emoji == emoji:
        return

    pop_user_from_semaphore(client, user_id, previous_emoji)

    if is_user_subscribed(user_id, emoji):
        push_user_to_semaphore(client, user_id, emoji)

    print(semaphores)  # TODO: REMOVE DEBUG


def semaphore_join(user_id, emoji):
    if emoji in semaphores.keys():
        semaphore = semaphores[emoji]

        if is_user_subscribed(user_id, emoji):
            return f"You're already part of {emoji}."

        subscriptions[emoji].add(user_id)
        return (
            f"Right-o! You've joined the {emoji} semaphore that manages access "
            + f"to {semaphore['resource']}.\nSet {emoji} as your status emoji "
            + "whenever you want to secure access to that resource. After you're "
            + "done using it, just clear your status and I'll notify the next "
            + "person in line so that they can use it."
        )
    else:
        return f"Sorry, there is no semaphore for {emoji}."


def semaphore_leave(user_id, emoji):
    if emoji in semaphores.keys():
        if not is_user_subscribed(user_id, emoji):
            return f"You are not participating in {emoji}."

        subscriptions[emoji].remove(user_id)
        return (
            f"You are no longer participating in the {emoji} semaphore.\n"
            + "Thank you for joining the experiment :patricklove:!"
        )
    else:
        return f"Sorry, there is no semaphore for {emoji}."


def semaphore_list():
    message = (
        "These are the available semaphores, the resources they manage and "
        + "how many may use them simultaneously:\n"
    )

    for emoji in semaphores.keys():
        semaphore = semaphores[emoji]
        resource = semaphore["resource"]
        seats = semaphore["seats"]
        message += f"\n- {emoji} - {resource} ({seats} seat{'s' if seats != 1 else ''})"

    return message


def semaphore_who(client, emoji):
    if emoji not in semaphores.keys():
        return f"Sorry, there is no semaphore for {emoji}."

    semaphore = semaphores[emoji]
    resource = semaphore["resource"]
    holders = semaphore["holders"]

    if len(holders) == 0:
        return f"Nobody has {emoji} now."

    holder_names = []
    for holder in holders:
        user = client.users_profile_get(user=holder)
        name = user["profile"]["real_name"]
        holder_names.append(name)

    message = f"Right now, these fine folks have secured access to {resource} through {emoji}:\n"
    message += ", ".join(holder_names) + "."

    return message


# Not working and not necessary.
# @app.message()
# def say_hello(message, say):
#     user = message["user"]
#     say(f"Hello, <@{user}>!")


@app.command("/semaphore_list")
def cmd_semaphore_list(ack, say):
    message = semaphore_list()
    ack()
    say(message)


@app.command("/semaphore_join")
def cmd_semaphore_join(ack, body, say):
    user_id = body["user_id"]
    emoji = body["text"]
    message = semaphore_join(user_id, emoji)
    ack()
    say(message)


@app.command("/semaphore_leave")
def cmd_semaphore_leave(ack, body, say):
    user_id = body["user_id"]
    emoji = body["text"]
    message = semaphore_leave(user_id, emoji)
    ack()
    say(message)


@app.command("/semaphore_who")
def cmd_semaphore_who(ack, body, client, say):
    emoji = body["text"]
    message = semaphore_who(client, emoji)
    ack()
    say(message)


@app.event("user_status_changed")
def receive_status_update(client, event):
    user = event["user"]
    emoji = event["user"]["profile"]["status_emoji"]
    ftime = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    print(f"[{ftime}] {user['name']} ({user['id']}) has {emoji}")  # TODO: REMOVE DEBUG
    # Any messages are sent back using client instead of say
    user_update(client, user["id"], emoji)


if __name__ == "__main__":
    init_semaphores(config.SEMAPHORE_CONFIG_FILE)
    init_subscriptions()

    handler = SocketModeHandler(app, config.SLACK_SOCKET_MODE_TOKEN)
    handler.start()  # use this to have an event listener
