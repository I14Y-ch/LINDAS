from time import time
from urllib.parse import urlparse
import requests as r
import stardog
from .config import *
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def timer(func):
    """Decorator that shows the execution time of the function object passed"""

    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        print(f"Function {func.__name__!r} executed in {(t2-t1):.4f}s")
        return result

    return wrap_func

def delete_orphaned_concepts_lindas():
    lindas_concept_versions = LindasAPIHelper.get_lindas_concept_versions()

    concepts_to_delete_identifiers = set(lindas_concept_versions.keys()) - set(
        [c["identifier"] for c in I14YAPIHelper.get_all_concepts()]
    )

    for concept_identifier in concepts_to_delete_identifiers:
        LindasAPIHelper.delete_concept(concept_identifier)

class LindasAPIHelper:

    # Key: concept identifier, value: set of versions
    lindas_concept_versions = {}

    # Key: concept identifier, value:
    #    dict with key: version and value: set of codes
    lindas_code_versions = {}

    @staticmethod
    def get_stardog_db_conn():
        stardog_url = os.environ.get("STARDOG_URL","")
        stardog_user = os.environ.get("STARDOG_USER","")
        stardog_password = os.environ.get("STARDOG_PASSWORD","")

        # Extract database from URL
        parsed = urlparse(stardog_url)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) > 0 and path_parts[-1]:
            database = path_parts[-1]
            endpoint = parsed._replace(path="/" + "/".join(path_parts[:-1])).geturl()
        else:
            database = os.environ.get("STARDOG_DATABASE")
            endpoint = stardog_url

        session = r.Session()
        session.request = lambda *args, **kwargs: r.Session.request(session, *args, timeout=3600, **kwargs)

        conn_details = {
            "endpoint": endpoint,
            "username": stardog_user,
            "password": stardog_password,
            "session": session,
        }

        return database, conn_details

    @staticmethod
    def lindas_query(query):
        url = LINDAS_QUERY_URL
        proxies = {
            "http": "http://proxy-bvcol.admin.ch:8080",
            "https": "http://proxy-bvcol.admin.ch:8080"
        }
        headers = {"Accept": "application/sparql-results+json", "Accept-Encoding": "identity"}

        if DEBUG_LOCAL_TEST:
            resp = r.post(url, data={"query": query}, headers=headers, timeout=300, verify=False,proxies=proxies)
        else:
            resp = r.post(url, data={"query": query}, headers=headers, timeout=300, verify=False)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", {}).get("bindings", [])

        return results

    @staticmethod
    def get_lindas_concept_versions():
        # Only fetch from LINDAS if we don't already have concept versions cached
        if not LindasAPIHelper.lindas_concept_versions:

            query = f"""
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX schema: <http://schema.org/>

    SELECT ?concept_uri ?validFrom
    WHERE {{
        GRAPH <{TARGET_GRAPH}> {{
            ?concept_uri 
                prov:wasDerivedFrom ?source ;
                schema:validFrom ?validFrom .
            FILTER(CONTAINS(STR(?concept_uri), "/version/"))
        }}
    }}
    """
            print("DEBUG: get_existing_concepts_lindas API call")

            rows = []

            results = LindasAPIHelper.lindas_query(query)

            for result in results:
                concept_uri = result["concept_uri"]["value"]
                valid_from = result["validFrom"]["value"]

                # Extract identifier and version from the URI
                identifier = concept_uri.split("/version/")[0].rstrip("/").split("/")[-1]
                version = concept_uri.split("/version/")[-1]

                # Collect all rows before sorting
                rows.append((identifier, version, valid_from))

            # --- SORTING ---
            # Sort first by validFrom (ISO date string ⇒ lexicographic sort is correct),
            # then by version (string comparison works for semver-like versions).
            rows.sort(key=lambda x: (x[2], x[1]))

            # --- BUILD SORTED DICTIONARY ---
            concept_versions = {}

            for identifier, version, valid_from in rows:
                concept_versions.setdefault(identifier, []).append(version)

            total_versions = sum(len(vs) for vs in concept_versions.values())
            print(f"DEBUG: {len(concept_versions)} concepts with {total_versions} versions")

            LindasAPIHelper.lindas_concept_versions = concept_versions

        return LindasAPIHelper.lindas_concept_versions

    @staticmethod
    def get_lindas_code_versions(concept_identifier):
        if concept_identifier not in LindasAPIHelper.lindas_code_versions.keys():
            query = f"""
PREFIX schema: <http://schema.org/>
SELECT ?code_uri
WHERE {{
  GRAPH <{TARGET_GRAPH}> {{
    ?code_uri a schema:DefinedTerm
    FILTER (STRSTARTS(STR(?code_uri),"{BASE_URI}{concept_identifier}/"))
    FILTER(CONTAINS(STR(?code_uri), "/version/"))
  }}
}}
"""
            version_codes_dict = {}
            print("DEBUG: get_lindas_code_versions get API call for concept_identifier: " + concept_identifier)
            results = LindasAPIHelper.lindas_query(query)
            for result in results:
                code_uri = result["code_uri"]["value"]
                # code_uri is like https://register.ld.admin.ch/i14y/concept/LINDAS_testConcept/aaa/version/1.0.0
                parts = code_uri.split(f"/{concept_identifier}/")[-1].split("/version/")
                # code=aaa and version=1.0.0 with the example above
                code, version = parts[0], parts[1]
                if version not in version_codes_dict.keys():
                    version_codes_dict[version] = set()

                version_codes_dict[version].add(code)

            LindasAPIHelper.lindas_code_versions[concept_identifier] = version_codes_dict

        return LindasAPIHelper.lindas_code_versions[concept_identifier]

    @staticmethod
    def delete_concept(concept_identifier):
        print(f"DEBUG: delete_concept concept {concept_identifier}")
        database, conn_details = LindasAPIHelper.get_stardog_db_conn()
        delete_query = f"""
DELETE {{
    GRAPH <{TARGET_GRAPH}> {{
        ?s ?p ?o .
    }}
}}
WHERE {{
    GRAPH <{TARGET_GRAPH}> {{
        ?s ?p ?o .
        FILTER (
            (REGEX(STR(?s), "^{BASE_URI}{concept_identifier}(/|$)")) ||
            (REGEX(STR(?o), "^{BASE_URI}{concept_identifier}(/|$)"))
        )
    }}
}}
"""
        if not DEBUG_LOCAL_TEST:
            with stardog.Connection(database, **conn_details) as conn:
                conn.update(query=delete_query)

