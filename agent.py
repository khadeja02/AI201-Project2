"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card, SEARCH_STOPWORDS

# Matches "size M", "size XXS", "size 8" — case-insensitive.
_SIZE_PATTERN = re.compile(r"\bsize\s+([A-Za-z0-9/]+)", re.IGNORECASE)
# Matches a dollar amount anywhere in the query, e.g. "$30", "$5.50".
_PRICE_PATTERN = re.compile(r"\$\s?(\d+(?:\.\d+)?)")


def _parse_query(query: str) -> dict:
    """
    Extracts a description, size, and max_price from a free-text query
    using regex rather than an LLM call — keeps this step deterministic
    and testable without an API key.

    Only looks at the query's first sentence for the description (the
    item request is expected up front; anything after the first period,
    like "I mostly wear baggy jeans...", is context for suggest_outfit's
    wardrobe pairing, not the search itself). Size and price are searched
    for across the whole query in case they're mentioned later.

    Limitation: this is intentionally simple. It won't catch phrasing like
    "around thirty dollars" (no $ sign) or "medium" (not "size M"). Good
    enough for the query patterns this project's example queries use.
    """
    size_match = _SIZE_PATTERN.search(query)
    size = size_match.group(1).upper() if size_match else None

    price_match = _PRICE_PATTERN.search(query)
    max_price = float(price_match.group(1)) if price_match else None

    first_sentence = re.split(r"[.!?]", query)[0]
    description = _SIZE_PATTERN.sub("", first_sentence)
    description = _PRICE_PATTERN.sub("", description)
    description = _strip_filler_words(description)

    if not description:
        description = first_sentence.strip()

    return {"description": description, "size": size, "max_price": max_price}


def _strip_filler_words(text: str) -> str:
    """Removes words in SEARCH_STOPWORDS (e.g. 'looking', 'under', 'a',
    "i'm") from free text, used to turn a raw query fragment into a clean
    item description. Order-preserving; only drops exact stopword tokens."""
    words = text.split()
    kept = [w for w in words if w.lower().strip(",.") not in SEARCH_STOPWORDS]
    return re.sub(r"\s+", " ", " ".join(kept)).strip(" ,.")


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    # --- Step 2: parse the query -----------------------------------------
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # --- Step 3: search -----------------------------------------------------
    results = search_listings(
        parsed["description"], size=parsed["size"], max_price=parsed["max_price"]
    )
    session["search_results"] = results

    if not results:
        filters_used = []
        if parsed["size"]:
            filters_used.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            filters_used.append(f"under ${parsed['max_price']:g}")
        filter_note = f" ({', '.join(filters_used)})" if filters_used else ""
        session["error"] = (
            f"No listings matched '{parsed['description']}'{filter_note}. "
            "Try loosening your size or price filter, or rephrasing the "
            "description with more general terms."
        )
        return session  # do NOT proceed to suggest_outfit with empty input

    # --- Step 4: select the top result ---------------------------------------
    session["selected_item"] = results[0]

    # --- Step 5: suggest an outfit --------------------------------------------
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    if outfit.startswith("Error"):
        # The LLM call itself failed. Stop before create_fit_card, but keep
        # search_results/selected_item so the caller can still show the item.
        session["error"] = (
            "Found an item, but couldn't generate a styling suggestion right "
            f"now. Details: {outfit}"
        )
        return session

    # --- Step 6: create the fit card ------------------------------------------
    fit_card = create_fit_card(outfit, session["selected_item"])
    session["fit_card"] = fit_card

    if fit_card.startswith("Error"):
        # Outfit succeeded but the caption failed — surface the partial
        # success (item + styling idea) instead of discarding it.
        session["error"] = (
            "Found an item and a styling idea, but couldn't generate a "
            f"shareable caption. Details: {fit_card}"
        )

    # --- Step 7: return the completed session ----------------------------------
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
