+++
id = "tax.exemption"
title = "The dividend tax exemption"
summary = "A resident individual's dividend is free of tax if it is reinvested in Indonesia in time and kept invested."
explains = ["term.claim_to_reinvest", "term.claim_protected", "exemption.deadline_missed"]
module = "costs-and-tax"
position = 5
see_also = ["tax.dividend"]
sources = ["docs/research/t-tax.md §3", "docs/research/t-tax.md §4", "docs/research/t-tax.md §5", "docs/superpowers/specs/2026-09-26-m4-income-design.md §6"]
+++

The 10% dividend tax is not due on a dividend that you invest in Indonesia. The rules, for a
resident individual:

- **The deadline.** Invest it by the end of March of the year after you received it. A dividend
  received in May 2026 must be invested by 31 March 2027.
- **What counts.** Buying shares on IDX qualifies, and so do several other Indonesian
  investments. Selling one qualifying investment to buy another keeps the exemption.
- **How long.** Keep it invested for at least three tax years. The rule counts them from the
  year the dividend was received, but whether that year itself counts is not settled, so the
  careful reading keeps it invested to the end of the second year after the one you invested
  in.
- **Paperwork.** You report the investment once a year through the tax office's online portal.
  The report is a condition of the exemption, not a formality.
- **Part of it.** Invest only part of a dividend and only that part is exempt; 10% is due on the
  rest.

If you miss a condition, the tax is owed as of the day you received the dividend, and penalties
can apply.

steadyhand cannot see your paperwork, or any investment you hold outside it. That is why it books
the full 10% by default: its income figures can only be too low, never too high.

With the exemption switch on, steadyhand books no tax when a dividend is paid. It opens a claim
for the dividend instead, and every figure the claim gives is an estimate:

- **To reinvest** is the part of the dividend not yet invested. A dividend whose ex-date is
  before 17 February 2021, when the rule came into force, gets no claim and is taxed as usual.
- **Protected** is a part that a purchase has reinvested, with the last day it must stay
  invested: 31 December of the second year after the purchase. A purchase counts towards the
  claims that are open on its day, oldest dividend first, up to its value before costs.

If part of a dividend is still to reinvest after its deadline, steadyhand books 10% of that part
on the first trading day after the deadline, at the rate in force when the dividend was paid. It
cannot book tax on a past date, so a note records that the tax was owed from the pay date.

This lesson describes the rules; whether they apply to you, and how, is a question for you or a
tax adviser.
