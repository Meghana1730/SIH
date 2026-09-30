"""Product configuration: the YAML files in config/ (weights, thresholds, sectors, districts,
languages, LLM/embedding and synthetic-data settings), validated with Pydantic.

    from app.config import get_config
    weights = get_config().scoring.demand.weights

Check the files from the command line (backend/ folder, venv active):
    python -m app.config
"""

from app.config.loader import ConfigError, ProductConfig, get_config, load_config

__all__ = ["ConfigError", "ProductConfig", "get_config", "load_config"]
