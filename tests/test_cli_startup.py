import io
import os
import sys
from contextlib import redirect_stderr
from unittest.mock import patch

from agent import main


def test_single_shot_missing_credential_fails_closed():
    err = io.StringIO()
    with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "PROVIDER": "openai"}, clear=False), patch.object(sys, "argv", ["xiaopu", "make", "a", "deck"]), redirect_stderr(err):
        assert main.main() == 2
    assert "CONFIGURATION ERROR" in err.getvalue()
    assert "OPENAI_API_KEY" in err.getvalue()
    assert "offline" not in err.getvalue().lower()


def test_provider_credential_name_tracks_selected_provider():
    with patch.dict(os.environ, {"PROVIDER": "anthropic"}, clear=False):
        assert main.config.provider_credential_name() == "ANTHROPIC_API_KEY"
