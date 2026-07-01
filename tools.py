"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_GROQ_MODEL = "llama-3.3-70b-versatile"

# Filtered out of `description` before keyword-scoring in search_listings, so
# a free-text query like "vintage graphic tee under $30" (or one that's had
# filler words left in after parsing) doesn't accidentally score every
# listing on common words like "a" or "for".
_SEARCH_STOPWORDS = {
    "a", "an", "the", "for", "of", "in", "on", "at", "is", "are", "i",
    "i'm", "im", "looking", "want", "need", "mostly", "wear", "and", "my",
    "under", "below", "less", "than", "out", "there", "how", "would",
    "style", "it", "what's", "whats", "some", "something", "to", "with",
    "find", "me", "you", "your", "this", "that",
}
# Public alias — agent.py reuses this same list to clean up the description
# it extracts from a free-text query, so "search-time" and "parse-time"
# filler-word handling stay in sync.
SEARCH_STOPWORDS = _SEARCH_STOPWORDS


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    if not description or not description.strip():
        return []

    listings = load_listings()

    keywords = [
        kw.strip(".,!?").lower()
        for kw in description.lower().split()
        if kw.strip(".,!?") and kw.strip(".,!?") not in _SEARCH_STOPWORDS
    ]

    scored = []
    for item in listings:
        if max_price is not None and item.get("price", float("inf")) > max_price:
            continue

        if size is not None:
            item_size = str(item.get("size", "")).lower()
            query_size = size.lower()
            # Case-insensitive, allows "M" to match a listing sized "S/M"
            if query_size not in item_size and item_size not in query_size:
                continue

        haystack = " ".join(
            [
                item.get("title", ""),
                item.get("description", ""),
                item.get("category", ""),
                item.get("brand", ""),
                " ".join(item.get("style_tags", [])),
            ]
        ).lower()

        score = sum(1 for kw in keywords if kw in haystack)
        if score == 0:
            continue

        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item:
        return "Error: no item was provided to build a styling suggestion around."

    item_desc = new_item.get("description") or new_item.get("title", "this item")
    item_line = (
        f"{new_item.get('title', 'Item')}: {item_desc} "
        f"({', '.join(new_item.get('style_tags', []))})"
    )

    wardrobe_items = (wardrobe or {}).get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A user just found this secondhand item: {item_line}. "
            "They haven't told me what else is in their wardrobe. Give 2-3 "
            "sentences of general styling advice for this piece — what kinds "
            "of pieces (by category and vibe, not brand) would pair well with "
            "it, and one concrete styling tip (tucking, layering, rolling "
            "sleeves, etc.)."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {w.get('description', 'item')} "
            f"({w.get('color', '')}, {', '.join(w.get('style_tags', []))})"
            for w in wardrobe_items
        )
        prompt = (
            f"A user just found this secondhand item: {item_line}.\n\n"
            f"Their current wardrobe includes:\n{wardrobe_lines}\n\n"
            "Suggest ONE complete outfit combination pairing the new item "
            "with specific pieces from their wardrobe. Name the exact "
            "wardrobe pieces to use. End with one concrete styling tip. "
            "Keep it to 2-4 sentences."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=200,
        )
        suggestion = response.choices[0].message.content.strip()
        if not suggestion:
            return (
                "Error: styling suggestion came back empty — try again or "
                "add a bit more wardrobe detail."
            )
        return suggestion
    except Exception as e:
        return f"Error generating outfit suggestion (styling service unavailable): {e}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "Error: can't create a fit card without a finished outfit "
            "suggestion — the outfit step must succeed first."
        )

    if not new_item:
        return "Error: can't create a fit card without knowing which item this outfit is built around."

    title = new_item.get("title", "this piece")
    price = new_item.get("price")
    platform = new_item.get("platform", "a thrift platform")
    price_str = f"${price:g}" if isinstance(price, (int, float)) else "a steal"

    prompt = (
        f"Write a short, casual Instagram-caption-style line (2-4 sentences, "
        f"lowercase-leaning, at most one emoji, no hashtags) for a thrift "
        f"outfit post. The item is: {title}, bought for {price_str} on "
        f"{platform}. The styling idea is: {outfit}\n\n"
        "Mention the item name, price, and platform naturally, each once. "
        "Sound like a real person casually captioning their own photo, not "
        "an ad or product description. Return only the caption text."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.1,
            max_tokens=120,
        )
        caption = response.choices[0].message.content.strip()
        if not caption:
            return "Error: fit card generation returned nothing usable — try again."
        return caption
    except Exception as e:
        return f"Error generating fit card (caption service unavailable): {e}"
