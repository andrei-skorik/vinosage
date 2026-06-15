"""Admin panel — catalog stats, CSV import, audit log."""
from __future__ import annotations

import io

import streamlit as st

from src.catalog import get_service_db, invalidate_cache
from src.i18n import t


def render_admin(locale: str) -> None:
    st.subheader(t("admin_stats_header", locale))
    _render_stats(locale)
    st.divider()

    st.subheader(t("admin_import_header", locale))
    _render_import(locale)
    st.divider()

    st.subheader(t("admin_audit_header", locale))
    _render_audit(locale)


def _render_stats(locale: str) -> None:
    try:
        db = get_service_db()
        result = db.table("wines").select("needs_embedding", count="exact").execute()
        total = result.count or len(result.data)
        pending = sum(1 for r in result.data if r.get("needs_embedding"))
        embedded = total - pending

        col1, col2, col3 = st.columns(3)
        col1.metric(t("total_wines", locale), total)
        col2.metric(t("embedded_wines", locale), embedded)
        col3.metric(t("pending_embed", locale), pending)
    except Exception as exc:
        st.error(f"Stats unavailable: {exc}")


def _render_import(locale: str) -> None:
    uploaded = st.file_uploader(
        t("admin_import_label", locale),
        type=["csv"],
        key="admin_csv_uploader",
    )

    col_sync, col_import = st.columns([1, 2])

    with col_sync:
        if st.button(t("admin_sync_button", locale), key="admin_sync_btn"):
            with st.spinner("Syncing…"):
                try:
                    from src.embeddings import reconcile_embeddings
                    reconcile_embeddings()
                    invalidate_cache()
                    st.success(t("admin_sync_success", locale))
                except Exception as exc:
                    st.error(str(exc))

    with col_import:
        if uploaded and st.button(t("admin_import_button", locale), key="admin_import_btn"):
            with st.spinner("Importing…"):
                try:
                    import pandas as pd
                    from src.ingest import normalise_row, upsert_wines
                    from src.embeddings import reconcile_embeddings

                    df = pd.read_csv(io.StringIO(uploaded.read().decode("utf-8")))
                    rows = []
                    for _, row in df.iterrows():
                        norm = normalise_row(row.to_dict())
                        if norm:
                            rows.append(norm)

                    if rows:
                        upsert_wines(rows)
                        reconcile_embeddings()
                        invalidate_cache()
                        st.success(t("admin_import_success", locale, count=len(rows)))
                    else:
                        st.warning("No valid rows found in CSV.")
                except Exception as exc:
                    st.error(t("admin_import_error", locale, error=str(exc)))


def _render_audit(locale: str) -> None:
    try:
        import pandas as pd
        db = get_service_db()
        result = (
            db.table("catalog_audit")
            .select("created_at, action, actor, wine_id, diff")
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        if result.data:
            df = pd.DataFrame(result.data)
            show_cols = [c for c in ["created_at", "action", "actor", "wine_id"] if c in df.columns]
            st.dataframe(df[show_cols], use_container_width=True)
        else:
            st.info("No audit entries yet.")
    except Exception as exc:
        st.error(f"Audit log unavailable: {exc}")
