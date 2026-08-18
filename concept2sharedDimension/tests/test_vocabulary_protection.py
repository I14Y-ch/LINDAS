from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import ConjunctiveGraph, Graph, Literal, Namespace, URIRef
ORG = Namespace("http://www.w3.org/ns/org#")
from rdflib.namespace import DCTERMS, RDF, FOAF

from concept2sharedDimension.src.versioning.config import AGENT_URI_BASE, BASE_URI, TARGET_GRAPH
from concept2sharedDimension.src.versioning.core import ConceptMetadataManager, GraphManager

from concept2sharedDimension.src.versioning.utils import I14YAPIHelper, LindasAPIHelper


class VocabularyProtectionTests(unittest.TestCase):
    def test_protected_vocabulary_is_not_deleted(self) -> None:
        protected = {("DV_DCAT_DATASET_THEME", "1.1.0")}
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=protected), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"DV_DCAT_DATASET_THEME": ["1.1.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            result = LindasAPIHelper.delete_concept("DV_DCAT_DATASET_THEME")

        self.assertFalse(result)
        update.assert_not_called()

    def test_forced_delete_uses_the_production_concept_anchored_closure(self) -> None:
        with patch.object(
            I14YAPIHelper, "get_protected_vocabulary_versions"
        ) as protected, patch.object(
            LindasAPIHelper, "get_lindas_concept_versions"
        ) as lindas_versions, patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("LIFECYCLE_TEST", force=True)

        protected.assert_not_called()
        lindas_versions.assert_not_called()
        self.assertEqual(2, update.call_count)
        query = update.call_args_list[1].args[0]
        self.assertIn("BIND(<https://register.ld.admin.ch/i14y/concept/LIFECYCLE_TEST> AS ?root)", query)
        self.assertIn("SELECT DISTINCT ?s", query)
        self.assertIn("vl:Version|vl:Identity", query)
        self.assertIn("PREFIX oa: <https://www.w3.org/ns/oa#>", query)
        self.assertNotIn("!(rdf:type|", query)
    def test_unprotected_vocabulary_keeps_existing_delete_behavior(self) -> None:
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=set()), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"OTHER": ["1.0.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("OTHER")

        self.assertEqual(2, update.call_count)


    def test_concept_publisher_uses_shared_agent_iri(self) -> None:
        concept_uri = URIRef(f"{BASE_URI}TEST_PUBLISHER")
        concept_data = {
            "id": "test-id",
            "identifiers": ["TEST_PUBLISHER"],
            "version": "1.0.0",
            "validFrom": "2026-01-01",
            "publisher": {"identifier": "CH1", "name": {"fr": "Office fédéral de la statistique"}},
            "name": {"fr": "Concept de test"},
            "description": {"fr": "Description"},
        }
        with TemporaryDirectory() as directory:
            output = Path(directory) / "concept.ttl"
            manager = GraphManager(BASE_URI, output)
            ConceptMetadataManager(manager).add_scheme_metadata(concept_uri, concept_data)
            manager.close()
            graph = Graph().parse(output, format="turtle")

        publisher = URIRef(f"{AGENT_URI_BASE}CH1")
        self.assertIn((concept_uri, DCTERMS.publisher, publisher), graph)
        self.assertIn((publisher, RDF.type, FOAF.Agent), graph)
        self.assertIn((publisher, RDF.type, ORG.Organization), graph)
        self.assertIn((publisher, RDF.type, FOAF.Organization), graph)
        self.assertIn((publisher, FOAF.name, Literal("Office fédéral de la statistique", lang="fr")), graph)

    def test_concept_deletion_keeps_shared_agent_until_last_publisher_reference(self) -> None:
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=set()), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"OTHER": ["1.0.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("OTHER")

        subject_delete = update.call_args_list[1].args[0]
        self.assertIn("?root dct:publisher ?publisher", subject_delete)
        self.assertIn(AGENT_URI_BASE, subject_delete)
        self.assertIn("FILTER NOT EXISTS", subject_delete)
    def test_dataset_structure_conforms_to_link_is_preserved_when_deleting_concept(self) -> None:
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=set()), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"OTHER": ["1.0.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("OTHER")

        object_delete = update.call_args_list[0].args[0]
        self.assertIn("BIND(<https://register.ld.admin.ch/i14y/concept/OTHER> AS ?root)", object_delete)
        self.assertIn("SELECT DISTINCT ?target", object_delete)
        self.assertIn('?root a schema:DefinedTermSet, vl:Version', object_delete)
        self.assertIn("PREFIX oa: <https://www.w3.org/ns/oa#>", object_delete)
        self.assertIn("?incoming_subject ?incoming_predicate ?target", object_delete)
        self.assertIn("?incoming_predicate = <http://purl.org/dc/terms/conformsTo>", object_delete)
        self.assertIn('STRSTARTS(STR(?incoming_subject), "https://register.ld.admin.ch/i14y/dataset/")', object_delete)
        self.assertIn('CONTAINS(STR(?incoming_subject), "/structure/")', object_delete)
        self.assertNotIn('STRSTARTS(STR(?o), "https://register.ld.admin.ch/i14y/concept/OTHER")', object_delete)


    def test_concept_deletion_removes_the_complete_local_hierarchy(self) -> None:
        schema = Namespace("http://schema.org/")
        version_link = Namespace("https://version.link/")
        dataset = ConjunctiveGraph()
        graph = dataset.get_context(URIRef(TARGET_GRAPH))

        root = URIRef(f"{BASE_URI}REGRESSION")
        level = URIRef(f"{BASE_URI}REGRESSION/all")
        entry = URIRef(f"{BASE_URI}REGRESSION/1")
        catalog = URIRef("https://register.ld.admin.ch/i14y/.well-known/void")
        graph.add((root, RDF.type, schema.DefinedTermSet))
        graph.add((root, RDF.type, version_link.Version))
        graph.add((root, schema.identifier, Literal("REGRESSION")))
        graph.add((root, schema.hasPart, level))
        graph.add((level, schema.member, entry))
        graph.add((entry, RDF.type, schema.DefinedTerm))
        graph.add((catalog, schema.dataset, root))

        with patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("REGRESSION", force=True)

        for call in update.call_args_list:
            dataset.update(call.args[0])

        self.assertEqual(0, len(graph))

if __name__ == "__main__":
    unittest.main()