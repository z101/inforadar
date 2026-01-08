import fnmatch
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from rich.markup import escape

from inforadar.tui.screens.view_screen import ViewScreen
from inforadar.models import Article

if TYPE_CHECKING:
    from inforadar.tui.app import AppState


class ArticlesViewScreen(ViewScreen):
    def __init__(self, app: "AppState"):
        super().__init__(app, "Info Radar [Articles]")

        # Filter State
        self.selected_sources = set()
        self.selected_topics = set()

        # Sort State
        # options: 'date_desc', 'rating_desc', 'rating_asc'
        self.current_sort = "date_desc"

        self.refresh_data()

        self.show_details = True

        self.apply_current_sort()

        # Build hub slug map from config
        self.hub_map = {}
        sources = self.app.engine.settings.get("sources", {})
        for source_cfg in sources.values():
            hubs = source_cfg.get("hubs", [])
            for hub in hubs:
                if isinstance(hub, dict) and "id" in hub and "slug" in hub:
                    self.hub_map[hub["id"]] = hub["slug"]

    def get_item_for_filter(self, item: Article) -> str:
        return item.title

    def apply_current_sort(self):
        if self.current_sort == "date_desc":
            self.sort_key = lambda a: a.published_date
            self.sort_reverse = True
        elif self.current_sort == "rating_desc":
            self.sort_key = lambda a: (a.extra_data.get("rating") or 0)
            self.sort_reverse = True
        elif self.current_sort == "rating_asc":
            self.sort_key = lambda a: (a.extra_data.get("rating") or 0)
            self.sort_reverse = False

        elif self.current_sort == "views_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("views"))
            self.sort_reverse = True
        elif self.current_sort == "views_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("views"))
            self.sort_reverse = False

        elif self.current_sort == "comments_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("comments"))
            self.sort_reverse = True
        elif self.current_sort == "comments_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("comments"))
            self.sort_reverse = False

        elif self.current_sort == "bookmarks_desc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("bookmarks"))
            self.sort_reverse = True
        elif self.current_sort == "bookmarks_asc":
            self.sort_key = lambda a: self._parse_metric(a.extra_data.get("bookmarks"))
            self.sort_reverse = False

        self.apply_filter_and_sort()

    def _parse_metric(self, val: Any) -> float:
        if val is None:
            return 0
        if isinstance(val, (int, float)):
            return float(val)

        s = str(val).lower().replace(",", ".").strip()
        try:
            if s.endswith("k"):
                return float(s[:-1]) * 1000
            elif s.endswith("m"):
                return float(s[:-1]) * 1000000
            else:
                return float(s)
        except ValueError:
            return 0

    def handle_input(self, key: str) -> bool:
        from inforadar.tui.keys import Key
        from inforadar.tui.screens.source_filter import SourceFilterScreen
        from inforadar.tui.screens.topic_filter import TopicFilterScreen
        from inforadar.tui.screens.fetch import FetchScreen
        from inforadar.tui.screens.settings_screen import SettingsScreen
        from inforadar.tui.screens.articles_help import ArticlesHelpScreen

        if self.command_mode or self.filter_mode:
            return super().handle_input(key)

        if key == Key.QUESTION:
            self.app.push_screen(ArticlesHelpScreen(self.app))
            return True

        if key == Key.R:
            # Cycle sort modes: date_desc -> rating_desc -> rating_asc -> rating_desc
            if self.current_sort == "date_desc":
                self.current_sort = "rating_desc"
            elif self.current_sort == "rating_desc":
                self.current_sort = "rating_asc"
            else:  # rating_asc or any other
                self.current_sort = "rating_desc"

            self.apply_current_sort()
            return True

        if key == Key.V:
            if self.current_sort == "views_desc":
                self.current_sort = "views_asc"
            else:
                self.current_sort = "views_desc"
            self.apply_current_sort()
            return True

        if key == Key.C:
            if self.current_sort == "comments_desc":
                self.current_sort = "comments_asc"
            else:
                self.current_sort = "comments_desc"
            self.apply_current_sort()
            return True

        if key == Key.B:
            if self.current_sort == "bookmarks_desc":
                self.current_sort = "bookmarks_asc"
            else:
                self.current_sort = "bookmarks_desc"
            self.apply_current_sort()
            return True

        elif key == Key.ESCAPE:
            if self.active_mode:
                self.active_mode = False
                self.input_buffer = ""
                return True
            
            if self.filter_text or self.final_filter_text:
                self.filter_text = ""
                self.final_filter_text = ""
                self.apply_filter_and_sort()
                return True

            if self.current_sort != "date_desc":
                self.current_sort = "date_desc"
                self.apply_current_sort()
                return True
            
            return super().handle_input(key)

        if key == Key.S:  # s - Settings
            self.app.push_screen(SettingsScreen(self.app))
            return True
        elif key == Key.T:  # t - Topic Filter
            self.app.push_screen(TopicFilterScreen(self.app, self))
            return True
        elif key == Key.F:  # f - Fetch
            fetch_screen = FetchScreen(
                self.app, self, self.selected_sources, self.selected_topics
            )
            self.app.push_screen(fetch_screen)
            return True
        elif (
            key == Key.SHIFT_G and False
        ):  # Disable G for now if needed, but S is Shift+s
            pass


        if key == Key.D:
            self.show_details = not self.show_details
            return True
        return super().handle_input(key)

    def refresh_data(self):
        # Fetch ALL articles
        self.items = self.app.engine.get_articles(read=None)
        self.apply_filter_and_sort()

    def apply_filter_and_sort(self):
        # 1. Filter by Text
        if not self.filter_text:
            filtered = list(self.items)
        else:
            pattern = self.filter_text.lower()
            
            def check_pattern(text, pat):
                text = text.lower()
                parts = pat.split('*')
                start_pos = 0
                for part in parts:
                    pos = text.find(part, start_pos)
                    if pos == -1:
                        return False
                    start_pos = pos + len(part)
                return True

            filtered = [
                item for item in self.items if check_pattern(self.get_item_for_filter(item), pattern)
            ]

        # 2. Filter by Source
        if self.selected_sources:
            filtered = [
                item for item in filtered if item.source in self.selected_sources
            ]

        # 3. Filter by Topic
        if self.selected_topics:
            filtered = [
                item
                for item in filtered
                if self._get_topic_slug(item) in self.selected_topics
            ]

        self.filtered_items = filtered

        # 4. Sort
        if self.sort_key:
            self.filtered_items.sort(key=self.sort_key, reverse=self.sort_reverse)

        # Update Header Title
        parts = ["[bold green dim]Info Radar[/bold green dim]"]
        if self.selected_sources:
            items = ", ".join(sorted(self.selected_sources))
            parts.append(
                f"[dim]Sources[/dim] [[bold white]{escape(items)}[/bold white]]"
            )
        if self.selected_topics:
            items = ", ".join(sorted(self.selected_topics))
            parts.append(
                f"[dim]Topics[/dim] [[bold white]{escape(items)}[/bold white]]"
            )

        if self.current_sort == "rating_desc":
            parts.append("[dim]Rating[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "rating_asc":
            parts.append("[dim]Rating[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "views_desc":
            parts.append("[dim]Views[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "views_asc":
            parts.append("[dim]Views[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "comments_desc":
            parts.append("[dim]Comments[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "comments_asc":
            parts.append("[dim]Comments[/dim] [bold white]↑[/bold white]")
        elif self.current_sort == "bookmarks_desc":
            parts.append("[dim]Bookmarks[/dim] [bold white]↓[/bold white]")
        elif self.current_sort == "bookmarks_asc":
            parts.append("[dim]Bookmarks[/dim] [bold white]↑[/bold white]")

        self.title = " | ".join(parts)

        # Reset to start
        self.start_index = 0

    def _get_topic_slug(self, item: Article) -> str:
        if item.extra_data.get("hub_id") in self.hub_map:
            return self.hub_map[item.extra_data["hub_id"]]
        elif item.extra_data and "tags" in item.extra_data and item.extra_data["tags"]:
            return item.extra_data["tags"][0]
        return ""

    def _format_compact(self, val: Any) -> str:
        """
        Formats numbers to compact string (e.g. '1.2k').
        """
        s_val = ""
        if val is None:
            s_val = "-"
        elif isinstance(val, (int, float)) or (
            isinstance(val, str) and val.replace(".", "", 1).isdigit()
        ):
            try:
                n = float(val)
                if n == 0:
                    s_val = "-"
                elif n < 1000:
                    s_val = f"{int(n)}"
                elif n < 1000000:
                    k = n / 1000
                    if k < 10:
                        s_val = f"{k:.1f}k".replace(".0k", "k")
                    else:
                        s_val = f"{int(k)}k"
                else:
                    m = n / 1000000
                    if m < 10:
                        s_val = f"{m:.1f}M".replace(".0M", "M")
                    else:
                        s_val = f"{int(m)}M"
            except ValueError:
                s_val = str(val)
        else:
            s_val = str(val)

        return s_val

    def render_row(self, item: Article, index: int) -> Tuple[List[str], str]:
        # Columns: #, Article, Source, Topic, Date, R, V, C, B

        idx_str = f"[green dim]{index}[/green dim]"
        title = item.title

        row = [idx_str, title]

        if self.show_details:
            source = f"[dim]{item.source or '?'}[/dim]"

            # Topic resolution
            topic_raw = ""
            if item.extra_data.get("hub_id") in self.hub_map:
                topic_raw = self.hub_map[item.extra_data["hub_id"]]
            elif (
                item.extra_data
                and "tags" in item.extra_data
                and item.extra_data["tags"]
            ):
                topic_raw = item.extra_data["tags"][0]

            topic = f"[dim]{topic_raw}[/dim]"

            d = item.published_date
            date_str = f"[dim]{d.day}-{d.strftime('%b')}-{d.strftime('%y')}[/dim]"

            # Details: Split into R, V, C, B

            # 1. Rating
            r_val = item.extra_data.get("rating", 0) or 0
            if isinstance(r_val, str) and not r_val.replace("-", "").isdigit():
                r_val = 0
            r_val = int(r_val)

            r_str = str(r_val)
            if r_val > 0:
                r_cell = f"[bold green]{r_str}[/bold green]"
            elif r_val < 0:
                r_cell = f"[bold red]{r_str}[/bold red]"
            else:
                r_cell = f"[dim]-[/dim]"  # Default to dash if 0

            # Helper for other metrics
            def fmt_metric(key, icon, fallback="-"):
                val = item.extra_data.get(key)
                # Special handling for comments count
                if key == "comments":
                    if val is None and item.comments_data:
                        val = len(item.comments_data)
                    elif val is None:
                        val = 0

                # Bookmarks fallback
                if key == "bookmarks" and val is None:
                    val = fallback

                if val is None:
                    val = fallback

                s_v = self._format_compact(val)
                return f"[dim]{icon} {s_v}[/dim]"

            v_cell = fmt_metric("views", "👁")
            c_cell = fmt_metric("comments", "💬", "0")
            b_cell = fmt_metric("bookmarks", "🔖", "-")

            row.extend([source, topic, date_str, r_cell, v_cell, c_cell, b_cell])

        style = ""

        return row, style

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        # Order: #, Article, Source, Topic, Date, Details

        cols = []
        cols.append({"header": "#", "justify": "right", "no_wrap": True})
        cols.append(
            {"header": "Article", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"}
        )

        if self.show_details:
            cols.append({"header": "Src", "justify": "left", "no_wrap": True})
            cols.append({"header": "Topic", "justify": "left", "no_wrap": True})
            cols.append({"header": "Date", "justify": "center", "no_wrap": True})

            # Metric columns
            cols.append({"header": "⭐", "justify": "right", "no_wrap": True})
            cols.append({"header": "👁", "justify": "left", "no_wrap": True})
            cols.append({"header": "💬", "justify": "left", "no_wrap": True})
            cols.append({"header": "🔖", "justify": "left", "no_wrap": True})

        return cols

    def on_select(self, item: Article):
        from inforadar.article_detail import ArticleDetailScreen

        self.app.push_screen(ArticleDetailScreen(self.app, item))