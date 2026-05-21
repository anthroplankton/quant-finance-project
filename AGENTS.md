# AGENTS.md

Repository-wide instructions for Codex and AI-assisted contributors.

## Project goal

This repository is a Quantitative Finance course project. Its likely final project topic is **Black-Litterman portfolio optimization with LLM-assisted news views**.

The intended research direction is:

1. study Black-Litterman, LLM-generated financial views, and news-aware time-series forecasting papers;
2. design a literature-grounded model architecture for converting market/news context into views `P`, `Q`, and `Omega`;
3. implement a reproducible baseline pipeline before adding live LLM or live news workflows;
4. evaluate the approach with clear backtest assumptions and report-ready evidence.

The model architecture is **not finalized yet**. Do not assume a fixed layer structure, agent structure, data schema, or LLM prompting strategy unless it is already documented in the repository. When architecture choices are unclear, add or update design notes instead of prematurely implementing a full pipeline.

This is not intended to become a production trading system, broker integration, real-money trading bot, high-frequency strategy, financial advisory product, or large MLOps platform.

When goals conflict, prioritize:

1. course assignments and required reading/report deliverables;
2. literature-grounded model design;
3. reproducible data and baseline Black-Litterman computations;
4. clear separation between research notes, prototypes, and reusable code;
5. small deterministic tests and smoke checks;
6. report-ready results and limitations;
7. live LLM/news integrations only after offline workflows are clear.

## Repository layout

Prefer a simple Python project structure:

```text
README.md
AGENTS.md
pyproject.toml
uv.lock
src/
examples/
scripts/
tests/
docs/
assignments/
report/
notebooks/
data/
configs/
```

Use these directories as follows:

- `src/`: reusable Python package code;
- `examples/`: small runnable examples and prototype entry points;
- `scripts/`: data preparation, diagnostics, result processing, and figure/table generation;
- `tests/`: pytest tests, smoke checks, and small fixtures;
- `docs/`: technical notes, paper summaries, architecture alternatives, formulas, and prompt design notes;
- `assignments/`: course assignments that may be only loosely related to the final project;
- `report/`: final report materials, progress logs, curated results, and figures;
- `notebooks/`: exploratory analysis only; move reusable logic into `src/`;
- `data/`: local datasets, cached data, and small documented samples;
- `configs/`: example configuration files only when repeated settings justify them.

Use `quant_finance_project` as the default Python package name:

```text
src/quant_finance_project/
```

Avoid multiple competing top-level packages. Use English names for files and directories. Use `snake_case.py` for Python modules and lowercase descriptive Markdown names such as `architecture_notes.md`, `paper_reading_log.md`, or `assignment_02.md`.

## Initial scaffolding order

Build the repository incrementally. Do not create every planned subsystem at once.

A suitable early order is:

1. root repository files: `README.md`, `AGENTS.md`, `.gitignore`, and `pyproject.toml`;
2. `assignments/`, `docs/`, and `report/` placeholders for current course work;
3. paper reading notes and architecture alternatives under `docs/`;
4. minimal Python package and tests only when reusable code is needed;
5. deterministic market-data sample or mocked data pipeline;
6. baseline Black-Litterman computation without LLM calls;
7. view-construction prototypes using fixed or mocked LLM outputs;
8. live LLM/news API workflows only after schemas, prompts, and offline tests are documented;
9. backtest, evaluation, figures, and report-ready summaries.

Do not scaffold all future modules only because they are listed below. Create subpackages only when real code for that responsibility is added.

Possible target organization inside `src/quant_finance_project/`:

```text
data/
news/
llm/
views/
black_litterman/
optimization/
backtesting/
evaluation/
utils/
```

This is a target organization, not an initial scaffolding requirement.

## Research and model-design rules

Model design must be traceable to papers, course materials, documented assumptions, or explicit experiments.

Do not invent formulas, citations, empirical claims, benchmark results, dataset availability, or paper conclusions. If a method is heuristic, label it as heuristic and explain why it is being tested.

For Black-Litterman work, keep these objects explicit when relevant:

