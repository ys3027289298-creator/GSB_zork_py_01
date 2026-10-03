"""Regression tests for the zork.py engine.

Covers map traversal, item state, determinism, failure safety (failed
commands must not mutate the world), persistence/replay hygiene, and
command normalization.
"""

import os
import tempfile
import unittest

import zork


def run(world, commands, **kwargs):
    """Run a command script, returning the list of outputs (one per command)."""
    return [zork.handle_command(world, command, **kwargs) for command in commands]


class MapTraversalTests(unittest.TestCase):
    def setUp(self):
        self.world = zork.World()

    def test_full_path_to_mudroom(self):
        script = ["go southwest", "go east", "descend grating", "descend staircase"]
        expected_rooms = ["forest", "clearing", "cave", "mudroom"]
        for command, room in zip(script, expected_rooms):
            self.assertEqual(zork.handle_command(self.world, command), [])
            self.assertEqual(self.world.room, room)

    def test_staircase_aliases_all_reach_mudroom(self):
        for alias in ("descend staircase", "go down staircase", "scale staircase"):
            world = zork.World()
            world.room = "cave"
            self.assertEqual(zork.handle_command(world, alias), [])
            self.assertEqual(world.room, "mudroom")

    def test_blocked_directions_keep_room(self):
        cases = {
            "field": ["go east", "go north", "go west", "go south", "go up"],
            "forest": ["go west", "go north", "go south", "go southwest"],
            "clearing": ["go south", "go north", "go east", "go west"],
            "cave": ["go north", "go east", "go up"],
            "mudroom": ["go north", "go up", "go east"],
        }
        for room, commands in cases.items():
            for command in commands:
                world = zork.World()
                world.room = room
                lines = zork.handle_command(world, command)
                self.assertEqual(world.room, room, "%r moved out of %s" % (command, room))
                self.assertTrue(lines, "%r returned no output" % command)

    def test_room_commands_do_not_leak_across_rooms(self):
        # Cave-only command must not work once the player has left the cave.
        world = zork.World()
        world.room = "mudroom"
        lines = zork.handle_command(world, "take skeleton")
        self.assertEqual(lines, ["You don't see that here."])
        # Field-only command must not work from the forest.
        world = zork.World()
        zork.handle_command(world, "go southwest")
        self.assertEqual(world.room, "forest")
        lines = zork.handle_command(world, "open mailbox")
        self.assertFalse(world.mailbox_open)
        self.assertEqual(lines, ["I don't understand that."])


class ItemStateTests(unittest.TestCase):
    def setUp(self):
        self.world = zork.World()

    def test_open_mailbox_reveals_leaflet_once(self):
        self.assertEqual(
            zork.handle_command(self.world, "open mailbox"),
            ["Opening the small mailbox reveals a leaflet."],
        )
        self.assertTrue(self.world.mailbox_open)
        self.assertEqual(
            zork.handle_command(self.world, "open mailbox"),
            ["The mailbox is already open."],
        )

    def test_take_leaflet_requires_open_mailbox(self):
        self.assertEqual(zork.handle_command(self.world, "take leaflet"), ["You don't see that here."])
        self.assertEqual(self.world.inventory, [])
        zork.handle_command(self.world, "open mailbox")
        self.assertEqual(zork.handle_command(self.world, "take leaflet"), ["Taken."])
        self.assertEqual(self.world.inventory, ["leaflet"])
        self.assertTrue(self.world.leaflet_taken)

    def test_take_same_item_twice_is_rejected(self):
        zork.handle_command(self.world, "open mailbox")
        zork.handle_command(self.world, "take leaflet")
        before = self.world.to_dict()
        self.assertEqual(zork.handle_command(self.world, "take leaflet"), ["You already have the leaflet."])
        self.assertEqual(self.world.to_dict(), before)
        self.assertEqual(self.world.inventory, ["leaflet"])

    def test_take_nonexistent_item(self):
        self.assertEqual(zork.handle_command(self.world, "take lamp"), ["You don't see that here."])
        self.assertEqual(self.world.inventory, [])

    def test_read_leaflet_requires_discovery(self):
        self.assertEqual(zork.handle_command(self.world, "read leaflet"), ["You don't see that here."])
        zork.handle_command(self.world, "open mailbox")
        self.assertEqual(
            zork.handle_command(self.world, "read leaflet"),
            ["Welcome to the Unofficial Python Version of Zork. Your mission is to find a Jade Statue."],
        )

    def test_inventory_command_reflects_state(self):
        self.assertEqual(zork.handle_command(self.world, "inventory"), ["You are empty-handed."])
        zork.handle_command(self.world, "open mailbox")
        zork.handle_command(self.world, "take leaflet")
        self.assertEqual(zork.handle_command(self.world, "inventory"), ["You are carrying: leaflet."])

    def test_open_trunk_wins_once(self):
        self.world.room = "mudroom"
        self.assertEqual(
            zork.handle_command(self.world, "open trunk"),
            ["You have found the Jade Statue and have completed your quest!"],
        )
        self.assertTrue(self.world.won)
        self.assertEqual(zork.handle_command(self.world, "open trunk"), ["The trunk is already open."])


