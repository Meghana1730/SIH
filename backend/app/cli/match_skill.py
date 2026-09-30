"""Try the skill matcher on phrases, against the skills in the development database.

    python -m app.cli.match_skill "EV troubleshooting" "house wiring"

Prints one JSON result per phrase (matched skill, confidence, method, decision).
"""

import argparse
import json
import sys

from sqlalchemy import func, select

from app.config import ConfigError, load_config
from app.core.db import SessionLocal
from app.models import Skill
from app.nlp.embeddings import get_embedder
from app.nlp.skill_matcher import SkillMatcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match phrases to skills.")
    parser.add_argument("phrases", nargs="+")
    args = parser.parse_args(argv)
    try:
        config = load_config()
    except ConfigError as error:
        print(f"Configuration is invalid:\n{error}", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(Skill)):
            print("The skill vocabulary is empty: load skills first.", file=sys.stderr)
            return 1
        matcher = SkillMatcher(db, config, get_embedder(config))
        for phrase in args.phrases:
            print(json.dumps(matcher.match(phrase).to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
