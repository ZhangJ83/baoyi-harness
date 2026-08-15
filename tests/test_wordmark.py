from agent.wordmark import wordmark


def test_wordmark_is_a_multiline_raster_when_lisu_is_available():
    mark = wordmark()
    assert "\n" in mark.plain
    assert "▀" in mark.plain
