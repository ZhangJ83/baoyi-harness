from agent.wordmark import _font_path, wordmark


def test_wordmark_fallback_when_no_font(monkeypatch):
    monkeypatch.setattr("agent.wordmark._font_path", lambda: None)
    mark = wordmark()
    assert mark.plain == "报一"


def test_wordmark_renders_or_falls_back():
    mark = wordmark()
    if _font_path() is not None:
        assert "\n" in mark.plain
        assert "▀" in mark.plain
    else:
        assert mark.plain == "报一"
