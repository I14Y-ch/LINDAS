import argparse
import sys
import os
from .versioning import VersionProcessor, CatalogManager
from .versioning.config import *
import warnings
from .versioning.utils import get_all_concepts  
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from rdflib import RDF

def main():
    parser = argparse.ArgumentParser(description='Process concepts in batches')
    parser.add_argument('--batch-index', type=int, default=0, help='Batch index number')
    parser.add_argument('--batch-size', type=int, default=30, help='Number of concepts per batch')
    parser.add_argument('--concept-ids', type=str, help='Comma-separated list of concept IDs to process')
    
    args = parser.parse_args()
    
    processor = VersionProcessor(BASE_URI)
    catalog = CatalogManager(processor.vm).create_catalog_description()

    try:
        # Priority 1: Check for environment variable (used by GitHub Actions)
        batch_concept_ids = os.environ.get('BATCH_CONCEPT_IDS', '').strip()
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
            all_concepts = get_all_concepts(STATUSES)
            all_concept_ids = [c['id'] for c in all_concepts]
            
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

        # Count results
        concept_count = len(set(rdf_graph.subjects(RDF.type, SDO.DefinedTermSet)) & 
                            set(rdf_graph.subjects(RDF.type, vl.Identity)))

        version_count = len(set(rdf_graph.subjects(RDF.type, SDO.DefinedTermSet)) & 
                            set(rdf_graph.subjects(RDF.type, vl.Version)))

        print(f"\nProcessed {concept_count} concepts with {version_count} total versions")

        print("\nSerializing graph to ttl")
        turtle_data = rdf_graph.serialize(format="turtle")

        # Determine output filename
        if batch_concept_ids or args.concept_ids:
            # For batch processing, use batch-specific filename
            batch_index = args.batch_index if args.batch_index is not None else 0
            output_file = f"batch_{batch_index}_{OUTPUT_FILE_NAME}"
        else:
            output_file = OUTPUT_FILE_NAME
            
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(turtle_data)

        print(f"\nTTL file saved to {output_file}")
        print(f"Total triples generated: {len(rdf_graph)}")

        # Additional verification for batch processing
        if batch_concept_ids:
            expected_concepts = len([cid.strip() for cid in batch_concept_ids.split(',') if cid.strip()])
            print(f"Expected to process {expected_concepts} concepts from environment variable")
            if concept_count != expected_concepts:
                print(f"WARNING: Processed {concept_count} concepts but expected {expected_concepts}")

    except Exception as e:
        print(f"\nERROR: Processing failed - {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
