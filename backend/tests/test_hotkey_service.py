import unittest

from voz_a_texto.desktop.hotkey_service import HotkeyStateMachine, parse_hotkey


class HotkeyServiceTestCase(unittest.TestCase):
    def test_parse_hotkey_recognizes_modifier_and_key(self):
        definition = parse_hotkey("Alt+Z")

        self.assertEqual(definition.modifiers, frozenset({"alt"}))
        self.assertEqual(definition.key, "z")

    def test_state_machine_emits_press_and_release_once(self):
        machine = HotkeyStateMachine(parse_hotkey("Alt+Z"))

        self.assertIsNone(machine.handle_press("alt"))
        self.assertEqual(machine.handle_press("z"), "pressed")
        self.assertIsNone(machine.handle_press("z"))
        self.assertEqual(machine.handle_release("alt"), "released")
        self.assertFalse(machine.active)


if __name__ == "__main__":
    unittest.main()
