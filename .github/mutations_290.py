"""#290 AC6: one realistic defect per moved property, in the code that property checks.

Each row: id -> (source file, anchor, replacement, the unit file holding the stand-in, the
property's name). PREDICTION, written before any run (2026-10-13): every mutation turns its unit
file RED with the stand-in of that name among the failures, and turns the property of that name
RED in the properties suite on CI. Shared by mutate.py (unit, here) and the CI workflow.
"""

P = "packages/steadyhand/src/steadyhand"
I = "packages/steadyhand-idx/src/steadyhand_idx"
E, X = "tests/engine", "tests/idx"

MUTATIONS = {
    "M01": (f"{P}/money.py", ".to_integral_value(rounding=rounding.value)", ".to_integral_value(rounding=ROUND_FLOOR)", f"{E}/test_money.py", "test_up_and_down_bracket_the_exact_value"),
    "M02": (f"{I}/fees.py", "/ _HUNDRED, Rounding.UP)\n        levy", "/ _HUNDRED, Rounding.DOWN)\n        levy", f"{X}/test_fees.py", "test_costs_round_once_against_the_trader"),
    "M03": (f"{I}/ticks.py", "price + self.tick_for(price) - remainder", "price + self.tick_for(price)", f"{X}/test_ticks.py", "test_rounding_is_tight_and_valid"),
    "M04": (f"{I}/rules.py", "high = ticks.round_down(math.floor(top))", "high = ticks.round_down(math.ceil(top))", f"{X}/test_rules.py", "test_band_edges_are_the_widest_valid_prices_inside_the_band"),
    "M05": (f"{P}/income.py", "    return gross - rules.dividend_tax(gross, on=on)", "    return gross + rules.dividend_tax(gross, on=on)", f"{E}/test_income_received.py", "test_take_home_is_never_more_than_gross"),
    "M06": (f"{P}/metrics.py", "        if report.unit_price > peak:\n", "        if report.unit_price < peak:\n", f"{E}/test_metrics.py", "test_the_drawdown_matches_every_pair_checked"),
    "M07": (f"{P}/risk.py", "self.units + ratio_down(amount.amount, self.price), self.price", "self.units + amount.amount, self.price", f"{E}/test_risk.py", "test_a_deposit_never_moves_the_price"),
    "M08": (f"{P}/portfolio.py", "quantity = held.quantity * split.new_shares // split.old_shares", "quantity = held.quantity * split.old_shares // split.new_shares", f"{E}/test_portfolio_actions.py", "test_splits_keep_the_total_cost_basis"),
    "M09": (f"{P}/income.py", "    return Money(numerator * shares * old * scale // (denominator * new), currency)", "    return Money(-(-numerator * shares * old * scale // (denominator * new)), currency)", f"{E}/test_income_run_rate.py", "test_without_a_later_split_a_dividend_is_priced_as_the_engine_credits_it"),
    "M10": (f"{P}/income.py", "            old *= action.old_shares\n            new *= action.new_shares\n", "            old, new = action.old_shares, action.new_shares\n", f"{E}/test_income_run_rate.py", "test_restating_across_two_splits_equals_restating_across_their_combined_ratio"),
    "M11": (f"{P}/snapshot.py", "        tuple(_read_protection(p) for p in _list(protections)),\n", "        (),\n", f"{E}/test_snapshot.py", "test_every_state_reads_back_equal_and_writes_the_same_json_again"),
    "M12": (f"{P}/snapshot.py", 'notes=tuple(_read_note(note) for note in _list(field["notes"])),', "notes=(),", f"{E}/test_snapshot.py", "test_every_report_reads_back_equal_and_writes_the_same_json_again"),
    "M13": (f"{P}/snapshot.py", "_read_money(amount), _date(settles_on))", "_read_money(amount), _date(day))", f"{E}/test_snapshot.py", "test_a_restored_portfolio_behaves_as_the_one_it_was_saved_from"),
    "M14": (f"{P}/sizing.py", "lots = abs((target - current).amount) // (price * lot).amount", "lots = -(-abs((target - current).amount) // (price * lot).amount)", f"{E}/test_sizing.py", "test_orders_are_whole_lots_that_never_overshoot_the_target"),
    "M15": (f"{P}/strategies/buy_and_hold.py", "buying = chosen & view.tradable.buyable", "buying = chosen", f"{E}/test_buy_and_hold.py", "test_it_never_sells_and_buys_only_its_set"),
    "M16": (f"{P}/strategies/dividend_growth.py", "if memory.get(_YEAR_KEY) != str(view.today.year):", "if _YEAR_KEY not in memory:", f"{E}/test_dividend_growth.py", "test_it_reviews_on_no_day_but_the_first_and_each_new_years_first"),
    "M17": (f"{P}/exemption.py", "owed = self._rules.dividend_tax(amount, on=claim.pay_date)", "owed = self._rules.dividend_tax(claim.gross, on=claim.pay_date)", f"{E}/test_exemption.py", "test_a_claims_tax_never_exceeds_its_full_tax_plus_one_unit_per_extra_booking"),
    "M18": (f"{P}/income.py", "if rate.annual_gross.amount == 0 or holdings_value.amount == 0:", "if holdings_value.amount == 0:", f"{E}/test_income_projection.py", "test_a_zero_run_rate_cannot_be_projected"),
    "M19": (f"{P}/income.py", "self._tax(monthly) + self.contribution).amount", "self._tax(monthly) - self.contribution).amount", f"{E}/test_income_projection.py", "test_a_larger_contribution_never_takes_longer"),
    "M20": (f"{P}/income.py", "(Scenario.BASE, rate.annual_gross, min(measured, BASE_GROWTH_CAP)),", "(Scenario.BASE, rate.annual_gross, measured),", f"{E}/test_income_projection.py", "test_pessimistic_never_beats_base_and_base_never_beats_optimistic"),
    "M21": (f"{P}/broker/simulated.py", "        if daily.amount > 0:\n", "        if daily.amount >= 0:\n", f"{E}/test_engine.py", "test_every_day_keeps_cash_whole_and_the_value_adding_up"),
    "M22": (f"{P}/portfolio.py", "chain, ledger = (movement, chain), None", "chain, ledger = (movement, chain), ledger", f"{E}/test_ledger_booking.py", "test_every_snapshot_in_a_tree_of_bookings_keeps_its_own_ledger"),
    "M23": (f"{P}/strategies/monthly_savings.py", "reserve = (due - 1) * instalment if due > 0 else 0", "reserve = (due - 2) * instalment if due > 1 else 0", f"{E}/test_monthly_savings.py", "test_the_reserve_for_the_instalments_still_due_is_never_spent_before_its_month"),
    "M24": (f"{P}/portfolio.py", "        cost = fill.gross + fill.costs.total\n", "        cost = fill.gross\n", f"{E}/test_portfolio_properties.py", "test_cash_and_share_invariants"),
    "M25": (f"{P}/portfolio.py", "        proceeds = fill.gross - fill.costs.total\n", "        proceeds = fill.gross\n", f"{E}/test_portfolio_properties.py", "test_a_round_trip_at_an_unchanged_price_loses_exactly_the_costs"),
    "M26": (f"{P}/portfolio.py", "pool = self._open if last is None or on >= last else self.ledger", "pool = self._open", f"{E}/test_portfolio_properties.py", "test_the_kept_totals_agree_with_the_whole_ledger_on_every_day"),
    "M27": (f"{P}/broker/simulated.py", "while quantity > 0 and self._cost(price * quantity) > available:", "while quantity > 0 and price * quantity > available:", f"{E}/test_simulated_broker.py", "test_the_settled_cash_is_never_negative_from_the_trade_to_its_settlement"),
    "M28": (f"{P}/broker/simulated.py", "        price = self._rules.round_to_tick(instrument, slipped, order.side, day)\n", "        price = slipped\n", f"{E}/test_simulated_broker.py", "test_fills_keep_cash_whole_lots_ticks_and_bands"),
    "M29": (f"{P}/view.py", "if split.ex_date >= dividend.ex_date]", "if split.ex_date > dividend.ex_date]", f"{E}/test_view.py", "test_nothing_after_today_is_returned_and_each_dividend_is_restated_by_its_own_splits"),
    "M30": (f"{I}/factor.py", "found.nearest(price * factor)) for price in recorded]", "found.nearest(price / factor)) for price in recorded]", f"{X}/test_factor.py", "test_a_proven_factor_restores_the_true_prices"),
}
