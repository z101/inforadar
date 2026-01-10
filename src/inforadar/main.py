from inforadar.tui.app import AppState


def main():
    """
    Main entry point for the Info Radar application.
    Initializes the application state and runs it, handling exceptions
    and screen clearing on exit.
    """
    app = AppState()
    try:
        app.run()
        # On clean exit, clear the screen
        app.console.clear()
    except KeyboardInterrupt:
        # On Ctrl+C, also treat as a clean exit
        app.console.clear()
        pass
    except Exception:
        # On crash, print the exception traceback
        app.console.print_exception(show_locals=True)


if __name__ == "__main__":
    main()
