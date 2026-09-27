"""The shipped course file: the eight modules of T1 spec §4.3, in order."""

from steadyhand.training import Catalogue
from steadyhand_idx.training import COURSE


def test_the_course_lists_the_eight_modules_in_order() -> None:
    modules = Catalogue.load([], COURSE).course()
    assert [(module.number, module.slug, module.title) for module in modules] == [
        (1, "start-here", "Start here"),
        (2, "shares-and-dividends", "Shares and dividends"),
        (3, "how-idx-works", "How IDX works"),
        (4, "costs-and-tax", "Costs and tax"),
        (5, "risk", "Risk, and why backtests mislead"),
        (6, "using-steadyhand", "Using steadyhand"),
        (7, "income-goal", "The income goal"),
        (8, "strategies", "Strategies"),
    ]
