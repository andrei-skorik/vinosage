"""Age gate + login/register forms + profile widget (avatar upload, logout).

Auth is optional — anonymous users can chat freely after confirming the age
gate. Registering only unlocks the avatar personalisation feature; it does
not gate any catalog/chat functionality by itself.
"""
from __future__ import annotations

import time

import streamlit as st

from src.auth import AuthSession, create_profile, get_profile, sign_in, sign_out, sign_up, upload_avatar
from src.i18n import t


def is_age_gate_passed() -> bool:
    auth = st.session_state.get("auth")
    if auth and auth.get("is_adult"):
        return True
    return bool(st.session_state.get("age_confirmed"))


def render_age_gate(locale: str) -> None:
    """Blocking screen — must be passed before any chat functionality renders."""
    st.markdown(f"## {t('age_gate_title', locale)}")
    st.markdown(t("age_gate_body", locale))
    col1, col2 = st.columns(2)
    if col1.button(t("age_gate_yes", locale), use_container_width=True, type="primary", key="age_yes"):
        st.session_state.age_confirmed = True
        st.rerun()
    if col2.button(t("age_gate_no", locale), use_container_width=True, key="age_no"):
        st.error(t("age_gate_blocked", locale))


def _set_authed_session(session: AuthSession, is_adult_hint: bool | None = None) -> None:
    profile = get_profile(session.access_token, session.refresh_token, session.user_id)
    st.session_state.auth = {
        "user_id":       session.user_id,
        "email":         session.email,
        "access_token":  session.access_token,
        "refresh_token": session.refresh_token,
        "is_adult":      (profile.get("is_adult") if profile else is_adult_hint) or False,
        "avatar_url":    profile.get("avatar_url") if profile else None,
    }
    # A confirmed-adult login satisfies the age gate too — no need to ask twice.
    if st.session_state.auth["is_adult"]:
        st.session_state.age_confirmed = True


def render_auth_forms(locale: str) -> None:
    """Login / register tabs — shown in the sidebar when no one is logged in."""
    tab_login, tab_register = st.tabs([t("login_tab", locale), t("register_tab", locale)])

    with tab_login:
        with st.form("login_form", border=False):
            email = st.text_input(t("email_label", locale), key="login_email")
            password = st.text_input(t("password_label", locale), type="password", key="login_password")
            submitted = st.form_submit_button(t("login_button", locale), use_container_width=True)
        if submitted:
            result = sign_in(email, password)
            if result.ok and result.session:
                _set_authed_session(result.session)
                st.rerun()
            else:
                st.error(t("auth_error_invalid", locale))

    with tab_register:
        with st.form("register_form", border=False):
            email = st.text_input(t("email_label", locale), key="register_email")
            password = st.text_input(t("password_label", locale), type="password", key="register_password")
            confirm = st.text_input(t("confirm_password_label", locale), type="password", key="register_confirm")
            is_adult = st.checkbox(t("age_confirm_checkbox", locale), key="register_is_adult")
            submitted = st.form_submit_button(t("register_button", locale), use_container_width=True)
        if submitted:
            if not is_adult:
                st.error(t("age_confirm_required", locale))
            elif password != confirm:
                st.error(t("password_mismatch", locale))
            elif len(password) < 6:
                st.error(t("password_too_short", locale))
            else:
                result = sign_up(email, password)
                if result.ok and result.session:
                    create_profile(
                        result.session.access_token,
                        result.session.refresh_token,
                        result.session.user_id,
                        is_adult=True,
                    )
                    _set_authed_session(result.session, is_adult_hint=True)
                    st.success(t("register_success", locale))
                    st.rerun()
                elif result.error == "confirm_email":
                    st.info(t("auth_check_email", locale))
                else:
                    st.error(t("auth_error_register", locale, error=result.error))


def render_profile_widget(locale: str) -> None:
    """Logged-in view: avatar + email + avatar upload + logout."""
    auth = st.session_state.get("auth")
    if not auth:
        return

    col_avatar, col_info = st.columns([1, 3])
    with col_avatar:
        if auth.get("avatar_url"):
            st.image(auth["avatar_url"], width=40)
        else:
            st.markdown("### 👤")
    with col_info:
        st.caption(auth["email"])

    uploaded = st.file_uploader(
        t("avatar_upload_label", locale), type=["png", "jpg", "jpeg"], key="avatar_uploader"
    )
    # st.file_uploader keeps returning the SAME file object on every rerun until
    # the user removes it — without this guard, the upload (and st.rerun() below)
    # would fire again on every single rerun, looping forever.
    upload_identity = (uploaded.name, uploaded.size) if uploaded is not None else None
    if uploaded is not None and st.session_state.get("_last_avatar_upload") != upload_identity:
        ext = uploaded.name.rsplit(".", 1)[-1].lower()
        url = upload_avatar(
            auth["access_token"], auth["refresh_token"], auth["user_id"], uploaded.read(), f"avatar.{ext}"
        )
        st.session_state["_last_avatar_upload"] = upload_identity
        if url:
            st.session_state.auth["avatar_url"] = f"{url}?t={int(time.time())}"  # cache-bust
            st.success(t("avatar_upload_success", locale))
            st.rerun()
        else:
            st.error(t("avatar_upload_error", locale))

    if st.button(f"🚪 {t('logout_button', locale)}", use_container_width=True, key="logout_btn"):
        sign_out(auth["access_token"], auth["refresh_token"])
        st.session_state.auth = None
        st.rerun()
