from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD

from dataset2lindas.src.config import DatasetConfig
from dataset2lindas.src.mapper import DCAT, DCATAP, FOAF, ORG, INVALID_URI, SCHEMA, SH, SPDX, VCARD, DatasetRdfMapper


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


def dataset() -> dict:
    return {
        "id": "dataset-id",
        "identifiers": ["DATASET_1"],
        "accessRights": {"uri": "https://example.org/access"},
        "contactPoints": [{"fn": {"fr": "Contact"}, "hasEmail": "contact@example.org"}],
        "description": {"fr": "Description"},
        "issued": "2025-01-02T00:00:00+00:00",
        "modified": "2025-01-03T00:00:00+00:00",
        "keywords": [{"label": {"fr": "mot-clé"}}],
        "languages": [{"code": "fr"}],
        "publisher": {"identifier": "CH1", "name": {"fr": "OFS"}},
        "temporalCoverage": [{"start": "2024-01-01T00:00:00+00:00", "end": "2024-12-31T00:00:00+00:00"}],
        "title": {"fr": "Jeu de données"},
        "themes": [{"uri": None}],
        "distributions": [{
            "accessUrl": {"uri": "https://example.org/access-url"},
            "availability": {"uri": "https://example.org/available"},
            "byteSize": 12.5,
            "checksum": {"algorithm": {"uri": "https://example.org/sha256"}, "checksumValue": "abc"},
            "coverage": [{"start": "2024-01-01T00:00:00+00:00"}],
            "identifier": "dist-1",
            "issued": "2025-01-04T00:00:00+00:00",
            "modified": "2025-01-05T00:00:00+00:00",
            "title": {"fr": "CSV"},
            "accessServices": [{"id": "public-service"}, {"id": "private-service"}],
        }],
    }


class DatasetRdfMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = DatasetRdfMapper(make_config(), lambda service_id: service_id == "public-service")
        self.uri = self.mapper.dataset_uri("DATASET_1")
        self.graph = self.mapper.map_dataset(dataset())

    def test_maps_dataset_and_distribution_with_csharp_terms(self) -> None:
        self.assertIn((self.uri, RDF.type, DCAT.Dataset), self.graph)
        self.assertIn((self.uri, DCTERMS.identifier, Literal("DATASET_1")), self.graph)
        self.assertIn((self.uri, DCTERMS.title, Literal("Jeu de données", lang="fr")), self.graph)
        self.assertIn((self.uri, DCAT.theme, INVALID_URI), self.graph)

        distribution = next(self.graph.objects(self.uri, DCAT.distribution))
        self.assertIsInstance(distribution, BNode)
        self.assertIn((distribution, DCAT.byteSize, Literal("12.5", datatype=XSD.decimal)), self.graph)
        self.assertIn((distribution, DCTERMS.coverage, Literal("2024-01-01")), self.graph)
        self.assertIn((distribution, DCATAP.availability, URIRef("https://example.org/available")), self.graph)
        self.assertIn((distribution, DCAT.accessService, self.mapper.dataservice_uri("public-service")), self.graph)
        self.assertNotIn((distribution, DCAT.accessService, self.mapper.dataservice_uri("private-service")), self.graph)
        publisher = self.mapper.agent_uri("CH1")
        self.assertIn((self.uri, DCTERMS.publisher, publisher), self.graph)
        self.assertIn((publisher, RDF.type, FOAF.Agent), self.graph)
        self.assertIn((publisher, RDF.type, ORG.Organization), self.graph)
        self.assertIn((publisher, RDF.type, FOAF.Organization), self.graph)
        self.assertIn((publisher, FOAF.name, Literal("OFS", lang="fr")), self.graph)

    def test_uses_xsd_date_for_dataset_dates(self) -> None:
        distribution = next(self.graph.objects(self.uri, DCAT.distribution))
        period = next(self.graph.objects(self.uri, DCTERMS.temporal))

        self.assertIn((self.uri, DCTERMS.issued, Literal("2025-01-02", datatype=XSD.date)), self.graph)
        self.assertIn((self.uri, DCTERMS.modified, Literal("2025-01-03", datatype=XSD.date)), self.graph)
        self.assertIn((distribution, DCTERMS.issued, Literal("2025-01-04", datatype=XSD.date)), self.graph)
        self.assertIn((distribution, DCTERMS.modified, Literal("2025-01-05", datatype=XSD.date)), self.graph)
        self.assertIn((period, SCHEMA.startDate, Literal("2024-01-01", datatype=XSD.date)), self.graph)
        self.assertIn((period, SCHEMA.endDate, Literal("2024-12-31", datatype=XSD.date)), self.graph)

    def test_uses_blank_nodes_and_never_uses_version_link(self) -> None:
        contact = next(self.graph.objects(self.uri, DCAT.contactPoint))
        self.assertIsInstance(contact, BNode)
        self.assertIn((contact, RDF.type, VCARD.Organization), self.graph)
        checksum = next(self.graph.subjects(SPDX.checksumValue, Literal("abc")))
        self.assertIsInstance(checksum, BNode)
        self.assertIn((checksum, RDF.type, SPDX.Checksum), self.graph)
        self.assertTrue(all("version.link" not in str(term) for triple in self.graph for term in triple))

    def test_maps_theme_codes_to_versioned_i14y_concept_iris(self) -> None:
        payload = dataset()
        payload["themes"] = [{"code": "101"}, {"code": "115"}]
        graph = self.mapper.map_dataset(payload)
        base = "https://register.ld.admin.ch/i14y/concept/DV_DCAT_DATASET_THEME"
        self.assertIn((self.uri, DCAT.theme, URIRef(f"{base}/101/version/1.1.0")), graph)
        self.assertIn((self.uri, DCAT.theme, URIRef(f"{base}/115/version/1.1.0")), graph)
        self.assertNotIn((self.uri, DCAT.theme, INVALID_URI), graph)
    def test_streamed_turtle_skolemizes_distinct_nodes_under_the_dataset_uri(self) -> None:
        payload = dataset()
        payload["distributions"].append(
            {"accessUrl": {"uri": "https://example.org/second-access-url"}, "identifier": "dist-2"}
        )
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "dataset.ttl"
            self.assertEqual(1, self.mapper.write_dataset_turtle([payload], output_path))
            turtle = output_path.read_text(encoding="utf-8")

        self.assertNotIn("_:", turtle)
        self.assertIn(f"<{self.uri}/.well-known/genid/", turtle)
        parsed = Graph().parse(data=turtle, format="turtle")
        self.assertIn((self.uri, RDF.type, DCAT.Dataset), parsed)
        self.assertEqual(2, len(list(parsed.objects(self.uri, DCAT.distribution))))

    def test_distribution_skolem_iris_are_stable_when_source_order_changes(self) -> None:
        first = {
            "id": "distribution-a",
            "identifier": "first",
            "accessUrl": {"uri": "https://example.org/first"},
        }
        second = {
            "id": "distribution-b",
            "identifier": "second",
            "accessUrl": {"uri": "https://example.org/second"},
        }

        def export_distribution_iris(distributions: list[dict]) -> dict[str, str]:
            payload = dataset()
            payload["distributions"] = distributions
            with TemporaryDirectory() as directory:
                output_path = Path(directory) / "dataset.ttl"
                self.mapper.write_dataset_turtle([payload], output_path)
                graph = Graph().parse(data=output_path.read_text(encoding="utf-8"), format="turtle")
            return {
                identifier: str(next(graph.subjects(DCTERMS.identifier, Literal(identifier))))
                for identifier in ("first", "second")
            }

        self.assertEqual(
            export_distribution_iris([first, second]),
            export_distribution_iris([second, first]),
        )
    def test_streamed_turtle_preserves_utf8_in_shape_iris(self) -> None:
        structure_uri = self.mapper.dataset_structure_uri("DATASET_1")
        first_shape = f"{structure_uri}/privaterUndÖffentlicherSektor"
        second_shape = f"{structure_uri}/erlaubteHöchstgeschwindigkeit"
        source_turtle = f'''@prefix sh: <{SH}> .

<{first_shape}> a sh:NodeShape ;
    sh:description "Âge"@fr .
<{second_shape}> a sh:NodeShape ;
    sh:name "Secteur privé / public"@fr .
'''
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "dataset.ttl"
            self.mapper.write_dataset_turtle(
                [dataset()], output_path, lambda dataset_id: source_turtle
            )
            turtle = output_path.read_text(encoding="utf-8")
            graph = Graph().parse(data=turtle, format="turtle")

        expected_shapes = {URIRef(first_shape), URIRef(second_shape)}
        self.assertIn(
            (URIRef(second_shape), SH.name, Literal("Secteur privé / public", lang="fr")),
            graph,
        )
        self.assertIn(
            (URIRef(first_shape), SH.description, Literal("Âge", lang="fr")),
            graph,
        )
        for expected_shape in expected_shapes:
            self.assertIn(f"<{expected_shape}>", turtle)
            self.assertIn((expected_shape, RDF.type, SH.NodeShape), graph)
    def test_catalog_is_only_added_explicitly(self) -> None:
        self.assertEqual([], list(self.graph.subjects(RDF.type, DCAT.Catalog)))
        self.mapper.add_catalog(self.graph, ["DATASET_1", "DATASET_2"])
        catalog = URIRef(self.mapper.config.catalog_uri)
        self.assertIn((catalog, RDF.type, DCAT.Catalog), self.graph)
        self.assertIn((catalog, DCAT.dataset, self.mapper.dataset_uri("DATASET_2")), self.graph)

    def test_keeps_structure_concept_links_and_indexes_external_subjects(self) -> None:
        structure_uri = self.mapper.dataset_structure_uri("DATASET_1")
        node_shape = URIRef(f"{structure_uri}/ExampleShape")
        ontology = URIRef("https://example.org/ontology")
        concept = URIRef("https://register.ld.admin.ch/i14y/concept/DV_EXAMPLE/version/1.0.0")
        source_turtle = f'''@prefix dct: <{DCTERMS}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix sh: <{SH}> .

<{node_shape}> a sh:NodeShape ;
    sh:property [
        a sh:PropertyShape ;
        dct:conformsTo <{concept}> ;
        sh:or ([ sh:class <https://example.org/first> ] [ sh:class <https://example.org/second> ])
    ] .
<{ontology}> a owl:Ontology .
'''
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "dataset.ttl"
            self.mapper.write_dataset_turtle(
                [dataset()], output_path, lambda dataset_id: source_turtle
            )
            turtle = output_path.read_text(encoding="utf-8")
            graph = Graph().parse(data=turtle, format="turtle")

        parts = set(graph.objects(structure_uri, DCTERMS.hasPart))
        property_shape = next(graph.subjects(RDF.type, SH.PropertyShape))
        self.assertNotIn("_:", turtle)
        self.assertIn((self.uri, DCTERMS.conformsTo, structure_uri), graph)
        self.assertEqual({node_shape, ontology}, parts)
        self.assertTrue(str(property_shape).startswith(f"{structure_uri}/.well-known/genid/"))
        self.assertIn((property_shape, DCTERMS.conformsTo, concept), graph)
        self.assertIn((ontology, RDF.type, URIRef("http://www.w3.org/2002/07/owl#Ontology")), graph)


if __name__ == "__main__":
    unittest.main()
