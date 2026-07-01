# FitFindr

A multi-tool AI agent that finds secondhand clothing items and figures out
how to style them, ending in a shareable outfit caption.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env               # then paste in your GROQ_API_KEY
python app.py
```

Open the URL printed in the terminal (check the output — it may not be
`localhost:7860`).

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `search_listings(description, size, max_price)` | `description` (str), `size` (str \| None), `max_price` (float \| None) | `list[dict]` of matching listings, ranked by keyword-overlap relevance; `[]` if none match | Filters the mock listings dataset for items matching a free-text request |
| `suggest_outfit(new_item, wardrobe)` | `new_item` (dict, a listing), `wardrobe` (dict: `{"items": [...]}`) | `str`, a 2–4 sentence styling suggestion | Pairs a found item with the user's existing wardrobe, or gives general advice if the wardrobe is empty |
| `create_fit_card(outfit, new_item)` | `outfit` (str), `new_item` (dict) | `str`, a short caption-style line | Turns a finished outfit suggestion into a shareable caption |

All three signatures match `tools.py` exactly.

## How the Planning Loop Works

`agent.run_agent(query, wardrobe)` first parses the free-text `query` into a
description/size/max_price using `_parse_query()` (regex-based: pulls a `$`
amount and a `"size X"` token from anywhere in the query, and cleans filler
words like "looking", "a", "under" out of the remaining description).

From there it calls the three tools in order, but **not unconditionally**:

1. Calls `search_listings`. **If it returns `[]`, the loop stops there** —
   it records which filters were active and suggests loosening them or
   rephrasing, and `suggest_outfit`/`create_fit_card` are never invoked.
2. If a match was found, it takes the top-ranked result and calls
   `suggest_outfit`. **If that result starts with `"Error"`** (the LLM
   call itself failed), the loop stops there too — but keeps the
   already-found item in the session so the UI can still show it.
3. If the outfit suggestion succeeded, it calls `create_fit_card`. If
   *that* fails, the loop still returns the item and the outfit
   suggestion — a partial success — rather than discarding everything.

## State Management

Everything lives in one `session` dict, created by `_new_session()`:
`query`, `parsed`, `search_results`, `selected_item`, `wardrobe`,
`outfit_suggestion`, `fit_card`, `error`. Each field is written once, right
after the call that produces it. Downstream tools read their main input
straight out of this dict — e.g. `suggest_outfit(session["selected_item"],
wardrobe)` — so the item found in step 1 flows into step 2 without the user
re-entering anything. `app.py` holds no state of its own; it reads the
finished session once and maps it onto the three UI panels.

## Error Handling (per tool)

- **`search_listings`** — returns `[]` on no match (never raises, never
  `None`). Example from testing: `search_listings("designer ballgown",
  size="XXS", max_price=5)` → `[]`, and the agent's resulting message was:
  *"No listings matched 'designer ballgown' (size XXS, under $5). Try
  loosening your size or price filter, or rephrasing the description..."*
- **`suggest_outfit`** — an empty wardrobe is valid input, not a failure:
  it returns general styling advice instead of wardrobe-specific pairing.
  Only an actual LLM/network failure returns an `"Error: ..."`-prefixed
  string, which the agent checks for before calling `create_fit_card`.
- **`create_fit_card`** — refuses to call the LLM at all if `outfit` is
  empty or `new_item` is missing, returning `"Error: ..."` immediately.
  Example from testing: `create_fit_card("", item)` →
  `"Error: can't create a fit card without a finished outfit suggestion..."`.

## Spec Reflection

One way the spec helped: Writing out create_fit_card's failure mode in planning.md before touching code ("If outfit is empty/whitespace-only... return an Error: string immediately — no LLM call is attempted") meant I caught the guard-clause requirement early. If I'd started coding first, I likely would've let the empty-outfit case fall through to the LLM and just gotten a weird/wasted API call instead of a clean, testable error.

One way my implementation diverged from the spec, and why: My original planning.md assumed run_agent would take pre-split description/size/max_price parameters. The actual starter stub takes a single free-text query string instead, which meant I had to add a _parse_query() regex step that wasn't in my original plan at all. I chose regex over an LLM-based parser so this step stays deterministic and testable without burning an API call just to extract "size M" from a sentence.

## AI Usage

Instance 1 — search_listings: I gave Claude the Tool 1 spec from planning.md (exact params, return shape, and the requirement to return [] instead of raising on no match) and asked it to implement the function. Before trusting the output, I had it run the three example queries from the assignment directly — "vintage graphic tee" with a $30 cap, a deliberately impossible "designer ballgown" query, and a price-filter check — and confirmed each one matched or correctly returned empty. I did catch one thing I wanted changed: the first draft matched size exactly, so I asked for it to handle a case like a listing sized "S/M" matching a query for "M" — that's why the size check in tools.py does a substring comparison instead of exact equality.

Instance 2 — the query parser: Since run_agent takes a single free-text string, I had Claude build a _parse_query() helper and directly tested it against all five example queries plus the long multi-sentence one in planning.md's walkthrough. It initially left filler words like "in" and "looking" sitting in the parsed description (e.g. "90s track jacket in" instead of "90s track jacket"), which I noticed by printing the parsed output — so I had it reuse the same stopword list search_listings already had, rather than write a second one, to keep the cleanup consistent.

## Tests

```bash
pytest tests/
```
