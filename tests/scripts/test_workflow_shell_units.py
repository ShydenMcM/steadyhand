"""Which lines of a workflow's shell step can run, read by tree-sitter-bash (#384).

bash's DEBUG trap fires once per simple command, at the command's LAST line when it is continued
over several (measured on bash 3.2, 2026-10-22: ``x=$(echo two \\`` then ``three)`` traced 3, not
2), and never for a line that holds only a keyword or a bare case pattern. So a unit is a line
RANGE: it ran if any traced line falls in it.
"""

import pytest

from workflow_coverage import ShellParseError, shell_units


def test_a_simple_command_is_its_own_line() -> None:
    assert shell_units("echo one\necho two\n") == [(1, 1), (2, 2)]


def test_a_continued_command_spans_every_line_it_is_written_on() -> None:
    assert shell_units("x=$(echo two \\\n  three)\n") == [(1, 2), (1, 2)]


def test_keyword_lines_hold_no_unit() -> None:
    script = 'if [ "$x" = y ]; then\n  echo yes\nelse\n  echo no\nfi\n'
    assert shell_units(script) == [(1, 1), (2, 2), (4, 4)]


def test_a_case_fires_on_its_header_and_a_bare_pattern_holds_no_unit() -> None:
    script = 'case "$x" in\n  nope) ;;\n  *) echo star ;;\nesac\n'
    assert shell_units(script) == [(1, 1), (3, 3)]


def test_a_heredoc_body_belongs_to_its_command() -> None:
    assert shell_units("cat <<'H'\nbody\nH\necho after\n") == [(1, 3), (4, 4)]


def test_a_loop_fires_on_its_header_and_its_body() -> None:
    script = "for i in 1 2; do\n  echo $i\ndone\nwhile read -r l; do\n  echo $l\ndone\n"
    assert shell_units(script) == [(1, 1), (2, 2), (4, 4), (5, 5)]


def test_a_c_style_loop_fires_on_its_header() -> None:
    assert shell_units("for ((i = 0; i < 2; i++)); do\n  echo $i\ndone\n") == [(1, 1), (2, 2)]


def test_a_function_body_is_a_unit_and_its_definition_line_is_not() -> None:
    script = "f() {\n  echo in\n}\nf\n"
    assert shell_units(script) == [(2, 2), (4, 4)]


def test_every_command_of_a_pipeline_and_a_list_is_a_unit() -> None:
    assert shell_units("a | b && c\n") == [(1, 1), (1, 1), (1, 1)]


def test_declarations_unsets_and_bare_assignments_are_units() -> None:
    script = "export A=1\nlocal b\nunset A\nB=2 C=3\nD=4\n"
    assert shell_units(script) == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]


def test_a_command_with_an_assignment_prefix_is_one_unit() -> None:
    assert shell_units("A=1 echo $A\n") == [(1, 1)]


def test_a_double_bracket_test_and_a_negation_are_units() -> None:
    assert shell_units("[[ -f x ]]\n! grep -q a b\n") == [(1, 1), (2, 2)]


def test_an_arithmetic_command_is_a_unit() -> None:
    """``(( ))`` fires the DEBUG trap; tree-sitter-bash reads it as a compound statement."""
    assert shell_units("(( n += 1 ))\n") == [(1, 1)]


def test_comments_and_blank_lines_hold_no_unit() -> None:
    assert shell_units("# a comment\n\necho x  # trailing\n") == [(3, 3)]


def test_a_script_that_does_not_parse_is_refused() -> None:
    with pytest.raises(ShellParseError, match=r"line 1"):
        shell_units("if then fi (\n")


def test_a_loop_with_a_brace_body_is_refused_not_guessed() -> None:
    """tree-sitter-bash reads no `for ...; { }` loop, so it cannot be judged."""
    with pytest.raises(ShellParseError, match=r"does not parse at line 2"):
        shell_units("echo a\nfor i in 1; { echo $i; }\n")


def test_a_select_fires_on_its_header() -> None:
    assert shell_units("select x in a b; do\n  break\ndone\n") == [(1, 1), (2, 2)]


def test_a_header_continued_over_lines_spans_them() -> None:
    assert shell_units("for i in a \\\n  b; do\n  echo $i\ndone\n") == [(1, 2), (3, 3)]


def test_an_empty_script_has_no_unit() -> None:
    assert shell_units("") == []
