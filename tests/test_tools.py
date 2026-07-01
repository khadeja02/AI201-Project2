"""
tests/test_tools.py

Covers:
  - search_listings: happy path, empty results, size/price filter correctness
  - agent._parse_query: size/price extraction and filler-word cleanup
  - create_fit_card: empty-outfit failure mode (no LLM call needed)
  - agent.run_agent: the no-results branch stops before suggest_outfit
"""

import os

import pytest

from tools import search_listings, create_fit_card
from agent import run_agent, _parse_query
from utils.data_loader import get_empty_wardrobe


# --- search_listings: no LLM involved, always runnable -----------------

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("graphic tee", size="L", max_price=None)
    assert all(item["size"] == "L" for item in results)


def test_search_blank_description_does_not_crash():
    results = search_listings("", size=None, max_price=None)
    assert results == []


# --- agent._parse_query: the free-text query parser ---------------------

def test_parse_query_extracts_price():
    parsed = _parse_query("vintage graphic tee under $30")
    assert parsed["max_price"] == 30.0
    assert parsed["size"] is None
    assert "vintage graphic tee" in parsed["description"].lower()


def test_parse_query_extracts_size():
    parsed = _parse_query("90s track jacket in size M")
    assert parsed["size"] == "M"
    assert "track jacket" in parsed["description"].lower()


def test_parse_query_extracts_both():
    parsed = _parse_query("designer ballgown size XXS under $5")
    assert parsed["size"] == "XXS"
    assert parsed["max_price"] == 5.0


def test_parse_query_strips_filler_from_long_sentence():
    parsed = _parse_query(
        "I'm looking for a vintage graphic tee under $30. "
        "I mostly wear baggy jeans and chunky sneakers."
    )
    assert parsed["max_price"] == 30.0
    # filler words shouldn't survive into the cleaned description
    for filler in ("looking", "i'm", " a "):
        assert filler not in parsed["description"].lower()


# --- create_fit_card: failure mode doesn't need the LLM ------------------

def test_fit_card_rejects_empty_outfit():
    fake_item = {"title": "Test Tee", "price": 20.0, "platform": "Depop", "condition": "Good"}
    result = create_fit_card("", fake_item)
    assert isinstance(result, str)
    assert result.startswith("Error")


def test_fit_card_rejects_missing_item():
    result = create_fit_card("pair with jeans", None)
    assert isinstance(result, str)
    assert result.startswith("Error")


# --- agent.run_agent: the branching logic itself -------------------------

def test_agent_stops_before_suggest_outfit_on_no_results():
    session = run_agent(
        "designer ballgown size XXS under $5", wardrobe=get_empty_wardrobe()
    )
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert session["error"] is not None


# --- LLM-dependent tests: require GROQ_API_KEY to be set -----------------
# Skipped automatically if no key is configured, so the rest of the suite
# still runs without network access / credentials.

_HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))


@pytest.mark.skipif(not _HAS_KEY, reason="GROQ_API_KEY not set")
def test_suggest_outfit_empty_wardrobe_gives_general_advice():
    from tools import suggest_outfit

    fake_item = {
        "title": "Faded Band Tee",
        "description": "vintage graphic tee",
        "style_tags": ["vintage", "grunge"],
    }
    result = suggest_outfit(fake_item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0
    assert not result.startswith("Error")


@pytest.mark.skipif(not _HAS_KEY, reason="GROQ_API_KEY not set")
def test_fit_card_varies_across_calls():
    fake_item = {"title": "Faded Band Tee", "price": 22.0, "platform": "Depop", "condition": "Good"}
    outfit = "Pair with wide-leg jeans and platform boots."
    a = create_fit_card(outfit, fake_item)
    b = create_fit_card(outfit, fake_item)
    assert a != b
