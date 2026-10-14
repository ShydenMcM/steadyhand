"""``steadyhand_idx.training.catalogue()`` reads the shipped lessons once per process (#282).

The lesson files inside an installed package do not change while it runs, and a ``Catalogue`` is
read-only (frozen lessons and modules, held in tuples), so every command in one process shares
one load. Before this, a run of nine commands read the 484 lesson files eleven times.
"""

from steadyhand.training import LESSONS as ENGINE_LESSONS
from steadyhand.training import Catalogue
from steadyhand_idx.training import COURSE, LESSONS, catalogue


def test_the_shipped_catalogue_is_loaded_once_per_process() -> None:
    assert catalogue() is catalogue()


def test_the_shared_catalogue_holds_what_a_fresh_load_reads() -> None:
    fresh = Catalogue.load([ENGINE_LESSONS, LESSONS], COURSE)
    assert catalogue().lessons() == fresh.lessons()
    assert catalogue().course() == fresh.course()
