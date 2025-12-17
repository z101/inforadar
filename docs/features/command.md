## Command line feature

Необходимо добавить функционал командной строки в приложение. Командная строка должна располагаться в footer'е рядом с отобржением pager'а и total count, но pager/total должны быть выровнены в право. Размещение header'а и таблицы с контентом не должно измениться.

Командный режим должен быть vim-like. Вызываться через ':', внизу слева в footer'е должна отображаться строка ввода команды - ":" и курсор. Экран не должен моргать. При вводе команды (при активном режиме командной строки) никакие прочие шорткаты не должны работать.

В режиме командной строки должны работать следующие шорткаты:
 - Ctrl-B: Move cursor to the beginning of the command line.
 - Ctrl-E: Move cursor to the end of the command line.
 - Ctrl-F or <Right>: Move cursor one character to the right.
 - Ctrl-B or <Left>: Move cursor one character to the left.
 - <M-b> or <S-Left>: Move cursor one word backward.
 - <M-f> or <S-Right>: Move cursor one word forward.
 - Ctrl-H or <BS>: Delete the character before the cursor.
 - <Del>: Delete the character under the cursor.
 - Ctrl-W: Delete the word before the cursor.
 - Ctrl-U: Delete all characters from the cursor to the beginning of the line. 
 - Esc: Exit command mode.
 - Enter: Execute command.

Необходимо добавить тестовую команду `:test` которая будет выводить во всплывающее окно текст `test`. Изучи документацию https://rich.readthedocs.io/ и проанализируй, с помощью каких features это можно сделать?