class CommandLine:
    def __init__(self):
        self.text = ""
        self.cursor_pos = 0

    def insert(self, char: str):
        self.text = self.text[: self.cursor_pos] + char + self.text[self.cursor_pos :]
        self.cursor_pos += 1

    def delete_back(self):
        if self.cursor_pos > 0:
            self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
            self.cursor_pos -= 1

    def delete_forward(self):
        if self.cursor_pos < len(self.text):
            self.text = self.text[: self.cursor_pos] + self.text[self.cursor_pos + 1 :]

    def move_left(self):
        if self.cursor_pos > 0:
            self.cursor_pos -= 1

    def move_right(self):
        if self.cursor_pos < len(self.text):
            self.cursor_pos += 1

    def move_start(self):
        self.cursor_pos = 0

    def move_end(self):
        self.cursor_pos = len(self.text)

    def _is_word_char(self, char):
        return char.isalnum() or char == "_"

    def move_word_left(self):
        # Skip spaces
        while self.cursor_pos > 0 and not self._is_word_char(
            self.text[self.cursor_pos - 1]
        ):
            self.cursor_pos -= 1
        # Skip word
        while self.cursor_pos > 0 and self._is_word_char(
            self.text[self.cursor_pos - 1]
        ):
            self.cursor_pos -= 1

    def move_word_right(self):
        n = len(self.text)
        # Skip word characters
        while self.cursor_pos < n and self._is_word_char(self.text[self.cursor_pos]):
            self.cursor_pos += 1
        # Skip spaces
        while self.cursor_pos < n and not self._is_word_char(
            self.text[self.cursor_pos]
        ):
            self.cursor_pos += 1

    def delete_word_back(self):
        start = self.cursor_pos
        self.move_word_left()
        new_pos = self.cursor_pos
        self.text = self.text[:new_pos] + self.text[start:]
        self.cursor_pos = new_pos

    def delete_to_start(self):
        self.text = self.text[self.cursor_pos :]
        self.cursor_pos = 0

    def clear(self):
        self.text = ""
        self.cursor_pos = 0
