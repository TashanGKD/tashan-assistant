from app.sanitize import sanitize_text

def test_redacts_common_secrets():
    text = "api_key=abcdef123456789 token: qwertyuiop12345 Bearer abcdefghijklmnopqrstuvwxyz sk-1234567890abcdefghijkl"
    clean = sanitize_text(text)
    assert "abcdef123456789" not in clean
    assert "qwertyuiop12345" not in clean
    assert "abcdefghijklmnopqrstuvwxyz" not in clean
    assert "sk-1234567890abcdefghijkl" not in clean
    assert "REDACTED" in clean
