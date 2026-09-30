"""Validate the configuration files:  python -m app.config

Prints a summary and exits with code 0 if everything is valid, or prints every problem
and exits with code 1.
"""

import sys

from app.config import ConfigError, load_config


def main() -> int:
    try:
        config = load_config()
    except ConfigError as error:
        print(f"Configuration is INVALID:\n{error}", file=sys.stderr)
        return 1
    print(config.summary())
    print("OK: configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
