# CLAUDE.md

An urbanization study (written Parts in `docs/deliverables/`) and its proof of concept (`poc/`) for Le Slip Français. [README.md](README.md) maps the repo; [poc/README.md](poc/README.md) explains the PoC, its marts and its tests.

## Words

Use the words of [CONTEXT.md](CONTEXT.md) in code, docs, commits and replies. Every report figure is defined in `governance/glossary.csv`: read the term before writing a rule that computes it, and when a new business rule needs a new word, add the glossary term (definition and owner) in the same change.

## Work

- Work comes from GitHub issues: #1 is the parent spec with the user stories; each sub-issue holds its acceptance criteria. Commit titles end with the issue number, e.g. `Add Inventory Optimization mart: ... (#12)`, and the body says what changed in plain words.
- Every new mart column goes in `governance/marts.csv` linked to a glossary term; `analysis/test_governance.py` fails otherwise.
- A threshold or tolerance is a dbt var in `poc/dbt/dbt_project.yml`, with a comment naming the Part it comes from or saying it is our assumption. A generator assumption is a named constant at the top of `poc/generate.py` and a row in the assumptions table of `poc/README.md`.
- PoC tests check the marts against the generated source files, computing the expected figure independently of the dbt SQL. To test one case (a stockout, a late source), change the source files in the test so it knows its exact case.
- The dashboard reads marts only, through `read()` in `poc/dashboard/sales.py`.
- When a mart, a rule or a test changes, update its table or bullet in `poc/README.md` in the same change.

## Data

Synthetic only, fixed seed. People are fake: names from short lists, emails on `example.com`, `example.org`, `example.net`. Fields that Part 6 marks "drop" are never generated.

## Writing the Parts and READMEs

Write for a business reader in plain English, with short sentences and the glossary's words. Every public figure carries a numbered source `[n]` listed under the Part's `## Sources`; every other figure is called "our assumption". When a figure changes in an `analysis/*.csv`, rerun its script and update the Part that quotes it.

## Running

- Python 3.10 to 3.13 (dbt does not run on 3.14): `py -3.12 poc/run.py` builds the PoC into `poc/.venv` and `poc/data/`; `--scale 0.1` is a quick run.
- PoC tests need a run first: `poc/.venv/Scripts/python -m unittest discover poc/tests`. Study tests: `python -m unittest discover analysis`.
- Search with `git grep` or exclude `poc/.venv` and `poc/data`: a plain recursive grep walks the virtual environment and the warehouse and times out.
