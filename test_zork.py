"""Regression tests for zork.py.

Covers map traversal and item state, guarantees that every command
returns a deterministic result and that failed commands never modify
the world state.  Also guards the original prompt text verbatim.
"""

import unittest

from zork import Game, ROOM_BANNERS, SEPARATOR, WELCOME


def fresh_game():
    return Game()


def play(game, commands):
    """Feed commands, auto-answering the continue prompt with 'y'."""
    outputs = []
    for command in commands:
        outputs.append(game.handle(command))
        if game.awaiting_continue:
            game.answer_continue("y")
    return outputs


def walk_to(game, room):
    """Drive a fresh-ish game to the requested room via the happy path."""
    routes = {
        "field": [],
        "forest": ["go southwest"],
        "clearing": ["go southwest", "go east"],
        "cave": ["go southwest", "go east", "descend grating"],
        "mud_room": ["go southwest", "go east", "descend grating", "descend staircase"],
    }
    play(game, routes[room])
    assert game.room == room
    return game


class TestOriginalTextPreserved(unittest.TestCase):
    """The original prompt text must survive the refactor verbatim."""

    def test_banner_text(self):
        self.assertEqual(
            ROOM_BANNERS["field"],
            [
                "You are standing in an open field west of a white house, with a boarded front door.",
                "(A secret path leads southwest into the forest.)",
                "There is a Small Mailbox.",
            ],
        )
        self.assertEqual(
            ROOM_BANNERS["forest"],
            ["This is a forest, with trees in all directions. To the east, there appears to be sunlight."],
        )
        self.assertEqual(
            ROOM_BANNERS["clearing"],
            [
                "You are in a clearing, with a forest surrounding you on all sides. A path leads south.",
                "There is an open grating, descending into darkness.",
            ],
        )
        self.assertEqual(
            ROOM_BANNERS["cave"],
            [
                "You are in a tiny cave with a dark, forbidding staircase leading down.",
                "There is a skeleton of a human male in one corner.",
            ],
        )
        self.assertEqual(
            ROOM_BANNERS["mud_room"],
            [
                "You have entered a mud-floored room.",
                "Lying half buried in the mud is an old trunk, bulging with jewels.",
            ],
        )
        self.assertEqual(WELCOME, "Welcome to Zork - The Unofficial Python Version.")
        self.assertEqual(SEPARATOR, "---------------------------------------------------------")

    def test_field_responses(self):
        expected = {
            "take mailbox": ["It is securely anchored."],
            "open mailbox": ["Opening the small mailbox reveals a leaflet."],
            "go east": ["The door is boarded and you cannot remove the boards."],
            "open door": ["The door cannot be opened."],
            "take boards": ["The boards are securely fastened."],
            "look at house": ["The house is a beautiful colonial house which is painted white. It is clear that the owners must have been extremely wealthy."],
            "read leaflet": ["Welcome to the Unofficial Python Version of Zork. Your mission is to find a Jade Statue."],
        }
        for command, lines in expected.items():
            with self.subTest(command=command):
                self.assertEqual(fresh_game().handle(command), lines)

    def test_forest_responses(self):
        expected = {
            "go west": ["You would need a machete to go further west."],
            "go north": ["The forest becomes impenetrable to the North."],
            "go south": ["Storm-tossed trees block your way."],
        }
        for command, lines in expected.items():
            with self.subTest(command=command):
                self.assertEqual(walk_to(fresh_game(), "forest").handle(command), lines)

    def test_clearing_responses(self):
        game = walk_to(fresh_game(), "clearing")
        self.assertEqual(game.handle("go south"), ["You see a large ogre and turn around."])

    def test_cave_responses(self):
        expected = {
            "take skeleton": ["Why would you do that? Are you some sort of sicko?"],
            "smash skeleton": ["Sick person. Have some respect mate."],
            "light up room": ["You would need a torch or lamp to do that."],
            "break skeleton": ["I have two questions: Why and With What?"],
            "suicide": ["You throw yourself down the staircase as an attempt at suicide. You die."],
        }
        for command, lines in expected.items():
            with self.subTest(command=command):
                self.assertEqual(walk_to(fresh_game(), "cave").handle(command), lines)

    def test_mud_room_responses(self):
        game = walk_to(fresh_game(), "mud_room")
        self.assertEqual(
            game.handle("open trunk"),
            ["You have found the Jade Statue and have completed your quest!"],
        )


