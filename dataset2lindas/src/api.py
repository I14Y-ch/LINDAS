"""HTTP clients for i14y and LINDAS."""

from __future__ import annotations

import os
import random
from pathlib import Path
from time import sleep
from typing import Any
from urllib.parse import urlparse

import requests

from .config import DatasetConfig


class I14YDatasetsAPI:
    """Read-only client for the public DCAT dataset and dataservice endpoints."""

    def __init__(self, config: DatasetConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self._dataservice_public_cache: dict[str, bool] = {}

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"User-Agent": self.config.user_agent, "Accept": "application/json"}
        last_error: Exception | None = None
        for attempt in range(1, self.config.api_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=60,
                    verify=False if self.config.debug_local_test else True,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError(f"Unexpected JSON payload from {url}")
                return payload
            except Exception as error:  # requests errors and invalid JSON are retried alike
                last_error = error
                if attempt < self.config.api_retries:
                    sleep(random.uniform(1, 2))
        raise RuntimeError(f"i14y request failed after {self.config.api_retries} attempts: {url}") from last_error

    def get_all_datasets(self) -> list[dict[str, Any]]:
        """Fetch every page without filters and retain only the sync inventory fields."""
        datasets: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self._get_json(
                self.config.datasets_api_url,
                params={"page": page, "pageSize": self.config.page_size},
            )
            data = payload.get("data") or []
            if not isinstance(data, list):
                raise ValueError("GET /api/datasets returned a non-list data member")
            for dataset in data:
                if not isinstance(dataset, dict):
                    raise ValueError("GET /api/datasets returned a non-object dataset")
                system = dataset.get("system") or {}
                datasets.append(
                    {
                        "id": dataset.get("id"),
                        "identifiers": dataset.get("identifiers") or [],
                        "system": {"modifiedAt": system.get("modifiedAt")},
                    }
                )
            if not data or len(data) < self.config.page_size:
                break
            page += 1
        return datasets

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        payload = self._get_json(f"{self.config.datasets_api_url}/{dataset_id}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"GET /api/datasets/{dataset_id} returned no dataset")
        return data

    def get_dataset_structure_turtle(self, dataset_id: str) -> str | None:
        """Return the dataset SHACL Turtle, or ``None`` when i14y has no structure.

        A missing structure is the documented ``404`` outcome. Other HTTP failures
        are retried with the same policy as the JSON endpoints.
        """
        url = f"{self.config.datasets_api_url}/{dataset_id}/structures/exports/TTL"
        headers = {"User-Agent": self.config.user_agent, "Accept": "text/turtle, */*"}
        last_error: Exception | None = None
        for attempt in range(1, self.config.api_retries + 1):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=60,
                    verify=False if self.config.debug_local_test else True,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.text
            except Exception as error:
                last_error = error
                if attempt < self.config.api_retries:
                    sleep(random.uniform(1, 2))
        raise RuntimeError(
            f"i14y structure request failed after {self.config.api_retries} attempts: {url}"
        ) from last_error

    def is_dataservice_public(self, dataservice_id: str) -> bool:
        if dataservice_id not in self._dataservice_public_cache:
            payload = self._get_json(f"{self.config.dataservices_api_url}/{dataservice_id}")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError(f"GET /api/dataservices/{dataservice_id} returned no dataservice")
            self._dataservice_public_cache[dataservice_id] = data.get("publicationLevel") == "Public"
        return self._dataservice_public_cache[dataservice_id]


class LindasDatasetsAPI:
    """SPARQL and RDF-upload client limited to the dataset exporter namespace."""

    def __init__(self, config: DatasetConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    @property
    def _auth(self) -> tuple[str, str] | None:
        username = os.environ.get("STARDOG_USER", "")
        password = os.environ.get("STARDOG_PASSWORD", "")
        return (username, password) if username and password else None

    def query(self, sparql: str) -> list[dict[str, Any]]:
        response = self.session.post(
            self.config.lindas_query_url,
            data={"query": sparql},
            headers={
                "Accept": "application/sparql-results+json",
                "Accept-Encoding": "identity",
                "User-Agent": self.config.user_agent,
            },
            timeout=60,
            verify=False if self.config.debug_local_test else True,
        )
        response.raise_for_status()
        return response.json().get("results", {}).get("bindings", [])

    def get_existing_dataset_identifiers(self) -> set[str]:
        query = f'''\
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT DISTINCT ?identifier
WHERE {{
  GRAPH <{self.config.target_graph}> {{
    ?dataset a dcat:Dataset ; 
             dct:identifier ?identifier .
  }}
}}'''
        return {
            value
            for row in self.query(query)
            if (value := row.get("identifier", {}).get("value"))
        }
    def _update_url(self) -> str:
        url = self.config.lindas_update_url.rstrip("/")
        if not url:
            raise ValueError("LINDAS_UPDATE_URL is required for updates")
        if "graphdb" in url.lower():
            return url if url.endswith("/statements") else f"{url}/statements"
        return url if url.endswith("/update") else f"{url}/update"

    def update(self, sparql: str) -> None:
        response = self.session.post(
            self._update_url(),
            data=sparql,
            headers={"Content-Type": "application/sparql-update", "User-Agent": self.config.user_agent},
            auth=self._auth,
            timeout=300,
            verify=False if self.config.debug_local_test else True,
        )
        response.raise_for_status()

    def clear_graph(self) -> None:
        self.update(f"DROP GRAPH <{self.config.target_graph}>")

    def delete_dataset(self, identifier: str) -> None:
        """Remove a dataset in two prefix-based SPARQL passes.

        The first pass removes every locally owned subject and, from the same
        query snapshot, the explicitly tracked external resources that became
        orphaned. The second removes all incoming references to the dataset
        namespace (including an optional catalogue membership).
        """
        dataset_uri = f"{self.config.dataset_uri_base}{identifier}"
        dataset_prefix = f"{dataset_uri}/"
        structure_uri = f"{dataset_uri}/structure"
        agent_uri_base = self.config.agent_uri_base
        graph = self.config.target_graph

        def dataset_iri_filter(node_variable: str) -> str:
            return (
                f'isIRI({node_variable}) && '
                f'(STR({node_variable}) = "{dataset_uri}" || '
                f'STRSTARTS(STR({node_variable}), "{dataset_prefix}"))'
            )

        delete_subjects = f'''\
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o . }} }}
WHERE {{
  GRAPH <{graph}> {{
    {{
      ?s ?p ?o .
      FILTER ({dataset_iri_filter("?s")})
    }}
    UNION
    {{
      <{dataset_uri}> dct:conformsTo <{structure_uri}> .
      <{structure_uri}> dct:hasPart ?part .
      FILTER(isIRI(?part) && !({dataset_iri_filter("?part")}))
      FILTER NOT EXISTS {{
        ?other_structure dct:hasPart ?part .
        FILTER(?other_structure != <{structure_uri}>)
      }}
      ?part ?p ?o .
      BIND(?part AS ?s)
    }}
    UNION
    {{
      <{dataset_uri}> dct:publisher ?publisher .
      FILTER(isIRI(?publisher) && STRSTARTS(STR(?publisher), "{agent_uri_base}"))
      FILTER NOT EXISTS {{
        ?other_owner dct:publisher ?publisher .
        FILTER(!({dataset_iri_filter("?other_owner")}))
      }}
      ?publisher ?p ?o .
      BIND(?publisher AS ?s)
    }}
    UNION
    {{
      VALUES (?relation ?resource_type) {{
        (dcat:accessURL rdfs:Resource)
        (dcat:downloadURL rdfs:Resource)
        (dcat:landingPage foaf:Document)
        (dct:conformsTo dct:standard)
        (dct:isReferencedBy rdfs:Resource)
        (dct:relation rdfs:Resource)
        (foaf:page foaf:Document)
        (schema:image schema:url)
      }}
      ?owner ?relation ?resource .
      FILTER ({dataset_iri_filter("?owner")})
      FILTER(isIRI(?resource) && !({dataset_iri_filter("?resource")}))
      ?resource rdf:type ?resource_type .
      FILTER NOT EXISTS {{
        ?other_owner ?relation ?resource .
        FILTER(!isIRI(?other_owner) || !({dataset_iri_filter("?other_owner")}))
      }}
      BIND(?resource AS ?s)
      BIND(rdf:type AS ?p)
      BIND(?resource_type AS ?o)
    }}
  }}
}}'''

        delete_objects = f'''\
DELETE {{ GRAPH <{graph}> {{ ?s ?p ?o . }} }}
WHERE {{
  GRAPH <{graph}> {{
    ?s ?p ?o .
    FILTER ({dataset_iri_filter("?o")})
  }}
}}'''
        self.update(delete_subjects)
        self.update(delete_objects)
    def upload_turtle(self, file_path: str | Path) -> None:
        """Upload a Turtle artifact transactionally on Stardog and directly on GraphDB."""
        path = Path(file_path)
        update_url = self._update_url()
        headers = {"Content-Type": "text/turtle", "User-Agent": self.config.user_agent}

        if "graphdb" in update_url.lower():
            with path.open("rb") as stream:
                response = self.session.post(
                    update_url,
                    data=stream,
                    headers=headers,
                    params={"context": f"<{self.config.target_graph}>"},
                    auth=self._auth,
                    timeout=1800,
                    verify=False if self.config.debug_local_test else True,
                )
            if response.status_code != 204:
                raise RuntimeError(f"GraphDB upload failed: {response.status_code} {response.text}")
            return

        parsed = urlparse(self.config.lindas_update_url)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("LINDAS_UPDATE_URL must include the Stardog database name")
        database = parts[-1]
        server_root = parsed._replace(path="/" + "/".join(parts[:-1])).geturl().rstrip("/")
        begin_url = f"{server_root}/{database}/transaction/begin"
        begin = self.session.post(
            begin_url,
            headers={"User-Agent": self.config.user_agent},
            auth=self._auth,
            timeout=300,
            verify=False if self.config.debug_local_test else True,
        )
        begin.raise_for_status()
        transaction = begin.text.strip('"')
        add_url = f"{server_root}/{database}/{transaction}/add"
        commit_url = f"{server_root}/{database}/transaction/commit/{transaction}"
        rollback_url = f"{server_root}/{database}/transaction/rollback/{transaction}"
        try:
            with path.open("rb") as stream:
                add = self.session.post(
                    add_url,
                    data=stream,
                    headers=headers,
                    params={"graph-uri": self.config.target_graph},
                    auth=self._auth,
                    timeout=1800,
                    verify=False if self.config.debug_local_test else True,
                )
            if add.status_code not in (200, 204):
                raise RuntimeError(f"Stardog upload failed: {add.status_code} {add.text}")
            commit = self.session.post(
                commit_url,
                headers={"User-Agent": self.config.user_agent},
                auth=self._auth,
                timeout=300,
                verify=False if self.config.debug_local_test else True,
            )
            commit.raise_for_status()
        except Exception:
            self.session.post(
                rollback_url,
                headers={"User-Agent": self.config.user_agent},
                auth=self._auth,
                timeout=300,
                verify=False if self.config.debug_local_test else True,
            )
            raise
