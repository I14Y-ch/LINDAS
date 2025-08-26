import requests as r
from .config import *
from rdflib import Literal 

def get_concept_data(concept_id):
    """Get combined concept metadata and codelist entries"""
    try:
        # Get concept metadata
        meta_url = f"{BASE_API_URL}{concept_id}"
        meta_response = r.get(meta_url, verify=False)
        meta_response.raise_for_status()
        concept_data = meta_response.json()['data']
        
        # Get codelist entries (if it's a CodeList concept)
        if concept_data.get('conceptType') == 'CodeList':
            entries_url = f"{BASE_API_URL}{concept_id}/codelist-entries/exports/json"
            entries_response = r.get(entries_url, verify=False)
            entries_response.raise_for_status()
            concept_data['codeListEntries'] = entries_response.json()['data']
        
        # Return in legacy format
        return {'data': concept_data}
    
    except Exception as e:
        print(f"Error fetching concept data for {concept_id}: {str(e)}")
        raise

def get_version_list(concept_identifier):
    """Get list of versions using the filter approach"""
    try:
        url = f"{BASE_API_URL}"
        params = {
            'conceptIdentifier': concept_identifier,
            'publicationLevel': 'Public',
            'pageSize': 100
        }
        
        response = r.get(url, params=params, verify=False)
        response.raise_for_status()
        
        concepts = response.json().get('data', [])
        
        versions = []
        for concept in concepts:
            versions.append({
                'id': concept.get('id'),
                'version': concept.get('version'),
                'validFrom': concept.get('validFrom'),
                'registrationStatus': concept.get('registrationStatus')
            })
        
        sorted_versions = sorted(versions, key=lambda x: x['validFrom'])
        
        version_data = []
        failed_concepts = []
        
        for version in sorted_versions:
            try:
                data = get_concept_data(version['id'])
                version_data.append(data["data"])
            except Exception as e:
                failed_concepts.append(version['id'])
                print(f"Warning: Failed to retrieve concept {version['id']}, continuing with other versions: {str(e)}")
        
        # Give warning if any concepts failed to retrieve
        if failed_concepts:
            print(f"Warning: {len(failed_concepts)} concept(s) could not be retrieved: {', '.join(failed_concepts)}")
        
        return version_data

    except Exception as e:
        print(f"Error fetching versions for {concept_identifier}: {str(e)}")
        raise

def get_all_concepts(registration_statuses=None):
    """Get all CodeList concepts with specified registration statuses"""
    base_url = f"{BASE_API_URL}"
    all_concepts = []
    printed_count = 0  
    failed_concepts = []

    if registration_statuses is None:
        registration_statuses = ['Standard', 'Qualified', 'PreferredStandard']

    page = 1
    while True:
        params = {
            'publicationLevel': 'Public',
            'page': page,
            'pageSize': 100  
        }
        
        response = r.get(base_url, params=params, verify=False)
        response.raise_for_status()
        data = response.json().get('data', [])
        
        if not data:
            break
            
        filtered = [
            c for c in data 
            if (c.get('conceptType') == 'CodeList' 
                and c.get('registrationStatus') in registration_statuses
                and c.get('id') not in EXCLUDED_IDS)
        ]

        for i, concept in enumerate(filtered, printed_count + 1):
            print(f"{i}. Identifier: {concept.get('identifier')}")
            print(f"   Title: {concept.get('name')}")
            print(f"   Status: {concept.get('registrationStatus')}")
            print(f"   Version: {concept.get('version')}\n")
        
        all_concepts.extend(filtered)
        printed_count = len(all_concepts)  
        
        if len(data) < 100:
            break
            
        page += 1
    
    # Give warning if any concepts failed during processing
    if failed_concepts:
        print(f"Warning: {len(failed_concepts)} concept(s) could not be retrieved during processing: {', '.join(failed_concepts)}")
                
    return all_concepts

def is_valid_value(value):
    """check for multilingual field if the value is not empty"""
    if value is None:
        return False
    clean_value = str(value).strip().upper()
    return clean_value and clean_value not in {"NA", "N/A", "-", "NULL", "NONE"}

class VersionDiff:
    @staticmethod
    def find_deleted_entries(old_version_data, new_version_data):
        """
        Compare two versions and find entries present in old_version but missing in new_version
        Returns list of deleted entry codes
        """
        old_entries = {e['code'] for e in old_version_data.get('codeListEntries', [])}
        new_entries = {e['code'] for e in new_version_data.get('codeListEntries', [])}
        return list(old_entries - new_entries)

    # @staticmethod
    # def find_modified_entries(old_version_data, new_version_data):
    #     """
    #     Compare two versions and find entries that have been modified
    #     Returns dict of {code: old_entry_data}
    #     """
    #     modified = {}
    #     new_entries = {e['code']: e for e in new_version_data.get('codeListEntries', [])}
        
    #     for old_entry in old_version_data.get('codeListEntries', []):
    #         code = old_entry['code']
    #         if code in new_entries:
    #             # Simple comparison - in real implementation you might want to compare specific fields
    #             if old_entry != new_entries[code]:
    #                 modified[code] = old_entry
    #     return modified

    # @staticmethod
    # def find_added_entries(old_version_data, new_version_data):
    #     """
    #     Compare two versions and find entries added in new_version
    #     Returns list of new entry codes
    #     """
    #     old_entries = {e['code'] for e in old_version_data.get('codeListEntries', [])}
    #     new_entries = {e['code'] for e in new_version_data.get('codeListEntries', [])}
    #     return list(new_entries - old_entries)

    # @staticmethod
    # def has_changes(old_entry, new_entry):
    #     """Compare two entries to detect meaningful changes"""
    #     # Compare basic fields
    #     if old_entry.get('name') != new_entry.get('name'):
    #         return True
    #     if old_entry.get('description') != new_entry.get('description'):
    #         return True
    #     if old_entry.get('code') != new_entry.get('code'):
    #         return True
            
    #     # Compare annotations if they exist
    #     if old_entry.get('annotations') != new_entry.get('annotations'):
    #         return True
            
    #     return False

    # @staticmethod
    # def get_unchanged_entries(old_version_data, new_version_data):
    #     """
    #     Find entries that are truly unchanged between versions
    #     Returns dict of {code: entry_data} that are identical
    #     """
    #     unchanged = {}
    #     old_entries = {e['code']: e for e in old_version_data.get('codeListEntries', [])}
        
    #     for new_entry in new_version_data.get('codeListEntries', []):
    #         code = new_entry['code']
    #         if code in old_entries and not VersionDiff.has_changes(old_entries[code], new_entry):
    #             unchanged[code] = old_entries[code]
    #     return unchanged
    
    # @staticmethod
    # def is_newer_version(current_version, existing_version):
    #     """Compare version strings to determine which is newer"""
    #     from packaging import version

    #     return version.parse(current_version) > version.parse(existing_version)


