from app.settings import Settings


def test_frontend_origins_string_splits_into_list() -> None:
    settings = Settings(
        FRONTEND_ORIGINS='http://localhost:3000, http://127.0.0.1:3000'
    )
    assert settings.FRONTEND_ORIGINS == [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]


def test_session_cookie_samesite_is_normalized() -> None:
    settings = Settings(SESSION_COOKIE_SAMESITE='STRICT')
    assert settings.SESSION_COOKIE_SAMESITE == 'strict'