class TestMapTraversal(unittest.TestCase):
    def test_happy_path(self):
        game = fresh_game()
        self.assertEqual(game.room, "field")
        self.assertEqual(game.handle("go southwest"), [])
        self.assertEqual(game.room, "forest")
        self.assertEqual(game.handle("go east"), [])
        self.assertEqual(game.room, "clearing")
        self.assertEqual(game.handle("descend grating"), [])
        self.assertEqual(game.room, "cave")
        self.assertEqual(game.handle("descend staircase"), [])
        self.assertEqual(game.room, "mud_room")

    def test_all_staircase_synonyms(self):
        for command in ("descend staircase", "go down staircase", "scale staircase"):
            with self.subTest(command=command):
                game = walk_to(fresh_game(), "cave")
                self.assertEqual(game.handle(command), [])
                self.assertEqual(game.room, "mud_room")

    def test_blocked_moves_keep_room(self):
        cases = [
            ("field", ["go east", "go north", "go west", "go south", "open door"]),
            ("forest", ["go west", "go north", "go south"]),
            ("clearing", ["go south", "go north", "go east", "go west"]),
            ("cave", ["go north", "go south", "go east", "go west"]),
        ]
        for room, commands in cases:
            for command in commands:
                with self.subTest(room=room, command=command):
                    game = walk_to(fresh_game(), room)
                    before = game.snapshot()
                    result = game.handle(command)
                    self.assertIsInstance(result, list)
                    self.assertTrue(result, "blocked moves must still give feedback")
                    self.assertEqual(game.room, room)
                    self.assertEqual(game.snapshot(), before)


class TestItemState(unittest.TestCase):
    def test_mailbox_is_anchored_no_matter_how_often_taken(self):
        game = fresh_game()
        for _ in range(3):
            before = game.snapshot()
            self.assertEqual(game.handle("take mailbox"), ["It is securely anchored."])
            self.assertEqual(game.snapshot(), before)
            self.assertNotIn("mailbox", game.inventory)

    def test_open_mailbox_twice(self):
        game = fresh_game()
        self.assertEqual(game.handle("open mailbox"), ["Opening the small mailbox reveals a leaflet."])
        self.assertTrue(game.mailbox_open)
        before = game.snapshot()
        self.assertEqual(game.handle("open mailbox"), ["The mailbox is already open."])
        self.assertEqual(game.snapshot(), before)

    def test_take_leaflet_requires_open_mailbox(self):
        game = fresh_game()
        before = game.snapshot()
        self.assertEqual(game.handle("take leaflet"), ["You can't see any leaflet here."])
        self.assertEqual(game.snapshot(), before)

    def test_take_leaflet_twice(self):
        game = fresh_game()
        game.handle("open mailbox")
        self.assertEqual(game.handle("take leaflet"), ["Taken."])
        self.assertIn("leaflet", game.inventory)
        self.assertFalse(game.leaflet_in_mailbox)
        before = game.snapshot()
        self.assertEqual(game.handle("take leaflet"), ["You already have the leaflet."])
        self.assertEqual(game.snapshot(), before)
        self.assertEqual(game.inventory.count("leaflet"), 1)

    def test_inventory_command(self):
        game = fresh_game()
        self.assertEqual(game.handle("inventory"), ["You are empty-handed."])
        play(game, ["open mailbox", "take leaflet"])
        self.assertEqual(game.handle("inventory"), ["You are carrying:", "A leaflet"])

    def test_open_trunk_wins(self):
        game = walk_to(fresh_game(), "mud_room")
        game.handle("open trunk")
        self.assertTrue(game.trunk_open)
        self.assertTrue(game.won)


class TestDeterministicResults(unittest.TestCase):
    SCRIPT = [
        "",
        "xyzzy",
        "go north",
        "take lamp",
        "open mailbox",
        "open mailbox",
        "take leaflet",
        "take leaflet",
        "take mailbox",
        "inventory",
        "go southwest",
        "go west",
        "go east",
        "descend grating",
        "take skeleton",
        "descend staircase",
        "open trunk",
    ]

    def test_same_script_same_results(self):
        runs = []
        for _ in range(2):
            game = fresh_game()
            outputs = play(game, self.SCRIPT)
            runs.append((outputs, game.snapshot()))
        self.assertEqual(runs[0], runs[1])

    def test_every_command_returns_a_list_of_strings(self):
        game = fresh_game()
        for command in self.SCRIPT:
            with self.subTest(command=command):
                result = game.handle(command)
                self.assertIsInstance(result, list)
                for line in result:
                    self.assertIsInstance(line, str)
                if game.awaiting_continue:
                    game.answer_continue("y")

    def test_empty_command(self):
        game = fresh_game()
        before = game.snapshot()
        self.assertEqual(game.handle(""), ["I beg your pardon?"])
        self.assertEqual(game.handle("   "), ["I beg your pardon?"])
        self.assertEqual(game.snapshot(), before)

    def test_unknown_command(self):
        game = fresh_game()
        before = game.snapshot()
        self.assertEqual(game.handle("xyzzy"), ["I don't understand that."])
        self.assertEqual(game.snapshot(), before)

    def test_unknown_direction(self):
        game = fresh_game()
        before = game.snapshot()
        self.assertEqual(game.handle("go north"), ["I don't understand that."])
        self.assertEqual(game.room, "field")
        self.assertEqual(game.snapshot(), before)

    def test_nonexistent_item(self):
        game = fresh_game()
        before = game.snapshot()
        self.assertEqual(game.handle("take lamp"), ["You can't see any lamp here."])
        self.assertEqual(game.snapshot(), before)


