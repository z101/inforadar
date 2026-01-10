from typing import Any, List, Dict, Optional
from datetime import datetime
import platform
import subprocess
import webbrowser

from inforadar.tui.screens.custom_list_editor import CustomListEditorScreen
from inforadar.tui.keys import Key
from inforadar.tui.screens.hub_fetch_screen import HubFetchScreen
from inforadar.tui.screens.simple_setting_editor import SimpleSettingEditor
from inforadar.tui.screens.habr_hubs_editor_help import HabrHubsEditorHelpScreen

class HabrHubsEditorScreen(CustomListEditorScreen):
    """
    A specialized list editor for Habr Hubs that includes fetching and custom sorting.
    """

    def __init__(self, app, setting_key, current_value, description, on_save):
        super().__init__(app, setting_key, current_value, description, on_save)
        self.help_screen_class = HabrHubsEditorHelpScreen
        # Sort State
        self.current_sort = "rating_desc"
        self.apply_current_sort()

    def get_item_for_filter(self, item: Dict[str, Any]) -> str:
        """Concatenate ID and Name for filtering."""
        return f"{item.get('id', '')} {item.get('name', '')}"

    def get_columns(self, width: int) -> List[Dict[str, Any]]:
        # --- Dynamic Column Width Calculation ---
        headers = {
            "id": "ID", "last_article_date": "Last", "articles": "📝",
            "rating": "⭐", "subscribers": "👥"
        }
        max_widths = {key: len(value) for key, value in headers.items()}
        max_widths["index"] = len("#")

        if hasattr(self, 'filtered_items'):
            for item in self.filtered_items:
                # ID
                max_widths["id"] = max(max_widths["id"], len(str(item.get("id", ""))))
                # Last Date (formatted as dd-mm-yy)
                max_widths["last_article_date"] = max(max_widths["last_article_date"], 8)
                # Articles
                max_widths["articles"] = max(max_widths["articles"], len(str(item.get("articles", ""))))
                # Rating
                rating_val = item.get("rating")
                max_widths["rating"] = max(max_widths["rating"], len(f"{rating_val:.2f}" if rating_val is not None else ""))
                # Subscribers
                subs = item.get("subscribers")
                if subs is None: subs_len = 0
                elif subs >= 1000: subs_len = len(f"{subs/1000:.1f}k".replace(".0k", "k"))
                else: subs_len = len(str(subs))
                max_widths["subscribers"] = max(max_widths["subscribers"], subs_len)

        # Add padding
        for key in max_widths:
            max_widths[key] += 1
        # --- End Calculation ---

        columns = [
            {"name": "index", "header": "#", "justify": "right", "width": max_widths["index"]},
            {"name": "id", "header": headers["id"], "width": max_widths["id"]},
            {"name": "name", "header": "Name", "ratio": 1, "no_wrap": True, "overflow": "ellipsis"},
            {"name": "last_article_date", "header": headers["last_article_date"], "width": max_widths["last_article_date"]},
            {"name": "articles", "header": headers["articles"], "justify": "right", "width": max_widths["articles"]},
            {"name": "rating", "header": headers["rating"], "justify": "right", "width": max_widths["rating"]},
            {"name": "subscribers", "header": headers["subscribers"], "justify": "right", "width": max_widths["subscribers"]},
        ]

        sort_field, direction = self.current_sort.rsplit("_", 1)
        arrow = "↓" if direction == "desc" else "↑"

        for col in columns:
            if col.get("name") == sort_field:
                col["header"] = f"{col['header']} {arrow}"
                break
        
        return [{k: v for k, v in col.items() if k != 'name'} for col in columns]

    def render_row(self, item: Dict[str, Any], index: int) -> tuple[list[str], str]:
        row_values = [f"[dim green]{index}[/dim green]"]
        row_values.append(f"[dim]{item.get('id', '')}[/dim]")
        row_values.append(item.get("name", ""))
        
        last_date_str = item.get("last_article_date")
        if last_date_str:
            try:
                dt = datetime.fromisoformat(last_date_str.replace('Z', '+00:00'))
                row_values.append(f"[dim]{dt.strftime('%d-%m-%y')}[/dim]")
            except ValueError:
                row_values.append("")
        else:
            row_values.append("")

        articles_count = item.get("articles")
        row_values.append(f"[dim]{articles_count}[/dim]" if articles_count is not None else "")
        
        enabled = item.get("enabled", True)
        rating = item.get("rating")
        subs = item.get("subscribers")

        row_values.append(f"[dim]{rating:.2f}[/dim]" if rating is not None else "")
        
        if subs is None:
            subs_str = ""
        elif subs >= 1000:
            subs_str = f"{subs/1000:.1f}k".replace(".0k", "k")
        else:
            subs_str = str(subs)
        row_values.append(f"[dim]{subs_str}[/dim]")

        style = ""
        if not enabled:
            style = "dim strikethrough"
            
        return row_values, style

    def handle_input(self, key: str) -> bool:
        if self.command_mode or self.filter_mode:
            return super().handle_input(key)

        if key in ('a', 'd'):
            return True

        if key == Key.QUESTION:
            self.app.push_screen(HabrHubsEditorHelpScreen(self.app))
            return True
        elif key == Key.F:
            def on_fetch_complete():
                updated_list = self.app.engine.settings.get(self.setting_key, [])
                safe_list = self._ensure_list_of_dicts(updated_list)
                self.items_list = [item.copy() for item in (safe_list or [])]
                self.apply_current_sort()
            fetch_screen = HubFetchScreen(self.app, on_complete=on_fetch_complete)
            self.app.push_screen(fetch_screen)
            return True
        elif key == 'e':
            if self.active_mode and 0 <= self.active_cursor < len(self.filtered_items):
                item = self.filtered_items[self.active_cursor]
                item['enabled'] = not item.get('enabled', True)
                self.refresh_data()
                self._save()
            return True
        elif key == 'o':
            if self.active_mode and 0 <= self.active_cursor < len(self.filtered_items):
                item = self.filtered_items[self.active_cursor]
                hub_id = item.get('id')
                if hub_id:
                    url = f"https://habr.com/ru/hubs/{hub_id}/"
                    try:
                        release_lower = platform.release().lower()
                        if 'microsoft-standard' in release_lower or 'wsl' in release_lower:
                            subprocess.run(['explorer.exe', url])
                        else:
                            webbrowser.open(url)
                    except Exception:
                        pass
            return True
        elif key == 'r':
            self.current_sort = "rating_asc" if self.current_sort == "rating_desc" else "rating_desc"
            self.apply_current_sort()
            return True
        elif key == 's':
             self.current_sort = "subscribers_asc" if self.current_sort == "subscribers_desc" else "subscribers_desc"
             self.apply_current_sort()
             return True
        elif key == 'n':
            self.current_sort = "name_asc" if self.current_sort == "name_desc" else "name_desc"
            self.apply_current_sort()
            return True
        elif key == 'l':
            self.current_sort = "last_article_date_asc" if self.current_sort == "last_article_date_desc" else "last_article_date_desc"
            self.apply_current_sort()
            return True
        elif key == 'c':
            self.current_sort = "articles_asc" if self.current_sort == "articles_desc" else "articles_desc"
            self.apply_current_sort()
            return True

        return super().handle_input(key)

    def apply_current_sort(self):
        sort_key_map = {
            "fetch_date_desc": (lambda i: i.get("fetch_date") or "", True),
            "fetch_date_asc": (lambda i: i.get("fetch_date") or "", False),
            "rating_desc": (lambda i: i.get("rating") or 0, True),
            "rating_asc": (lambda i: i.get("rating") or 0, False),
            "subscribers_desc": (lambda i: i.get("subscribers") or 0, True),
            "subscribers_asc": (lambda i: i.get("subscribers") or 0, False),
            "name_asc": (lambda i: i.get("name", "").lower(), False),
            "name_desc": (lambda i: i.get("name", "").lower(), True),
            "last_article_date_asc": (lambda i: i.get("last_article_date") or "", False),
            "last_article_date_desc": (lambda i: i.get("last_article_date") or "", True),
            "articles_asc": (lambda i: i.get("articles") or 0, False),
            "articles_desc": (lambda i: i.get("articles") or 0, True),
        }

        if self.current_sort in sort_key_map:
            key_func, reverse = sort_key_map[self.current_sort]
            self.items_list.sort(key=key_func, reverse=reverse)

        self.apply_filter_and_sort()
    
    def apply_filter_and_sort(self):
        super().apply_filter_and_sort()
        
        last_fetch_str = ""
        if self.items_list:
            fetch_dates = [item.get("fetch_date") for item in self.items_list if item.get("fetch_date")]
            if fetch_dates:
                latest_date_str = max(fetch_dates)
                try:
                    dt = datetime.fromisoformat(latest_date_str)
                    last_fetch_str = f" [dim]| Last Fetch[/dim] [yellow]{dt.day}-{dt.strftime('%b')}-{dt.strftime('%y')}[/yellow]"
                except (ValueError, TypeError):
                    pass
        
        self.title = f"[green bold dim]Info Radar Settings Edit[/green bold dim] | Habr Hubs{last_fetch_str}"
        

    def _get_shortcuts_text(self) -> str:
        return " | [[dim green bold]?[/] Help | [r] Rating | [s] Subs | [n] Name | [l] Last | [c] Count"

    def on_select(self, item: Dict[str, str]):
        def on_name_save(new_name: str):
            item['name'] = new_name
            self.refresh_data()
            self._save()

        editor = SimpleSettingEditor(
            app=self.app,
            setting_key=f"Hub Name for '{item.get('id')}'",
            current_value=item.get("name", ""),
            setting_type='string',
            description="Edit the display name for this hub.",
            on_save=on_name_save
        )
        self.app.push_screen(editor)

