"""Every property draws 500 fresh cases with no deadline (#290; the profile: hypothesis_profile.py).

CI is where it matters: there Hypothesis would fix the seed by itself. The second test reads the
mark the suites plugin refuses a property by, off real properties.
"""

import test_engine_money
import test_engine_portfolio_properties
from hypothesis import settings
from suites import is_property


def test_every_property_draws_500_fresh_cases_with_no_deadline() -> None:
    loaded = settings.default
    assert loaded is not None
    assert (loaded.max_examples, loaded.derandomize, loaded.deadline, loaded.print_blob) == (
        500,
        False,
        None,
        True,
    )


def test_the_suites_plugin_knows_a_real_property_by_hypothesis_s_own_mark() -> None:
    # The plugin's unit tests plant the mark; this reads it off real @given functions.
    assert is_property(test_engine_money.test_up_and_down_bracket_the_exact_value)
    assert is_property(test_engine_portfolio_properties.test_cash_and_share_invariants)
    assert not is_property(test_every_property_draws_500_fresh_cases_with_no_deadline)
