import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from inforadar.tui import CommandLine

class TestCommandLine(unittest.TestCase):
    def test_insert(self):
        cl = CommandLine()
        cl.insert("a")
        self.assertEqual(cl.text, "a")
        self.assertEqual(cl.cursor_pos, 1)
        cl.insert("b")
        self.assertEqual(cl.text, "ab")
        self.assertEqual(cl.cursor_pos, 2)

    def test_move(self):
        cl = CommandLine()
        cl.text = "abc"
        cl.cursor_pos = 3
        cl.move_left()
        self.assertEqual(cl.cursor_pos, 2)
        cl.insert("d")
        self.assertEqual(cl.text, "abdc")
        self.assertEqual(cl.cursor_pos, 3)

    def test_delete_back(self):
        cl = CommandLine()
        cl.text = "abc"
        cl.cursor_pos = 3
        cl.delete_back()
        self.assertEqual(cl.text, "ab")
        self.assertEqual(cl.cursor_pos, 2)

    def test_delete_forward(self):
        cl = CommandLine()
        cl.text = "abc"
        cl.cursor_pos = 1
        cl.delete_forward()
        self.assertEqual(cl.text, "ac")
        self.assertEqual(cl.cursor_pos, 1)

    def test_words(self):
        cl = CommandLine()
        cl.text = "hello world"
        cl.cursor_pos = 11
        cl.move_word_left()
        self.assertEqual(cl.cursor_pos, 6) # 'w'
        cl.move_word_left()
        self.assertEqual(cl.cursor_pos, 0) # 'h'
        cl.move_word_right()
        self.assertEqual(cl.cursor_pos, 6) # start of 'world'
        cl.move_end()
        cl.delete_word_back()
        self.assertEqual(cl.text, "hello ")

    def test_move_start_end(self):
        cl = CommandLine()
        cl.text = "hello"
        cl.cursor_pos = 3
        cl.move_start()
        self.assertEqual(cl.cursor_pos, 0)
        cl.move_end()
        self.assertEqual(cl.cursor_pos, 5)

if __name__ == '__main__':
    unittest.main()
