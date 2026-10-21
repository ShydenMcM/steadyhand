"""The CLI test world's own stand-ins (#374): each is run, for what it is."""

from pathlib import Path

import pytest
from cli_world import no_data


def test_a_command_that_opens_no_data_fails_naming_the_folder(tmp_path: Path) -> None:
    """The default source of a world for commands that must not read market data: it is a
    tripwire, so opening it must fail, never hand back a source."""
    with (
        pytest.raises(AssertionError, match="this command opened the data source in"),
        no_data(tmp_path),
    ):
        pass
