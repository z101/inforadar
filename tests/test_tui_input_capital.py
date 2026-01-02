import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from inforadar.tui.input import get_key
from inforadar.tui.keys import Key

class TestInput(unittest.TestCase):
    @patch('os.read')
    @patch('sys.stdin.fileno')
    @patch('select.select')
    def test_capital_s(self, mock_select, mock_fileno, mock_read):
        # Setup mock to return 'S' when read is called
        mock_fileno.return_value = 0
        mock_select.return_value = ([0], [], [])
        
        # Determine how os.read is called. 
        # get_key calls os.read(fd, 1) to read first byte.
        # 'S' is length 1.
        mock_read.side_effect = [b'S'] 
        
        key = get_key()
        print(f"Input 'S' resulted in key: {repr(key)}")
        
        # Currently, we expect this to fail if we assert it equals 'S', 
        # because input.py converts it to Key.S ('s').
        # So this test documents CURRENT BROKEN behavior if we assert key == 's'
        # Or documents DESIRED behavior if we assert key == 'S' (which will fail now)
        self.assertEqual(key, 'S', f"Expected 'S', but got {repr(key)}")

    @patch('os.read')
    @patch('sys.stdin.fileno')
    @patch('select.select')
    def test_capital_a(self, mock_select, mock_fileno, mock_read):
        # 'A' is NOT in the normalized list, so it should return 'A'
        mock_fileno.return_value = 0
        mock_select.return_value = ([0], [], [])
        mock_read.side_effect = [b'A']
        
        key = get_key()
        print(f"Input 'A' resulted in key: {repr(key)}")
        self.assertEqual(key, 'A')

if __name__ == '__main__':
    unittest.main()
