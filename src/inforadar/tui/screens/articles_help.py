from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from inforadar.tui.screens.base import BaseScreen
from inforadar.tui.keys import Key


class ArticlesHelpScreen(BaseScreen):
    """A screen that displays help information for the Articles View."""

    def __init__(self, app: "AppState"):
        super().__init__(app)
        self.scroll_offset = 0
        self.total_lines = 0
        self.all_help_lines = []

        self._build_help_content()

    def _build_help_content(self):
        # Build raw help content
        help_parts = []

        help_parts.append("[dim green bold]Навигация и Основные Действия[/dim green bold]\n")
        help_parts.append("""
• [green]j[/]/[green]k[/] или [green]↓[/]/[green]↑[/]: Навигация по списку
• [green]d[/]: Показать/скрыть детальную информацию (источник, топик, метрики)
• [green]q[/]: Выход из приложения (только на главном экране)
• [green]ESCAPE[/]: Закрыть текущий экран или выйти из режима выбора
• [green]ENTER[/]: Открыть выбранную статью для детального просмотра
• [green]?[/]: Показать этот экран справки

""") # Added empty line here

        help_parts.append("[dim green bold]Сортировка[/dim green bold]\n")
        help_parts.append("""
• [green]r[/]: Сортировка по дате/рейтингу
• [green]v[/]: Сортировка по просмотрам (desc/asc)
• [green]c[/]: Сортировка по комментариям (desc/asc)
• [green]b[/]: Сортировка по закладкам (desc/asc)

""") # Added empty line here

        help_parts.append("[dim green bold]Действия и Фильтры[/dim green bold]\n")
        help_parts.append("""
• [green]f[/]: Открыть экран для загрузки новых статей (Fetch)
• [green]s[/]: Открыть настройки
• [green]t[/]: Открыть фильтр по топикам

""") # Added empty line here

        help_parts.append("[dim green bold]Команды (ввод через :)[/dim green bold]\n")
        help_parts.append("""
• [green]:fetch[/]: Загрузить новые статьи
• [green]:help[/] или [green]:?[/]: Показать этот экран справки
• [red]:q[/]: Выйти из приложения
""")

        # Combine all parts into a single Text object
        raw_text_content = "\n".join(part.strip() for part in help_parts).strip()
        self.all_help_lines = Text.from_markup(raw_text_content).split()
        self.total_lines = len(self.all_help_lines)

    def render(self):
        console = self.app.console
        width, height = console.size
        self.app.console.clear()

        # Allow for panel borders and title
        # A simple estimate, exact value would depend on Rich's panel rendering
        # Let's say 2 lines for top/bottom border, 1 for title
        # 1 line each for top and bottom padding
        # Total 5 lines reserved.
        reserved_lines = 5
        visible_height = height - reserved_lines

        if visible_height < 1:
            visible_height = 1

        # Adjust scroll offset to ensure it's within bounds
        max_scroll_offset = max(0, self.total_lines - visible_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))

        # Get visible lines
        display_lines = self.all_help_lines[
            self.scroll_offset : self.scroll_offset + visible_height
        ]

        # Create a new Text object from the visible lines
        content_to_render = Text("\n").join(display_lines)

        main_panel = Panel(
            content_to_render,
            title="[bold blue]Info Radar[/bold blue] | Справка по списку статей",
            border_style="green",
            expand=True,
        )

        console.print(main_panel)

    def handle_input(self, key: str) -> bool:
        # Check for scroll keys first
        if key == Key.K or key == Key.UP:
            self.scroll_offset = max(0, self.scroll_offset - 1)
            return True
        elif key == Key.J or key == Key.DOWN:
            # Need to know visible_height to calculate max scroll offset
            _, height = self.app.console.size
            reserved_lines = 5 # Same as in render
            visible_height = height - reserved_lines
            max_scroll_offset = max(0, self.total_lines - visible_height)
            self.scroll_offset = min(max_scroll_offset, self.scroll_offset + 1)
            return True
        # Close screen on 'q' or 'escape' or '?'
        elif key in (Key.Q, Key.ESCAPE, Key.QUESTION):
            self.app.pop_screen()
            return True
        return False
