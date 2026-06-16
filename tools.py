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
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── search_listings helpers ───────────────────────────────────────────────────

def _size_matches(listing_size: str, user_size: str) -> bool:
    ls = listing_size.strip()
    us = user_size.strip()

    # One Size variants always pass
    if "one size" in ls.lower():
        return True

    # US shoe sizes: exact match only
    if ls.upper().startswith("US"):
        return ls.lower() == us.lower()

    # Waist sizes (W28, W30 L30): listing starts with user's input
    if ls.upper().startswith("W"):
        return ls.upper().startswith(us.upper())

    # Letter / range sizes (S, M, L, XL, S/M, M/L, L/XL): token match
    tokens = [t.upper() for t in re.split(r"[/\s()]+", ls) if t]
    return us.upper() in tokens


def _score_listing(listing: dict, keywords: list[str]) -> int:
    parts = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
    ]
    blob_words = set(re.split(r"\W+", " ".join(parts).lower()))
    blob_words.discard("")
    return sum(1 for kw in keywords if kw in blob_words)


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
    listings = load_listings()

    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and not _size_matches(listing["size"], size):
            continue
        filtered.append(listing)

    keywords = [w for w in re.split(r"\W+", description.lower()) if w]

    scored = []
    for listing in filtered:
        score = _score_listing(listing, keywords)
        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


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
    """
    client = _get_groq_client()

    item_summary = (
        f"Title: {new_item.get('title', 'Unknown')}\n"
        f"Category: {new_item.get('category', 'Unknown')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Condition: {new_item.get('condition', 'Unknown')}"
    )

    items = wardrobe.get("items", [])

    if not items:
        prompt = (
            f"A thrift shopper is considering buying this item:\n{item_summary}\n\n"
            "They haven't shared their wardrobe yet. Give them 1–2 general styling ideas "
            "for how to wear this piece — what kinds of bottoms, shoes, or layers would "
            "work with it, and what overall aesthetic it suits. Be specific about types "
            "of pieces and vibes rather than vague generalities. Keep it to 1–2 sentences."
        )
    else:
        wardrobe_lines = []
        for item in items:
            notes = f" ({item['notes']})" if item.get("notes") else ""
            wardrobe_lines.append(
                f"- {item['name']} [{item['category']}] "
                f"colors: {', '.join(item['colors'])} | "
                f"style: {', '.join(item['style_tags'])}{notes}"
            )
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            f"A thrift shopper is considering buying this item:\n{item_summary}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfits that incorporate the new piece with specific "
            "items from their wardrobe. Name the exact pieces by name as listed above. "
            "Be concrete about styling details (tucking, layering, etc.). Keep it to 2–3 sentences total."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    return response.choices[0].message.content or "No outfit suggestion could be generated."


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

    """
    if not outfit.strip():
        return "No outfit suggestion was available to generate a caption from."

    client = _get_groq_client()

    title = new_item.get("title", "thrifted find")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "")

    price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)

    prompt = (
        f"Write a casual Instagram/TikTok OOTD caption for this outfit.\n\n"
        f"Thrifted item: {title} — {price_str} from {platform}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- 1–3 sentences, lowercase, sounds like a real person not a brand\n"
        "- Mention the item name, price, and platform exactly once each\n"
        "- Capture the specific vibe of the outfit (don't be generic)\n"
        "- Write it as if you're posting it yourself, not describing an outfit to someone\n"
        "- No hashtags"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.2,
    )

    return response.choices[0].message.content or "Caption could not be generated."
