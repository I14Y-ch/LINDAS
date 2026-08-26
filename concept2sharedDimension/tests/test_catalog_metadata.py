import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, VOID

from concept2sharedDimension.src.versioning.core import CatalogManager, GraphManager


DCAT = Namespace("http://www.w3.org/ns/dcat#")
SCHEMA = Namespace("http://schema.org/")
LINDAS = URIRef("https://schema.ld.admin.ch/LindasDataset")


class CatalogMetadataTests(unittest.TestCase):
    def test_portal_metadata_scope_writes_only_requested_description(self):
        cases = (
            ("concepts", CatalogManager.CONCEPTS_DATASET_URI, CatalogManager.DATASETS_DATASET_URI),
            ("datasets", CatalogManager.DATASETS_DATASET_URI, CatalogManager.CONCEPTS_DATASET_URI),
        )
        for scope, expected, absent in cases:
            with self.subTest(scope=scope), TemporaryDirectory() as directory:
                output = Path(directory) / f"{scope}.ttl"
                graph_manager = GraphManager("https://register.ld.admin.ch/i14y/concept/", output_file=output)
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
            graph_manager = GraphManager("https://register.ld.admin.ch/i14y/concept/", output_file=output)
            try:
                with patch.dict(os.environ, {"LINDAS_QUERY_URL": "https://test.lindas.example/query"}):
                    CatalogManager(graph_manager).create_publication_descriptions()
            finally:
                graph_manager.close()

            graph = Graph().parse(output, format="turtle")

        descriptions = (
            URIRef("https://register.ld.admin.ch/.well-known/void/dataset/i14y-concepts"),
            URIRef("https://register.ld.admin.ch/.well-known/void/dataset/i14y-datasets"),
        )
        self.assertIn(Literal("Code-list concepts registered in I14Y and published as Linked Data.", lang="en"), graph.objects(descriptions[0], DCTERMS.description))
        for description in descriptions:
            self.assertIn((description, RDF.type, VOID.Dataset), graph)
            self.assertIn((description, RDF.type, DCAT.Dataset), graph)
            self.assertIn((description, RDF.type, SCHEMA.Dataset), graph)
            self.assertIn((description, RDF.type, LINDAS), graph)
            self.assertIn((description, VOID.sparqlEndpoint, URIRef("https://test.lindas.example/query")), graph)
            self.assertIn((description, DCTERMS.publisher, URIRef("https://register.ld.admin.ch/i14y/agent/CH1")), graph)
            self.assertIn((description, SCHEMA.publisher, URIRef("https://register.ld.admin.ch/i14y/agent/CH1")), graph)
            self.assertIn((description, DCAT.landingPage, URIRef("https://www.i14y.admin.ch/")), graph)
            self.assertEqual(4, len(list(graph.objects(description, DCTERMS.title))))
            self.assertEqual(4, len(list(graph.objects(description, DCTERMS.description))))


if __name__ == "__main__":
    unittest.main()
