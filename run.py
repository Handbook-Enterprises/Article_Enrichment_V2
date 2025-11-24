"""
Thin wrapper to run the CLI from scripts/run.py while preserving the
expected entry point name for some submission environments.
"""

from scripts.run import main

if __name__ == "__main__":
    main()