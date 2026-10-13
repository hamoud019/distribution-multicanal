"""The proof of concept in one command: generate -> ingest -> freshness -> dbt build -> docs.

    py -3.12 poc/run.py                 # Windows (any Python 3.10 to 3.13 works)
    python3 poc/run.py                  # macOS / Linux
    py -3.12 poc/run.py --incremental   # keep the warehouse and load only new files
    py -3.12 poc/run.py --docs          # open the dbt docs and lineage graph in the browser

The first run creates a virtual environment in poc/.venv and installs poc/requirements.txt
(dbt-core, dbt-duckdb, duckdb). No cloud account is needed: DuckDB stands in for the
cloud warehouse (Fabric in the study) in a single local file, poc/data/warehouse.duckdb.
"""

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

POC = Path(__file__).resolve().parent
VENV = POC / ".venv"
DATA = POC / "data"
DBT_PROJECT = POC / "dbt"
SUPPORTED_PYTHON = ((3, 10), (3, 13))  # what dbt supports


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_environment():
    """Make sure this script runs inside poc/.venv with the pinned requirements, never another dbt.

    Outside the environment: create it if needed, install the requirements when they changed,
    then run this script again inside it. Inside it: stop with a message if dbt still cannot be
    imported, instead of trying again forever.
    """
    if Path(sys.prefix).resolve() == VENV.resolve():
        try:
            import dbt.cli.main  # noqa: F401
            import duckdb  # noqa: F401
        except ImportError as error:
            sys.exit(f"The environment in poc/.venv is broken ({error}). Delete poc/.venv and run again.")
        return
    if not SUPPORTED_PYTHON[0] <= sys.version_info[:2] <= SUPPORTED_PYTHON[1]:
        sys.exit(f"dbt needs Python 3.10 to 3.13, this is {sys.version.split()[0]}. "
                 "On Windows, try: py -3.12 poc/run.py")
    if not venv_python().exists():
        print("Creating the environment in poc/.venv ...", flush=True)
        venv.create(VENV, with_pip=True)
    requirements = (POC / "requirements.txt").read_text(encoding="utf-8")
    installed = VENV / "installed-requirements.txt"
    if not installed.exists() or installed.read_text(encoding="utf-8") != requirements:
        print("Installing poc/requirements.txt ...", flush=True)
        subprocess.check_call([str(venv_python()), "-m", "pip", "install", "-q", "-r", str(POC / "requirements.txt")])
        installed.write_text(requirements, encoding="utf-8")
    sys.exit(subprocess.call([str(venv_python()), str(Path(__file__).resolve()), *sys.argv[1:]]))


def run_dbt(*command):
    from dbt.cli.main import dbtRunner

    print(f"\n== dbt {' '.join(command)}")
    result = dbtRunner().invoke([*command, "--project-dir", str(DBT_PROJECT), "--profiles-dir", str(DBT_PROJECT)])
    if not result.success:
        sys.exit(f"dbt {' '.join(command)} failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--incremental", action="store_true",
                        help="keep the existing warehouse and only load new or changed files")
    parser.add_argument("--seed", default=2026, type=int)
    parser.add_argument("--scale", default=1.0, type=float, help="fraction of the 1 %% sample, for a quick run")
    parser.add_argument("--docs", action="store_true", help="serve the dbt docs of the last run, then stop")
    args = parser.parse_args()

    ensure_environment()
    warehouse = DATA / "warehouse.duckdb"
    os.environ["LSF_POC_WAREHOUSE"] = str(warehouse)
    if args.docs:
        run_dbt("docs", "serve")
        return

    sys.path.insert(0, str(POC))
    from generate import generate
    from ingest import ingest

    if not args.incremental and warehouse.exists():
        warehouse.unlink()

    print("== Generating the synthetic sources")
    generate(DATA / "landing", seed=args.seed, scale=args.scale)
    print("== Loading them into the raw layer")
    for table, rows in ingest(DATA / "landing", warehouse).items():
        print(f"   {table:28} {rows:>9,} new rows")

    run_dbt("source", "freshness")  # stale sources are flagged before the reports are rebuilt
    run_dbt("build")
    run_dbt("docs", "generate")

    print(f"\nDone. The warehouse is {warehouse.relative_to(POC.parent)}.")
    print("To see the lineage graph: py -3.12 poc/run.py --docs")


if __name__ == "__main__":
    main()
