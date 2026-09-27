"""Running ``steadyhand-idx`` in-process, as the console script does, with a fixed clock (M5 spec
§9.1). Nothing of steadyhand's is stubbed: the tests pass ``main`` the same kind of ``World`` the
console script builds, with text streams, an environment naming a temporary data directory, a
fixed clock and a data source."""

import io
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from steadyhand import DataSource
from steadyhand_idx.cli import SourceFactory, World, main

NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
"""18:00 UTC is 01:00 on 28 September in Jakarta, so 'today' is the Jakarta date."""


@contextmanager
def no_data(folder: Path) -> Iterator[DataSource]:
    """A source for commands that must not read market data: opening it fails the test."""
    msg = f"this command opened the data source in {folder}"
    raise AssertionError(msg)
    yield  # unreachable: it makes this a generator, as @contextmanager needs


class Result(NamedTuple):
    code: int
    out: str
    err: str


@dataclass(frozen=True, slots=True)
class Cli:
    """``steadyhand-idx`` with its data directory at ``home``."""

    home: Path
    source: SourceFactory = no_data
    now: datetime = NOW

    @property
    def config(self) -> Path:
        return self.home / "steadyhand.toml"

    def __call__(self, *argv: str, stdin: str = "") -> Result:
        out, err = io.StringIO(), io.StringIO()
        env = {"STEADYHAND_HOME": str(self.home)}
        world = World(io.StringIO(stdin), out, err, env, lambda: self.now, self.source)
        code = main(list(argv), world)
        return Result(code, out.getvalue(), err.getvalue())

    def init(self, *, training: str = "new", exemption: str = "off") -> Result:
        """``init`` answered by its flags, as a script runs it."""
        result = self(
            "init", "--training", training, "--exemption", exemption, stdin="I understand\n"
        )
        assert result.code == 0, result.err
        return result
