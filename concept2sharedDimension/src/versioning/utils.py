import heapq
import random
import re
from time import time, sleep
from urllib.parse import urlparse
import requests as r
from .config import *
import warnings
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        [c["identifiers"][0] for c in I14YAPIHelper.get_all_concepts()]
    )

    for concept_identifier in concepts_to_delete_identifiers:
        LindasAPIHelper.delete_concept(concept_identifier)


class LindasAPIHelper:

    # Key: concept identifier, value: set of versions
    lindas_concept_versions = {}

    # Key: concept identifier, value:
    #    dict with key: version and value: set of codes
    lindas_code_versions = {}

    # Key: concept identifier, value:
    #   dict with key: version and value: dict with following attributes: title, description, status
    lindas_concept_attributes = {}

    @staticmethod
    def graphdb_update(update_query):
        graphdb_url = os.environ.get("LINDAS_UPDATE_URL", "")
        graphdb_user = os.environ.get("STARDOG_USER", "")
        graphdb_password = os.environ.get("STARDOG_PASSWORD", "")

        if not graphdb_url.endswith("/statements") and "graphdb" in graphdb_url:
            graphdb_url += "/statements"
        elif not graphdb_url.endswith("/update") and "graphdb" not in graphdb_url:
            graphdb_url += "/update"

        headers = {
            "Content-Type": "application/sparql-update",
            "User-Agent": I14Y_USER_AGENT,
        }

        auth = None
        if graphdb_user and graphdb_password:
            auth = (graphdb_user, graphdb_password)

        # Keep retries configurable: CI can set it to 1 to fail fast.
        retries = int(os.environ.get("GRAPHDB_UPDATE_RETRIES", "1"))
        retries = max(1, retries)
        backoff_min = float(os.environ.get("GRAPHDB_UPDATE_BACKOFF_MIN", "0.5"))
        backoff_max = float(os.environ.get("GRAPHDB_UPDATE_BACKOFF_MAX", "1.5"))

        for attempt in range(1, retries + 1):
            try:
                if DEBUG_LOCAL_TEST:
                    resp = r.post(
                        graphdb_url,
                        data=update_query,
                        headers=headers,
                        auth=auth,
                        timeout=300,
                        verify=False,
                        proxies=PROXIES,
                    )
                else:
                    resp = r.post(
                        graphdb_url,
                        data=update_query,
                        headers=headers,
                        auth=auth,
                        timeout=300,
                    )

                resp.raise_for_status()
                break

            except Exception as e:
                if attempt == retries:
                    raise
                sleep(random.uniform(backoff_min, backoff_max))

    @staticmethod
    def graphdb_upload_ttl(file_path, graph_uri):
        graphdb_url = os.environ.get("LINDAS_UPDATE_URL", "")
        user = os.environ.get("STARDOG_USER", "")
        pwd = os.environ.get("STARDOG_PASSWORD", "")
        auth = (user, pwd) if user and pwd else None

        print(f"Uploading {file_path} to {graphdb_url}")

        # --- GraphDB case ---
        if "graphdb" in graphdb_url.lower():
            if not graphdb_url.endswith("/statements"):
                graphdb_url += "/statements"

            headers = {
                "Content-Type": "text/turtle",
                "User-Agent": I14Y_USER_AGENT,
            }
            params = {"context": f"<{graph_uri}>"}

            with open(file_path, "rb") as f:
                response = r.post(
                    graphdb_url,
                    data=f,
                    headers=headers,
                    auth=auth,
                    timeout=1800,
                    verify=False if DEBUG_LOCAL_TEST else True,
                    params=params,
                    # proxies=PROXIES if DEBUG_LOCAL_TEST else None,
                )

            if response.status_code == 204:
                print("Upload successful (GraphDB)")
            else:
                raise Exception(
                    f"GraphDB upload failed: {response.status_code} {response.text}\n"
                    f"URL: {response.url}\nParams: {params}"
                )

        # --- Stardog case ---
        else:
            parsed = urlparse(graphdb_url)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) == 0:
                raise Exception(f"Invalid Stardog URL: {graphdb_url}")
            database = path_parts[-1]
            server_root = parsed._replace(path="/" + "/".join(path_parts[:-1])).geturl()

            # Begin transaction
            tx_url = f"{server_root.rstrip('/')}/{database}/transaction/begin"
            tx_resp = r.post(
                tx_url,
                auth=auth,
                verify=False if DEBUG_LOCAL_TEST else True,
                headers={
                    "User-Agent": I14Y_USER_AGENT,
                },
            )
            tx_resp.raise_for_status()
            transaction = tx_resp.text.strip('"')
            print(f"Started Stardog transaction: {transaction}")

            # URLs for add, commit, rollback
            add_url = f"{server_root.rstrip('/')}/{database}/{transaction}/add"
            rollback_url = f"{server_root.rstrip('/')}/{database}/transaction/rollback/{transaction}"
            commit_url = f"{server_root.rstrip('/')}/{database}/transaction/commit/{transaction}"

            params = {"graph-uri": graph_uri or database}
            print("Posting to URL:", add_url)
            print("Target graph URI:", params["graph-uri"])

            try:
                with open(file_path, "rb") as f:
                    add_resp = r.post(
                        add_url,
                        data=f,
                        headers={
                            "Content-Type": "text/turtle",
                            "User-Agent": I14Y_USER_AGENT,
                        },
                        params=params,
                        auth=auth,
                        timeout=1800,
                        verify=False if DEBUG_LOCAL_TEST else True,
                    )

                if add_resp.status_code not in (200, 204):
                    # Rollback on error
                    r.post(
                        rollback_url,
                        auth=auth,
                        verify=False if DEBUG_LOCAL_TEST else True,
                        headers={
                            "User-Agent": I14Y_USER_AGENT,
                        },
                    )
                    raise Exception(
                        f"Stardog upload failed: {add_resp.status_code} {add_resp.text}\n"
                        f"URL: {add_url}\nParams: {params}"
                    )

                # Commit transaction
                commit_resp = r.post(
                    commit_url,
                    auth=auth,
                    verify=False if DEBUG_LOCAL_TEST else True,
                    headers={
                        "User-Agent": I14Y_USER_AGENT,
                    },
                )
                commit_resp.raise_for_status()
                print("Upload successful (Stardog)")

            except Exception as e:
                # Ensure rollback in case of any exception
                try:
                    r.post(
                        rollback_url,
                        auth=auth,
                        verify=False if DEBUG_LOCAL_TEST else True,
                        headers={
                            "User-Agent": I14Y_USER_AGENT,
                        },
                    )
                except Exception:
                    pass  # ignore rollback errors
                raise e

    @staticmethod
    def get_stardog_db_conn():
        stardog_url = os.environ.get("LINDAS_UPDATE_URL", "")
        stardog_user = os.environ.get("STARDOG_USER", "")
        stardog_password = os.environ.get("STARDOG_PASSWORD", "")

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
        session.request = lambda *args, **kwargs: r.Session.request(session, *args, timeout=360, **kwargs)

        if DEBUG_LOCAL_TEST:
            session.proxies.update(PROXIES)
            session.verify = False

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
        headers = {
            "Accept": "application/sparql-results+json",
            "Accept-Encoding": "identity",
            "User-Agent": I14Y_USER_AGENT,
        }

        # TODO Sergiy: retry mechanism in decorator and use it instead of copy-pasting the same code
        retries = 1

        for attempt in range(1, retries + 1):
            try:
                if DEBUG_LOCAL_TEST:
                    resp = r.post(
                        url, data={"query": query}, headers=headers, timeout=60, verify=False, proxies=PROXIES
                    )
                else:
                    resp = r.post(url, data={"query": query}, headers=headers, timeout=60, verify=True)
                resp.raise_for_status()
                break

            except Exception as e:
                if attempt == retries:
                    raise
                sleep(random.uniform(1, 2))

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
                PREFIX vl: <https://version.link/>
                PREFIX pav: <http://purl.org/pav/>

                SELECT ?version ?concept_identifier ?validFrom
                WHERE {{
                    GRAPH <{TARGET_GRAPH}> {{
                        ?concept a schema:DefinedTermSet;
                            schema:identifier ?concept_identifier;
                            schema:validFrom ?validFrom ;
                            a vl:Version ;
                            pav:version ?version.
                    }}
                }}
                """
            print("DEBUG: get_existing_concepts_lindas API call")

            rows = []

            results = LindasAPIHelper.lindas_query(query)

            for result in results:
                concept_identifier = result["concept_identifier"]["value"]
                valid_from = result["validFrom"]["value"]
                version = result["version"]["value"]

                # Collect all rows before sorting
                rows.append((concept_identifier, version, valid_from))

            # --- SORTING ---
            # Sort first by validFrom (ISO date string ⇒ lexicographic sort is correct),
            # then by version (string comparison works for semver-like versions).
            rows.sort(key=lambda x: (x[2], x[1]))

            # --- BUILD SORTED DICTIONARY ---
            concept_versions = {}

            for concept_identifier, version, valid_from in rows:
                concept_versions.setdefault(concept_identifier, []).append(version)

            total_versions = sum(len(vs) for vs in concept_versions.values())
            print(f"DEBUG: {len(concept_versions)} concepts with {total_versions} versions")

            LindasAPIHelper.lindas_concept_versions = concept_versions

        return LindasAPIHelper.lindas_concept_versions

    @staticmethod
    def get_lindas_code_versions(concept_identifier):
        if concept_identifier not in LindasAPIHelper.lindas_code_versions.keys():
            query = f"""
                PREFIX schema: <http://schema.org/>
                PREFIX vl: <https://version.link/>
                PREFIX pav: <http://purl.org/pav/>
                SELECT ?code_identifier ?version
                WHERE {{
                    GRAPH <{TARGET_GRAPH}> {{
                        ?code a schema:DefinedTerm;
                            a vl:Version;
                            schema:identifier ?code_identifier.
                        ?concept a schema:DefinedTermSet;
                                schema:identifier "{concept_identifier}";
                                schema:hasDefinedTerm ?code;
                                pav:version ?version.
                    }}
                }}
                """
            version_codes_dict = {}
            print("DEBUG: get_lindas_code_versions get API call for concept_identifier: " + concept_identifier)
            results = LindasAPIHelper.lindas_query(query)
            for result in results:
                code = result.get("code_identifier", {}).get("value")
                version = result.get("version", {}).get("value")
                if version not in version_codes_dict.keys():
                    version_codes_dict[version] = set()

                version_codes_dict[version].add(code)

            LindasAPIHelper.lindas_code_versions[concept_identifier] = version_codes_dict

        return LindasAPIHelper.lindas_code_versions[concept_identifier]

    @staticmethod
    def get_lindas_concept_attributes(concept_identifier):
        if concept_identifier not in LindasAPIHelper.lindas_concept_attributes.keys():
            query = f"""
