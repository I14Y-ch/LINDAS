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
    def __init__(self, payload=None, *, text="", content=None, status_code=204):
        self.payload = payload or {}
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

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
    def test_dataset_structure_returns_turtle_and_treats_404_as_absence(self):
        class StructureSession(Session):
            def get(self, url, **kwargs):
                self.get_calls.append((url, kwargs))
                if url.endswith("/missing/structures/exports/TTL"):
                    return Response(status_code=404)
                return Response(
                    text='incorrect charset: Zusatzstimmen_unverÃ¤nderte_Wahlzettel',
                    content=(
                        '<https://example.org/shape> a '
                        '<http://www.w3.org/ns/shacl#NodeShape> ; '
                        '<http://www.w3.org/ns/shacl#name> "Zusatzstimmen_'
                        'unveränderte_Wahlzettel"@de .'
                    ).encode("utf-8"),
                )

        session = StructureSession()
        api = I14YDatasetsAPI(make_config(), session)
        turtle = api.get_dataset_structure_turtle("present")
        self.assertIn("NodeShape", turtle)
        self.assertIn("Zusatzstimmen_unveränderte_Wahlzettel", turtle)
        self.assertNotIn("Zusatzstimmen_unverÃ¤nderte_Wahlzettel", turtle)
        self.assertIsNone(api.get_dataset_structure_turtle("missing"))
        self.assertEqual(
            "https://api.example/datasets/present/structures/exports/TTL",
            session.get_calls[0][0],
        )
        self.assertIn("text/turtle", session.get_calls[0][1]["headers"]["Accept"])
        self.assertIn("charset=utf-8", session.get_calls[0][1]["headers"]["Accept"])

    def test_dataset_deletion_uses_indexed_structure_cleanup_then_local_traversal(self):
        session = Session()
        client = LindasDatasetsAPI(make_config(), session)

        client.delete_dataset("DATASET_1")

        updates = [call[1]["data"] for call in session.post_calls]
        self.assertEqual(3, len(updates))
        external_cleanup, local_cleanup, catalog_cleanup = updates
        self.assertIn("dct:hasPart ?part", external_cleanup)
        self.assertIn("FILTER NOT EXISTS", external_cleanup)
        self.assertIn("?part ?p ?o", external_cleanup)

        self.assertIn("BIND(<https://register.ld.admin.ch/i14y/dataset/DATASET_1> AS ?dataset)", local_cleanup)
        self.assertIn("?dataset ?root_predicate ?start", local_cleanup)
        self.assertIn("?start !(rdf:type|dct:publisher|dct:conformsTo", local_cleanup)
        self.assertIn("STRSTARTS(STR(?s), STR(?dataset))", local_cleanup)
        self.assertNotIn("FILTER(isIRI(?o)", local_cleanup)

        self.assertIn("DELETE DATA", catalog_cleanup)
        self.assertIn("dcat:dataset", catalog_cleanup)

    def test_orphaned_publisher_cleanup_is_limited_to_unreferenced_i14y_agents(self):
        session = Session()
        api = LindasDatasetsAPI(make_config(), session)
        api.delete_orphaned_publisher_agents()
        update = session.post_calls[0][1]["data"]

        self.assertIn("?agent a foaf:Agent", update)
        self.assertIn("https://register.ld.admin.ch/i14y/agent/", update)
        self.assertIn("?owner dct:publisher ?agent", update)
        self.assertIn("FILTER NOT EXISTS", update)
        self.assertNotIn("STRSTARTS(STR(?o)", update)
if __name__ == "__main__":
    unittest.main()
