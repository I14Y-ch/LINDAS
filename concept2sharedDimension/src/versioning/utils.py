import heapq
import json
import random
import re
from pathlib import Path
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
    def delete_orphaned_publisher_agents():
        """Remove i14y publisher agents that no longer have an owner."""
        LindasAPIHelper.graphdb_update(f'''\
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
DELETE {{ GRAPH <{TARGET_GRAPH}> {{ ?agent ?p ?o . }} }}
WHERE {{
  GRAPH <{TARGET_GRAPH}> {{
    ?agent a foaf:Agent ;
           ?p ?o .
    FILTER(isIRI(?agent) && STRSTARTS(STR(?agent), "{AGENT_URI_BASE}"))
    FILTER NOT EXISTS {{ ?owner dct:publisher ?agent . }}
  }}
}}''')

    @staticmethod
    def delete_concept(concept_identifier, *, force=False):
        """Delete a concept and its local skolemized closure.

        force is reserved for the isolated full-lifecycle test: it bypasses
        only the protected-vocabulary policy after that test has cleared the
        graph. The SPARQL deletion mechanism is otherwise the production one.
        """
        if not force:
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

        print(f"DEBUG: delete_concept concept={concept_identifier} force={force}")
        concept_base = f"{BASE_URI}{concept_identifier}"

        def concept_iri_filter(node_variable):
            return (
                f'isIRI({node_variable}) && '
                f'(STR({node_variable}) = "{concept_base}" || STRSTARTS(STR({node_variable}), "{concept_base}/"))'
            )

        # Traverse only predicates emitted by the concept mapper. A positive
        # path cannot escape through the common I14Y catalogue or external IRIs.
        concept_identifier_literal = json.dumps(str(concept_identifier))
        owned_path = """(
          vl:Version|vl:Identity|
          schema:hasPart|schema:hasDefinedTerm|schema:member|schema:isPartOf|schema:inDefinedTermSet|
          skos:member|skos:broader|skos:narrower|skos:topConceptOf|skos:inScheme|
          xkos:level|
          cube:inHierarchy|cube:hierarchyRoot|cube:nextInHierarchy|
          sh:property|
          dct:subject|dct:conformsTo|
          oa:hasBody|
          rdf:rest
        )*"""
        owned_roots = f"""
        {{
          BIND(<{concept_base}> AS ?root)
        }}
        UNION
        {{
          ?root a schema:DefinedTermSet, vl:Version ;
                schema:identifier {concept_identifier_literal} .
        }}"""

        # Materialize every locally owned node before joining it as an object.
        # This avoids GraphDB reordering the query into a full graph scan.
        # Dataset structure conformsTo links intentionally remain until their
        # dataset is deleted.
        structure_conforms_to = (
            '?incoming_predicate = <http://purl.org/dc/terms/conformsTo> && '
            'isIRI(?incoming_subject) && '
            f'STRSTARTS(STR(?incoming_subject), "{DATASET_URI_BASE}") && '
            'CONTAINS(STR(?incoming_subject), "/structure/")'
        )
        # The subject-deletion pass needs local hierarchy links to remain
        # available until it has traversed the complete concept closure.
        incoming_local_subject = concept_iri_filter("?incoming_subject")
        delete_incoming = f"""
PREFIX cube: <https://cube.link/meta/>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX oa: <https://www.w3.org/ns/oa#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <http://schema.org/>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX vl: <https://version.link/>
PREFIX xkos: <http://rdf-vocabulary.ddialliance.org/xkos#>
DELETE {{
  GRAPH <{TARGET_GRAPH}> {{
    ?incoming_subject ?incoming_predicate ?target .
  }}
}}
WHERE {{
  {{
    SELECT DISTINCT ?target
    WHERE {{
      GRAPH <{TARGET_GRAPH}> {{
        {owned_roots}
        ?root {owned_path} ?target .
        FILTER(isIRI(?target) && STRSTARTS(STR(?target), "{concept_base}"))
      }}
    }}
  }}
  GRAPH <{TARGET_GRAPH}> {{
    ?incoming_subject ?incoming_predicate ?target .
    FILTER(!({structure_conforms_to}) && !({incoming_local_subject}))
  }}
}}
"""
        print(f"DEBUG: delete_concept side=object concept={concept_identifier}")
        LindasAPIHelper.graphdb_update(delete_incoming)

        delete_subjects = f"""
PREFIX cube: <https://cube.link/meta/>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX oa: <https://www.w3.org/ns/oa#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <http://schema.org/>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX vl: <https://version.link/>
PREFIX xkos: <http://rdf-vocabulary.ddialliance.org/xkos#>
DELETE {{
  GRAPH <{TARGET_GRAPH}> {{
    ?s ?p ?o .
  }}
}}
WHERE {{
  {{
    {{
      SELECT DISTINCT ?s
      WHERE {{
        GRAPH <{TARGET_GRAPH}> {{
          {owned_roots}
          ?root {owned_path} ?s .
          FILTER(isIRI(?s) && STRSTARTS(STR(?s), "{concept_base}"))
        }}
      }}
    }}
    GRAPH <{TARGET_GRAPH}> {{
      ?s ?p ?o .
    }}
  }}
  UNION
  {{
    GRAPH <{TARGET_GRAPH}> {{
      {owned_roots}
      ?root dct:publisher ?publisher .
      FILTER(isIRI(?publisher) && STRSTARTS(STR(?publisher), "{AGENT_URI_BASE}"))
      FILTER NOT EXISTS {{
        ?other_owner dct:publisher ?publisher .
        FILTER(!({concept_iri_filter("?other_owner")}))
      }}
      ?publisher ?p ?o .
      BIND(?publisher AS ?s)
    }}
  }}
}}
"""
        print(f"DEBUG: delete_concept side=subject concept={concept_identifier}")
        LindasAPIHelper.graphdb_update(delete_subjects)


