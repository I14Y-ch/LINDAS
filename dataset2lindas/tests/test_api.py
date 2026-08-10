from __future__ import annotations

import unittest

from dataset2lindas.src.api import I14YDatasetsAPI, LindasDatasetsAPI
from dataset2lindas.src.config import DatasetConfig


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
        page_size=2,
        api_retries=1,
        modified_lookback_hours=24,
        output_file_name="datasets.ttl",
        user_agent="tests",
    )


class Response:
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.status_code = 204
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        page = (kwargs.get("params") or {}).get("page")
        payloads = {
            1: {"data": [{"id": "1"}, {"id": "2"}]},
            2: {"data": [{"id": "3"}]},
        }
        return Response(payloads.get(page, {"data": {"publicationLevel": "Public"}}))

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return Response()


class ApiTests(unittest.TestCase):
    def test_dataset_listing_paginates_without_filters(self):
        session = Session()
        datasets = I14YDatasetsAPI(make_config(), session).get_all_datasets()
        self.assertEqual(["1", "2", "3"], [dataset["id"] for dataset in datasets])
        self.assertEqual(
            {"page": 1, "pageSize": 2}, session.get_calls[0][1]["params"]
        )
        self.assertEqual(
            {"page": 2, "pageSize": 2}, session.get_calls[1][1]["params"]
        )

    def test_existing_datasets_reads_dct_identifier_without_uri_prefix_filter(self):
        api = LindasDatasetsAPI(make_config(), Session())
        queries = []

        def query(sparql):
            queries.append(sparql)
            return [
                {"identifier": {"value": "DATASET_1"}},
                {"identifier": {"value": "DATASET_2"}},
            ]

        api.query = query
        self.assertEqual({"DATASET_1", "DATASET_2"}, api.get_existing_dataset_identifiers())
        self.assertIn("dct:identifier ?identifier", queries[0])
        self.assertNotIn("STRSTARTS", queries[0])
    def test_dataset_deletion_uses_dataset_anchored_skolem_queries(self):
        session = Session()
        api = LindasDatasetsAPI(make_config(), session)
        api.delete_dataset("DATASET_1")
        updates = [call[1]["data"] for call in session.post_calls]
        self.assertEqual(4, len(updates))
        self.assertTrue(all("?s ?p ?o" not in update for update in updates))
        self.assertIn("<{dataset_uri}> ?dataset_predicate ?parent".format(
            dataset_uri="https://register.ld.admin.ch/i14y/dataset/DATASET_1"
        ), updates[0])
        self.assertIn("STRSTARTS(STR(?parent)", updates[0])
        self.assertIn("dcat:dataset", updates[-1])


if __name__ == "__main__":
    unittest.main()
