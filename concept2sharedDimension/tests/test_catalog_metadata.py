import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, VOID

from concept2sharedDimension.src.versioning.core import CatalogManager, GraphManager


DCAT = Namespace("http://www.w3.org/ns/dcat#")
SCHEMA = Namespace("http://schema.org/")
LINDAS = URIRef("https://schema.ld.admin.ch/LindasDataset")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")


class CatalogMetadataTests(unittest.TestCase):
    def test_portal_metadata_scope_writes_only_requested_description(self):
        cases = (
            ("concepts", CatalogManager.CONCEPTS_DATASET_URI, CatalogManager.DATASETS_DATASET_URI),
            ("datasets", CatalogManager.DATASETS_DATASET_URI, CatalogManager.CONCEPTS_DATASET_URI),
        )
        for scope, expected, absent in cases:
            with self.subTest(scope=scope), TemporaryDirectory() as directory:
                output = Path(directory) / f"{scope}.ttl"
                graph_manager = GraphManager("https://register.ld.admin.ch/i14y/concept/", output_file=output, enable_skolem=False)
                try:
                    CatalogManager(graph_manager).create_publication_descriptions(scope)
                finally:
                    graph_manager.close()
                graph = Graph().parse(output, format="turtle")

            self.assertIn((expected, RDF.type, VOID.Dataset), graph)
            self.assertNotIn((absent, RDF.type, VOID.Dataset), graph)
    def test_portal_metadata_contains_both_dataset_descriptions(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "portal_metadata.ttl"
            graph_manager = GraphManager("https://register.ld.admin.ch/i14y/concept/", output_file=output, enable_skolem=False)
            try:
                CatalogManager(
                    graph_manager,
                    sparql_endpoint="https://test.lindas.example/query",
                ).create_publication_descriptions()
            finally:
                graph_manager.close()

            graph = Graph().parse(output, format="turtle")

        descriptions = (
            CatalogManager.CONCEPTS_DATASET_URI,
            CatalogManager.DATASETS_DATASET_URI,
        )
        self.assertIn(Literal("Code-list concepts registered in I14Y and published as Linked Data.", lang="en"), graph.objects(CatalogManager.CONCEPTS_DATASET_URI, DCTERMS.description))
        expected_initial_dates = {
            CatalogManager.CONCEPTS_DATASET_URI: "2026-02-17",
            CatalogManager.DATASETS_DATASET_URI: "2026-08-27",
        }
        expected_example_resources = {
            CatalogManager.CONCEPTS_DATASET_URI: CatalogManager.CONCEPTS_EXAMPLE_RESOURCE_URI,
            CatalogManager.DATASETS_DATASET_URI: CatalogManager.DATASETS_EXAMPLE_RESOURCE_URI,
        }
        for description in descriptions:
            examples = list(graph.objects(description, SCHEMA.workExample))
            self.assertEqual(1, len(examples))
            example = examples[0]
            self.assertIsInstance(example, BNode)
            self.assertIn((description, RDF.type, VOID.Dataset), graph)
            self.assertIn((description, RDF.type, DCAT.Dataset), graph)
            self.assertIn((description, RDF.type, SCHEMA.Dataset), graph)
            self.assertIn((description, RDF.type, LINDAS), graph)
            self.assertIn((description, VOID.sparqlEndpoint, URIRef("https://test.lindas.example/query")), graph)
            self.assertIn((description, DCTERMS.publisher, URIRef("https://register.ld.admin.ch/i14y/agent/CH1")), graph)
            self.assertIn((description, SCHEMA.publisher, URIRef("https://register.ld.admin.ch/i14y/agent/CH1")), graph)
            self.assertIn((description, DCAT.landingPage, URIRef("https://www.i14y.admin.ch/")), graph)
            self.assertIn((description, VOID.exampleResource, expected_example_resources[description]), graph)
            contact_points = list(graph.objects(description, DCAT.contactPoint))
            self.assertEqual(1, len(contact_points))
            contact_point = contact_points[0]
            self.assertIsInstance(contact_point, BNode)
            self.assertIn((description, SCHEMA.contactPoint, contact_point), graph)
            self.assertIn((contact_point, RDF.type, VCARD.Organization), graph)
            self.assertIn((contact_point, VCARD.fn, Literal("I14Y")), graph)
            self.assertIn((contact_point, VCARD.hasEmail, URIRef("mailto:i14y@bfs.admin.ch")), graph)
            initial_date = Literal(expected_initial_dates[description], datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))
            for predicate in (SCHEMA.dateCreated, SCHEMA.datePublished, DCTERMS.issued):
                self.assertIn((description, predicate, initial_date), graph)
            for predicate in (SCHEMA.dateModified, DCTERMS.modified):
                self.assertIn((description, predicate, initial_date), graph)
            self.assertEqual(4, len(list(graph.objects(description, DCTERMS.title))))
            self.assertEqual(4, len(list(graph.objects(description, DCTERMS.description))))
            self.assertIn((description, SCHEMA.workExample, example), graph)
            self.assertIn((example, RDF.type, SCHEMA.CreativeWork), graph)
            self.assertIn((example, SCHEMA.encodingFormat, Literal("text/html")), graph)
            self.assertIn((example, SCHEMA.url, URIRef("https://github.com/metadata-swiss/LINDAS/blob/main/SPARQL_EXAMPLES.md")), graph)
            self.assertEqual(4, len(list(graph.objects(example, SCHEMA.name))))


    def test_source_modified_date_uses_the_latest_frozen_resource_date(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "datasets.json"
            manifest.write_text(
                json.dumps(
                    {
                        "datasets": [
                            {"system": {"modifiedAt": "2026-08-26T23:30:00Z"}},
                            {"system": {"modifiedAt": "2026-08-28T01:00:00+02:00"}},
                            {"system": {"modifiedAt": "not-a-date"}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            modified_date = CatalogManager.source_modified_date_from_manifest(manifest, "datasets")

        self.assertEqual(date(2026, 8, 27), modified_date)
if __name__ == "__main__":
    unittest.main()