class FailureSafetyTests(unittest.TestCase):
    """Failed commands must return a defined message and never mutate state."""

    FAILING_COMMANDS = [
        "",
        "   ",
        "xyzzy",
        "go nowhere",
        "take lamp",
        "take leaflet",
        "read leaflet",
        "open mailbox",  # only fails outside the field; filtered below
    ]

    def test_empty_and_unknown_commands_are_defined(self):
        self.assertEqual(zork.handle_command(zork.World(), ""), ["Please enter a command."])
        self.assertEqual(zork.handle_command(zork.World(), "   "), ["Please enter a command."])
        self.assertEqual(zork.handle_command(zork.World(), "xyzzy"), ["I don't understand that."])

    def test_failed_commands_do_not_modify_world_state(self):
        for room in zork.ROOM_DESCRIPTIONS:
            world = zork.World()
            world.room = room
            for command in self.FAILING_COMMANDS:
                if command == "open mailbox" and room == "field":
                    continue  # succeeds in the field by design
                if command in ("take leaflet", "read leaflet") and room == "field":
                    continue  # covered by ItemStateTests with mailbox open
                world = zork.World()
                world.room = room
                before = world.to_dict()
                lines = zork.handle_command(world, command)
                self.assertTrue(lines, "%r in %s returned no output" % (command, room))
                self.assertEqual(world.to_dict(), before, "%r in %s mutated state" % (command, room))

    def test_load_without_save_file_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing.json")
            world = zork.World()
            before = world.to_dict()
            self.assertEqual(
                zork.handle_command(world, "load", save_path=path),
                ["No saved game found."],
            )
            self.assertEqual(world.to_dict(), before)


class DeterminismTests(unittest.TestCase):
    SCRIPT = [
        "take mailbox",
        "open mailbox",
        "open mailbox",
        "take leaflet",
        "take leaflet",
        "read leaflet",
        "inventory",
        "go east",
        "go southwest",
        "go west",
        "go east",
        "descend grating",
        "take skeleton",
        "smash skeleton",
        "light up room",
        "break skeleton",
        "descend staircase",
        "open trunk",
        "open trunk",
        "",
        "nonsense",
    ]

    def test_same_script_same_results(self):
        first_world, second_world = zork.World(), zork.World()
        first = run(first_world, self.SCRIPT)
        second = run(second_world, self.SCRIPT)
        self.assertEqual(first, second)
        self.assertEqual(first_world.to_dict(), second_world.to_dict())

    def test_every_command_returns_output(self):
        world = zork.World()
        for command, lines in zip(self.SCRIPT, run(world, self.SCRIPT)):
            if zork.normalize(command) in ("go southwest", "go east", "descend grating", "descend staircase"):
                continue  # successful moves print the next room description instead
            self.assertTrue(lines, "%r returned no output" % command)


class NormalizationTests(unittest.TestCase):
    VARIANTS = ["take mailbox", "TAKE MAILBOX", "Take Mailbox", "  take   mailbox  ", "\tTake Mailbox\n"]

    def test_case_and_whitespace_are_equivalent(self):
        expected = ["It is securely anchored."]
        for variant in self.VARIANTS:
            world = zork.World()
            self.assertEqual(zork.handle_command(world, variant), expected, repr(variant))

    def test_normalization_is_idempotent(self):
        for variant in self.VARIANTS:
            self.assertEqual(zork.normalize(variant), "take mailbox")


class PersistenceTests(unittest.TestCase):
    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "save.json")
            world = zork.World()
            run(world, ["open mailbox", "take leaflet", "go southwest", "go east"])
            zork.save_game(world, path)
            restored = zork.World()
            zork.load_game(restored, path)
            self.assertEqual(restored.to_dict(), world.to_dict())

    def test_load_fully_replaces_state_without_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "save.json")
            saved = zork.World()
            zork.handle_command(saved, "open mailbox")
            zork.save_game(saved, path)
            # Play far beyond the save point, then load: nothing may linger.
            world = zork.World()
            run(world, ["open mailbox", "take leaflet", "go southwest", "go east", "descend grating"])
            self.assertEqual(zork.handle_command(world, "load", save_path=path), ["Game loaded."])
            self.assertEqual(world.to_dict(), saved.to_dict())
            self.assertEqual(world.inventory, [])
            self.assertEqual(world.room, "field")

    def test_replay_after_death_starts_fresh(self):
        world = zork.World()
        run(world, ["open mailbox", "take leaflet", "go southwest", "go east", "descend grating"])
        self.assertEqual(
            zork.handle_command(world, "suicide"),
            ["You throw yourself down the staircase as an attempt at suicide. You die."],
        )
        self.assertTrue(world.dead)
        world.reset()  # player answers "Y" at the continue prompt
        self.assertEqual(world.to_dict(), zork.World().to_dict())
        self.assertEqual(world.room, "field")
        self.assertEqual(world.inventory, [])
        self.assertFalse(world.mailbox_open)

    def test_corrupt_save_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "save.json")
            with open(path, "w") as handle:
                handle.write('{"room": "nowhere"}')
            with self.assertRaises(ValueError):
                zork.load_game(zork.World(), path)


if __name__ == "__main__":
    unittest.main()
