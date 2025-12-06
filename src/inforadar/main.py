
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
import webbrowser
import os
from typing import List
from .core import CoreEngine
from .models import Article

app = typer.Typer()
console = Console()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Inforadar - Information Radar.
    Run without commands to start the interactive TUI.
    """
    if ctx.invoked_subcommand is None:
        from .tui import AppState
        AppState().run()

@app.command()
def sync():
    """Syncs new articles from configured sources."""
    engine = CoreEngine()
    engine.run_sync()

@app.command()
def refresh(
    days: int = typer.Option(7, "--days", "-d", help="Refresh articles from last N days"),
    unread_only: bool = typer.Option(True, "--unread-only", "-u", help="Refresh only unread articles")
):
    """Refreshes metadata (rating, comments, views) for existing articles."""
    engine = CoreEngine()
    engine.run_refresh(days=days, unread_only=unread_only)

@app.command(name="list")
def list_articles(
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive triage mode."),
    read: bool = typer.Option(False, "--read", "-r", help="Show read articles."),
    interesting: bool = typer.Option(False, "--interesting", "-n", help="Show interesting articles."),
):
    """Lists articles, optionally in interactive triage mode."""
    engine = CoreEngine()
    articles = engine.get_articles(read=read, interesting=interesting)

    if not articles:
        console.print("[bold yellow]No articles found matching criteria.[/bold yellow]")
        return

    if interactive:
        _interactive_triage(articles, engine)
    else:
        _display_articles_table(articles)

def _display_articles_table(articles: List[Article]):
    """Displays articles in a table format."""
    table = Table(title="[bold blue]Inforadar Articles[/bold blue]")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Hub", style="green")
    table.add_column("Rating", justify="right")
    table.add_column("Views", justify="right")
    table.add_column("Date", style="dim")

    for article in articles:
        rating_text = Text(str(article.extra_data.get('rating', 'N/A')))
        if isinstance(article.extra_data.get('rating'), int):
            if article.extra_data['rating'] > 50: rating_text.stylize("bold green")
            elif article.extra_data['rating'] > 10: rating_text.stylize("green")
            elif article.extra_data['rating'] < 0: rating_text.stylize("bold red")

        table.add_row(
            str(article.id),
            article.title,
            article.extra_data.get('tags', ['N/A'])[0] if article.extra_data.get('tags') else 'N/A',
            rating_text,
            str(article.extra_data.get('views', 'N/A')),
            article.published_date.strftime("%Y-%m-%d")
        )
    console.print(table)

def _interactive_triage(articles: List[Article], engine: CoreEngine):
    """Starts the interactive triage mode."""
    for i, article in enumerate(articles):
        console.clear()
        console.print(f"([bold cyan]{i + 1}[/bold cyan] из [bold cyan]{len(articles)}[/bold cyan])")
        
        rating_text = Text(str(article.extra_data.get('rating', 'N/A')))
        if isinstance(article.extra_data.get('rating'), int):
            if article.extra_data['rating'] > 50: rating_text.stylize("bold green")
            elif article.extra_data['rating'] > 10: rating_text.stylize("green")
            elif article.extra_data['rating'] < 0: rating_text.stylize("bold red")

        panel_content = Text()
        panel_content.append(f"Название: ", style="bold")
        panel_content.append(f"{article.title}\n")
        panel_content.append(f"Хаб: ", style="bold")
        panel_content.append(f"{article.extra_data.get('tags', ['N/A'])[0] if article.extra_data.get('tags') else 'N/A'}\n")
        panel_content.append(f"Рейтинг: ", style="bold")
        panel_content.append(rating_text)
        panel_content.append(f"   Просмотры: ", style="bold")
        panel_content.append(str(article.extra_data.get('views', 'N/A')))
        panel_content.append(f"\nВремя чтения: ", style="bold")
        panel_content.append(str(article.extra_data.get('reading_time', 'N/A')))
        panel_content.append(f"   Комментарии: ", style="bold")
        panel_content.append(str(article.extra_data.get('comments', 'N/A')))
        panel_content.append(f"\nТеги: ", style="bold")
        panel_content.append(" ".join([f"[blue]#{tag}[/blue]" for tag in article.extra_data.get('tags', [])]))
        panel_content.append(f"\n\nКраткое описание:\n", style="bold")
        panel_content.append(article.extra_data.get('description', 'Описание отсутствует.'))

        console.print(Panel(panel_content, title="[bold yellow]Статья[/bold yellow]", border_style="blue"))
        console.print("[bold]Действия: (o)pen, (s)kip, (i)nteresting, (d)iscard, (q)uit[/bold]")
        
        choice = console.input("[bold green]Ваш выбор: [/bold green]").lower()

        if choice == 'o':
            webbrowser.open(article.link)
            engine.update_article_status(article.id, read=True)
        elif choice == 'i':
            engine.update_article_status(article.id, interesting=True)
        elif choice == 'd':
            engine.update_article_status(article.id, read=True, interesting=False)
        elif choice == 'q':
            break
        # 's' (skip) does nothing, article remains unread/uninteresting

