"""Note: a stable key and a sentence (M4 spec §7)."""

import pytest

from steadyhand.notes import INCOME_GROWTH_SHORT_HISTORY, Note


def test_a_note_keeps_its_key_and_text() -> None:
    note = Note(INCOME_GROWTH_SHORT_HISTORY, "BBCA: taken as 0%")
    assert (note.key, note.text) == ("income.growth.short_history", "BBCA: taken as 0%")


@pytest.mark.parametrize("key", ["income", "Income.growth", "income.growth.", "income..growth"])
def test_a_key_is_a_dotted_lowercase_identifier(key: str) -> None:
    with pytest.raises(ValueError, match=r"^a note key is a dotted lowercase identifier, got '"):
        Note(key, "some text")


def test_a_note_has_words() -> None:
    with pytest.raises(ValueError, match=r"^the note income\.growth\.short_history has no text$"):
        Note(INCOME_GROWTH_SHORT_HISTORY, "  ")


def test_a_key_and_a_text_are_strings() -> None:
    with pytest.raises(TypeError, match=r"^key must be a str, got int$"):
        Note(1, "some text")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^text must be a str, got NoneType$"):
        Note(INCOME_GROWTH_SHORT_HISTORY, None)  # type: ignore[arg-type]
