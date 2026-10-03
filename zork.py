# Introduction narration of game
#
# Zork - The Unofficial Python Version.
#
# The game is modelled as a small state machine so that every command
# produces a deterministic result and failed commands never mutate the
# world state.  All of the original prompt text is preserved verbatim.

SEPARATOR = "---------------------------------------------------------"

WELCOME = "Welcome to Zork - The Unofficial Python Version."

ROOM_BANNERS = {
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
    "mud_room": [
        "You have entered a mud-floored room.",
        "Lying half buried in the mud is an old trunk, bulging with jewels.",
    ],
}

START_ROOM = "field"


class Game:
    """The whole world state of one play-through."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Start a fresh play-through, clearing every leftover state."""
        self.room = START_ROOM
        self.inventory = []
        self.mailbox_open = False
        self.leaflet_in_mailbox = True
        self.trunk_open = False
        self.won = False
        self.died = False
        self.awaiting_continue = False
        self.quit = False

    def snapshot(self):
        """An immutable, comparable view of the world state."""
        return (
            self.room,
            tuple(sorted(self.inventory)),
            self.mailbox_open,
            self.leaflet_in_mailbox,
            self.trunk_open,
            self.won,
        )

    def save(self):
        """Serialize the world state; the result is JSON-friendly."""
        return {
            "room": self.room,
            "inventory": list(self.inventory),
            "mailbox_open": self.mailbox_open,
            "leaflet_in_mailbox": self.leaflet_in_mailbox,
            "trunk_open": self.trunk_open,
            "won": self.won,
        }

    def load(self, state):
        """Restore a saved game, discarding every trace of the current one."""
        self.reset()
        self.room = state["room"]
        self.inventory = list(state["inventory"])
        self.mailbox_open = state["mailbox_open"]
        self.leaflet_in_mailbox = state["leaflet_in_mailbox"]
        self.trunk_open = state["trunk_open"]
        self.won = state["won"]

    def banner(self):
        return list(ROOM_BANNERS[self.room])

    @staticmethod
    def normalize(command):
        return " ".join(command.lower().split())

    def handle(self, command):
        """Run one command.

        Returns the list of text lines to show the player.  An empty list
        means the command moved the player (the next room banner is the
        only output, exactly like the original script).  Commands that
        fail never change the world state.
        """
        command = self.normalize(command)
        if not command:
            return ["I beg your pardon?"]
        if command in ("inventory", "i"):
            return self._inventory_lines()

        room = self.room
        if room == "field":
            lines = self._handle_field(command)
        elif room == "forest":
            lines = self._handle_forest(command)
        elif room == "clearing":
            lines = self._handle_clearing(command)
        elif room == "cave":
            lines = self._handle_cave(command)
        else:
            lines = self._handle_mud_room(command)

        if lines is None:
            lines = self._unknown_lines(command)
        if room == "mud_room":
            self.awaiting_continue = True
        return lines

    def answer_continue(self, answer):
        """Answer the 'Do you want to continue? Y/N' prompt."""
        self.awaiting_continue = False
        self.died = False
        answer = self.normalize(answer)
        if answer == "n":
            self.quit = True
        elif answer == "y":
            self.reset()

    def _inventory_lines(self):
        if not self.inventory:
            return ["You are empty-handed."]
        return ["You are carrying:"] + ["A " + item for item in self.inventory]

    def _unknown_lines(self, command):
        if command.startswith("take "):
            return ["You can't see any " + command[len("take "):] + " here."]
        return ["I don't understand that."]

    def _handle_field(self, command):
        if command == "take mailbox":
            return ["It is securely anchored."]
        if command == "open mailbox":
            if self.mailbox_open:
                return ["The mailbox is already open."]
            self.mailbox_open = True
            return ["Opening the small mailbox reveals a leaflet."]
        if command == "take leaflet":
            if "leaflet" in self.inventory:
                return ["You already have the leaflet."]
            if self.mailbox_open and self.leaflet_in_mailbox:
                self.leaflet_in_mailbox = False
                self.inventory.append("leaflet")
                return ["Taken."]
            return ["You can't see any leaflet here."]
        if command == "go east":
            return ["The door is boarded and you cannot remove the boards."]
        if command == "open door":
            return ["The door cannot be opened."]
        if command == "take boards":
            return ["The boards are securely fastened."]
        if command == "look at house":
            return ["The house is a beautiful colonial house which is painted white. It is clear that the owners must have been extremely wealthy."]
        if command == "go southwest":
            self.room = "forest"
            return []
        if command == "read leaflet":
            return ["Welcome to the Unofficial Python Version of Zork. Your mission is to find a Jade Statue."]
        return None

    def _handle_forest(self, command):
        if command == "go west":
            return ["You would need a machete to go further west."]
        if command == "go north":
            return ["The forest becomes impenetrable to the North."]
        if command == "go south":
            return ["Storm-tossed trees block your way."]
        if command == "go east":
            self.room = "clearing"
            return []
        return None

    def _handle_clearing(self, command):
        if command == "go south":
            return ["You see a large ogre and turn around."]
        if command == "descend grating":
            self.room = "cave"
            return []
        return None

    def _handle_cave(self, command):
        if command in ("descend staircase", "go down staircase", "scale staircase"):
            self.room = "mud_room"
            return []
        if command == "take skeleton":
            return ["Why would you do that? Are you some sort of sicko?"]
        if command == "smash skeleton":
            return ["Sick person. Have some respect mate."]
        if command == "light up room":
            return ["You would need a torch or lamp to do that."]
        if command == "break skeleton":
            return ["I have two questions: Why and With What?"]
        if command == "suicide":
            self.died = True
            self.awaiting_continue = True
            return ["You throw yourself down the staircase as an attempt at suicide. You die."]
        return None

    def _handle_mud_room(self, command):
        if command == "open trunk":
            self.trunk_open = True
            self.won = True
            return ["You have found the Jade Statue and have completed your quest!"]
        return None


def main():
    loop = Game()
    print(SEPARATOR)
    print(WELCOME)
    try:
        while not loop.quit:
            print(SEPARATOR)
            for line in loop.banner():
                print(line)
            command = input("What do you do? ")
            lines = loop.handle(command)
            if lines:
                print(SEPARATOR)
                for line in lines:
                    print(line)
            if loop.awaiting_continue:
                if loop.died:
                    print(SEPARATOR)
                answer = input("Do you want to continue? Y/N ")
                loop.answer_continue(answer)
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
