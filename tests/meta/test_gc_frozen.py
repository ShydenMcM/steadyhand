"""Everything built while collecting is out of the garbage collector's reach (#302).

A full collection walks every tracked object, so with the whole collected suite tracked it cost
35-442 ms and landed on whichever test was running: a 2 ms test read 77 ms. Freezing once
collection finishes leaves each test paying only for the garbage it makes itself.
"""

import gc

import pytest


def test_the_collected_test_itself_is_frozen(request: pytest.FixtureRequest) -> None:
    item = request.node
    # The collector would walk it if it were not frozen, so its absence below means frozen.
    assert gc.is_tracked(item)
    walked = {id(tracked) for tracked in gc.get_objects()}
    assert id(item) not in walked
