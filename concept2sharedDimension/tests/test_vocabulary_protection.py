from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import ConjunctiveGraph, Graph, Literal, Namespace, URIRef
ORG = Namespace("http://www.w3.org/ns/org#")
from rdflib.namespace import DCTERMS, RDF, FOAF

from concept2sharedDimension.src.versioning.config import AGENT_URI_BASE, BASE_URI, STATUSES, TARGET_GRAPH
from concept2sharedDimension.src.versioning.core import ConceptMetadataManager, GraphManager
from concept2sharedDimension.src.versioning.processor import VersionProcessor

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

    def test_all_codelist_versions_are_exported(self) -> None:
        class ConceptsResponse:
            def __init__(self, data):
                self._data = data

            def json(self):
                return {"data": self._data}

            def raise_for_status(self) -> None:
                return None

        rows = [
            {
                "id": "current-codelist",
                "identifiers": ["CURRENT_CODELIST"],
                "validFrom": "2026-01-01",
                "version": "2.0.0",
                "conceptType": "CodeList",
                "registrationStatus": "Recorded",
            },
            {
                "id": "old-string",
                "identifiers": ["CURRENT_CODELIST"],
                "validFrom": "2025-01-01",
                "version": "1.0.0",
                "conceptType": "String",
                "registrationStatus": "Recorded",
            },
            {
                "id": "current-string",
                "identifiers": ["CURRENT_STRING"],
                "validFrom": "2026-01-01",
                "version": "2.0.0",
                "conceptType": "String",
                "registrationStatus": "Recorded",
            },
            {
                "id": "old-codelist",
                "identifiers": ["CURRENT_STRING"],
                "validFrom": "2025-01-01",
                "version": "1.0.0",
                "conceptType": "CodeList",
                "registrationStatus": "Recorded",
            },
        ]
        saved_ids = I14YAPIHelper.local_id_concepts_map
        saved_versions = I14YAPIHelper.local_identifier_concepts_map
        saved_counts = I14YAPIHelper.source_concept_status_counts
        saved_inventory_loaded = I14YAPIHelper.source_inventory_loaded
        try:
            I14YAPIHelper.local_id_concepts_map = {}
            I14YAPIHelper.local_identifier_concepts_map = {}
            I14YAPIHelper.source_concept_status_counts = {}
            I14YAPIHelper.source_inventory_loaded = False
            with patch(
                "concept2sharedDimension.src.versioning.utils.r.get",
                return_value=ConceptsResponse(rows),
            ):
                selected = I14YAPIHelper.get_all_concepts(["Recorded"])

            self.assertEqual(
                ["CURRENT_CODELIST", "CURRENT_STRING"],
                [item["identifiers"][0] for item in selected],
            )
            self.assertEqual({"Recorded": 2}, I14YAPIHelper.get_exported_concept_status_counts(["Recorded"]))
            self.assertEqual({"2.0.0"}, I14YAPIHelper.get_exported_concept_versions("CURRENT_CODELIST"))
            self.assertEqual({"1.0.0"}, I14YAPIHelper.get_exported_concept_versions("CURRENT_STRING"))
        finally:
            I14YAPIHelper.local_id_concepts_map = saved_ids
            I14YAPIHelper.local_identifier_concepts_map = saved_versions
            I14YAPIHelper.source_concept_status_counts = saved_counts
            I14YAPIHelper.source_inventory_loaded = saved_inventory_loaded

    def test_export_manifest_is_reused_by_a_fresh_batch_process(self) -> None:
        status = STATUSES[0]
        old_version = {
            "id": "frozen-old",
            "identifiers": ["FROZEN"],
            "version": "1.0.0",
            "validFrom": "2025-01-01",
            "registrationStatus": status,
            "conceptType": "CodeList",
        }
        latest_version = {
            "id": "frozen-latest",
            "identifiers": ["FROZEN"],
            "version": "2.0.0",
            "validFrom": "2026-01-01",
            "registrationStatus": status,
            "conceptType": "CodeList",
            "name": {"fr": "Frozen metadata"},
        }
        saved_ids = I14YAPIHelper.local_id_concepts_map
        saved_versions = I14YAPIHelper.local_identifier_concepts_map
        saved_counts = I14YAPIHelper.source_concept_status_counts
        saved_inventory_loaded = I14YAPIHelper.source_inventory_loaded
        try:
            I14YAPIHelper.local_id_concepts_map = {latest_version["id"]: latest_version}
            I14YAPIHelper.local_identifier_concepts_map = {"FROZEN": [old_version, latest_version]}
            I14YAPIHelper.source_concept_status_counts = {status: 2}
            I14YAPIHelper.source_inventory_loaded = True

            with TemporaryDirectory() as directory:
                manifest_path = Path(directory) / "concept_source_manifest.json"
                I14YAPIHelper.write_export_manifest(manifest_path)

                # Simulate the separate GitHub Actions batch process.
                I14YAPIHelper.local_id_concepts_map = {}
                I14YAPIHelper.local_identifier_concepts_map = {}
                I14YAPIHelper.source_concept_status_counts = {}
                I14YAPIHelper.source_inventory_loaded = False
                I14YAPIHelper.load_export_manifest(manifest_path)

                selected = I14YAPIHelper.get_all_concepts()
                self.assertEqual([latest_version["id"]], [item["id"] for item in selected])
                self.assertEqual({"fr": "Frozen metadata"}, selected[0]["name"])
                self.assertEqual({status: 2}, I14YAPIHelper.get_exported_concept_status_counts([status]))
                self.assertEqual({"1.0.0", "2.0.0"}, I14YAPIHelper.get_exported_concept_versions("FROZEN"))

                def get_changed_detail(concept_id):
                    return {
                        "data": {
                            "id": concept_id,
                            "identifiers": ["FROZEN"],
                            "version": "changed-after-scan",
                            "validFrom": "2099-01-01",
                            "registrationStatus": "ChangedAfterScan",
                            "conceptType": "CodeList",
                            "codeListEntries": [],
                        }
                    }

                with patch.object(I14YAPIHelper, "get_concept_data", side_effect=get_changed_detail):
                    version_data = I14YAPIHelper.get_version_list("FROZEN")

            self.assertEqual(["1.0.0", "2.0.0"], [item["version"] for item in version_data])
            self.assertEqual([status, status], [item["registrationStatus"] for item in version_data])
        finally:
            I14YAPIHelper.local_id_concepts_map = saved_ids
            I14YAPIHelper.local_identifier_concepts_map = saved_versions
            I14YAPIHelper.source_concept_status_counts = saved_counts
            I14YAPIHelper.source_inventory_loaded = saved_inventory_loaded

    def test_version_set_difference_bypasses_modified_at_cutoff(self) -> None:
        concept = {
            "id": "current-codelist",
            "identifiers": ["CURRENT_CODELIST"],
            "validFrom": "2026-01-01",
            "version": "2.0.0",
            "conceptType": "CodeList",
            "registrationStatus": "Recorded",
            "codeListEntries": [{"code": "A"}],
            "system": {"modifiedAt": "2020-01-01T00:00:00+00:00"},
        }
        saved_ids = I14YAPIHelper.local_id_concepts_map
        saved_versions = I14YAPIHelper.local_identifier_concepts_map
        try:
            I14YAPIHelper.local_id_concepts_map = {concept["id"]: concept}
            I14YAPIHelper.local_identifier_concepts_map = {"CURRENT_CODELIST": [concept]}
            with TemporaryDirectory() as directory, patch.object(
                LindasAPIHelper,
                "get_lindas_concept_versions",
                return_value={"CURRENT_CODELIST": ["1.0.0", "2.0.0"]},
            ), patch.object(LindasAPIHelper, "delete_concept") as delete_concept, patch.object(
                VersionProcessor, "process_new_concept"
            ) as process_new_concept:
                processor = VersionProcessor(BASE_URI, Path(directory) / "concept.ttl")
                processor.process_all_concepts(concept_ids=[concept["id"]], clear_graph=False)
                processor.vm.close()

            delete_concept.assert_called_once_with("CURRENT_CODELIST")
            process_new_concept.assert_called_once_with(concept["id"])
        finally:
            I14YAPIHelper.local_id_concepts_map = saved_ids
            I14YAPIHelper.local_identifier_concepts_map = saved_versions

    def test_concept_status_counts_use_i14y_search_headers(self) -> None:
        class SearchResponse:
            def __init__(self, total: str):
                self.headers = {"x-paging-totalrows": total}

            def raise_for_status(self) -> None:
                return None

        with patch(
            "concept2sharedDimension.src.versioning.utils.r.get",
            side_effect=[SearchResponse("92"), SearchResponse("14")],
        ) as get:
            counts = I14YAPIHelper.get_concept_status_counts(["Standard", "PreferredStandard"])

        self.assertEqual({"Standard": 92, "PreferredStandard": 14}, counts)
        self.assertEqual(
            {
                "registrationStatuses": "Standard",
                "types": "Concept",
                "conceptValueTypes": "CodeList",
                "page": 1,
                "pageSize": 25,
            },
            get.call_args_list[0].kwargs["params"],
        )
if __name__ == "__main__":
    unittest.main()