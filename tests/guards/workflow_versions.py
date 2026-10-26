"""The readers behind the versions guard (#382), kept apart so their unit tests run them on plants.

``tests/guards/test_versions.py`` runs them over the repository; ``tests/guard_helpers/
test_workflow_versions.py`` plants every form each one must recognise and sees it found.
"""

import re
import shlex
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from typing import Any

RUNNER = "ubuntu-26.04"
SETUP_UV = "astral-sh/setup-uv@"

EXACT = re.compile(r"(\d+)\.(\d+)\.(\d+)\n")
# A Python interpreter by any name a shell finds it: python, python3, python3.13, /usr/bin/python3.
INTERPRETER = re.compile(r"(?:.*/)?python(?:\d+(?:\.\d+)*)?")
# Words that start a command without being its program (the guard-forms catalogue's Command start
# row, from yawelo-idle PR #667): shell keywords and the wrappers that run the next word.
PREFIXES = frozenset(
    {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time", "command", "exec"}
    | {"nohup", "env", "sudo", "xargs"}
)
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SEPARATORS = frozenset("();<>|&")
BACKTICKS = re.compile(r"`([^`]*)`")
# A Python minor named in a workflow string: "test (py3.13)", "python-3.13", "python3.13".
NAMED_MINOR = re.compile(r"\bpy(?:thon)?-?(\d+\.\d+)\b")
# A trove classifier naming one Python minor; "Python :: 3" and "Python :: 3 :: Only" name none.
CLASSIFIER = re.compile(r"Programming Language :: Python :: (\d+\.\d+)")


class UnreadableShellError(AssertionError):
    """A run step's line shlex cannot read: nothing in it can be judged, so it is refused."""


def runner_findings(workflow: dict[Any, Any]) -> list[str]:
    """Each job whose ``runs-on`` is anything but the one image, spelled exactly: a list, an
    expression, another case or no ``runs-on`` at all (a called workflow) is a finding."""
    jobs: dict[str, dict[str, Any]] = workflow["jobs"]
    return [
        f"{name}: {job.get('runs-on')!r}"
        for name, job in jobs.items()
        if job.get("runs-on") != RUNNER
    ]


def commands(script: str) -> Iterator[list[str]]:
    """The words of each simple command in a shell *script*, one logical line at a time (see
    ``read_line``). A heredoc's body is the program's input, not shell: it is skipped to its
    delimiter."""
    delimiter = None
    for line in script.replace("\\\n", " ").splitlines():
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        found, delimiter = read_line(BACKTICKS.sub(r"$(\1)", line))
        yield from found


def read_line(line: str) -> tuple[list[list[str]], str | None]:
    """The commands on one shell *line*, and the delimiter of a heredoc it opens. Any token made
    only of separators ends a command, a grouped ``);`` included, and a redirection drops its
    target, which is never a program (the catalogue's Grouped punctuation row: a token holding
    ``<`` or ``>`` is no separator); ``<(`` and ``>(`` open a command as ``$(`` does. The text
    inside a ``$(...)`` that shlex keeps in one word (inside double quotes) is read as commands
    too, and a backtick pair as the ``$(...)`` it means. A line shlex cannot read is refused."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError as error:
        msg = f"cannot read the shell line {line!r}: {error}"
        raise UnreadableShellError(msg) from error
    found: list[list[str]] = []
    words: list[str] = []
    delimiter = None
    target = False
    for before, token in zip(["", *tokens], tokens, strict=False):
        if token and set(token) <= SEPARATORS:
            redirect = bool(set(token) & set("<>")) and "(" not in token
            if words and (not redirect or set(token) & set(");|")):
                found.append(words)
                words = []
            target = redirect
            continue
        if not target:
            words.append(token)
        elif before in {"<<", "<<-"}:
            # shlex reads <<-EOF as << and -EOF: the dash is the operator's, not the word's.
            delimiter = token.removeprefix("-")
        target = False
        for inner in substitutions(token, line):
            found.extend(commands(inner))
    if words:
        found.append(words)
    return found, delimiter


def substitutions(word: str, line: str) -> Iterator[str]:
    """The text inside each ``$(...)`` held whole in one shell *word*, brackets balanced."""
    start = word.find("$(")
    while start != -1:
        depth, end = 1, start + 2
        while depth and end < len(word):
            depth += {"(": 1, ")": -1}.get(word[end], 0)
            end += 1
        if depth:
            msg = f"cannot read the shell line {line!r}: an unclosed $( in {word!r}"
            raise UnreadableShellError(msg)
        yield word[start + 2 : end - 1]
        start = word.find("$(", end)


def program(words: list[str]) -> str | None:
    """The program a command runs: its first word past keywords, wrappers, assignments and the
    lone ``$`` shlex leaves before a command substitution's bracket."""
    for word in words:
        if word in PREFIXES or ASSIGNMENT.match(word) or word == "$":
            continue
        return word
    return None


# A Python asked for by version (``3.12``, ``cpython-3.12``, ``python3.12``), not an environment
# named by its path, which ``uv pip install --python <venv>`` takes.
VERSION_REQUEST = re.compile(r"(?:cpython-?|python)?\d")


def asks_for_a_python(words: list[str]) -> bool:
    """Whether a uv command asks for a Python by version: ``--python X``, ``-p X``,
    ``--python=X``."""
    for index, word in enumerate(words):
        if word.startswith("--python="):
            value = word.removeprefix("--python=")
        elif word in {"--python", "-p"} and index + 1 < len(words):
            value = words[index + 1]
        else:
            continue
        if VERSION_REQUEST.match(value):
            return True
    return False


def venvs_made(script: str) -> set[str]:
    """The folder each ``uv venv <folder>`` in *script* makes, as the script spells it. uv makes
    it from the pinned Python (``.python-version``), so its ``bin/`` runs that Python."""
    made = set()
    for words in commands(script):
        if program(words) != "uv" or "venv" not in words:
            continue
        after = words[words.index("venv") + 1 :]
        folders = [word for word in after if not word.startswith("-")]
        made.add(folders[0] if folders else ".venv")
    return made


def python_findings(script: str, venvs: AbstractSet[str] = frozenset()) -> list[str]:
    """Each command in *script* that runs Python other than through ``uv run``: an interpreter by
    name or path, a ``.py`` file run as a program, uv asked for a Python of its own, or a program
    the shell expands later (``$PY``, ``$(which python3)``), which cannot be judged. A program in
    the ``bin/`` of one of *venvs*, made by ``uv venv``, runs the pinned Python and is allowed."""
    found = []
    for words in commands(script):
        runs = program(words)
        if runs is None:
            continue
        if any(runs.startswith(f"{venv}/bin/") for venv in venvs):
            continue
        expanded = "$" in runs or "`" in runs
        by_uv = runs in {"uv", "uvx"} and asks_for_a_python(words)
        if INTERPRETER.fullmatch(runs) or runs.endswith(".py") or expanded or by_uv:
            found.append(" ".join(words))
    return found


def runs_uv(script: str) -> bool:
    return any(program(words) in {"uv", "uvx"} for words in commands(script))


def step_findings(workflow: dict[Any, Any]) -> list[str]:
    """Per job: Python run any way but ``uv run``, a Python shell, a second pin
    (``actions/setup-python``), and uv run before ``setup-uv`` installs the pinned one."""
    found = []
    jobs: dict[str, dict[str, Any]] = workflow["jobs"]
    shell = str(workflow.get("defaults", {}).get("run", {}).get("shell", ""))
    if "python" in shell:
        found.append(f"defaults: shell {shell!r}")
    for name, job in jobs.items():
        set_up = False
        venvs: set[str] = set()
        for index, step in enumerate(job.get("steps", [])):
            where = f"{name} step {index + 1}"
            uses = str(step.get("uses", ""))
            if uses.lower().startswith("actions/setup-python@"):
                found.append(f"{where}: {uses}")
            if uses.lower().startswith(SETUP_UV):
                set_up = True
            if "python" in str(step.get("shell", "")):
                found.append(f"{where}: shell {step['shell']!r}")
            script = step.get("run")
            if script is None:
                continue
            if set_up:
                venvs |= venvs_made(str(script))
            found.extend(f"{where}: {command}" for command in python_findings(str(script), venvs))
            if runs_uv(str(script)) and not set_up:
                found.append(f"{where}: uv before setup-uv")
    return found


def python_version_keys(node: Any, path: str = "") -> Iterator[str]:  # noqa: ANN401 - parsed YAML
    """Where a parsed workflow names a Python for an action (``python-version``, any case)."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if str(key).lower() in {"python-version", "python-version-file"}:
                yield here
            yield from python_version_keys(value, here)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from python_version_keys(item, f"{path}[{index}]")


def strings(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    """Every key and string value in a parsed workflow."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings(item)
    elif isinstance(node, str):
        yield node


def exact_version(text: str) -> tuple[int, int, int]:
    """The version in a ``.python-version`` file's *text*, which must be one exact X.Y.Z line."""
    exact = EXACT.fullmatch(text)
    if exact is None:
        msg = f".python-version holds {text!r}, not one exact X.Y.Z line"
        raise AssertionError(msg)
    major, minor, patch = exact.groups()
    return int(major), int(minor), int(patch)


def pyproject_findings(where: str, project: dict[str, Any], major: int, minor: int) -> list[str]:
    """Each place a parsed pyproject names a Python minor other than *major*.*minor*: its
    ``requires-python`` (a missing one too), a Python classifier, ruff's and mypy's targets."""
    found = []
    requires = project.get("project", {}).get("requires-python")
    if requires != f">={major}.{minor}":
        found.append(f"{where}: requires-python {requires}")
    for classifier in project.get("project", {}).get("classifiers", []):
        named = CLASSIFIER.fullmatch(classifier)
        if named and named[1] != f"{major}.{minor}":
            found.append(f"{where}: classifier {classifier}")
    tool = project.get("tool", {})
    if "ruff" in tool and tool["ruff"].get("target-version") != f"py{major}{minor}":
        found.append(f"{where}: ruff target-version {tool['ruff'].get('target-version')}")
    if "mypy" in tool and tool["mypy"].get("python_version") != f"{major}.{minor}":
        found.append(f"{where}: mypy python_version {tool['mypy'].get('python_version')}")
    return found
