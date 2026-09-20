"""
Build the bundled demo database end to end:

    python -m synthetic.build_demo

  1. create data/loan_portfolio.db from schema_sqlite.sql
  2. generate 30 daily raw exports (synthetic.generate)
  3. push each export through the UNMODIFIED etl.py (same cleaning, engineered
     metrics and loaders as the production pipeline)
  4. give the pipeline_run_log a realistic nightly cadence (see note below)

Note on step 4: the ETL stamps each run with the wall-clock time it executed, which for a
batch rebuild would put 30 runs in the same minute. To make the System Health page
representative of a nightly job, run times are re-stamped to ~02:00 the morning after each
extraction date, and two failed-then-retried runs are inserted. This run log is simulated.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "loan_portfolio.db"
os.environ["LOAN_DB_URL"] = f"sqlite:///{DB_PATH}"          # must be set before config is imported
os.environ.setdefault("LOAN_PIPELINE_RAW_DIR", str(ROOT / "raw"))
os.environ.setdefault("LOAN_PIPELINE_PROCESSED_DIR", str(ROOT / "processed"))

import etl                                # noqa: E402  (unmodified production ETL)
from synthetic.generate import generate   # noqa: E402

FAILURES = {  # index of snapshot -> error message (run fails first, succeeds on retry ~20 min later)
    8: "FileNotFoundError: scheduled export not present at 02:00 (upstream extract delayed)",
    21: "OperationalError: database connection timed out after 30s",
}


def main() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript((ROOT / "schema_sqlite.sql").read_text())
    con.commit(); con.close()

    raw = ROOT / "raw"
    shutil.rmtree(raw, ignore_errors=True)
    paths = sorted(generate(raw))

    for p in paths:
        etl.run(str(p))

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    runs = cur.execute("SELECT run_id, extraction_date FROM pipeline_run_log ORDER BY extraction_date").fetchall()
    for i, (run_id, ed) in enumerate(runs):
        day = datetime.fromisoformat(ed) + timedelta(days=1, hours=2, minutes=(7 * i) % 40)
        end = day + timedelta(seconds=40 + (13 * i) % 25)
        if i in FAILURES:
            day += timedelta(minutes=20); end += timedelta(minutes=20)   # the retry
        cur.execute("UPDATE pipeline_run_log SET started_at=?, finished_at=? WHERE run_id=?",
                    (day.isoformat(sep=" "), end.isoformat(sep=" "), run_id))
        if i in FAILURES:
            fstart = day - timedelta(minutes=20)
            cur.execute(
                "INSERT INTO pipeline_run_log (started_at, finished_at, source_filename, extraction_date, rows_loaded, status, error_message)"
                " VALUES (?,?,?,?,?,?,?)",
                (fstart.isoformat(sep=" "), (fstart + timedelta(seconds=6)).isoformat(sep=" "),
                 paths[i].name, ed, 0, "failed", FAILURES[i]))
    con.commit()
    cur.execute("VACUUM")
    con.close()
    print(f"built {DB_PATH}  ({DB_PATH.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
