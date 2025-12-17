import sys
import os
import select
import termios
import tty
from typing import Optional

from inforadar.tui.keys import Key, LAYOUT_MAP


# Resize handling
class ResizeScreen(Exception):
    pass


resize_needed = False


def handle_winch(signum, frame):
    global resize_needed
    resize_needed = True


def get_key() -> Optional[str]:
    """Reads a key press and decodes escape sequences. Returns None on timeout."""
    global resize_needed

    fd = sys.stdin.fileno()

    if resize_needed:
        resize_needed = False
        raise ResizeScreen()

    try:
        # Wait for input with timeout to allow periodic refresh
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            return None  # Timeout - no input
    except (OSError, InterruptedError):
        return None

    # Read first byte
    try:
        b1 = os.read(fd, 1)
    except OSError:
        return Key.UNKNOWN

    ch = ""
    # Decode UTF-8
    if b1:
        byte1 = ord(b1)
        # Determine sequence length
        seq_len = 1
        if (byte1 & 0x80) == 0:
            seq_len = 1
        elif (byte1 & 0xE0) == 0xC0:
            seq_len = 2
        elif (byte1 & 0xF0) == 0xE0:
            seq_len = 3
        elif (byte1 & 0xF8) == 0xF0:
            seq_len = 4

        # Read remaining bytes if any
        raw_bytes = b1
        if seq_len > 1:
            try:
                raw_bytes += os.read(fd, seq_len - 1)
            except OSError:
                pass

        try:
            ch = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            ch = Key.UNKNOWN

    # Handle CTRL+D (EOT) and CTRL+U (NAK)
    if ch == "\x04":
        return Key.CTRL_D
    if ch == "\x15":
        return Key.CTRL_U
    if ch == "\x02":
        return Key.CTRL_B
    if ch == "\x05":
        return Key.CTRL_E
    if ch == "\x06":
        return Key.CTRL_F
    if ch == "\x08":
        return Key.CTRL_H
    if ch == "\x17":
        return Key.CTRL_W
    if ch == "\x01":
        return Key.CTRL_A

    # Handle Alt+Key (Esc followed by char)
    if ch == "\x1b":
        # Non-blocking check for a following character.
        r, _, _ = select.select([sys.stdin.fileno()], [], [], 0)
        if not r:
            return Key.ESCAPE

        try:
            ch2 = os.read(fd, 1).decode()
            if ch2 == "b":
                return Key.ALT_B
            if ch2 == "f":
                return Key.ALT_F

            # ANSI sequences check again (merged from above logic to be safe)
            if ch2 == "[":
                try:
                    ch3 = os.read(fd, 1).decode()
                    if ch3 == "A":
                        return Key.UP
                    if ch3 == "B":
                        return Key.DOWN
                    if ch3 == "C":
                        return Key.RIGHT
                    if ch3 == "D":
                        return Key.LEFT
                    if ch3 == "3":  # Delete is usually [3~
                        ch4 = os.read(fd, 1).decode()
                        if ch4 == "~":
                            return Key.DELETE
                except OSError:
                    pass
            elif ch2 == "O":
                try:
                    ch3 = os.read(fd, 1).decode()
                    if ch3 == "A":
                        return Key.UP
                    if ch3 == "B":
                        return Key.DOWN
                    if ch3 == "C":
                        return Key.RIGHT
                    if ch3 == "D":
                        return Key.LEFT
                except OSError:
                    pass

        except (OSError, UnicodeDecodeError):
            pass
        return Key.ESCAPE

    # Convert from other keyboard layouts to English
    if ch in LAYOUT_MAP:
        ch = LAYOUT_MAP[ch]

    if ch == "\r":
        return Key.ENTER
    if ch == "\n":
        return Key.ENTER
    if ch == "\x7f":
        return Key.BACKSPACE

    if ch == "q" or ch == "Q":
        return Key.Q
    if ch == "s" or ch == "S":
        return Key.S
    if ch == "r" or ch == "R":
        return Key.R
    if ch == "f" or ch == "F":
        return Key.F
    if ch == "h" or ch == "H":
        return Key.H
    if ch == "j" or ch == "J":
        return Key.J
    if ch == "k" or ch == "K":
        return Key.K
    if ch == "l" or ch == "L":
        return Key.L
    if ch == "v" or ch == "V":
        return Key.V
    if ch == "c" or ch == "C":
        return Key.C
    if ch == "b" or ch == "B":
        return Key.B
    if ch == "d" or ch == "D":
        return Key.D
    if ch == "g":
        return Key.G
    if ch == "G":
        return Key.SHIFT_G
    if ch == "?":
        return Key.QUESTION
    if ch == ":":
        return Key.COLON
    if ch == "/":
        return Key.SLASH
    if ch == " ":
        return Key.SPACE

    # Return digits as is
    if ch.isdigit():
        return ch

    return ch