PREFIX schema: <http://schema.org/>
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX pav: <http://purl.org/pav/>
PREFIX vl: <https://version.link/>

SELECT ?version ?status ?attr ?lang ?value
WHERE {{
  GRAPH <{TARGET_GRAPH}> {{
    ?concept a schema:DefinedTermSet ;
            a vl:Version ;
             schema:identifier "{concept_identifier}" ;
             adms:status ?status ;
             pav:version ?version .

    {{ ?concept schema:name ?value .
      BIND("name" AS ?attr)
    }}
    UNION
    {{ ?concept schema:description ?value .
      BIND("description" AS ?attr)
    }}

    BIND(LANG(?value) AS ?lang)
  }}
}}
    """
            version_attributes_dict = {}
            print("DEBUG: get_lindas_concept_attributes get API call for concept_identifier: " + concept_identifier)
            results = LindasAPIHelper.lindas_query(query)
            for result in results:
                version = result.get("version", {}).get("value")

                if version not in version_attributes_dict.keys():
                    # "title" in LINDAS = "name" in i14y
                    version_attributes_dict[version] = {"description": {}, "name": {}}

                status = result.get("status", {}).get("value")

                version_attributes_dict[version]["registrationStatus"] = status

                lang = result.get("lang", {}).get("value")

                attr = result.get("attr", {}).get("value")
                value = result.get("value", {}).get("value")
                if attr == "name":
                    # Title on LINDAS is like "xxx (version a.b.c)" or "xxx (Identity)" so we extract what is before "(...)"
                    value = re.sub(r"\s*\([^)]*\)$", "", value)

                version_attributes_dict[version][attr][lang] = value

            LindasAPIHelper.lindas_concept_attributes[concept_identifier] = version_attributes_dict

        return LindasAPIHelper.lindas_concept_attributes[concept_identifier]

    @staticmethod
    def delete_concept(concept_identifier):
        protected_versions = I14YAPIHelper.get_protected_vocabulary_versions()
        lindas_versions = LindasAPIHelper.get_lindas_concept_versions().get(concept_identifier, [])
        matched_versions = sorted(
            version for version in lindas_versions if (concept_identifier, version) in protected_versions
        )
        if matched_versions:
            print(
                f"DEBUG: skip delete_concept for protected vocabulary {concept_identifier} "
                f"version(s) {', '.join(matched_versions)}"
            )
            return False
        print(f"DEBUG: delete_concept concept {concept_identifier}")
        concept_base = f"{BASE_URI}{concept_identifier}"

        def build_delete_query(filter_expression):
            return f"""
