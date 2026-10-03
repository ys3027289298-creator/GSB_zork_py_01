"""Zork - The Unofficial Python Version.

Single-file game structured as a pure, testable world/command engine plus a
thin REPL front-end. All original prompt and narration text is preserved
verbatim; only the control flow and state handling were rebuilt.
"""

import json
import os

SEPARATOR = "---------------------------------------------------------"
SAVE_PATH = "zork_save.json"

WELCOME = "Welcome to Zork - The Unofficial Python Version."

ROOM_DESCRIPTIONS = {
    "field": [
        "You are standing in an open field west of a white house, with a boarded front door.",
        "(A secret path leads southwest into the forest.)",
        "There is a Small Mailbox.",
    ],
    "forest": [
        "This is a forest, with trees in all directions. To the east, there appears to be sunlight.",
    ],
    "clearing": [
        "You are in a clearing, with a forest surrounding you on all sides. A path leads south.",
        "There is an open grating, descending into darkness.",
    ],
    "cave": [
        "You are in a tiny cave with a dark, forbidding staircase leading down.",
        "There is a skeleton of a human male in one corner.",
    ],
    "mudroom": [
        "You have entered a mud-floored room.",
        "Lying half buried in the mud is an old trunk, bulging with jewels.",
    ],
}

STATE_KEYS = (
    "room",
    "inventory",
    "mailbox_open",
    "leaflet_taken",
    "trunk_open",
    "dead",
    "won",
)


class World:
    """Complete, serializable game state."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.room = "field"
        self.inventory = []
        self.mailbox_open = False
        self.leaflet_taken = False
        self.trunk_open = False
        self.dead = False
        self.won = False

    def to_dict(self):
        return {key: list(getattr(self, key)) if key == "inventory" else getattr(self, key) for key in STATE_KEYS}

    def load_dict(self, data):
        # Full replacement: every key is overwritten so no stale state survives.
        for key in STATE_KEYS:
            if key not in data:
                raise ValueError("save data is missing key: %s" % key)
        self.room = data["room"]
        self.inventory = list(data["inventory"])
        self.mailbox_open = bool(data["mailbox_open"])
        self.leaflet_taken = bool(data["leaflet_taken"])
        self.trunk_open = bool(data["trunk_open"])
        self.dead = bool(data["dead"])
        self.won = bool(data["won"])
        if self.room not in ROOM_DESCRIPTIONS:
            raise ValueError("save data has unknown room: %s" % self.room)


def save_game(world, path=SAVE_PATH):
    with open(path, "w") as handle:
        json.dump(world.to_dict(), handle)


def load_game(world, path=SAVE_PATH):
    with open(path) as handle:
        data = json.load(handle)
    world.load_dict(data)


def normalize(raw):
    """Single normalization point: case- and whitespace-insensitive commands."""
    return " ".join(raw.strip().lower().split())


def handle_command(world, raw, save_path=SAVE_PATH):
    """Run one command against the world. Returns the list of output lines.

    Pure with respect to I/O: every command, including failures, returns a
    deterministic result. Failed commands never mutate the world.
    """
    cmd = normalize(raw)
    if not cmd:
        return ["Please enter a command."]

    if cmd == "look":
        return list(ROOM_DESCRIPTIONS[world.room])
    if cmd == "inventory":
        if world.inventory:
            return ["You are carrying: " + ", ".join(world.inventory) + "."]
        return ["You are empty-handed."]
    if cmd == "save":
        save_game(world, save_path)
        return ["Game saved."]
    if cmd == "load":
        if not os.path.exists(save_path):
            return ["No saved game found."]
        load_game(world, save_path)
        return ["Game loaded."]

    handler = ROOM_HANDLERS[world.room]
    lines = handler(world, cmd)
    if lines is not None:
        return lines

    if cmd.startswith("go "):
        return ["You can't go that way."]
    if cmd.startswith("take "):
        return ["You don't see that here."]
    return ["I don't understand that."]


def _read_leaflet(world):
    if world.mailbox_open:
        return ["Welcome to the Unofficial Python Version of Zork. Your mission is to find a Jade Statue."]
    return ["You don't see that here."]


def _take_leaflet(world):
    if world.leaflet_taken:
        return ["You already have the leaflet."]
    if not world.mailbox_open:
        return ["You don't see that here."]
    world.leaflet_taken = True
    world.inventory.append("leaflet")
    return ["Taken."]


def _field(world, cmd):
    if cmd == "take mailbox":
        return ["It is securely anchored."]
    if cmd == "open mailbox":
        if world.mailbox_open:
            return ["The mailbox is already open."]
        world.mailbox_open = True
        return ["Opening the small mailbox reveals a leaflet."]
    if cmd == "go east":
        return ["The door is boarded and you cannot remove the boards."]
    if cmd == "open door":
        return ["The door cannot be opened."]
    if cmd == "take boards":
        return ["The boards are securely fastened."]
    if cmd == "look at house":
        return ["The house is a beautiful colonial house which is painted white. It is clear that the owners must have been extremely wealthy."]
    if cmd == "go southwest":
        world.room = "forest"
        return []
    if cmd == "read leaflet":
        return _read_leaflet(world)
    if cmd == "take leaflet":
        return _take_leaflet(world)
    return None


def _forest(world, cmd):
    if cmd == "go west":
        return ["You would need a machete to go further west."]
    if cmd == "go north":
        return ["The forest becomes impenetrable to the North."]
    if cmd == "go south":
        return ["Storm-tossed trees block your way."]
    if cmd == "go east":
        world.room = "clearing"
        return []
    return None


def _clearing(world, cmd):
    if cmd == "go south":
        return ["You see a large ogre and turn around."]
    if cmd == "descend grating":
        world.room = "cave"
        return []
    return None


def _cave(world, cmd):
    if cmd in ("descend staircase", "go down staircase", "scale staircase"):
        world.room = "mudroom"
        return []
    if cmd == "take skeleton":
        return ["Why would you do that? Are you some sort of sicko?"]
    if cmd == "smash skeleton":
        return ["Sick person. Have some respect mate."]
    if cmd == "light up room":
        return ["You would need a torch or lamp to do that."]
    if cmd == "break skeleton":
        return ["I have two questions: Why and With What?"]
    if cmd == "suicide":
        world.dead = True
        return ["You throw yourself down the staircase as an attempt at suicide. You die."]
    return None


def _mudroom(world, cmd):
    if cmd == "open trunk":
        if world.trunk_open:
            return ["The trunk is already open."]
        world.trunk_open = True
        world.won = True
        return ["You have found the Jade Statue and have completed your quest!"]
    return None


ROOM_HANDLERS = {
    "field": _field,
    "forest": _forest,
    "clearing": _clearing,
    "cave": _cave,
    "mudroom": _mudroom,
}


def main():
    world = World()
    print(SEPARATOR)
    print(WELCOME)
    while True:
        print(SEPARATOR)
        for line in ROOM_DESCRIPTIONS[world.room]:
            print(line)
        try:
            command = input("What do you do? ")
        except EOFError:
            print()
            break
        lines = handle_command(world, command)
        if lines:
            print(SEPARATOR)
            for line in lines:
                print(line)
        if world.dead or world.won:
            if world.dead:
                print(SEPARATOR)
            try:
                answer = input("Do you want to continue? Y/N ")
            except EOFError:
                print()
                break
            answer = answer.strip().lower()
            if answer == "n":
                break
            if answer == "y":
                world.reset()
            else:
                world.dead = False
                world.won = False


if __name__ == "__main__":
    main()