- market universe and dates;
- return frequency and forecast horizon;
- covariance estimate `Sigma`;
- prior return `pi`;
- picking matrix `P`;
- view vector `Q`;
- view uncertainty/confidence matrix `Omega`;
- `tau` choice;
- optimization objective and constraints;
- rebalancing schedule;
- transaction-cost and no-short assumptions.

Do not mix different `Omega` construction methods without documenting the rationale. For example, repeated-query LLM variance, canonical Black-Litterman choices, Idzorek-style confidence mapping, residual variance, and shrinkage variants should be implemented as separate named methods or clearly documented alternatives.

The default final-project market universe should follow the reference LLM-Black-Litterman paper as closely as practical: a large-cap S&P 500 universe, preferably the top 50 S&P 500 constituents by market capitalization at the paper's selection date. If exact constituents, dates, prices, sectors, or market-cap data cannot be replicated, document deviations before running backtests. Taiwan equity data may be explored later as an extension, but it should not be the default baseline unless the project direction is explicitly changed.

## Data and market-data workflow

Market-data retrieval belongs in this repository when it is needed for reproducibility, but it should be isolated from model logic.

Prefer reproducible scripts or adapters such as:

```text
scripts/download_prices.py
scripts/build_universe.py
scripts/prepare_returns.py
```

or reusable modules under `src/quant_finance_project/data/` once the design stabilizes.

Do not commit large raw datasets, proprietary data, paid vendor exports, credentials, API keys, or private cache files. Keep raw and regenerated data ignored by default. Commit only small, safe, documented samples when tests or examples need them.

Document every data source used for backtests, including source name, access date, coverage period, symbols, adjusted-price assumptions, missing-data handling, survivorship-bias risks, and any manual edits.

Use clear boundaries:

- `data/raw/`: local raw downloads, ignored by Git;
- `data/processed/`: regenerated intermediate data, usually ignored;
- `data/samples/`: tiny redistributable samples for tests or examples;
- `report/results/`: curated tables or summaries intended for the course report.

## LLM, news, and prompt workflow

The LLM should not directly choose final portfolio weights. Its role is to assist view generation, uncertainty estimation, news filtering, event reasoning, or scenario analysis. Portfolio weights should come from documented Black-Litterman and optimization code.

News should not be passed directly and indiscriminately into view generation. Prefer a staged workflow:

1. collect or curate candidate news;
2. align news with asset, sector, date, and forecast horizon;
3. filter and summarize relevant events;
4. record event rationale;
5. construct or update numerical views `P`, `Q`, and/or `Omega`.

For each selected event, record when practical:

- affected asset, sector, or market;
- publication date and event date;
- expected direction;
- expected horizon;
- rationale;
- confidence or uncertainty signal;
- whether it affects `Q`, `Omega`, or both.

Prefer deterministic offline fixtures before live LLM calls. Store prompt templates, expected JSON schemas, and example mocked responses in documented locations. Do not require live LLM APIs, paid APIs, news subscriptions, or network access for default tests.

Never commit LLM API keys, provider credentials, paid news credentials, `.env` files, or private prompts containing sensitive data. Use `.env.example` or documented placeholders when configuration is needed.

## Python, tooling, and code style

Use `pyproject.toml` as the primary Python project configuration file.

Use `uv` for environment and dependency management when practical. Do not manually edit `uv.lock`; regenerate it with the package manager when dependency changes require it.

Prefer routine validation commands such as:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Follow PEP 8 conventions as enforced by Ruff. Use type hints for public functions and important quantitative logic. Keep numerical assumptions visible: shapes, units, dates, return convention, annualization convention, random seeds, tolerances, and optimization constraints.

Avoid modifying `sys.path` inside examples or scripts unless there is a clear temporary reason. Prefer running commands from the repository root using documented `uv run ...` commands.

## Dependencies

Keep the default environment small enough for assignments, reading notes, and baseline numerical work.

Use optional dependency groups only when needed, for example:

- `dev`: Ruff, pytest, pre-commit, and local development tools;
- `notebook`: Jupyter and exploratory analysis tools;
- `data`: market-data and data-cleaning dependencies;
- `llm`: LLM client libraries and prompt-evaluation helpers;
- `report`: figure, table, or document-generation dependencies.

