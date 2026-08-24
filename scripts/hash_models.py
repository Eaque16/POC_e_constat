"""Inventaire JSON et SHA-256 des fichiers de modèles locaux."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcule les empreintes des modèles locaux.")
    parser.add_argument("paths", nargs="+", type=Path)
    arguments = parser.parse_args()
    inventory = []
    for root in arguments.paths:
        if not root.is_dir():
            raise SystemExit(f"Dossier modèle introuvable : {root}")
        files = [path for path in sorted(root.rglob("*")) if path.is_file()]
        inventory.append(
            {
                "model_path": str(root),
                "files": [
                    {
                        "path": str(path.relative_to(root)),
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                    for path in files
                    if ".cache" not in path.parts
                ],
            }
        )
    print(json.dumps(inventory, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
