"""Send the daily job alert emails. Run by .github/workflows/daily-digest.yml.

    python scripts/daily_digest.py --dry-run   # print the emails instead of sending them
"""
import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobfinder import digest  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print digests, don't send or record anything")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL secret is not set; refusing to run against an empty local SQLite file.")
    print(digest.run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
