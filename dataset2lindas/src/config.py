"""Runtime configuration for the i14y dataset exporter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DatasetConfig:
    datasets_api_url: str
    dataservices_api_url: str
    lindas_query_url: str
    lindas_update_url: str
    target_graph: str
    dataset_uri_base: str
    dataservice_uri_base: str
    catalog_uri: str
    create_dataset_catalog: bool
    clear_graph: bool
    debug_local_test: bool
    page_size: int
    api_retries: int
    modified_lookback_hours: int
    output_file_name: str
    user_agent: str
    dataset_theme_concept_identifier: str = "DV_DCAT_DATASET_THEME"
    dataset_theme_concept_version: str = "1.1.0"

    @classmethod
    def from_env(cls) -> "DatasetConfig":
        default_lookback = 96 if datetime.now(timezone.utc).weekday() == 0 else 24
        datasets_url = os.environ.get("I14Y_DATASETS_API_URL", "https://api.i14y.admin.ch/api/datasets").rstrip("/")
        dataservices_url = os.environ.get("I14Y_DATASERVICES_API_URL", "https://api.i14y.admin.ch/api/dataservices").rstrip("/")
        return cls(
            datasets_api_url=datasets_url,
            dataservices_api_url=dataservices_url,
            lindas_query_url=os.environ.get("LINDAS_QUERY_URL", "https://lindas.admin.ch/query"),
            lindas_update_url=os.environ.get("LINDAS_UPDATE_URL", ""),
            target_graph=os.environ.get("TARGET_GRAPH", "https://lindas.admin.ch/fso/i14y"),
            dataset_uri_base=os.environ.get(
                "DATASET_URI_BASE", "https://register.ld.admin.ch/i14y/dataset/"
            ).rstrip("/")
            + "/",
            dataservice_uri_base=os.environ.get(
                "DATASERVICE_URI_BASE", "https://register.ld.admin.ch/i14y/dataservice/"
            ).rstrip("/")
            + "/",
            dataset_theme_concept_identifier=os.environ.get(
                "DATASET_THEME_CONCEPT_IDENTIFIER", "DV_DCAT_DATASET_THEME"
            ),
            dataset_theme_concept_version=os.environ.get(
                "DATASET_THEME_CONCEPT_VERSION", "1.1.0"
            ),
            catalog_uri=os.environ.get(
                "DATASET_CATALOG_URI", "https://register.ld.admin.ch/i14y/catalog/datasets"
            ),
            create_dataset_catalog=_as_bool(os.environ.get("CREATE_DATASET_CATALOG", "false")),
            clear_graph=_as_bool(os.environ.get("CLEAR_GRAPH", "false")),
            debug_local_test=_as_bool(os.environ.get("DEBUG_LOCAL_TEST", "false")),
            page_size=int(os.environ.get("I14Y_DATASET_PAGE_SIZE", "100")),
            api_retries=max(1, int(os.environ.get("I14Y_API_RETRIES", "10"))),
            modified_lookback_hours=int(
                os.environ.get("I14Y_MODIFIED_LOOKBACK_HOURS", str(default_lookback))
            ),
            output_file_name=os.environ.get("DATASET_OUTPUT_FILE_NAME", "datasets.ttl"),
            user_agent=os.environ.get(
                "I14Y_USER_AGENT", "I14Y datasets to LINDAS pipeline (contact: i14y@bfs.admin.ch)"
            ),
        )
