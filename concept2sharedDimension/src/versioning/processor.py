from .core import ConceptMetadataManager, CodeListManager, GraphManager
from .utils import I14YAPIHelper, LindasAPIHelper, VersionDiff, timer
from .config import CLEAR_GRAPH, DEBUG_INCLUDE_CODE_VERSIONS, OUTPUT_FILE_NAME, vl

class VersionProcessor:
    def __init__(self, base_uri,output_file=OUTPUT_FILE_NAME):
        self.vm = GraphManager(base_uri,output_file=output_file)
        self.metadata = ConceptMetadataManager(self.vm)
        self.codelist = CodeListManager(self.vm)
        # self.all_entry_codes = set()
        # self.version_data = []
        self.failed_concepts = []  # Track failed concepts

    @timer
    def process_all_concepts(self, concept_ids=None, registration_statuses=None, clear_graph=CLEAR_GRAPH):
        """Process multiple concepts"""
        if concept_ids is None:
            concepts = I14YAPIHelper.get_all_concepts(registration_statuses)
            concept_ids = [c['id'] for c in concepts]
        else:
            concepts = [I14YAPIHelper.get_concept_data(id)['data'] for id in concept_ids]

        if not clear_graph:

            concepts_to_delete_identifiers = set()

            concepts_unchanged = []

            for concept in concepts:
                identifier = concept["identifier"]
                concept_id = concept["id"]
                # Versions are sorted in chronological order
                i14y_code_versions = I14YAPIHelper.get_i14y_code_versions(identifier)
                lindas_code_versions = LindasAPIHelper.get_lindas_code_versions(identifier)

                if set(i14y_code_versions.keys()) != set(lindas_code_versions.keys()):
                    print(f"DEBUG: for concept {identifier} there are different versions on LINDAS and i14y")
                    concepts_to_delete_identifiers.add(identifier)
                    continue

                nb_same_versions = 0
                for version, codes in i14y_code_versions.items():
                    if codes != lindas_code_versions.get(version, {}):
                        print(f"DEBUG: for concept {identifier} version {version} there is a difference between i14y and lindas codes")
                        concepts_to_delete_identifiers.add(identifier)
                        break
                    else:
                        print(f"DEBUG: for concept {identifier} version {version} there is no difference between i14y and lindas codes")
                        nb_same_versions += 1

                if nb_same_versions == len(lindas_code_versions.keys()):
                    concepts_unchanged.append(concept_id)

            for concept_identifier in concepts_to_delete_identifiers:
                LindasAPIHelper.delete_concept(concept_identifier)

            # We reimport only concepts that have changed on I14y
            concept_ids = list(set(concept_ids) - set(concepts_unchanged))

        for concept_id in concept_ids:
            self.process_new_concept(concept_id)

        # Print summary of failed concepts
        if self.failed_concepts:
            print(f"Warning: {len(self.failed_concepts)} concept(s) failed to process: {', '.join(self.failed_concepts)}")

        return self.vm.graph

    def process_new_concept(self, concept_id):
        self.codelist = CodeListManager(self.vm)
        concept_meta = I14YAPIHelper.get_concept_data(concept_id)

        # Check if concept retrieval failed
        if concept_meta is None:
            raise ValueError(f"Concept {concept_id} could not be retrieved")

        concept_identifier = concept_meta["data"].get("identifier")
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
            self.vm.set_current_identifier_version(current_data["identifier"], current_data["version"])

            if i == len(version_data)-1:
                self._process_latest_version(current_data)
            else:
                self._process_older_version(current_data, next_data)

        return self.vm.graph

    def _process_entry_with_identity(self, concept_data, entry, version_uri, version_all_uri, identity_uri, identity_all_uri):
        """Process an entry ensuring both version and identity are created"""
        entry_version_uri = self.vm.create_uri(concept_data['identifier'],entry['code'],concept_data['version'])

        self.codelist._process_entry(entry,concept_data,version_uri,version_all_uri,is_version=True)

        entry_identity_uri = self.vm.create_uri(concept_data['identifier'], entry['code'])
        self.codelist._process_entry(entry,concept_data,identity_uri,identity_all_uri,is_version=False)

        if DEBUG_INCLUDE_CODE_VERSIONS:
            self.codelist.add_versioning_relationships(entry_version_uri, entry_identity_uri)

    def _process_latest_version(self, concept_data):
        """Process latest version"""
        identity_uri = self.vm.create_uri(concept_data['identifier'])
        version_uri = self.vm.create_uri(concept_data['identifier'], version=concept_data['version'])

        # It's useful to reset self.codelist
        self.codelist = CodeListManager(self.vm)

        # First create the identity hierarchy (without level info)
        self.metadata.add_scheme_metadata(identity_uri, concept_data, is_version=False)
        identity_all_uri = self.metadata.add_concept_hierarchy(identity_uri, concept_data, is_version=False)

        # Create version hierarchy (with level info)
        self.metadata.add_scheme_metadata(version_uri, concept_data, is_version=True)
        version_all_uri = self.metadata.add_concept_hierarchy(version_uri, concept_data, is_version=True)

        # Now process all entries which will populate level information
        current_entries = {e['code']: e for e in concept_data.get('codeListEntries', [])}
        for code, entry in current_entries.items():
            self._process_entry_with_identity(concept_data, entry, version_uri, version_all_uri, identity_uri, identity_all_uri)

        # After processing all entries, add the level information to hierarchies
        self._add_level_information_to_hierarchy( identity_uri, identity_all_uri, concept_data, is_version=False)
        self._add_level_information_to_hierarchy(version_uri,  version_all_uri, concept_data, is_version=True)

        self.codelist.add_versioning_relationships(version_uri, identity_uri)

    def _add_level_information_to_hierarchy(self, concept_uri, all_uri, concept_data, is_version):
        """Add level information to an existing hierarchy"""
        if not hasattr(self.codelist, 'levels_info_all') or not self.codelist.levels_info_all:
            return

        # Add the collected level information
        self.metadata._add_xkos_level_information(concept_uri,all_uri, self.codelist.level_depths, self.codelist.levels_dict, self.codelist.levels_info_all, is_version, concept_data )

    def _process_older_version(self, version_data, next_version_data=None):
        """Process older version with combined codelist and concept handling"""
        version_uri = self.vm.create_uri(version_data['identifier'], version=version_data['version'])
        identity_uri = self.vm.create_uri(version_data['identifier'])
        identity_all_uri = self.vm.create_uri(version_data['identifier'], "all")

        # It's useful to reset self.codelist
        self.codelist = CodeListManager(self.vm)

        # First create basic hierarchy without level info
        self.metadata.add_scheme_metadata(version_uri, version_data, is_version=True)
        version_all_uri = self.metadata.add_concept_hierarchy( version_uri,  version_data, is_version=True)

        # Process all entries which will populate level information
        for entry in version_data.get('codeListEntries', []):
            entry_version_uri = self.vm.create_uri(version_data['identifier'],entry['code'],version_data['version'])

            self.codelist._process_entry(entry, version_data,version_uri,version_all_uri,is_version=True)

            if DEBUG_INCLUDE_CODE_VERSIONS:
                if next_version_data and entry['code'] in {e['code'] for e in next_version_data.get('codeListEntries', [])}:
                    next_entry_uri = self.vm.create_uri(version_data['identifier'], entry['code'], next_version_data['version'] )
                    self.vm.graph.add((entry_version_uri, vl.successor, next_entry_uri))
                    self.vm.graph.add((next_entry_uri, vl.predecessor, entry_version_uri))

        # Add the level information after processing all entries
        self._add_level_information_to_hierarchy(version_uri, version_all_uri, version_data,is_version=True)

        if DEBUG_INCLUDE_CODE_VERSIONS:
            if next_version_data:
                deleted_entries = VersionDiff.find_deleted_entries(version_data, next_version_data)
                for code in deleted_entries:
                    entry = next(e for e in version_data['codeListEntries'] if e['code'] == code)
                    entry_version_uri = self.vm.create_uri(version_data['identifier'], code,version_data['version'])

                    # Mark as deprecated in identity
                    entry_identity_uri = self.vm.create_uri(version_data['identifier'], code)
                    self.codelist.mark_as_deprecated(entry_identity_uri,valid_to=version_data.get('validTo'))

                    # Also mark last version as deprecated
                    self.codelist.mark_as_deprecated(entry_version_uri,valid_to=version_data.get('validTo'))

                    self.codelist.add_versioning_relationships(entry_version_uri, entry_identity_uri)

                    self.codelist._process_entry(entry,version_data,identity_uri,identity_all_uri,is_version=False)

        if next_version_data:
            next_version_uri = self.vm.create_uri(version_data['identifier'], version=next_version_data['version'])
            self.vm.graph.add((version_uri, vl.successor, next_version_uri))
            self.vm.graph.add((next_version_uri, vl.predecessor, version_uri))