class I14YAPIHelper:

    # We call the API only once to get all the concepts, then we work on the data locally
    # local_concepts is a i14y id -> concept map
    local_id_concepts_map = {}

    # Same idea, but here we have a concept identifier -> concept list map, useful when a concept identifier has multiple versions
    local_identifier_concepts_map = {}

    # Status counts from the exact CodeList version inventory selected for export.
    source_concept_status_counts = {}
    source_registration_statuses = ()

    # ``local_id_concepts_map`` is also the metadata cache used by
    # ``get_concept_data``. Keep a distinct flag so a manifest can preload a
    # sparse cache without triggering a second, potentially different, source scan.
    source_inventory_loaded = False

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
    def get_concept_status_counts(registration_statuses=None):
        """Read one i14y search count per requested concept registration status."""
        statuses = registration_statuses if registration_statuses is not None else (I14YAPIHelper.source_registration_statuses or STATUSES)
        statuses = list(dict.fromkeys(str(status).strip() for status in statuses if str(status).strip()))
        counts = {}
        for status in statuses:
            last_error = None
            for attempt in range(1, 11):
                try:
                    response = r.get(
                        I14Y_SEARCH_URL,
                        params={
                            "registrationStatuses": status,
                            "types": "Concept",
                            "conceptValueTypes": "CodeList",
                            "page": 1,
                            "pageSize": 25,
                        },
                        verify=False if DEBUG_LOCAL_TEST else True,
                        headers={"User-Agent": I14Y_USER_AGENT},
                    )
                    response.raise_for_status()
                    raw_total = response.headers.get("x-paging-totalrows")
                    if raw_total is None:
                        raise ValueError(
                            f"i14y search response has no x-paging-totalrows header for status {status}"
                        )
                    total = int(raw_total)
                    if total < 0:
                        raise ValueError(
                            f"i14y search returned a negative x-paging-totalrows value for status {status}: {raw_total}"
                        )
                    counts[status] = total
                    break
                except Exception as error:
                    last_error = error
                    if attempt < 10:
                        sleep(random.uniform(1, 2))
            else:
                raise RuntimeError(
                    f"Could not read i14y concept count for registration status {status}"
                ) from last_error
        return counts

    @staticmethod
    def get_all_concepts(registration_statuses=None, pageSize=50):
        """Get public CodeList concepts with the selected registration statuses.

        Every matching CodeList version is exportable, even if another version
        of the same identifier has a different concept type.
        """
        if not I14YAPIHelper.source_inventory_loaded:
            print("DEBUG: get_all_concepts API call")

            if registration_statuses is None:
                registration_statuses = STATUSES
            I14YAPIHelper.source_registration_statuses = tuple(registration_statuses)

            base_url = f"{BASE_API_URL}"
            all_public_concepts = []
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
                            headers={"User-Agent": I14Y_USER_AGENT},
                        )
                        response.raise_for_status()
                        break
                    except Exception:
                        if attempt == retries:
                            raise
                        sleep(random.uniform(1, 2))

                data = response.json().get("data", [])
                if not data:
                    break

                all_public_concepts.extend(data)
                if len(data) < pageSize:
                    break
                page += 1

            # Every public CodeList version matching the requested status is
            # exportable.  Non-CodeList versions of the same identifier never
            # enter the cache or the RDF output.
            latest_concepts = {}
            for concept in all_public_concepts:
                identifiers = concept.get("identifiers") or []
                if not identifiers:
                    continue
                identifier = identifiers[0]
                if (
                    concept.get("conceptType") != "CodeList"
                    or concept.get("registrationStatus") not in registration_statuses
                    or concept.get("id") in EXCLUDED_IDS
                ):
                    continue
                current_latest = latest_concepts.get(identifier)
                if current_latest is None or (concept.get("validFrom") or "") > (current_latest.get("validFrom") or ""):
                    latest_concepts[identifier] = concept

            selected_identifiers = set(latest_concepts)

            # Cache exactly the historical CodeList versions that this exporter
            # may emit. Never include a String/Numeric/etc. version.
            I14YAPIHelper.local_identifier_concepts_map = {}
            for concept in all_public_concepts:
                identifiers = concept.get("identifiers") or []
                if not identifiers:
                    continue
                identifier = identifiers[0]
                if (
                    identifier in selected_identifiers
                    and concept.get("conceptType") == "CodeList"
                    and concept.get("registrationStatus") in registration_statuses
                ):
                    I14YAPIHelper.local_identifier_concepts_map.setdefault(identifier, []).append(concept)

            I14YAPIHelper._refresh_exported_concept_status_counts(registration_statuses)

            for index, concept in enumerate(latest_concepts.values(), 1):
                print(f"{index}. Identifier: {concept.get('identifiers')[0]}")
                print(f"   Title: {concept.get('name')}")
                print(f"   Status: {concept.get('registrationStatus')}")
                print(f"   Version: {concept.get('version')}\n")
                I14YAPIHelper.local_id_concepts_map[concept["id"]] = concept

            I14YAPIHelper.source_inventory_loaded = True

        return list(I14YAPIHelper.local_id_concepts_map.values())

    @staticmethod
    def _refresh_exported_concept_status_counts(registration_statuses=None):
        """Recompute metrics from the current, final export inventory."""
        statuses = registration_statuses if registration_statuses is not None else (I14YAPIHelper.source_registration_statuses or STATUSES)
        I14YAPIHelper.source_concept_status_counts = {
            status: sum(
                1
                for versions in I14YAPIHelper.local_identifier_concepts_map.values()
                for concept in versions
                if concept.get("registrationStatus") == status
            )
            for status in statuses
        }

    @staticmethod
    def get_exported_concept_status_counts(registration_statuses=None):
        """Return status counts from the exact source inventory selected for export."""
        statuses = registration_statuses if registration_statuses is not None else (I14YAPIHelper.source_registration_statuses or STATUSES)
        return {status: I14YAPIHelper.source_concept_status_counts.get(status, 0) for status in statuses}

    @staticmethod
    def get_exported_concept_versions(concept_identifier):
        """Return the CodeList versions retained by the current source scan."""
        return {
            str(concept["version"])
            for concept in I14YAPIHelper.local_identifier_concepts_map.get(concept_identifier, [])
            if concept.get("version") is not None
        }

    @staticmethod
    def write_export_manifest(path):
        """Persist the exact public CodeList version inventory for this run."""
        if not I14YAPIHelper.source_inventory_loaded:
            raise RuntimeError("Cannot write a concept manifest before the source inventory is loaded")

        version_fields = (
            "id",
            "identifiers",
            "version",
            "validFrom",
            "registrationStatus",
            "conceptType",
            "system",
        )
        versions = [
            {field: concept[field] for field in version_fields if field in concept}
            for identifier_versions in I14YAPIHelper.local_identifier_concepts_map.values()
            for concept in identifier_versions
        ]
        manifest = {
            "schemaVersion": 1,
            # The representative records contain the metadata used by the RDF
            # mapper; the version list below is the frozen export inventory.
            "selectedConcepts": list(I14YAPIHelper.local_id_concepts_map.values()),
            "versions": versions,
        }
        Path(path).write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    @staticmethod
    def load_export_manifest(path):
        """Load a frozen source inventory produced by ``write_export_manifest``."""
        try:
            manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read concept export manifest {path}") from error

        if manifest.get("schemaVersion") != 1:
            raise RuntimeError(f"Unsupported concept export manifest schema in {path}")

        versions = manifest.get("versions")
        selected_concepts = manifest.get("selectedConcepts")
        if not isinstance(versions, list) or not isinstance(selected_concepts, list):
            raise RuntimeError(f"Invalid concept export manifest {path}")

        records_by_id = {}
        versions_by_identifier = {}
        for concept in versions:
            identifiers = concept.get("identifiers") if isinstance(concept, dict) else None
            concept_id = concept.get("id") if isinstance(concept, dict) else None
            if not concept_id or not identifiers or not identifiers[0] or concept.get("version") is None:
                raise RuntimeError(f"Invalid concept version in export manifest {path}")
            records_by_id[concept_id] = concept
            versions_by_identifier.setdefault(identifiers[0], []).append(concept)

        selected_records = {}
        for concept in selected_concepts:
            concept_id = concept.get("id") if isinstance(concept, dict) else None
            if concept_id not in records_by_id:
                raise RuntimeError(f"Selected concept {concept_id} is absent from export manifest {path}")
            selected_records[concept_id] = concept

        I14YAPIHelper.local_id_concepts_map = selected_records
        I14YAPIHelper.local_identifier_concepts_map = versions_by_identifier
        I14YAPIHelper.source_concept_status_counts = {
            status: sum(
                1
                for concept in versions
                if concept.get("registrationStatus") == status
            )
            for status in STATUSES
        }
        I14YAPIHelper.source_inventory_loaded = True

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

        # An entirely empty CodeList has no useful shared-dimension content.
        # Fetch every selected version before freezing the inventory, so the
        # decision is identical for the matrix, every batch and the metrics.
        def fetch_versions(concept):
            identifier = concept["identifiers"][0]
            return concept["id"], identifier, I14YAPIHelper.get_version_list(identifier)

        empty_identifiers = set()
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(fetch_versions, concept) for concept in all_concepts]
            for future in as_completed(futures):
                concept_id, identifier, versions = future.result()
                if not any(version.get("codeListEntries") for version in versions):
                    print(f"Skipping empty CodeList {identifier}")
                    empty_identifiers.add(identifier)
                    all_concept_data.pop(concept_id, None)

        if empty_identifiers:
            I14YAPIHelper.local_id_concepts_map = {
                concept_id: concept
                for concept_id, concept in I14YAPIHelper.local_id_concepts_map.items()
                if concept.get("identifiers", [None])[0] not in empty_identifiers
            }
            I14YAPIHelper.local_identifier_concepts_map = {
                identifier: versions
                for identifier, versions in I14YAPIHelper.local_identifier_concepts_map.items()
                if identifier not in empty_identifiers
            }
            I14YAPIHelper._refresh_exported_concept_status_counts()

        if not all_concept_data:
            return []

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

        concepts = [
            concept
            for concept in I14YAPIHelper.local_identifier_concepts_map[concept_identifier]
            if concept.get("conceptType") == "CodeList" and concept.get("registrationStatus") in STATUSES
        ]
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
                concept_data = data["data"]
                # Metadata in the manifest/source scan determines which
                # versions and statuses this run exports. Details are fetched
                # later, but must not silently alter the frozen inventory.
                for field in ("id", "identifiers", "version", "validFrom", "registrationStatus", "conceptType"):
                    if field in version:
                        concept_data[field] = version[field]
                version_data.append(concept_data)
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