class TestFailedCommandsKeepState(unittest.TestCase):
    FAILED_BY_ROOM = {
        "field": ["", "xyzzy", "go north", "take lamp", "take mailbox", "take boards",
                  "open door", "go east", "take leaflet"],
        "forest": ["", "go west", "go north", "go south", "take tree", "climb tree"],
        "clearing": ["", "go south", "take grating", "descend staircase"],
        "cave": ["", "take skeleton", "smash skeleton", "break skeleton",
                 "light up room", "take lamp", "go north"],
        "mud_room": ["", "take trunk", "go north", "xyzzy"],
    }

    def test_failed_commands_do_not_mutate_state(self):
        for room, commands in self.FAILED_BY_ROOM.items():
            for command in commands:
                with self.subTest(room=room, command=command):
                    game = walk_to(fresh_game(), room)
                    before = game.snapshot()
                    game.handle(command)
                    self.assertEqual(game.snapshot(), before)


class TestCommandNormalization(unittest.TestCase):
    def test_case_is_insensitive_everywhere(self):
        for command in ("GO SOUTHWEST", "Go SouthWest", "go southwest"):
            with self.subTest(command=command):
                game = fresh_game()
                self.assertEqual(game.handle(command), [])
                self.assertEqual(game.room, "forest")

    def test_surrounding_and_inner_whitespace_is_normalized(self):
        for command in (" go southwest", "go southwest ", "  go   southwest  "):
            with self.subTest(command=command):
                game = fresh_game()
                self.assertEqual(game.handle(command), [])
                self.assertEqual(game.room, "forest")

    def test_item_commands_normalized_too(self):
        game = fresh_game()
        self.assertEqual(game.handle("  OPEN   MAILBOX "), ["Opening the small mailbox reveals a leaflet."])
        self.assertEqual(game.handle("Take Leaflet"), ["Taken."])


class TestReplayAndSaveLoad(unittest.TestCase):
    def test_replay_after_suicide_resets_everything(self):
        game = fresh_game()
        play(game, ["open mailbox", "take leaflet", "go southwest", "go east",
                    "descend grating"])
        game.handle("suicide")
        self.assertTrue(game.awaiting_continue)
        game.answer_continue("y")
        self.assertEqual(game.snapshot(), fresh_game().snapshot())
        self.assertFalse(game.awaiting_continue)
        self.assertFalse(game.died)

    def test_replay_after_winning_resets_everything(self):
        game = walk_to(fresh_game(), "mud_room")
        game.handle("open trunk")
        self.assertTrue(game.won)
        game.answer_continue("y")
        self.assertEqual(game.snapshot(), fresh_game().snapshot())

    def test_continue_with_n_quits(self):
        game = walk_to(fresh_game(), "cave")
        game.handle("suicide")
        game.answer_continue("n")
        self.assertTrue(game.quit)

    def test_unrecognized_continue_answer_stays_put(self):
        game = walk_to(fresh_game(), "cave")
        game.handle("suicide")
        game.answer_continue("maybe")
        self.assertFalse(game.quit)
        self.assertEqual(game.room, "cave")

    def test_load_discards_leftover_state(self):
        game = fresh_game()
        play(game, ["open mailbox", "take leaflet", "go southwest"])
        saved = game.save()
        saved_snapshot = game.snapshot()

        play(game, ["go east", "descend grating", "suicide"])
        game.answer_continue("y")
        play(game, ["open mailbox"])
        self.assertNotEqual(game.snapshot(), saved_snapshot)

        game.load(saved)
        self.assertEqual(game.snapshot(), saved_snapshot)
        self.assertFalse(game.awaiting_continue)
        self.assertFalse(game.died)
        self.assertFalse(game.quit)

    def test_save_load_round_trip(self):
        game = walk_to(fresh_game(), "cave")
        clone = fresh_game()
        clone.load(game.save())
        self.assertEqual(clone.snapshot(), game.snapshot())
        self.assertEqual(clone.handle("take skeleton"), game.handle("take skeleton"))


class TestFullWalkthrough(unittest.TestCase):
    def test_winning_run(self):
        game = fresh_game()
        play(game, [
            "open mailbox",
            "take leaflet",
            "read leaflet",
            "go southwest",
            "go east",
            "descend grating",
            "descend staircase",
        ])
        self.assertEqual(
            game.handle("open trunk"),
            ["You have found the Jade Statue and have completed your quest!"],
        )
        self.assertTrue(game.won)
        self.assertTrue(game.awaiting_continue)
        game.answer_continue("n")
        self.assertTrue(game.quit)


if __name__ == "__main__":
    unittest.main()
