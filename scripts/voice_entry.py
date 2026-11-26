"""Frozen Windows entry. Secrets are loaded only at runtime, never into the bundle."""
import sys
from voice.__main__ import main

if __name__ == "__main__":
    if "--fake-demo" not in sys.argv:
        sys.argv.append("--live")
    main()
