# I14Y to LINDAS

This repository synchronizes public [i14y](https://www.i14y.admin.ch/) metadata to the LINDAS graph:

`https://lindas.admin.ch/fso/i14y`

The two maintained exporters are independent Python packages:

- `concept2sharedDimension`: public i14y `CodeList` concepts to LINDAS.
- `dataset2lindas`: public i14y DCAT datasets to LINDAS.

`CPSV_mapping` and `DCAT_mapping` are legacy, standalone mappings and are not part of the automated synchronization.

## Synchronization model

Both exporters follow the same safe incremental model:

1. Scan the complete i14y source inventory.
2. Persist that inventory as a run-specific manifest before creating batches.
3. Build and validate Turtle files locally in the workflow.
4. Upload batches sequentially to LINDAS.
5. Delete resources no longer present in the frozen source inventory.
6. Check source/LINDAS metrics after publication and fail the workflow if they differ.

The manifest means that every batch, reconciliation step and final metric uses the same source snapshot, even if i14y changes while the workflow is running.

## Concepts

`concept2sharedDimension` exports public `CodeList` versions for the configured registration statuses. A CodeList for which every selected version has no entries is excluded. Concepts are incrementally re-imported when their version inventory differs from LINDAS, when `system.modifiedAt` is recent, or when a conservative deep comparison detects a drift.

Concept resources use the following URI family:

```text
https://register.ld.admin.ch/i14y/concept/{identifier}
https://register.ld.admin.ch/i14y/concept/{identifier}/version/{version}
```

The exporter produces the CodeList hierarchy, deterministic skolem IRIs for internal nodes and shared publisher agents below:

```text
https://register.ld.admin.ch/i14y/agent/{publisher-identifier}
```

The daily workflow compares the number of exported concept _versions_ per registration status between i14y and LINDAS.

See [concept2sharedDimension/README.md](concept2sharedDimension/README.md) for details.

## Datasets

`dataset2lindas` scans every page of `GET /api/datasets`, obtains details from `GET /api/datasets/{datasetId}` and exports new or changed datasets. The change window is controlled by `I14Y_MODIFIED_LOOKBACK_HOURS` (24 hours by default, 96 hours on Monday).

Dataset URIs are:

```text
https://register.ld.admin.ch/i14y/dataset/{identifier}
```

For each dataset, the exporter also requests `GET /api/datasets/{datasetId}/structures/exports/TTL`. A `404` simply means that no structure exists. Structures are linked through `dct:conformsTo`, indexed with `dct:hasPart`, and their internal blank nodes are deterministically skolemized under the dataset URI. This permits reliable deletion of a dataset and its owned structure graph.

No `dcat:Catalog` is created by default. `CREATE_DATASET_CATALOG=true` is an independent opt-in switch that creates or updates `https://register.ld.admin.ch/i14y/catalog/datasets`; it is unrelated to `CLEAR_GRAPH`.

The daily workflow verifies both the dataset count and the number of datasets with a structure.

See [dataset2lindas/README.md](dataset2lindas/README.md) for configuration and local batch usage.

## GitHub Actions

The reusable workflows are:

- `.github/workflows/reusable_workflow.yml` for concepts.
- `.github/workflows/dataset_reusable_workflow.yml` for datasets.

Caller workflows target GraphDB TEST, INT and PROD. They validate Turtle with `rapper`, keep artifacts only for generated batches or failures, and use per-environment concurrency locks because LINDAS update requests must not overlap.

After each run, both reusable workflows also upload the same two stable VoID/DCAT dataset descriptions for the LINDAS portal: one for i14y concepts and one for i14y dataset metadata.

Two additional TEST-only lifecycle workflows clear the graph, import the complete inventory, delete every imported resource and verify that the graph is empty. If triples remain, they export the remaining graph as an artifact for diagnosis.

## SPARQL examples

Ready-to-run queries for inspecting the concepts and datasets in LINDAS are available in [SPARQL_EXAMPLES.md](SPARQL_EXAMPLES.md).

## Local usage

Install the dependencies once:

```bash
python -m pip install -r requirements.txt
```

Generate a concept batch:

```bash
$env:BATCH_CONCEPT_IDS = "<i14y-concept-id>"
python -m concept2sharedDimension.src.main --batch-index 0
```

Generate a dataset batch:

```bash
python -m dataset2lindas.src.main --dataset-ids <i14y-dataset-id> --batch-index 0
```

Generation only writes Turtle. Uploading or deleting resources additionally requires `LINDAS_UPDATE_URL` and, for protected environments, `STARDOG_USER` and `STARDOG_PASSWORD`. The target graph defaults to `https://lindas.admin.ch/fso/i14y`.

`stardog_queries_examples.ipynb` contains HTTP/SPARQL examples for inspecting the graph.
