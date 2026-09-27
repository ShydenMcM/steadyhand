+++
id = "start.explanations"
title = "How the explanations work"
summary = "How much steadyhand explains under its output, and how to change it or read a lesson."
explains = []
module = "start-here"
position = 2
see_also = ["start.welcome"]
sources = ["docs/superpowers/specs/2026-09-27-training-design.md §6"]
+++

The first time you set steadyhand up, it asks whether you would like explanations as you go and,
if so, how much investing experience you have. Your answer sets how much it explains under
each command's output:

- **New**: a one-line explanation of each figure and note the output showed, with the lesson to
  read for more.
- **Some**: just the names of the lessons to read.
- **Experienced**: nothing extra.
- **Off**: no explanations at all.

Your level changes only how much is explained. It never changes what steadyhand shows, suggests
or does.

You can change it at any time: `steadyhand-idx training` shows the setting, and
`steadyhand-idx training new`, `some`, `experienced` or `off` changes it.

The lessons also form a course. `steadyhand-idx learn` lists its modules in order, and
`steadyhand-idx learn <lesson>` prints one lesson, such as `steadyhand-idx learn
income.run_rate`.
