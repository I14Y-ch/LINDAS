"""Command line entrypoint for creating dataset RDF artifacts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .api import I14YDatasetsAPI
from .config import DatasetConfig
from .mapper import DatasetRdfMapper
from .synchronizer import DatasetSourceManifest


def _dataset_ids(argument: str | None) -> list[str]:
    raw = argument or os.environ.get("BATCH_DATASET_IDS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export i14y datasets to Turtle")
    parser.add_argument("--dataset-ids", help="Comma-separated i14y dataset UUIDs")
    parser.add_argument("--batch-index", type=int, default=0)
    parser.add_argument("--output", help="Output Turtle path")
    parser.add_argument("--catalog-only", action="store_true", help="Write the optional common catalogue")
    args = parser.parse_args()

    config = DatasetConfig.from_env()
    api = I14YDatasetsAPI(config)
    mapper = DatasetRdfMapper(config, api.is_dataservice_public)
    output = Path(args.output or f"batch_{args.batch_index}_{config.output_file_name}")
    manifest_path = os.environ.get("I14Y_DATASET_MANIFEST_PATH", "").strip()
    manifest = DatasetSourceManifest.read(manifest_path) if manifest_path else None
    if manifest:
        print(f"Loaded frozen dataset source manifest: {manifest_path}")

    if args.catalog_only:
        if not config.create_dataset_catalog:
            raise ValueError("CREATE_DATASET_CATALOG must be true for --catalog-only")
        if manifest:
            identifiers = manifest.source_identifiers
        else:
            identifiers = (dataset["identifiers"][0] for dataset in api.get_all_datasets())
        mapper.write_catalog_turtle(identifiers, output)
        print(f"Wrote optional catalogue to {output}")
        return

    ids = _dataset_ids(args.dataset_ids)
    if not ids:
        raise ValueError("Provide --dataset-ids or BATCH_DATASET_IDS")
    if manifest:
        manifest.validate_batch_ids(ids)
    datasets = (api.get_dataset(dataset_id) for dataset_id in ids)
    count = mapper.write_dataset_turtle(datasets, output, api.get_dataset_structure_turtle)
    print(f"Wrote {count} dataset(s) to {output}")


if __name__ == "__main__":
    main()
