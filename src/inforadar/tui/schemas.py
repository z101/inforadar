"""
This module defines the schemas for 'custom' type settings.

A schema defines the structure of the items within a list-based custom setting.
It specifies the fields for each item, which allows for generic UI generation
for editing these items.
"""

# A dictionary mapping a setting key (e.g., 'sources.habr.hubs') to its schema definition.
#
# Schema Definition:
# - description (str): A help text explaining what the setting is for.
# - item_name (str): The singular name for an item in the list (e.g., "Hub").
# - fields (List[Dict]): A list of dictionaries, where each dictionary defines a field.
#
# Field Definition:
# - name (str): The key of the field in the item dictionary (e.g., 'slug').
# - label (str): The human-readable label for the field (e.g., "Slug").
# - required (bool, optional): Whether the field is mandatory. Defaults to True.
CUSTOM_TYPE_SCHEMAS = {
    "sources.habr.hubs": {
        "description": "A list of Habr hubs to track. The 'ID' is used for fetching, and 'Name' is the display name.",
        "item_name": "Habr Hub",
        "fields": [
            {"name": "id", "label": "ID"},
            {"name": "name", "label": "Name"},
            {"name": "enabled", "label": "Enabled", "type": "bool", "default": True},
            {"name": "new", "label": "New", "type": "bool", "default": False, "readonly": True},
            {"name": "fetch_date", "label": "F Date", "readonly": True, "required": False},
            {"name": "rating", "label": "⭐", "readonly": True, "required": False, "type": "float"},
            {"name": "subscribers", "label": "👥", "readonly": True, "required": False, "type": "int"},
        ]
    }
}
