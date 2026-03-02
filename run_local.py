#!/usr/bin/env python3
"""Local development: scrape then serve."""
import subprocess
import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")


def main():
    print("=== Running scraper ===")
    result = subprocess.run(
        [sys.executable, "-m", "scraper.main"],
        cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        print("Scraper failed!")
        sys.exit(1)

    print("\n=== Starting local server ===")
    print("Open http://localhost:8000 in your browser")
    print("Press Ctrl+C to stop\n")
    os.chdir(DOCS_DIR)
    subprocess.run([sys.executable, "-m", "http.server", "8000"])


if __name__ == "__main__":
    main()
