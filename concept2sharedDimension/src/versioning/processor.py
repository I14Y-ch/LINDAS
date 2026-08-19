from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import re
from .core import ConceptMetadataManager, CodeListManager, GraphManager
from .utils import I14YAPIHelper, LindasAPIHelper, VersionDiff, timer
from .config import CLEAR_GRAPH, DEBUG_INCLUDE_CODE_VERSIONS, I14Y_MODIFIED_LOOKBACK_HOURS, MAX_WORKERS, OUTPUT_FILE_NAME, vl


class VersionProcessor:
    def __init__(self, base_uri, output_file=OUTPUT_FILE_NAME):
        self.vm = GraphManager(base_uri, output_file=output_file)
        self.metadata = ConceptMetadataManager(self.vm)
        self.codelist = CodeListManager(self.vm)
        # self.all_entry_codes = set()
        # self.version_data = []
        self.failed_concepts = []  # Track failed concepts

    @staticmethod
    def _parse_i14y_modified_at(concept):
        modified_at = concept.get("system", {}).get("modifiedAt")
        if not modified_at:
            return None

        modified_at = modified_at.strip()
        if modified_at.endswith("Z"):
            modified_at = modified_at[:-1] + "+00:00"

        def normalize_fraction(match):
            fraction = match.group(1)[:6].ljust(6, "0")
            return f".{fraction}"

        modified_at = re.sub(r"\.(\d+)(?=(?:[+-]\d{2}:?\d{2})?$)", normalize_fraction, modified_at)

        parsed = datetime.fromisoformat(modified_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _concept_needs_reimport_by_deep_comparison(self, concept):
        identifier = concept["identifiers"][0]

        i14y_code_versions = I14YAPIHelper.get_i14y_code_versions(identifier)
        lindas_code_versions = LindasAPIHelper.get_lindas_code_versions(identifier)

        if not self.i14y_concept_equal_lindas_concept(identifier):
            print(f"DEBUG: for concept {identifier} there are differences in attributes between LINDAS and i14y")
            return True, True

        not_same_versions = set(i14y_code_versions.keys()) != set(lindas_code_versions.keys())
        if not_same_versions:
            print(f"DEBUG: for concept {identifier} there are different versions on LINDAS and i14y")

        empty_codelist = all([len(codelist) == 0 for codelist in i14y_code_versions.values()])
        if empty_codelist:
            print(f"DEBUG: for concept {identifier} the codelist is empty on i14y")
            return not_same_versions, False

        if not_same_versions:
            return True, True

        nb_same_versions = 0
        for version, codes in i14y_code_versions.items():
            if codes != lindas_code_versions.get(version, {}):
                print(
                    f"DEBUG: for concept {identifier} version {version} "
                    "there is a difference between i14y and lindas codes"
                )
                return True, True

            print(
                f"DEBUG: for concept {identifier} version {version} "
                "there is no difference between i14y and lindas codes"
            )
            nb_same_versions += 1

        if nb_same_versions == len(lindas_code_versions.keys()):
            return False, False

        return False, False

    def i14y_concept_equal_lindas_concept(self, identifier):

        def normalize_text(s):
            return s.replace("\r\n", "\n").replace("\r", "\n").strip()

        lindas_concept_attributes = LindasAPIHelper.get_lindas_concept_attributes(identifier)
        concept_version_list = I14YAPIHelper.get_version_list(identifier)

        # The concept versiosn are sorted by chronological order
        for i14y_concept in concept_version_list:
            i14y_version = i14y_concept["version"]

            if i14y_version not in lindas_concept_attributes.keys():
                return False

            lindas_concept = lindas_concept_attributes[i14y_version]

            if not i14y_concept["registrationStatus"] == lindas_concept["registrationStatus"]:
                return False

            for attribute in ["name", "description"]:
                for lang, i14y_attr in i14y_concept[attribute].items():
                    if i14y_attr and lang not in lindas_concept[attribute].keys():
                        return False
                    if i14y_attr and not normalize_text(i14y_attr) == normalize_text(lindas_concept[attribute][lang]):
                        return False

        return True

    @timer
    def process_all_concepts(self, concept_ids=None, registration_statuses=None, clear_graph=CLEAR_GRAPH):
        """Process multiple concepts"""
        if concept_ids is None:
            concepts = I14YAPIHelper.get_all_concepts(registration_statuses)
            concept_ids = [c["id"] for c in concepts]
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(I14YAPIHelper.get_concept_data, cid): cid for cid in concept_ids}
                concepts = [future.result()["data"] for future in as_completed(futures)]

        if not clear_graph:
            lindas_concept_versions = LindasAPIHelper.get_lindas_concept_versions()
            known_lindas_identifiers = set(lindas_concept_versions.keys())
            modified_cutoff = datetime.now(timezone.utc) - timedelta(hours=I14Y_MODIFIED_LOOKBACK_HOURS)
            concepts_to_delete_identifiers = set()
            concepts_to_process = []

            print(f"DEBUG: incremental mode uses i14y system.modifiedAt cutoff {modified_cutoff.isoformat()}")

            for concept in concepts:
                concept_id = concept["id"]
                identifier = concept["identifiers"][0]

                if identifier not in known_lindas_identifiers:
                    print(f"DEBUG: concept {identifier} is missing on LINDAS and will be imported")
                    concepts_to_process.append(concept_id)
                    continue

                source_versions = I14YAPIHelper.get_exported_concept_versions(identifier)
                lindas_versions = set(lindas_concept_versions.get(identifier, []))
                if source_versions and source_versions != lindas_versions:
                    print(
                        f"DEBUG: concept {identifier} has different CodeList versions "
                        "on i14y and LINDAS, will be deleted and reimported"
                    )
                    concepts_to_delete_identifiers.add(identifier)
                    concepts_to_process.append(concept_id)
                    continue

                try:
                    modified_at = self._parse_i14y_modified_at(concept)
                except ValueError as e:
                    print(
                        f"WARNING: concept {identifier} has invalid i14y system.modifiedAt, "
                        f"falling back to deep comparison: {e}"
                    )
                    should_delete, should_process = self._concept_needs_reimport_by_deep_comparison(concept)
                    if should_delete:
                        concepts_to_delete_identifiers.add(identifier)
                    if should_process:
                        concepts_to_process.append(concept_id)
                    continue

                if modified_at is None:
                    print(
                        f"DEBUG: concept {identifier} has no i14y system.modifiedAt, "
                        "falling back to deep comparison"
                    )
                    should_delete, should_process = self._concept_needs_reimport_by_deep_comparison(concept)
                    if should_delete:
                        concepts_to_delete_identifiers.add(identifier)
                    if should_process:
                        concepts_to_process.append(concept_id)
                    continue

                if modified_at >= modified_cutoff:
                    print(
                        f"DEBUG: concept {identifier} modified at {modified_at.isoformat()} "
                        "on i14y, will be deleted and reimported"
                    )
                    concepts_to_delete_identifiers.add(identifier)
                    concepts_to_process.append(concept_id)
                else:
                    print(
                        f"DEBUG: concept {identifier} modified at {modified_at.isoformat()} "
                        "on i14y, no reimport needed"
                    )

            for concept_identifier in concepts_to_delete_identifiers:
                LindasAPIHelper.delete_concept(concept_identifier)

            concept_ids = concepts_to_process

        for concept_id in concept_ids:
            self.process_new_concept(concept_id)

        # Print summary of failed concepts
        if self.failed_concepts:
            print(
                f"Warning: {len(self.failed_concepts)} concept(s) failed to process: {', '.join(self.failed_concepts)}"
            )

        return self.vm.graph

    def process_new_concept(self, concept_id):
        self.codelist = CodeListManager(self.vm)
        concept_meta = I14YAPIHelper.get_concept_data(concept_id)

        # Check if concept retrieval failed
        if concept_meta is None:
            raise ValueError(f"Concept {concept_id} could not be retrieved")

        concept_identifier = concept_meta["data"].get("identifiers")[0]
        version_data = I14YAPIHelper.get_version_list(concept_identifier)
        if not version_data:
            print(f"Skipping concept {concept_identifier}, no version data")
            return

        if not version_data:
            raise ValueError("No version data found")

        # all entry codes that ever existed
        # for data in version_data:
        #     self.all_entry_codes.update(e['code'] for e in data.get('codeListEntries', []))

        # if len(version_data) > 1:
        #     print(f"DEBUG: Concept with multiple versions: {concept_id}")

        # chronological order
        for i, current_data in enumerate(version_data):
            previous_data = version_data[i - 1] if i > 0 else None
            next_data = version_data[i + 1] if i < len(version_data) - 1 else None
            self.vm.set_current_identifier_version(current_data["identifiers"][0], current_data["version"])

            if i == len(version_data) - 1:
                self._process_latest_version(current_data)
            else:
                self._process_older_version(current_data, next_data)

        return self.vm.graph

    def _process_entry_with_identity(
        self, concept_data, entry, version_uri, version_all_uri, identity_uri, identity_all_uri
    ):
        """Process an entry ensuring both version and identity are created"""
        entry_version_uri = self.vm.create_uri(concept_data["identifiers"][0], entry["code"], concept_data["version"])

        self.codelist._process_entry(entry, concept_data, version_uri, version_all_uri, is_version=True)

        entry_identity_uri = self.vm.create_uri(concept_data["identifiers"][0], entry["code"])
        self.codelist._process_entry(entry, concept_data, identity_uri, identity_all_uri, is_version=False)

        if DEBUG_INCLUDE_CODE_VERSIONS:
            self.codelist.add_versioning_relationships(entry_version_uri, entry_identity_uri)

    def _process_latest_version(self, concept_data):
        """Process latest version"""
        identity_uri = self.vm.create_uri(concept_data["identifiers"][0])
        version_uri = self.vm.create_uri(concept_data["identifiers"][0], version=concept_data["version"])

        # It's useful to reset self.codelist
        self.codelist = CodeListManager(self.vm)

        # First create the identity hierarchy (without level info)
        self.metadata.add_scheme_metadata(identity_uri, concept_data, is_version=False)
        identity_all_uri = self.metadata.add_concept_hierarchy(identity_uri, concept_data, is_version=False)

        # Create version hierarchy (with level info)
        self.metadata.add_scheme_metadata(version_uri, concept_data, is_version=True)
        version_all_uri = self.metadata.add_concept_hierarchy(version_uri, concept_data, is_version=True)

        # Now process all entries which will populate level information
        current_entries = {e["code"]: e for e in concept_data.get("codeListEntries", [])}
        for code, entry in current_entries.items():
            self._process_entry_with_identity(
                concept_data, entry, version_uri, version_all_uri, identity_uri, identity_all_uri
            )

        # After processing all entries, add the level information to hierarchies
        self._add_level_information_to_hierarchy(identity_uri, identity_all_uri, concept_data, is_version=False)
        self._add_level_information_to_hierarchy(version_uri, version_all_uri, concept_data, is_version=True)

        self.codelist.add_versioning_relationships(version_uri, identity_uri)

    def _add_level_information_to_hierarchy(self, concept_uri, all_uri, concept_data, is_version):
        """Add level information to an existing hierarchy"""
        if not hasattr(self.codelist, "levels_info_all") or not self.codelist.levels_info_all:
            return

        # Add the collected level information
        self.metadata._add_xkos_level_information(
            concept_uri,
            all_uri,
            self.codelist.level_depths,
            self.codelist.levels_dict,
            self.codelist.levels_info_all,
            is_version,
            concept_data,
        )

    def _process_older_version(self, version_data, next_version_data=None):
        """Process older version with combined codelist and concept handling"""
        version_uri = self.vm.create_uri(version_data["identifiers"][0], version=version_data["version"])
        identity_uri = self.vm.create_uri(version_data["identifiers"][0])
        identity_all_uri = self.vm.create_uri(version_data["identifiers"][0], "all")

        # It's useful to reset self.codelist
        self.codelist = CodeListManager(self.vm)

        # First create basic hierarchy without level info
        self.metadata.add_scheme_metadata(version_uri, version_data, is_version=True)
        version_all_uri = self.metadata.add_concept_hierarchy(version_uri, version_data, is_version=True)

        # Process all entries which will populate level information
        for entry in version_data.get("codeListEntries", []):
            entry_version_uri = self.vm.create_uri(version_data["identifiers"][0], entry["code"], version_data["version"])

            self.codelist._process_entry(entry, version_data, version_uri, version_all_uri, is_version=True)

            if DEBUG_INCLUDE_CODE_VERSIONS:
                if next_version_data and entry["code"] in {
                    e["code"] for e in next_version_data.get("codeListEntries", [])
                }:
                    next_entry_uri = self.vm.create_uri(
                        version_data["identifiers"][0], entry["code"], next_version_data["version"]
                    )
                    self.vm.graph.add((entry_version_uri, vl.successor, next_entry_uri))
                    self.vm.graph.add((next_entry_uri, vl.predecessor, entry_version_uri))

        # Add the level information after processing all entries
        self._add_level_information_to_hierarchy(version_uri, version_all_uri, version_data, is_version=True)

        if DEBUG_INCLUDE_CODE_VERSIONS:
            if next_version_data:
                deleted_entries = VersionDiff.find_deleted_entries(version_data, next_version_data)
                for code in deleted_entries:
                    entry = next(e for e in version_data["codeListEntries"] if e["code"] == code)
                    entry_version_uri = self.vm.create_uri(version_data["identifiers"][0], code, version_data["version"])

                    # Mark as deprecated in identity
                    entry_identity_uri = self.vm.create_uri(version_data["identifiers"][0], code)
                    self.codelist.mark_as_deprecated(entry_identity_uri, valid_to=version_data.get("validTo"))

                    # Also mark last version as deprecated
                    self.codelist.mark_as_deprecated(entry_version_uri, valid_to=version_data.get("validTo"))

                    self.codelist.add_versioning_relationships(entry_version_uri, entry_identity_uri)

                    self.codelist._process_entry(entry, version_data, identity_uri, identity_all_uri, is_version=False)

        if next_version_data:
            next_version_uri = self.vm.create_uri(version_data["identifiers"][0], version=next_version_data["version"])
            self.vm.graph.add((version_uri, vl.successor, next_version_uri))
            self.vm.graph.add((next_version_uri, vl.predecessor, version_uri))
