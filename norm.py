"""Compatibility launcher. Application code lives in openlufs/."""
from openlufs.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
