from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import Graph, Literal, Namespace, URIRef
ORG = Namespace("http://www.w3.org/ns/org#")
from rdflib.namespace import DCTERMS, RDF, FOAF

from concept2sharedDimension.src.versioning.config import AGENT_URI_BASE, BASE_URI
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

    def test_force_delete_bypasses_protected_vocabulary_guard(self) -> None:
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions") as protected, patch.object(
            LindasAPIHelper, "get_lindas_concept_versions"
        ) as lindas_versions, patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("DV_DCAT_DATASET_THEME", force=True)

        protected.assert_not_called()
        lindas_versions.assert_not_called()
        self.assertEqual(2, update.call_count)
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
        self.assertIn("dct:publisher ?publisher", subject_delete)
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
        self.assertIn("?p = <http://purl.org/dc/terms/conformsTo>", object_delete)
        self.assertIn('STRSTARTS(STR(?s), "https://register.ld.admin.ch/i14y/dataset/")', object_delete)
        self.assertIn('CONTAINS(STR(?s), "/structure/")', object_delete)


if __name__ == "__main__":
    unittest.main()