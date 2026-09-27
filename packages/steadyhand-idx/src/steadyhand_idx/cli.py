"""The ``steadyhand-idx`` command: its entry point, its commands and its exit codes (M5 spec §3.2,
§8, core spec §9.6).

``main`` takes everything from outside as an argument (the streams, the environment, the clock
and the data source, together a ``World``), so tests call it in-process with recorded data and a
fixed clock, and there is no test-only branch here. A command's output goes to ``stdout``; every
error goes to ``stderr``, so a script that captures a report never captures an error in it.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn, TextIO

from steadyhand import DISCLAIMER, DataSource
from steadyhand_idx import __version__
from steadyhand_idx._datafile import DataFileError
from steadyhand_idx.cache import JAKARTA, BarCache, CachedDataSource
from steadyhand_idx.config import Config, ConfigMissingError, load, starter
from steadyhand_idx.output import (
    LEVELS,
    Page,
    UnknownNameError,
    course_page,
    lesson_page,
    render,
    training_level,
    with_training_level,
)
from steadyhand_idx.paths import (
    APP,
    CONFIG_FILE,
    create_private,
    data_dir,
    make_private_dir,
    replace_private,
)
from steadyhand_idx.yahoo import YahooDataSource

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

type SourceFactory = Callable[[Path], AbstractContextManager[DataSource]]
"""Opens the data source over the data directory's cache, and closes it after the command."""

ACCEPT: Final = "I understand"
DEBUG_HINT: Final = "run again with --debug for details"


class UsageError(Exception):
    """The command line, or an answer to one of its questions, cannot be acted on."""


class ConfigRewriteError(RuntimeError):
    """``training`` wrote a configuration that no longer loads, so it put the old one back."""


EXIT_CODES: Final[tuple[tuple[type[Exception], int], ...]] = (
    (UsageError, 2),
    (ConfigMissingError, 2),
    (DataFileError, 2),
    (UnknownNameError, 2),
)
"""Each error a command raises on purpose, and its exit code (core spec §9.6). The first row
that matches wins. Anything else is unexpected, and exits 1."""


def exit_code(error: Exception) -> int:
    """The exit code for *error*: its row in ``EXIT_CODES``, or 1."""
    return next((code for kind, code in EXIT_CODES if isinstance(error, kind)), 1)


@dataclass(frozen=True, slots=True)
class World:
    """Everything a command reads or writes besides its arguments."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    env: Mapping[str, str]
    now: Callable[[], datetime]
    source: SourceFactory


@dataclass(frozen=True, slots=True)
class Context:
    """One command's arguments and the world it runs in."""

    args: argparse.Namespace
    world: World

    @property
    def data_dir(self) -> Path:
        return data_dir(self.args.data_dir, self.world.env)

    @property
    def config_path(self) -> Path:
        return self.data_dir / CONFIG_FILE

    def config(self) -> Config:
        """The configuration, which must exist: every command but the few that need none."""
        return load(self.config_path)

    def training(self) -> Mapping[str, object]:
        """The ``[training]`` table for a command that needs no configuration: the file's, when
        there is one, and otherwise none, which means ``new``."""
        if not self.config_path.exists():
            return {}
        return self.config().training

    def today(self) -> date:
        """Today in Jakarta, where the IDX trading day is counted."""
        return self.world.now().astimezone(JAKARTA).date()

    def say(self, text: str) -> None:
        self.world.stdout.write(text)

    def ask(self, question: str) -> str:
        """Print *question* and read one line of answer; the end of input is an empty answer."""
        self.say(question)
        self.world.stdout.flush()
        return self.world.stdin.readline().rstrip("\r\n")


def _parser(stdout: TextIO) -> argparse.ArgumentParser:
    """The command line. Help goes to *stdout* and a usage error becomes ``UsageError``, so
    nothing is written to ``sys.stdout`` or ``sys.stderr`` behind ``main``'s back. ``--help``
    still ends in ``SystemExit``, which ``main`` turns into its exit code."""

    class Parser(argparse.ArgumentParser):
        def print_help(self, file: SupportsWrite[str] | None = None) -> None:
            super().print_help(stdout if file is None else file)

        def error(self, message: str) -> NoReturn:
            msg = f"{message}\n{self.format_usage().rstrip()}"
            raise UsageError(msg)

    parser = Parser(prog=APP, description=DISCLAIMER)
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument("--debug", action="store_true", help="print the traceback of any error")
    parser.add_argument("--data-dir", type=Path, help="the data directory to use")
    commands = parser.add_subparsers(dest="command", metavar="command")

    init = commands.add_parser("init", help="write the configuration and accept the disclaimer")
    init.add_argument("--training", choices=LEVELS, help="answer both training questions")
    init.add_argument("--exemption", choices=("on", "off"), help="answer the exemption question")
    init.set_defaults(run=_init)

    training = commands.add_parser("training", help="show or change how much is explained")
    training.add_argument("level", nargs="?", choices=LEVELS)
    training.set_defaults(run=_training)

    learn = commands.add_parser("learn", help="list the lessons, or read one")
    learn.add_argument("lesson", nargs="?")
    learn.set_defaults(run=_learn)
    return parser


