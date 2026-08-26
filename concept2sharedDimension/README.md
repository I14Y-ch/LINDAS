# i14y concepts to LINDAS

`concept2sharedDimension` incrementally exports public i14y `CodeList` concepts to the LINDAS i14y graph:

`https://lindas.admin.ch/fso/i14y`

## Source inventory and incremental plan

The exporter scans every public concept record from `BASE_API_URL` once per workflow run. It builds one frozen export inventory before creating batches or publishing any Turtle.

For each primary concept identifier, the inventory is selected as follows:

- Only `CodeList` records with a registration status configured in `STATUSES` are eligible.
- The latest eligible CodeList record is used as the representative of an identifier.
- All historical eligible CodeList versions of that selected identifier are included; versions of another concept type are ignored.
- Identifiers in `EXCLUDED_IDS`, or without a usable primary identifier, are ignored.
- An identifier is excluded when every selected CodeList version has no `codeListEntries`.

The exporter fetches the selected versions before batching, then persists the resulting snapshot to `concept_source_manifest.json`. Batch generation, orphan reconciliation and the final metrics all reload that manifest, so a change in i14y during a workflow cannot make different workflow steps use different source inventories.

With `CLEAR_GRAPH=false`, reconciliation is per concept identifier:

| LINDAS state / source change | Action |
| --- | --- |
| Identifier absent from LINDAS | Import all selected versions. |
| Exported source-version set differs from the LINDAS version set | Delete the identifier and import it again. |
| `system.modifiedAt` is inside the configurable lookback window | Delete the identifier and import it again. |
| `system.modifiedAt` is absent or invalid | Compare the selected versions, attributes and entries deeply; replace only if they differ. |
| Identifier is absent from the frozen source inventory | Delete it from LINDAS during orphan reconciliation. |
| No change detected | Produce no Turtle for that identifier. |

The default lookback window is 24 hours and is extended to 96 hours on Mondays. With `CLEAR_GRAPH=true`, every selected identifier is exported and the workflow drops the target graph before the generated batches are uploaded.

## RDF model and URIs

Each concept has a persistent identity and one resource per version:

```text
https://register.ld.admin.ch/i14y/concept/{identifier}
https://register.ld.admin.ch/i14y/concept/{identifier}/version/{version}
```

Code entries, hierarchy roots, levels and internal list nodes use the same concept prefix. Internal nodes are deterministically skolemized below:

```text
https://register.ld.admin.ch/i14y/concept/{identifier}/.well-known/genid/{hash}
```

Publishers are shared agents, not per-concept blank nodes:

```text
https://register.ld.admin.ch/i14y/agent/{publisher-identifier}
```

The exporter maps the code-list hierarchy, multilingual metadata, version/identity relations and publisher information. A shared agent is removed only when no concept or dataset in the graph still references it.

## Reconciliation and deletion

Deletion uses a bounded RDF closure rooted in the concept URI. Dataset-structure `dct:conformsTo` links to concept resources are deliberately preserved when a concept is deleted; they disappear when the owning dataset structure is deleted.

## Local usage

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Generate one batch without publishing it:

```bash
$env:BATCH_CONCEPT_IDS = "<i14y-concept-uuid>"
python -m concept2sharedDimension.src.main --batch-index 0
```

The resulting Turtle file is `batch_0_output.ttl`. Useful configuration is defined in `src/versioning/config.py` or by environment variables:

- `BASE_API_URL`: i14y public concepts endpoint.
- `STATUSES`: comma-separated registration statuses.
- `TARGET_GRAPH`, `LINDAS_QUERY_URL`, `LINDAS_UPDATE_URL`: LINDAS endpoints.
- `I14Y_MODIFIED_LOOKBACK_HOURS`: incremental change window.
- `CLEAR_GRAPH`: workflow switch that drops the target graph before publishing the generated batches.
- `STARDOG_USER` / `STARDOG_PASSWORD`: credentials for protected LINDAS environments.

Set `DEBUG_LOCAL_TEST=true` only in environments that require the local proxy/TLS configuration.

## GitHub Actions

`.github/workflows/reusable_workflow.yml` is called by TEST, INT and PROD workflows. It:

1. Builds batches and archives the frozen source manifest.
2. Produces Turtle in parallel batches and validates it with `rapper`.
3. Uploads the generated artifacts sequentially.
4. Generates and uploads the two stable VoID/DCAT portal dataset descriptions, even when no concept requires a new Turtle batch.
5. Compares i14y and LINDAS counts of concept *versions* for every configured registration status.

A metric mismatch fails the workflow. The TEST full-lifecycle workflow additionally clears the graph, imports the complete inventory, deletes every concept with the production deletion mechanism and verifies that no triples remain.
