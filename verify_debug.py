import sys
from inforadar.config import SettingsManager, get_db_url
from inforadar.storage import Storage

def verify_settings():
    storage = Storage(get_db_url())
    settings = SettingsManager(storage.Session)
    settings.load_settings()

    print("Checking default settings...")
    debug_enabled = settings.get("debug.enabled")
    debug_limit = settings.get("debug.hub_limit")

    print(f"debug.enabled: {debug_enabled} (Type: {type(debug_enabled)})")
    print(f"debug.hub_limit: {debug_limit} (Type: {type(debug_limit)})")

    if debug_enabled is False and debug_limit == 10:
        print("SUCCESS: Defaults are correct.")
    else:
        print("FAILURE: Defaults are incorrect.")
        sys.exit(1)

    print("\nModifying settings...")
    settings.set("debug.enabled", "true", "boolean")
    settings.set("debug.hub_limit", "5", "integer")
    
    # Reload
    settings.load_settings()
    new_enabled = settings.get("debug.enabled")
    new_limit = settings.get("debug.hub_limit")
    
    print(f"New debug.enabled: {new_enabled}")
    print(f"New debug.hub_limit: {new_limit}")

    if new_enabled is True and new_limit == 5:
        print("SUCCESS: Settings updated correctly.")
    else:
        print("FAILURE: Settings update failed.")
        sys.exit(1)

    # Clean up (restore defaults)
    settings.set("debug.enabled", "false", "boolean")
    settings.set("debug.hub_limit", "10", "integer")
    print("\nRestored defaults.")

if __name__ == "__main__":
    verify_settings()
