import argparse
import os
from time import time
from .versioning import VersionProcessor, CatalogManager
from .versioning.config import *
from .versioning.utils import I14YAPIHelper, timer  
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
import tracemalloc

@timer
def main():
    parser = argparse.ArgumentParser(description='Process concepts in batches')
    parser.add_argument('--batch-index', type=int, default=0, help='Batch index number')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of concepts per batch')
    parser.add_argument('--concept-ids', type=str, help='Comma-separated list of concept IDs to process')
    parser.add_argument(
        '--publication-metadata-only',
        action='store_true',
        help='Write the stable I14Y portal dataset descriptions without processing concepts',
    )
    parser.add_argument('--output', help='Output Turtle path for --publication-metadata-only')
    parser.add_argument(
        '--publication-metadata-kind',
        choices=('concepts', 'datasets', 'all'),
        default='all',
        help='Portal metadata description to write; defaults to both descriptions',
    )
    parser.add_argument(
        '--publication-metadata-source-manifest',
        help='Frozen i14y source manifest used to derive the portal modified date',
    )

    args = parser.parse_args()
    if args.publication_metadata_only:
        output_file = args.output or "i14y_portal_metadata.ttl"
        if args.publication_metadata_source_manifest and args.publication_metadata_kind == 'all':
            parser.error('--publication-metadata-source-manifest requires a concepts or datasets scope')
        modified_date = (
            CatalogManager.source_modified_date_from_manifest(
                args.publication_metadata_source_manifest,
                args.publication_metadata_kind,
            )
            if args.publication_metadata_source_manifest
            else None
        )
        processor = VersionProcessor(BASE_URI, output_file=output_file, enable_skolem=False)
        try:
            CatalogManager(processor.vm).create_publication_descriptions(
                args.publication_metadata_kind,
                modified_date,
            )
        finally:
            processor.vm.close()
        print(f"Wrote I14Y portal metadata ({args.publication_metadata_kind}) to {output_file}")
        return

    # Workflow batches receive the same source inventory that built their
    # matrix. This prevents a change on i14y during the run from changing the
    # set of versions emitted by a later batch.
    manifest_path = os.environ.get("I14Y_CONCEPT_MANIFEST_PATH", "").strip()
    if manifest_path:
        I14YAPIHelper.load_export_manifest(manifest_path)
        print(f"Loaded frozen concept export manifest: {manifest_path}")
    else:
        I14YAPIHelper.get_all_concepts()

    batch_concept_ids = os.environ.get('BATCH_CONCEPT_IDS', '').strip()

    # Determine output filename
    if batch_concept_ids or args.concept_ids:
        # For batch processing, use batch-specific filename
        batch_index = args.batch_index if args.batch_index is not None else 0
        output_file = f"batch_{batch_index}_{OUTPUT_FILE_NAME}"
    else:
        output_file = OUTPUT_FILE_NAME

    processor = VersionProcessor(BASE_URI,output_file=output_file)

    try:
        # Priority 1: Check for environment variable (used by GitHub Actions)
        if batch_concept_ids:
            concept_ids = [cid.strip() for cid in batch_concept_ids.split(',') if cid.strip()]
            print(f"Processing batch from environment variable with {len(concept_ids)} concepts")
            print(f"Concept IDs: {concept_ids[:3]}{'...' if len(concept_ids) > 3 else ''}")
            rdf_graph = processor.process_all_concepts(concept_ids=concept_ids)

        # Priority 2: Command line argument
        elif args.concept_ids:
            concept_ids = [cid.strip() for cid in args.concept_ids.split(',') if cid.strip()]
            print(f"Processing batch from command line with {len(concept_ids)} concepts")
            rdf_graph = processor.process_all_concepts(concept_ids=concept_ids)

        # Priority 3: Use status-based filtering with batching
        elif USE_STATUSES:
            print(f"\nFetching all CodeList concepts with statuses: {', '.join(STATUSES)}")
            all_concepts = I14YAPIHelper.get_all_concepts(STATUSES)
            all_concept_ids = [c['id'] for c in all_concepts]
            print(f"Number of total concepts to process: {len(all_concept_ids)}")

            # Apply batching if batch parameters are provided
            if args.batch_index is not None and args.batch_size is not None:
                start_idx = args.batch_index * args.batch_size
                end_idx = start_idx + args.batch_size
                batch_ids = all_concept_ids[start_idx:end_idx]

                print(f"Processing batch {args.batch_index} (concepts {start_idx}-{min(end_idx-1, len(all_concept_ids)-1)})")
                print(f"Batch contains {len(batch_ids)} concepts")
                rdf_graph = processor.process_all_concepts(concept_ids=batch_ids)
            else:
                # Process all concepts if no batching specified
                print(f"Processing all {len(all_concept_ids)} concepts")
                rdf_graph = processor.process_all_concepts(concept_ids=all_concept_ids)

        # Priority 4: Use hardcoded CONCEPT_IDS
        else:
            print(f"\nProcessing concepts by ID from config: {', '.join(CONCEPT_IDS)}")
            rdf_graph = processor.process_all_concepts(concept_ids=CONCEPT_IDS)

        rdf_graph.close()

        concept_count, version_count = rdf_graph.final_counts()

        print(f"\nProcessed {concept_count} concepts with {version_count} total versions")
        # Additional verification for batch processing
        if batch_concept_ids:
            expected_concepts = len([cid.strip() for cid in batch_concept_ids.split(',') if cid.strip()])
            print(f"Expected to process {expected_concepts} concepts from environment variable")
            if concept_count != expected_concepts:
                print(f"WARNING: Processed {concept_count} concepts but expected {expected_concepts}")

        if concept_count == 0 and version_count==0:
            if os.path.exists(output_file):
                os.remove(output_file)
                print(f"{output_file} deleted because no concepts have been updated")

    except Exception as e:
        print(f"\nERROR: Processing failed - {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    tracemalloc.start()
    main()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    print(f"Peak RAM usage: {peak_mem/1024/1024/1024} GB")
    tracemalloc.stop()
