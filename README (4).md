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

*(Fill this in from your own run of the project — two or three sentences
each is plenty. Answer these two exact prompts:)*

- **One way the spec helped:** Look at `planning.md`'s Tool 2/3 specs —
  did having the exact failure-mode description written down *before*
  coding change how you (or the AI) handled the empty-wardrobe or
  empty-outfit case? Say what would've gone differently without it.
- **One way your implementation diverged from the spec, and why:** Run
  `python agent.py` or the app with a few different queries. Did anything
  come out differently than what you planned in `planning.md`'s walkthrough
  — e.g. the parser handling a query you didn't originally think through,
  or a tool's output format differing from what you specified? Name the
  actual divergence you hit.

## AI Usage

*(The assignment wants **your own** record of directing an AI tool and
catching/fixing something in its output — not a description of AI writing
the whole thing unsupervised. Two real, concrete instances. A filled-in
example of the *shape* this should take:)*

1. **[tool/file name]** — Gave [AI tool] the [exact spec section] from
   `planning.md`. It produced [what it produced]. Before trusting it, I
   checked [specific thing you checked — ran a specific test query, printed
   a specific variable, re-read a specific line] and found [what matched or
   didn't]. I changed/kept: ___
2. **[tool/file name]** — same structure.

If you worked through this with an AI assistant open in another tab, this
is genuinely easy to fill in truthfully — you were reviewing generated code
against a spec at almost every step. Write down the specific moment you
caught something (a wrong return type, a missing guard clause, output that
didn't match the failure-mode you'd written) rather than a generic summary.

## Tests

```bash
pytest tests/
```