Do not add heavy LLM, optimization, notebook, or data-vendor dependencies to the default environment unless there is a clear project-level reason. Explain dependency changes and update setup documentation when needed.

## Testing and reproducibility

Use pytest for local tests and smoke checks.

Default tests should be lightweight, deterministic, offline, and suitable for local CPU execution. Tests should not require live market data, network access, LLM APIs, paid credentials, large downloads, or private datasets.

Use small synthetic data or committed samples for tests. For numerical code, check tolerances explicitly with `pytest.approx`, NumPy testing utilities, or equivalent methods.

Test naming should be clear, such as:

```text
test_black_litterman_posterior_shapes
test_view_schema_rejects_missing_confidence
test_backtest_smoke_uses_fixed_seed
```

Do not claim that tests, backtests, LLM runs, data downloads, or report-generation commands passed unless they were actually run. If checks cannot be run because dependencies, data, credentials, or network access are unavailable, state that clearly.

## Assignments and course materials

Use `assignments/` for course assignments, even when they are only loosely related to the final project topic.

Assignment materials may include problem statements, notes, solution drafts, figures, and small supporting scripts. Keep each assignment isolated, for example:

```text
assignments/assignment_02/
assignments/assignment_03/
```

Do not force assignment code into the final project package unless it becomes reusable project logic. Do not let assignment-specific assumptions silently influence the final model pipeline.

## Documentation and report materials

The README should be the main project entry point. It should state the project purpose, current status, repository layout, setup commands, major documents, and known limitations.

Use `docs/` for technical notes, paper reading summaries, formulas, architecture alternatives, prompt designs, and design decisions.

Use `report/` for course-report materials and curated outputs:

```text
report/
├── final_report.md
├── project_outline.md
├── progress_log.md
├── figures/
└── results/
```

Code, comments, reusable technical documentation, and prompt/schema files should generally be written in English. Course reports, progress logs, and learning notes may be written in Traditional Chinese when that improves clarity. Preserve English technical terms, formulas, commands, library names, and paper titles where appropriate.

Report materials must remain grounded in actual work. Do not fabricate results, plots, tables, logs, paper claims, citations, or completed experiments. Connect claims to code, documented workflows, result artifacts, paper notes, or explicit assumptions.

After meaningful changes, update `report/progress_log.md` when it helps preserve what was done, what was learned, open questions, and next steps.

## Notebooks

Notebooks may be used for exploration, paper replication attempts, data inspection, visualization, and presentation preparation.

Runnable scripts and reusable Python modules should remain the primary source for reproducible workflows. Clear notebook outputs before committing unless the outputs are intentionally small, relevant, and useful for the report.

## Git, commits, and PRs

Use clear commit messages, preferably Conventional Commits such as:

```text
docs: add paper reading notes
feat: add black litterman posterior helper
test: add deterministic view schema checks
```

Do not create Git commits unless explicitly requested. Do not push to remote repositories unless explicitly requested. Before pushing, identify the target remote and branch, summarize changes, and report checks.

## Agent working rules

Inspect existing files before editing.

Prefer small, focused, reviewable changes. Do not rewrite unrelated files, reformat the entire repository, introduce large new structures, or add new frameworks unless the task explicitly requires it.

When the architecture is unclear, document alternatives and open questions instead of silently choosing a final design.

Before deleting, moving, renaming, or rewriting many files, summarize the intended change and affected paths.

Be especially careful with assignments, report materials, paper summaries, formulas, prompt templates, configuration files, generated result artifacts, figures, `LICENSE`, and files that may contain project history or evidence.

Do not run destructive Git commands such as `git reset --hard`, `git clean -fd`, force pushes, or history rewrites unless explicitly requested.

After making repository changes, summarize:

- what changed;
- which files were modified or added;
- which commands or checks were run;
- which checks could not be run and why;
- important assumptions, limitations, or follow-up steps.

## Nested AGENTS.md files

Start with this single root `AGENTS.md` for repository-wide instructions.

Add nested `AGENTS.md` files only when a subdirectory needs substantially different or more detailed rules that would make the root file too long. Possible future candidates are `assignments/AGENTS.md`, `report/AGENTS.md`, or `data/AGENTS.md`.

Do not duplicate shared instructions across multiple AGENTS files.
