"""Every note and term key is a stable constant, defined once and used (M4 §7, T1 §3.1).

The training sub-project attaches lessons to keys, so a key must never be reworded or reused,
and no note may be built from a literal that could drift from its constant. The keys are read
from the key modules of both packages and the ``Note(...)`` calls from every module of both,
all by walking the AST (``key_walk.py``), so a comment or a docstring that mentions a key is
never a finding.
"""

import re
from pathlib import Path

import pytest
from key_walk import (
    ENGINE,
    IDX,
    KEY_MODULES,
    NOTE_MODULES,
    SAVED_NOTE_READERS,
    TERM_MODULE,
    TERM_PREFIX,
    constants_in,
    key_constants,
    note_keys,
    package_sources,
    string_literals,
)

KEY = r"[a-z]+(\.[a-z_]+)+"
KNOWN = {
    "corporate.split.fraction_dropped",
    "data.bar.missing",
    "data.bar.refused",
    "income.growth.short_history",
    "income.projection.costs_ignored",
    "universe.survivorship.gap",
    "term.run_rate",
}


def test_the_constant_detector() -> None:
    source = "A = 'x.y'\n_B = 'z.w'\nC: str = 'c.d'\nD = 2\nE = F = 'e.f'\n"
    assert key_constants(source) == [("A", "x.y"), ("C", "c.d"), ("E", "e.f"), ("F", "e.f")]


def test_the_note_detector() -> None:
    source = (
        "Note(KEY, 't')\n"
        "notes.Note(notes.OTHER, 't')\n"
        "Note(key=NAMED, text='t')\n"
        "Note('income.x', 't')\n"
        "Note(f'{a}.b', 't')\n"
        "Note(make(), 't')\n"
        "Note()\n"
        "Other('income.y', 't')\n"
    )
    assert note_keys(source) == [
        "KEY",
        "OTHER",
        "NAMED",
        "line 4: key is not a constant",
        "line 5: key is not a constant",
        "line 6: key is not a constant",
        "line 7: key is not a constant",
    ]


def test_the_note_detector_leaves_out_only_the_reader_it_is_given() -> None:
    source = (
        "def _read(saved):\n"
        "    return Note(str(saved), 't')\n"
        "def other(saved):\n"
        "    return Note(str(saved), 't')\n"
    )
    assert note_keys(source) == [
        "line 2: key is not a constant",
        "line 4: key is not a constant",
    ]
    assert note_keys(source, reader="_read") == ["line 4: key is not a constant"]


@pytest.mark.parametrize("path", sorted(SAVED_NOTE_READERS), ids=lambda path: path.name)
def test_each_saved_note_reader_is_its_modules_one_note_built_from_saved_data(path: Path) -> None:
    names = {name for name, _ in constants_in(NOTE_MODULES)}
    source = path.read_text(encoding="utf-8")
    assert len([key for key in note_keys(source) if key not in names]) == 1
    read = note_keys(source, reader=SAVED_NOTE_READERS[path])
    assert [key for key in read if key not in names] == []


def test_the_literal_detector() -> None:
    source = '"""Mentions income.x in passing."""\nK = "income.x"\nNote("income.y", "t")\n'
    assert {"income.x", "income.y"} <= set(string_literals(source))
    assert "income.x" not in string_literals('"""Mentions income.x in passing."""\n')


def test_every_key_is_a_dotted_lowercase_identifier_named_after_itself() -> None:
    keys = constants_in(KEY_MODULES)
    assert {value for _, value in keys} >= KNOWN
    for name, value in keys:  # runtime population: the constants the reader found
        assert re.fullmatch(KEY, value), f"{name} = {value!r} is not a dotted lowercase identifier"
        assert name == value.upper().replace(".", "_"), f"{name} is not named after {value!r}"


def test_terms_and_only_terms_carry_the_term_prefix() -> None:
    notes = [value for _, value in constants_in(NOTE_MODULES)]
    terms = [value for _, value in constants_in((TERM_MODULE,))]
    assert len(notes) >= 6
    assert len(terms) >= 30
    assert [value for value in notes if value.startswith(TERM_PREFIX)] == []
    assert [value for value in terms if not value.startswith(TERM_PREFIX)] == []


def test_no_key_is_defined_twice() -> None:
    values = [value for _, value in constants_in(KEY_MODULES)]
    assert len(set(values)) == len(values) >= len(KNOWN)
    elsewhere = {
        path.relative_to(ENGINE.parents[2]).as_posix(): sorted(
            set(values) & set(string_literals(source))
        )
        for path, source in package_sources().items()
        if path not in KEY_MODULES
    }
    assert len(elsewhere) >= 30, "fewer than 30 of the packages' modules were found"
    assert any(  # runtime population: the modules the walk found; a disjunction
        name.startswith("steadyhand-idx/") for name in elsewhere
    )
    assert {name: found for name, found in elsewhere.items() if found} == {}


def test_every_note_is_built_from_a_note_key_and_every_note_key_is_used() -> None:
    names = {name for name, _ in constants_in(NOTE_MODULES)}
    sources = package_sources()
    used = [
        key
        for path, source in sources.items()
        for key in note_keys(source, reader=SAVED_NOTE_READERS.get(path))
    ]
    assert len(used) >= len(names) >= 6, "fewer Note(...) calls in the packages than note keys"
    assert any(  # runtime population: the sources the walk found; a disjunction
        note_keys(source) for path, source in sources.items() if IDX in path.parents
    )
    assert sorted(set(used) - names) == []
    assert sorted(names - set(used)) == []
