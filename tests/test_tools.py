from unittest.mock import MagicMock, patch

from tools import search_listings, suggest_outfit, create_fit_card


# ── Shared test data ──────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_033",
    "title": "Vintage Band Tee",
    "description": "Faded grey band tee with distressed print",
    "category": "tops",
    "style_tags": ["vintage", "grunge", "band tee"],
    "size": "M",
    "condition": "fair",
    "price": 19.0,
    "colors": ["grey", "black"],
    "brand": None,
    "platform": "depop",
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans",
            "category": "bottoms",
            "colors": ["dark blue"],
            "style_tags": ["streetwear", "baggy"],
            "notes": None,
        }
    ]
}

EMPTY_WARDROBE = {"items": []}


def _mock_groq(text: str):
    """Return a fake Groq client whose create() yields `text`."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = text
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: nothing matches → empty list, no exception raised
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Every result must contain "M" as a size token or be One Size
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        size = item["size"]
        is_one_size = "one size" in size.lower()
        tokens = [t.upper() for t in size.replace("/", " ").split()]
        assert is_one_size or "M" in tokens


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_returns_nonempty():
    # Failure mode: empty wardrobe → general styling advice, non-empty string
    with patch("tools._get_groq_client", return_value=_mock_groq("Try wide-leg trousers and chunky sneakers.")):
        result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_empty_wardrobe_calls_llm():
    # Confirm the empty-wardrobe branch still calls the LLM (doesn't short-circuit)
    mock_client = _mock_groq("General advice here.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert mock_client.chat.completions.create.called


def test_suggest_outfit_with_wardrobe_returns_nonempty():
    with patch("tools._get_groq_client", return_value=_mock_groq("Pair with your Baggy straight-leg jeans.")):
        result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert result.strip() != ""


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    # Failure mode: empty outfit → specific error message, no exception
    result = create_fit_card("", SAMPLE_ITEM)
    assert result == "No outfit suggestion was available to generate a caption from."


def test_create_fit_card_whitespace_outfit_returns_error_string():
    # Failure mode: whitespace-only outfit → same guard catches it
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert result == "No outfit suggestion was available to generate a caption from."


def test_create_fit_card_returns_caption():
    outfit = "Pair with baggy jeans and combat boots for a grunge look."
    caption = "thrifted this band tee off depop for $19 and it just works 🖤"
    with patch("tools._get_groq_client", return_value=_mock_groq(caption)):
        result = create_fit_card(outfit, SAMPLE_ITEM)
    assert result == caption
