"""
utils/data_loader.py

Small helper module that centralizes access to the mock data files so that
tools.py never has to know about file paths or JSON structure directly.
"""

import json
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_LISTINGS_PATH = os.path.join(_DATA_DIR, "listings.json")
_WARDROBE_PATH = os.path.join(_DATA_DIR, "wardrobe_schema.json")


def load_listings():
    """
    Loads the mock listings dataset.

    Returns:
        list[dict]: every listing in data/listings.json, each with keys
        id, title, description, category, style_tags, size, condition,
        price, colors, brand, platform.
    """
    with open(_LISTINGS_PATH, "r") as f:
        return json.load(f)


def get_example_wardrobe():
    """
    Returns a populated example wardrobe, useful for testing the
    "happy path" of suggest_outfit.

    Returns:
        dict: {"items": [ {id, category, description, color, style_tags}, ... ]}
    """
    with open(_WARDROBE_PATH, "r") as f:
        data = json.load(f)
    return data["example_wardrobe"]


def get_empty_wardrobe():
    """
    Returns an empty wardrobe, used to test suggest_outfit's fallback
    behavior when the user hasn't entered any items yet.

    Returns:
        dict: {"items": []}
    """
    with open(_WARDROBE_PATH, "r") as f:
        data = json.load(f)
    return data["empty_wardrobe"]
