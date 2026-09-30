"""YAML loading that refuses repeated keys.

PyYAML silently keeps the LAST of two identical keys, so a copy-paste slip in a config or
spec file would drop data without any error. This loader raises instead, naming the line.
"""

from typing import Any

import yaml


class DuplicateKeyError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                line = key_node.start_mark.line + 1
                raise DuplicateKeyError(f"key '{key}' appears twice (line {line})")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_yaml_text(text: str) -> Any:
    """Like yaml.safe_load, but repeated keys are an error. Raises DuplicateKeyError for a
    repeated key and ValueError for any other YAML syntax problem."""
    try:
        return yaml.load(text, Loader=UniqueKeyLoader)  # noqa: S506 (a SafeLoader subclass)
    except DuplicateKeyError:
        raise
    except yaml.YAMLError as exc:
        raise ValueError(str(exc)) from None
