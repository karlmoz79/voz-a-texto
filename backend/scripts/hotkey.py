import sys

from pynput import keyboard

ALT_PRESSED = False
I_PRESSED = False
SESSION_ACTIVE = False

def on_press(key):
    global ALT_PRESSED, I_PRESSED, SESSION_ACTIVE
    try:
        # pynput can read alt as Key.alt, Key.alt_l, Key.alt_r, or Key.alt_gr
        if key in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
            ALT_PRESSED = True
        elif hasattr(key, 'char') and key.char and key.char.lower() == 'i':
            I_PRESSED = True
            
        if ALT_PRESSED and I_PRESSED and not SESSION_ACTIVE:
            SESSION_ACTIVE = True
            print("HOTKEY_START", flush=True)
    except Exception:
        pass

def on_release(key):
    global ALT_PRESSED, I_PRESSED, SESSION_ACTIVE
    try:
        was_alt = key in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]
        was_i = hasattr(key, 'char') and key.char and key.char.lower() == 'i'
        
        if was_alt:
            ALT_PRESSED = False
        if was_i:
            I_PRESSED = False
            
        # Stop session if either key is released
        if (was_alt or was_i) and SESSION_ACTIVE:
            SESSION_ACTIVE = False
            print("HOTKEY_STOP", flush=True)
    except Exception:
        pass

if __name__ == "__main__":
    print("READY", flush=True)
    # Block and wait for global keys
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
