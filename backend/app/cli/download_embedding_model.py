"""Download an embedding model ONCE into the repository's models/ folder.

    python -m app.cli.download_embedding_model                 # the model in config/llm.yaml
    python -m app.cli.download_embedding_model --model <hf-id> --to models/<folder>

If the files are already there, nothing is downloaded (use --force to download again).
Only the files needed by sentence-transformers are fetched (no ONNX/TensorFlow copies).
Afterwards the app loads the model from disk and needs no internet.
"""

import argparse
import sys
from pathlib import Path

from app.config import ConfigError, load_config
from app.core.settings import REPO_ROOT
from app.nlp.embeddings import model_files_present

ALWAYS = ["*.json", "*.txt", "*.model", "1_Pooling/*", "2_Normalize/*"]
IGNORE = ["onnx/*", "openvino/*", "*.onnx", "*.h5", "*.msgpack", "*.ot"]


def main(argv: list[str] | None = None) -> int:
    try:
        embeddings = load_config().llm.embeddings
    except ConfigError as error:
        print(f"Configuration is invalid:\n{error}", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description="Download an embedding model once.")
    parser.add_argument("--model", default=embeddings.model_name, help="Hugging Face model id")
    parser.add_argument("--to", default=embeddings.local_path, help="target folder")
    parser.add_argument("--force", action="store_true", help="download even if present")
    args = parser.parse_args(argv)

    target = Path(args.to)
    target = target if target.is_absolute() else REPO_ROOT / target
    if model_files_present(target) and not args.force:
        print(f"Already downloaded: {target} (nothing to do).")
        return 0

    from huggingface_hub import HfApi, snapshot_download

    files = set(HfApi().list_repo_files(args.model))
    # Prefer the safe, fast "safetensors" weights; fall back to the older PyTorch file.
    weights = "model.safetensors" if "model.safetensors" in files else "pytorch_model.bin"
    print(f"Downloading {args.model} ({weights}) to {target} ...")
    snapshot_download(
        repo_id=args.model,
        local_dir=target,
        allow_patterns=[*ALWAYS, weights],
        ignore_patterns=IGNORE,
    )
    size_mb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1e6
    print(f"Done: {target} ({size_mb:.0f} MB). The app will load it from disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
