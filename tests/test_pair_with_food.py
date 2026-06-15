"""Unit tests for pair_with_food tool."""
from __future__ import annotations

from unittest.mock import patch

import pytest

_MODULE = "src.tools.pair_with_food.get_active_wines_df"


class TestPairWithFood:
    def test_pair_steak_prefers_red(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "steak"})
        assert "pairings" in result
        types = {p["type"] for p in result["pairings"]}
        assert "Red" in types

    def test_pair_salmon_prefers_white(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "salmon"})
        assert "pairings" in result
        types = {p["type"] for p in result["pairings"]}
        assert "White" in types

    def test_pair_dessert_prefers_tawny(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "chocolate dessert"})
        assert "pairings" in result
        types = {p["type"] for p in result["pairings"]}
        assert "Tawny" in types

    def test_pair_bbq_prefers_red_rich(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "BBQ ribs"})
        assert "pairings" in result
        # Should prefer Red + Rich & Juicy style
        types = {p["type"] for p in result["pairings"]}
        assert "Red" in types

    def test_pair_returns_rationale(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "pasta"})
        for p in result["pairings"]:
            assert "rationale" in p
            assert len(p["rationale"]) > 0

    def test_pair_max_price_respected(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "fish", "max_price_eur": 12.0})
        for p in result["pairings"]:
            if p["price_eur"] is not None:
                assert p["price_eur"] <= 12.0

    def test_pair_limit_respected(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "cheese", "limit": 2})
        assert len(result["pairings"]) <= 2

    def test_pair_prefer_type_overrides_rule(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            # fish rule → White, but user prefers Red
            result = pair_with_food.invoke({"dish": "fish", "prefer_type": "Red"})
        types = {p["type"] for p in result["pairings"]}
        assert "Red" in types

    def test_pair_unknown_dish_returns_some_wines(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "xyzzy_unknown_food_123"})
        assert "pairings" in result
        assert len(result["pairings"]) > 0

    def test_pair_empty_catalog_returns_error(self, empty_df):
        with patch(_MODULE, return_value=empty_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "steak"})
        assert "error" in result

    def test_pair_price_format(self, mock_df):
        with patch(_MODULE, return_value=mock_df):
            from src.tools.pair_with_food import pair_with_food
            result = pair_with_food.invoke({"dish": "pasta"})
        for p in result["pairings"]:
            if p["price_eur"] is not None:
                assert round(p["price_eur"], 2) == p["price_eur"]