class I14YAPIHelper:

    # We call the API only once to get all the concepts, then we work on the data locally
    # local_concepts is a i14y id -> concept map
    local_id_concepts_map = {}

    # Same idea, but here we have a concept identifier -> concept list map, useful when a concept identifier has multiple versions
    local_identifier_concepts_map = {}

    @staticmethod
    def get_all_concepts(registration_statuses=None, pageSize=100):
        """Get all CodeList concepts with specified registration statuses"""
        if not I14YAPIHelper.local_id_concepts_map:

            print("DEBUG: get_all_concepts API call")

            base_url = f"{BASE_API_URL}"
            all_concepts = []
            printed_count = 0  
            failed_concepts = []

            if registration_statuses is None:
                registration_statuses = STATUSES

            page = 1
            while True:
                params = {"publicationLevel": "Public", "page": page, "pageSize": pageSize}

                response = r.get(base_url, params=params, verify=False)
                response.raise_for_status()
                data = response.json().get('data', [])

                if not data:
                    break

                filtered = []
                for c in data:
                    if c.get("conceptType") != "CodeList":
                        continue

                    if c.get("registrationStatus") not in registration_statuses:
                        continue

                    if c.get("id") in EXCLUDED_IDS:
                        continue

                    identifier = c.get("identifier")
                    version = c.get("version")

                    filtered.append(c)

                for i, concept in enumerate(filtered, printed_count + 1):
                    print(f"{i}. Identifier: {concept.get('identifier')}")
                    print(f"   Title: {concept.get('name')}")
                    print(f"   Status: {concept.get('registrationStatus')}")
                    print(f"   Version: {concept.get('version')}\n")

                all_concepts.extend(filtered)
                printed_count = len(all_concepts)  

                if len(data) < pageSize:
                    break

                page += 1

            # Give warning if any concepts failed during processing
            if failed_concepts:
                print(f"Warning: {len(failed_concepts)} concept(s) could not be retrieved during processing: {', '.join(failed_concepts)}")

            # We get only the latest concept version from i14y because we will get all the versions for each concept afterwards anyway
            latest_concepts = {}
            for concept in all_concepts:
                identifier = concept["identifier"]
                valid_from = concept["validFrom"]

                if identifier not in latest_concepts or valid_from > latest_concepts[identifier]["validFrom"]:
                    latest_concepts[identifier] = concept

            for concept in all_concepts:
                concept_identifier = concept["identifier"]
                if concept["id"] == latest_concepts[concept_identifier]["id"]:
                    # local_id_concepts_map is used to store only the latest version of a concept, by id
                    I14YAPIHelper.local_id_concepts_map[concept["id"]] = concept

        return list(I14YAPIHelper.local_id_concepts_map.values())

    @staticmethod
    def get_concept_data(concept_id):
        """Get combined concept metadata and codelist entries"""
        if concept_id not in I14YAPIHelper.local_id_concepts_map.keys():
            print(f"DEBUG: get_concept_data get API call for concept_id: {concept_id}")
            # Get concept metadata
            meta_url = f"{BASE_API_URL}{concept_id}"
            meta_response = r.get(meta_url, verify=False)
            meta_response.raise_for_status()
            concept_data = meta_response.json()['data']

            I14YAPIHelper.local_id_concepts_map[concept_id] = concept_data

        concept_data = I14YAPIHelper.local_id_concepts_map[concept_id]
        # Get codelist entries (if it's a CodeList concept)
        if concept_data.get("conceptType") == "CodeList" and (
            "codeListEntries" not in concept_data.keys() or not concept_data.get("codeListEntries", [])
        ):
            print(f"DEBUG: get_concept_data /codelist-entries/exports/Json API call for concept_id: {concept_id}")
            entries_url = f"{BASE_API_URL}{concept_id}/codelist-entries/exports/Json"
            entries_response = r.get(entries_url, verify=False)
            entries_response.raise_for_status()
            concept_data['codeListEntries'] = entries_response.json()['data']
            I14YAPIHelper.local_id_concepts_map[concept_id] = concept_data

        # Return in legacy format
        return {'data': I14YAPIHelper.local_id_concepts_map[concept_id]}

    @staticmethod
    def get_i14y_code_versions(concept_identifier):
        version_codes_dict = {}
        concept_version_list = I14YAPIHelper.get_version_list(concept_identifier)
        for concept_version in concept_version_list:
            version = concept_version["version"]
            if version not in version_codes_dict.keys():
                version_codes_dict[version] = set()
            for codeListEntry in concept_version["codeListEntries"]:
                code = codeListEntry["code"]
                version_codes_dict[version].add(code)
        return version_codes_dict

    @staticmethod
    def get_version_list(concept_identifier):
        """Get list of versions using the filter approach"""
        if concept_identifier not in I14YAPIHelper.local_identifier_concepts_map.keys():
            print(f"DEBUG: get_version_list get API call for concept_identifier: {concept_identifier}")
            try:
                url = f"{BASE_API_URL}"
                page = 1
                page_size = 100
                all_concepts = []

                while True:
                    params = {
                        'conceptIdentifier': concept_identifier,
                        'publicationLevel': 'Public',
                        'page': page,
                        'pageSize': page_size
                    }

                    response = r.get(url, params=params, verify=False)
                    response.raise_for_status()

                    data = response.json().get('data', [])

                    # Stop when no more items
                    if not data:
                        break

                    all_concepts.extend(data)

                    # If API returns fewer items than page_size, we are done
                    if len(data) < page_size:
                        break

                    page += 1

                # Store all results for this identifier
                I14YAPIHelper.local_identifier_concepts_map[concept_identifier] = all_concepts

            except Exception as e:
                print(f"Error fetching versions for {concept_identifier}: {str(e)}")
                raise

        concepts = I14YAPIHelper.local_identifier_concepts_map[concept_identifier]
        versions = []
        for concept in concepts:
            versions.append({
                'id': concept.get('id'),
                'version': concept.get('version'),
                'validFrom': concept.get('validFrom'),
                'registrationStatus': concept.get('registrationStatus')
            })

        # We sort on validFrom date, if 2 elements have the same date we sort by version number
        sorted_versions = sorted(versions, key=lambda x: (x['validFrom'], x['version']))

        version_data = []
        failed_concepts = []

        for version in sorted_versions:
            data = I14YAPIHelper.get_concept_data(version['id'])
            if data is not None:
                version_data.append(data["data"])
            else:
                failed_concepts.append(version['id'])

        # Give warning if any concepts failed to retrieve
        if failed_concepts:
            print(f"Warning: {len(failed_concepts)} concept version(s) could not be retrieved: {', '.join(failed_concepts)}")

        return version_data


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