DELETE {{
    GRAPH <{TARGET_GRAPH}> {{
        ?s ?p ?o .
    }}
}}
WHERE {{
    GRAPH <{TARGET_GRAPH}> {{
        ?s ?p ?o .
        FILTER ({filter_expression})
    }}
}}
"""

        for node_var, node_name in (("?o", "object"), ("?s", "subject")):
            node_filter = (
                f'isIRI({node_var}) && '
                f'(STR({node_var}) = "{concept_base}" || STRSTARTS(STR({node_var}), "{concept_base}/"))'
            )
            print(f"DEBUG: delete_concept side={node_name} concept={concept_identifier}")
            LindasAPIHelper.graphdb_update(build_delete_query(node_filter))


class I14YAPIHelper:

    # We call the API only once to get all the concepts, then we work on the data locally
    # local_concepts is a i14y id -> concept map
    local_id_concepts_map = {}

    # Same idea, but here we have a concept identifier -> concept list map, useful when a concept identifier has multiple versions
    local_identifier_concepts_map = {}

    # Pairs from the core vocabulary configuration endpoint. None means not loaded yet.
    protected_vocabulary_versions = None

    @staticmethod
    def get_protected_vocabulary_versions():
        """Return configured (conceptIdentifier, conceptVersion) pairs; fail closed on errors."""
        if I14YAPIHelper.protected_vocabulary_versions is not None:
            return I14YAPIHelper.protected_vocabulary_versions

        last_error = None
        for attempt in range(1, 4):
            try:
                response = r.get(
                    VOCABULARY_CONFIGURATIONS_URL,
                    timeout=60,
                    verify=False if DEBUG_LOCAL_TEST else True,
                    headers={"User-Agent": I14Y_USER_AGENT, "Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError("Vocabulary configurations endpoint returned a non-list payload")
                pairs = {
                    (item["conceptIdentifier"], item["conceptVersion"])
                    for item in payload
                    if isinstance(item, dict)
                    and item.get("conceptIdentifier")
                    and item.get("conceptVersion")
                }
                I14YAPIHelper.protected_vocabulary_versions = pairs
                print(f"DEBUG: loaded {len(pairs)} protected vocabulary version(s)")
                return pairs
            except Exception as error:
                last_error = error
                if attempt < 3:
                    sleep(random.uniform(1, 2))

        raise RuntimeError(
            f"Could not load protected vocabulary configurations from {VOCABULARY_CONFIGURATIONS_URL}"
        ) from last_error
    @staticmethod
    def get_all_concepts(registration_statuses=None, pageSize=50):
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
                retries = 10
                for attempt in range(1, retries + 1):
                    try:
                        response = r.get(
                            base_url,
                            params=params,
                            verify=False if DEBUG_LOCAL_TEST else True,
                            headers={
                                "User-Agent": I14Y_USER_AGENT,
                            },
                        )
                        response.raise_for_status()
                        break
                    except Exception as e:
                        if attempt == retries:
                            raise
                        sleep(random.uniform(1, 2))

                data = response.json().get("data", [])

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

                    identifier = c.get("identifiers")[0]
                    version = c.get("version")

                    filtered.append(c)

                for i, concept in enumerate(filtered, printed_count + 1):
                    print(f"{i}. Identifier: {concept.get('identifiers')[0]}")
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
                print(
                    f"Warning: {len(failed_concepts)} concept(s) could not be retrieved during processing: {', '.join(failed_concepts)}"
                )

            # We get only the latest concept version from i14y because we will get all the versions for each concept afterwards anyway
            latest_concepts = {}
            for concept in all_concepts:
                identifier = concept["identifiers"][0]
                valid_from = concept["validFrom"]

                if identifier not in latest_concepts or valid_from > latest_concepts[identifier]["validFrom"]:
                    latest_concepts[identifier] = concept

            for concept in all_concepts:
                concept_identifier = concept["identifiers"][0]
                if concept["id"] == latest_concepts[concept_identifier]["id"]:
                    # local_id_concepts_map is used to store only the latest version of a concept, by id
                    I14YAPIHelper.local_id_concepts_map[concept["id"]] = concept

        return list(I14YAPIHelper.local_id_concepts_map.values())

    @staticmethod
    def get_concept_batches():
        # 1. Fetch all concepts
        all_concepts = I14YAPIHelper.get_all_concepts()
        all_concept_data = {}

        # 2. Function to fetch concept data
        def fetch_data(concept):
            concept_id = concept["id"]
            data = I14YAPIHelper.get_concept_data(concept_id)["data"]
            return concept_id, data

        # 3. Parallelize API calls using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(fetch_data, c) for c in all_concepts]
            for future in as_completed(futures):
                concept_id, data = future.result()
                all_concept_data[concept_id] = data

        # 4. Compute size of each concept (number of codeListEntries)
        concept_sizes = [(cid, len(data.get("codeListEntries", []))) for cid, data in all_concept_data.items()]

        # 5. Set n_batches so that no batch is bigger than the biggest codeListEntries
        # and cap workflow parallelism via MAX_BATCHES (default: 3).
        max_entries = max(len(data.get("codeListEntries", [])) for _, data in all_concept_data.items())
        total_entries = sum(len(data.get("codeListEntries", [])) for _, data in all_concept_data.items())
        n_batches = max(1, total_entries // max_entries)

        max_batches = int(os.environ.get("MAX_BATCHES", "3"))
        max_batches = max(1, max_batches)
        n_batches = min(n_batches, max_batches, max(1, len(concept_sizes)))

        # 6. Initialize min-heap for Largest Differencing
        # Each heap element: (current_sum, batch_index, list_of_ids)
        batches_heap = [(0, i, []) for i in range(n_batches)]
        heapq.heapify(batches_heap)

        # 7. Sort concepts largest first
        for concept_id, size in sorted(concept_sizes, key=lambda x: -x[1]):
            current_sum, batch_idx, batch_list = heapq.heappop(batches_heap)
            batch_list.append(concept_id)
            current_sum += size
            heapq.heappush(batches_heap, (current_sum, batch_idx, batch_list))

        # 8. Extract only the list of concept IDs, ordered by batch index
        batches = [batch_list for _, batch_idx, batch_list in sorted(batches_heap, key=lambda x: x[1])]

        return batches

    @staticmethod
    def get_concept_data(concept_id):
        """Get combined concept metadata and codelist entries"""
        if concept_id not in I14YAPIHelper.local_id_concepts_map.keys():
            print(f"DEBUG: get_concept_data get API call for concept_id: {concept_id}")
            # Get concept metadata
            meta_url = f"{BASE_API_URL}{concept_id}"

            retries = 10

            for attempt in range(1, retries + 1):
                try:
                    meta_response = r.get(
                        meta_url,
                        verify=False if DEBUG_LOCAL_TEST else True,
                        headers={
                            "User-Agent": I14Y_USER_AGENT,
                        },
                    )
                    meta_response.raise_for_status()
                    concept_data = meta_response.json()["data"]
                    break
                except Exception:
                    if attempt == retries:
                        raise
                    sleep(random.uniform(1, 2))

            I14YAPIHelper.local_id_concepts_map[concept_id] = concept_data

        concept_data = I14YAPIHelper.local_id_concepts_map[concept_id]
        # Get codelist entries (if it's a CodeList concept)
        if concept_data.get("conceptType") == "CodeList" and (
            "codeListEntries" not in concept_data.keys() or not concept_data.get("codeListEntries", [])
        ):
            print(f"DEBUG: get_concept_data /codelist-entries/exports/Json API call for concept_id: {concept_id}")
            entries_url = f"{BASE_API_URL}{concept_id}/codelist-entries/exports/Json"

            retries = 10

            for attempt in range(1, retries + 1):
                try:
                    entries_response = r.get(
                        entries_url,
                        verify=False if DEBUG_LOCAL_TEST else True,
                        headers={
                            "User-Agent": I14Y_USER_AGENT,
                        },
                    )
                    entries_response.raise_for_status()
                    concept_data["codeListEntries"] = entries_response.json()["data"]
                    I14YAPIHelper.local_id_concepts_map[concept_id] = concept_data
                    break
                except Exception:
                    if attempt == retries:
                        raise
                    sleep(random.uniform(1, 2))

        # Return in legacy format
        return {"data": I14YAPIHelper.local_id_concepts_map[concept_id]}

    @staticmethod
    def get_i14y_code_versions(concept_identifier):
        version_codes_dict = {}
        concept_version_list = I14YAPIHelper.get_version_list(concept_identifier)
        for concept_version in concept_version_list:
            version = concept_version["version"]
            if version not in version_codes_dict.keys():
                version_codes_dict[version] = set()
            if "codeListEntries" in concept_version.keys():
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
                page_size = 50
                all_concepts = []

                while True:
                    params = {
                        "conceptIdentifier": concept_identifier,
                        "publicationLevel": "Public",
                        "page": page,
                        "pageSize": page_size,
                    }

                    retries = 10

                    for attempt in range(1, retries + 1):
                        try:
                            response = r.get(
                                url,
                                params=params,
                                verify=False if DEBUG_LOCAL_TEST else True,
                                headers={
                                    "User-Agent": I14Y_USER_AGENT,
                                },
                            )
                            response.raise_for_status()

                            data = response.json().get("data", [])
                            break

                        except Exception:
                            if attempt == retries:
                                raise
                            sleep(random.uniform(1, 2))

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
            versions.append(
                {
                    "id": concept.get("id"),
                    "version": concept.get("version"),
                    "validFrom": concept.get("validFrom"),
                    "registrationStatus": concept.get("registrationStatus"),
                }
            )

        # We sort on validFrom date, if 2 elements have the same date we sort by version number
        sorted_versions = sorted(versions, key=lambda x: (x["validFrom"], x["version"]))

        version_data = []
        failed_concepts = []

        for version in sorted_versions:
            data = I14YAPIHelper.get_concept_data(version["id"])
            if data is not None:
                version_data.append(data["data"])
            else:
                failed_concepts.append(version["id"])

        # Give warning if any concepts failed to retrieve
        if failed_concepts:
            print(
                f"Warning: {len(failed_concepts)} concept version(s) could not be retrieved: {', '.join(failed_concepts)}"
            )

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
        old_entries = {e["code"] for e in old_version_data.get("codeListEntries", [])}
        new_entries = {e["code"] for e in new_version_data.get("codeListEntries", [])}
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