def main(argv: Sequence[str], world: World) -> int:
    """Run the command *argv* names in *world* and return its exit code (M5 spec §3.2, §8)."""
    debug = "--debug" in argv
    try:
        world.stdout.write(_dispatch(_parser(world.stdout).parse_args(argv), world))
    except SystemExit as done:
        return int(done.code or 0)
    except Exception as error:  # noqa: BLE001 - every error ends in one line and an exit code
        code = exit_code(error)
        world.stderr.write(f"{APP}: {error}\n")
        if debug:
            world.stderr.write("".join(traceback.format_exception(error)))
        elif code == 1:
            world.stderr.write(f"{DEBUG_HINT}\n")
        return code
    return 0


def _dispatch(args: argparse.Namespace, world: World) -> str:
    if args.version:
        return f"{APP} {__version__}\n"
    if args.command is None:
        msg = f"choose a command; {APP} --help lists them"
        raise UsageError(msg)
    command: Callable[[Context], str] = args.run
    return command(Context(args, world))


def run() -> NoReturn:
    """The console script: ``main`` with the real streams, environment, clock and Yahoo."""
    world = World(sys.stdin, sys.stdout, sys.stderr, os.environ, _now, open_source)
    sys.exit(main(sys.argv[1:], world))


def _now() -> datetime:
    return datetime.now(UTC)


@contextmanager
def open_source(folder: Path) -> Iterator[DataSource]:
    """Yahoo through the bar cache in the data directory, closed when the command ends."""
    with BarCache(folder / "cache.sqlite") as cache:
        yield CachedDataSource(YahooDataSource(), cache)


def _init(ctx: Context) -> str:
    """Accept the disclaimer, answer three questions, and write the configuration (M5 §5.1)."""
    path = ctx.config_path
    if path.exists():
        msg = f"{path} already exists, and init never overwrites it; edit it instead"
        raise UsageError(msg)
    ctx.say(f"{DISCLAIMER}\n\n")
    if ctx.ask(f"Type '{ACCEPT}' to accept this and continue: ") != ACCEPT:
        msg = "the disclaimer was not accepted, so nothing was written"
        raise UsageError(msg)
    level = ctx.args.training or _ask_training(ctx)
    exemption = (ctx.args.exemption or _ask_exemption(ctx)) == "on"
    make_private_dir(ctx.data_dir)
    create_private(path, starter(level, exemption=exemption, accepted=ctx.today()))
    page = Page()
    page.add(f"Wrote {path}")
    page.add()
    page.add(
        "Before your first backtest, set your starting cash ([account] starting_cash_idr), your "
        "income goal ([goal] monthly_income_target_idr) and your LQ45 file ([universe] "
        "lq45_members) there. docs/lq45-members.md says where IDX publishes each LQ45 list."
    )
    return render(page, {"level": level})


def _ask_training(ctx: Context) -> str:
    """T1 spec §6 item 1's two questions."""
    wanted = ctx.ask("Would you like explanations as you go? [Y/n] ").strip().lower()
    if wanted in ("n", "no"):
        return "off"
    if wanted not in ("", "y", "yes"):
        msg = f"answer y or n, not {wanted!r}; nothing was written"
        raise UsageError(msg)
    question = "How much investing experience do you have? 1 New / 2 Some / 3 Experienced [1] "
    experience = ctx.ask(question).strip()
    levels = {"": "new", "1": "new", "2": "some", "3": "experienced"}
    if experience not in levels:
        msg = f"answer 1, 2 or 3, not {experience!r}; nothing was written"
        raise UsageError(msg)
    return levels[experience]


def _ask_exemption(ctx: Context) -> str:
    ctx.say(
        "The dividend reinvestment exemption: a resident individual's dividend is free of the 10% "
        "tax if it is reinvested in Indonesia in time and kept invested. steadyhand can estimate "
        "it for you; it cannot claim it.\n"
    )
    answer = ctx.ask("Claim the dividend reinvestment exemption? [y/N] ").strip().lower()
    if answer in ("", "n", "no"):
        return "off"
    if answer in ("y", "yes"):
        return "on"
    msg = f"answer y or n, not {answer!r}; nothing was written"
    raise UsageError(msg)


def _training(ctx: Context) -> str:
    """Show the training level, or change only its line of the configuration (M5 spec §5.2)."""
    config = ctx.config()
    current = training_level(config.training)
    page = Page()
    wanted = ctx.args.level
    if wanted is None:
        page.add(f"Training level: {current}")
        page.add(f"Change it with: {APP} training {'|'.join(LEVELS)}")
        return render(page, config.training)
    path = config.path
    original = path.read_text(encoding="utf-8")
    replace_private(path, with_training_level(original, wanted))
    try:
        changed = load(path)
        training_level(changed.training)
    except Exception as error:
        replace_private(path, original)
        msg = f"could not change the training level ({error}); {path.name} is unchanged"
        raise ConfigRewriteError(msg) from error
    page.add(f"Training level: {wanted} (was {current})")
    return render(page, changed.training)


def _learn(ctx: Context) -> str:
    """The course, or one lesson (T1 spec §6 item 3)."""
    page = course_page() if ctx.args.lesson is None else lesson_page(ctx.args.lesson)
    return render(page, ctx.training())
