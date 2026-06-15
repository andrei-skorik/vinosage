"""Tool 2: pair_with_food — recommend wines for a given dish."""
from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.catalog import get_active_wines_df

_ERR = lambda code, msg: {"error": {"code": code, "message": msg}}   # noqa: E731

# keyword → preferred wine type/style when no catalog description match exists
PAIRING_RULES: dict[str, dict[str, Any]] = {
    "steak":     {"type": "Red",   "styles": ["Rich & Juicy", "Bold & Spicy"]},
    "beef":      {"type": "Red",   "styles": ["Rich & Juicy"]},
    "lamb":      {"type": "Red",   "styles": ["Rich & Juicy"]},
    "venison":   {"type": "Red"},
    "pork":      {"type": "Red",   "styles": ["Light & Fruity"]},
    "chicken":   {"type": "White", "styles": ["Rich & Toasty", "Crisp & Zesty"]},
    "turkey":    {"type": "White"},
    "duck":      {"type": "Red",   "styles": ["Light & Fruity"]},
    "salmon":    {"type": "White", "styles": ["Rich & Toasty"]},
    "tuna":      {"type": "White", "styles": ["Crisp & Zesty"]},
    "fish":      {"type": "White", "styles": ["Crisp & Zesty", "Light & Fresh"]},
    "seafood":   {"type": "White", "styles": ["Crisp & Zesty"]},
    "lobster":   {"type": "White"},
    "shrimp":    {"type": "White"},
    "oyster":    {"type": "White", "styles": ["Crisp & Zesty"]},
    "sushi":     {"type": "White"},
    "pasta":     {"type": "Red"},
    "pizza":     {"type": "Red"},
    "risotto":   {"type": "White"},
    "mushroom":  {"type": "Red",   "grapes": ["Pinot Noir"]},
    "truffle":   {"type": "Red",   "grapes": ["Pinot Noir"]},
    "cheese":    {"type": "Red"},
    "salad":     {"type": "White", "styles": ["Crisp & Zesty"]},
    "dessert":   {"type": "Tawny"},
    "chocolate": {"type": "Tawny"},
    "spicy":     {"styles": ["Light & Fruity", "Crisp & Zesty"]},
    "bbq":       {"type": "Red",   "styles": ["Rich & Juicy", "Bold & Spicy"]},
    "barbecue":  {"type": "Red",   "styles": ["Rich & Juicy"]},
    "curry":     {"styles": ["Light & Fruity", "Crisp & Zesty"]},
    "indian":    {"styles": ["Light & Fruity"]},
    "asian":     {"type": "White"},
    "thai":      {"type": "White"},
    "mexican":   {"type": "Red"},
    "tapas":     {"type": "Red",   "styles": ["Light & Fruity"]},
}


def _best_rule(dish: str) -> dict[str, Any]:
    dl = dish.lower()
    for kw, rule in PAIRING_RULES.items():
        if kw in dl:
            return rule
    return {}


def _desc_keywords(dish: str) -> list[str]:
    """Extract meaningful keywords from dish name for description search."""
    words = [w for w in re.split(r'\W+', dish.lower()) if len(w) > 3]
    return list(dict.fromkeys([dish.lower()] + words))


def _desc_mentions_food(desc: str, title: str, keywords: list[str]) -> bool:
    """
    Return True only if the description mentions a keyword as a food (lowercase),
    NOT as part of a wine/product name (which would be capitalised).

    Example: "stand up to chocolate puddings" → match (lowercase 'chocolate').
             "the man behind The Chocolate Block" → no match ('Chocolate' is capitalised).
    """
    for kw in keywords:
        # Case-sensitive search for the lowercase keyword as a whole word.
        # Wine-name references are always title-cased; food references are lowercase.
        if re.search(r'\b' + re.escape(kw) + r'\b', desc):
            return True
    return False


class PairWithFoodArgs(BaseModel):
    dish:          str            = Field(..., min_length=2, description="Dish or cuisine name")
    prefer_type:   str            = Field("any", description="Red/White/Rosé/any")
    max_price_eur: Optional[float]= Field(None, ge=0)
    limit:         int            = Field(3, ge=1, le=8)


def _run(
    dish: str,
    prefer_type: str = "any",
    max_price_eur: float | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    try:
        df = get_active_wines_df()
        if df.empty:
            return _ERR("INTERNAL", "Catalog not available")

        active = df["is_active"].notna()
        keywords = _desc_keywords(dish)

        # ── Priority 1: wines whose description explicitly mentions this food ──
        # Use title-aware matching to exclude wine-name false positives.
        desc_hit = df.apply(
            lambda row: _desc_mentions_food(
                row.get("description") or "", row.get("title") or "", keywords
            ),
            axis=1,
        )
        catalog_matches = df[active & desc_hit].copy()
        catalog_matches["_source"] = "catalog_description"

        if max_price_eur is not None:
            max_cents = int(max_price_eur * 100)
            catalog_matches = catalog_matches[
                catalog_matches["price_eur_cents"].notna() &
                (catalog_matches["price_eur_cents"] <= max_cents)
            ]

        # Only return wines with explicit catalog description evidence.
        # Style-rule matches are excluded: the LLM ignores the "pairing_rule" signal
        # and invents pairing claims regardless, causing hallucinations.
        pool = catalog_matches.sort_values("price_eur_cents", ascending=True)

        if pool.empty:
            return {
                "dish": dish,
                "pairings": [],
                "result": "no_match",
                "agent_instruction": (
                    f"Search result: zero catalog wines mention {dish!r} in their description. "
                    f"Tell the customer directly (no apology) that the catalog has no specific "
                    f"recommendation for this dish. You may suggest they browse by wine style "
                    f"(e.g. Tawny Port for chocolate, white wines for fish) without naming "
                    f"specific wines as pairings."
                ),
            }

        results = pool.head(limit)

        pairings = []
        for _, row in results.iterrows():
            cents = row.get("price_eur_cents")
            style = row.get("style") or ""
            grape = row.get("grape") or ""
            description = row.get("description") or ""

            pairings.append({
                "wine_id":     row["wine_id"],
                "title":       row["title"],
                "price_eur":   round(cents / 100, 2) if cents else None,
                "type":        row.get("type"),
                "grape":       grape,
                "style":       style,
                "description": description,
                "rationale":   "Catalog description explicitly recommends this wine with this dish.",
                "source":      "catalog_description",
            })

        return {"dish": dish, "pairings": pairings}

    except Exception as exc:
        return _ERR("INTERNAL", str(exc))


pair_with_food = StructuredTool.from_function(
    func=_run,
    name="pair_with_food",
    description=(
        "Given a dish or cuisine, return catalog wines whose description explicitly recommends "
        "them with that dish. All returned wines are catalog-confirmed pairings — cite them "
        "confidently using the catalog description text. If result is 'no_match', follow "
        "agent_instruction exactly."
    ),
    args_schema=PairWithFoodArgs,
)
