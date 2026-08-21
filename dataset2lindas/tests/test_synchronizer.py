from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from dataset2lindas.src.config import DatasetConfig
from dataset2lindas.src.synchronizer import DatasetSourceManifest, DatasetSynchronizer


def make_config() -> DatasetConfig:
    return DatasetConfig(
        datasets_api_url="https://api.example/datasets",
        dataservices_api_url="https://api.example/dataservices",
        lindas_query_url="https://lindas.example/query",
        lindas_update_url="https://lindas.example/lindas",
        target_graph="https://lindas.example/graph",
        dataset_uri_base="https://register.ld.admin.ch/i14y/dataset/",
        dataservice_uri_base="https://register.ld.admin.ch/i14y/dataservice/",
        catalog_uri="https://register.ld.admin.ch/i14y/catalog/datasets",
        create_dataset_catalog=False,
        clear_graph=False,
        debug_local_test=False,
        page_size=100,
        api_retries=1,
        modified_lookback_hours=24,
        output_file_name="datasets.ttl",
        user_agent="tests",
    )


class FakeI14Y:
    def __init__(self, datasets):
        self.datasets = datasets

    def get_all_datasets(self):
        return self.datasets


class FakeLindas:
    def __init__(self, existing):
        self.existing = set(existing)
        self.deleted = []

    def get_existing_dataset_identifiers(self):
        return self.existing

    def delete_dataset(self, identifier):
        self.deleted.append(identifier)


def dataset(identifier, dataset_id, modified_at):
    return {"id": dataset_id, "identifiers": [identifier], "system": {"modifiedAt": modified_at}}


class DatasetSynchronizerTests(unittest.TestCase):
    def test_detects_new_changed_missing_timestamp_and_orphaned_datasets(self):
        datasets = [
            dataset("unchanged", "1", "2025-01-01T00:00:00+00:00"),
            dataset("changed", "2", "2026-01-01T11:00:00+00:00"),
            dataset("new", "3", "2025-01-01T00:00:00+00:00"),
            dataset("missing-timestamp", "4", None),
        ]
        lindas = FakeLindas({"unchanged", "changed", "orphan", "missing-timestamp"})
        synchronizer = DatasetSynchronizer(make_config(), FakeI14Y(datasets), lindas)

        plan = synchronizer.build_plan(datasets, now=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))

        self.assertEqual(["2", "4", "3"], plan.process_ids)
        self.assertEqual(["changed", "missing-timestamp", "orphan"], plan.delete_identifiers)
        synchronizer.apply_deletions(plan)
        self.assertEqual(plan.delete_identifiers, lindas.deleted)

    def test_source_manifest_round_trip_freezes_inventory_and_validates_batches(self):
        datasets = [
            dataset("FIRST", "1", "2026-01-01T00:00:00+00:00"),
            dataset("SECOND", "2", "2026-01-02T00:00:00+00:00"),
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dataset_source_manifest.json"
            DatasetSourceManifest(datasets, 1).write(path)
            restored = DatasetSourceManifest.read(path)

        self.assertEqual(["FIRST", "SECOND"], restored.source_identifiers)
        self.assertEqual(1, restored.structured_dataset_count)
        restored.validate_batch_ids(["1", "2"])
        with self.assertRaisesRegex(ValueError, "absent from the frozen source manifest"):
            restored.validate_batch_ids(["missing"])

    def test_parse_modified_at_accepts_high_precision_and_rejects_invalid_values(self):
        parsed = DatasetSynchronizer.parse_modified_at(
            {"system": {"modifiedAt": "2026-01-01T12:00:00.123456789Z"}}
        )
        self.assertEqual("2026-01-01T12:00:00.123456+00:00", parsed.isoformat())
        with self.assertRaises(ValueError):
            DatasetSynchronizer.parse_modified_at({"system": {"modifiedAt": "not-a-date"}})


if __name__ == "__main__":
    unittest.main()
