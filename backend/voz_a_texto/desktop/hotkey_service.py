from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


MODIFIER_ALIASES = {
    "alt": "alt",
    "option": "alt",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "meta": "meta",
    "super": "meta",
    "win": "meta",
    "cmd": "meta",
}

PYNPUT_MODIFIER_TOKENS = {
    "alt": {"alt", "alt_l", "alt_r", "alt_gr"},
    "ctrl": {"ctrl", "ctrl_l", "ctrl_r"},
    "shift": {"shift", "shift_l", "shift_r"},
    "meta": {"cmd", "cmd_l", "cmd_r"},
}


@dataclass(frozen=True, slots=True)
class HotkeyDefinition:
    modifiers: frozenset[str]
    key: str

    @property
    def required_tokens(self):
        return self.modifiers | {self.key}

    def matches(self, pressed_tokens):
        return self.required_tokens.issubset(pressed_tokens)


def parse_hotkey(hotkey):
    if not isinstance(hotkey, str) or not hotkey.strip():
        raise ValueError("Hotkey vacio")

    tokens = [token.strip().lower() for token in hotkey.split("+") if token.strip()]
    if not tokens:
        raise ValueError("Hotkey invalido")

    normalized_modifiers = []
    primary_key = None

    for token in tokens:
        normalized_modifier = MODIFIER_ALIASES.get(token)
        if normalized_modifier:
            normalized_modifiers.append(normalized_modifier)
            continue

        if primary_key is not None:
            raise ValueError("Solo se permite una tecla principal en la combinacion")

        primary_key = token

    if primary_key is None:
        raise ValueError("La combinacion debe incluir una tecla principal")

    return HotkeyDefinition(modifiers=frozenset(normalized_modifiers), key=primary_key)


def key_to_token(key):
    name = getattr(key, "name", None)
    if name:
        normalized_name = name.lower()
        for modifier, aliases in PYNPUT_MODIFIER_TOKENS.items():
            if normalized_name in aliases:
                return modifier
        if normalized_name.startswith("f") and normalized_name[1:].isdigit():
            return normalized_name
        if normalized_name in {"space", "enter", "tab", "esc", "delete", "backspace", "up", "down", "left", "right"}:
            return normalized_name

    char = getattr(key, "char", None)
    if isinstance(char, str) and char:
        return char.lower()

    return None


class HotkeyStateMachine:
    def __init__(self, definition):
        self.definition = definition
        self.pressed_tokens = set()
        self.active = False

    def handle_press(self, token):
        if not token:
            return None

        self.pressed_tokens.add(token)
        if not self.active and self.definition.matches(self.pressed_tokens):
            self.active = True
            return "pressed"

        return None

    def handle_release(self, token):
        if not token:
            return None

        self.pressed_tokens.discard(token)
        if self.active and not self.definition.matches(self.pressed_tokens):
            self.active = False
            return "released"

        return None

    def reset(self):
        self.pressed_tokens.clear()
        self.active = False


class GlobalHotkeyService(QObject):
    activated = Signal()
    released = Signal()
    error = Signal(str)

    def __init__(self, hotkey):
        super().__init__()
        self.hotkey = hotkey
        self._definition = parse_hotkey(hotkey)
        self._state_machine = HotkeyStateMachine(self._definition)
        self._listener = None

    def start(self):
        if self._listener is not None:
            return

        try:
            from pynput import keyboard

            self._listener = keyboard.Listener(
                on_press=self._handle_press,
                on_release=self._handle_release,
            )
            self._listener.start()
        except Exception as exc:
            self._listener = None
            self.error.emit(f"No se pudo iniciar el hotkey global: {exc}")

    def stop(self):
        listener = self._listener
        self._listener = None
        self._state_machine.reset()
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def update_hotkey(self, hotkey):
        self.hotkey = hotkey
        self._definition = parse_hotkey(hotkey)
        self._state_machine = HotkeyStateMachine(self._definition)

    def _handle_press(self, key):
        event = self._state_machine.handle_press(key_to_token(key))
        if event == "pressed":
            self.activated.emit()

    def _handle_release(self, key):
        event = self._state_machine.handle_release(key_to_token(key))
        if event == "released":
            self.released.emit()
