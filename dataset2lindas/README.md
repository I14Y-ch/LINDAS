# i14y datasets to LINDAS

`dataset2lindas` incrementally exports the public i14y DCAT datasets into the i14y LINDAS graph.

The normal workflow scans every page of `GET /api/datasets`, retaining only the primary identifier, i14y id and `system.modifiedAt` in its inventory. It compares that inventory with LINDAS and creates RDF only for new or recently changed datasets. Detail payloads always come from `GET /api/datasets/{datasetId}`, one at a time.

## Configuration

- `I14Y_DATASETS_API_URL` / `I14Y_DATASERVICES_API_URL`: public i14y API endpoints.
- `LINDAS_QUERY_URL`, `LINDAS_UPDATE_URL`, `STARDOG_USER`, `STARDOG_PASSWORD`: LINDAS connection.
- `TARGET_GRAPH`: defaults to `https://lindas.admin.ch/fso/i14y`.
- `I14Y_MODIFIED_LOOKBACK_HOURS`: change window; defaults to 24 hours, or 96 hours on Monday.
- `CREATE_DATASET_CATALOG`: defaults to `false`. When `true`, the workflow writes `dcat:Catalog` membership triples to `DATASET_CATALOG_URI` (default `https://register.ld.admin.ch/i14y/catalog/datasets`). This toggle is independent from `CLEAR_GRAPH`.
- `DATASET_THEME_CONCEPT_IDENTIFIER` / `DATASET_THEME_CONCEPT_VERSION`: defaults to `DV_DCAT_DATASET_THEME` / `1.1.0`. Theme codes are mapped to the corresponding versioned i14y concept IRIs.
- Turtle is written through StreamingTurtleWriter; internal RDF blank nodes are deterministically skolemized below <dataset-uri>/.well-known/genid/. A replacement/removal can therefore delete the complete owned subgraph from the dataset identifier alone.

For an ad-hoc RDF batch:

```bash
python -m dataset2lindas.src.main --dataset-ids <uuid>,<uuid> --batch-index 0
```
