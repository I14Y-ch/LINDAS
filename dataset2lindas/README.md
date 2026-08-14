# i14y datasets to LINDAS

`dataset2lindas` incrementally exports the public i14y DCAT datasets into the i14y LINDAS graph.

The normal workflow scans every page of `GET /api/datasets`, retaining only the primary identifier, i14y id and `system.modifiedAt` in its inventory. It compares that inventory with LINDAS and creates RDF only for new or recently changed datasets. Detail payloads always come from `GET /api/datasets/{datasetId}`, one at a time.

## Configuration

- `I14Y_DATASETS_API_URL` / `I14Y_DATASERVICES_API_URL`: public i14y API endpoints.
- `LINDAS_QUERY_URL`, `LINDAS_UPDATE_URL`, `STARDOG_USER`, `STARDOG_PASSWORD`: LINDAS connection.
- `TARGET_GRAPH`: defaults to `https://lindas.admin.ch/fso/i14y`.
- `I14Y_MODIFIED_LOOKBACK_HOURS`: change window; defaults to 24 hours, or 96 hours on Monday.
- `GRAPHDB_UPDATE_RETRIES`, `GRAPHDB_UPDATE_BACKOFF_MIN` and `GRAPHDB_UPDATE_BACKOFF_MAX`: retries for idempotent SPARQL updates such as `DROP GRAPH` and dataset deletions. The workflows use 3 attempts.
- `AGENT_URI_BASE`: defaults to `https://register.ld.admin.ch/i14y/agent/`. Publishers use their i14y `identifier` below this base, so datasets and concepts share the same `foaf:Agent`.
- `CREATE_DATASET_CATALOG`: defaults to `false`. When `true`, the workflow writes `dcat:Catalog` membership triples to `DATASET_CATALOG_URI` (default `https://register.ld.admin.ch/i14y/catalog/datasets`). This toggle is independent from `CLEAR_GRAPH`.
- `DATASET_THEME_CONCEPT_IDENTIFIER` / `DATASET_THEME_CONCEPT_VERSION`: defaults to `DV_DCAT_DATASET_THEME` / `1.1.0`. Theme codes are mapped to the corresponding versioned i14y concept IRIs.
- Turtle is written through StreamingTurtleWriter; internal RDF blank nodes are deterministically skolemized below <dataset-uri>/.well-known/genid/. A replacement/removal can therefore delete the complete owned subgraph from the dataset identifier alone.
- For each dataset, `GET /api/datasets/{datasetId}/structures/exports/TTL` is also requested. A `404` means that no structure exists. Its NodeShapes and named external subjects are indexed as `dct:hasPart` of `<dataset-uri>/structure`; blank nodes are skolemized below `<dataset-uri>/structure/.well-known/genid/`. Dataset deletion uses the structure `dct:hasPart` index to remove unshared external structure subjects, then traverses the local subgraph from the dataset with a bounded property path and removes optional catalogue membership with a constant `DELETE DATA`.

For an ad-hoc RDF batch:

```bash
python -m dataset2lindas.src.main --dataset-ids <uuid>,<uuid> --batch-index 0
```
