from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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
                CatalogManager(
                    graph_manager,
                    sparql_endpoint="https://test.lindas.example/query",
                ).create_publication_descriptions()
            finally:
                graph_manager.close()

            graph = Graph().parse(output, format="turtle")

        descriptions = (
            (CatalogManager.CONCEPTS_DATASET_URI, CatalogManager.CONCEPTS_SPARQL_EXAMPLE_URI),
            (CatalogManager.DATASETS_DATASET_URI, CatalogManager.DATASETS_SPARQL_EXAMPLE_URI),
        )
        self.assertIn(Literal("Code-list concepts registered in I14Y and published as Linked Data.", lang="en"), graph.objects(CatalogManager.CONCEPTS_DATASET_URI, DCTERMS.description))
        for description, example in descriptions:
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
            self.assertIn((description, SCHEMA.workExample, example), graph)
            self.assertIn((example, RDF.type, SCHEMA.CreativeWork), graph)
            self.assertIn((example, SCHEMA.encodingFormat, Literal("text/html")), graph)
            self.assertIn((example, SCHEMA.url, URIRef("https://github.com/metadata-swiss/LINDAS/blob/main/SPARQL_EXAMPLES.md")), graph)
            self.assertEqual(4, len(list(graph.objects(example, SCHEMA.name))))


if __name__ == "__main__":
    unittest.main()
