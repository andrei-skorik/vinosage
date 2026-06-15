"""Chat view helpers — rendering history, empty state, and message details."""
from __future__ import annotations

import random
from typing import Any

import streamlit as st

from src.i18n import t, tlist

_EXAMPLE_COUNT = 3


def render_empty_state(locale: str) -> None:
    """Render the welcome screen. Clicked button label is written to queued_prompt."""
    st.markdown(f"## {t('welcome_title', locale)}")
    st.markdown(t("welcome_body", locale))
    st.markdown("")

    # Cache picks so button keys map to the same labels across reruns.
    cache_key = f"_welcome_picks_{locale}"
    if cache_key not in st.session_state:
        pool = tlist("welcome_examples", locale)
        if not pool:
            return
        st.session_state[cache_key] = random.sample(pool, min(_EXAMPLE_COUNT, len(pool)))

    picks: list[str] = st.session_state[cache_key]
    cols = st.columns(len(picks))
    for i, (col, label) in enumerate(zip(cols, picks)):
        with col:
            if st.button(label, use_container_width=True, key=f"example_{i}"):
                st.session_state.queued_prompt = label


def render_assistant_extras(
    sources: list[Any],
    tool_calls: list[dict[str, Any]],
    locale: str,
) -> None:
    if sources:
        label = t("sources_label", locale, count=len(sources))
        with st.expander(label, expanded=False):
            for w in sources:
                payload = getattr(w, "payload", {}) or {}
                cents = payload.get("price_eur_cents")
                price = f"€{cents / 100:.2f}" if cents else "N/A"
                country = payload.get("country", "")
                wine_type = payload.get("type", "")
                title = getattr(w, "title", str(w))
                parts = [p for p in [country, wine_type] if p]
                meta = " · ".join(parts)
                st.markdown(f"**{title}** — {price}" + (f" · {meta}" if meta else ""))

    if tool_calls:
        label = t("actions_label", locale)
        with st.expander(label, expanded=False):
            for tc in tool_calls:
                st.code(f"🔧 {tc.get('tool_name', '?')}", language=None)


def render_chat_history(messages: list[dict[str, Any]], locale: str) -> None:
    for msg in messages:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            if role == "assistant":
                render_assistant_extras(
                    msg.get("sources", []),
                    msg.get("tool_calls", []),
                    locale,
                )
