import argparse
import sys
from .versioning import VersionProcessor, CatalogManager
from .versioning.config import *
import warnings
from .utils import get_all_concepts  
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
        if args.concept_ids:

            concept_ids = [cid.strip() for cid in args.concept_ids.split(',') if cid.strip()]
            print(f"Processing batch {args.batch_index} with {len(concept_ids)} concepts")
            rdf_graph = processor.process_all_concepts(concept_ids=concept_ids)
        elif USE_STATUSES:
            print(f"\nFetching all CodeList concepts with statuses: {', '.join(STATUSES)}")
            all_concepts = get_all_concepts(STATUSES)
            concept_ids = [c['id'] for c in all_concepts]
            

            start_idx = args.batch_index * args.batch_size
            end_idx = start_idx + args.batch_size
            batch_ids = concept_ids[start_idx:end_idx]
            
            print(f"Processing batch {args.batch_index} (concepts {start_idx}-{end_idx-1})")
            rdf_graph = processor.process_all_concepts(concept_ids=batch_ids)
        else:
            print(f"\nFetching concepts by ID: {', '.join(CONCEPT_IDS)}")
            rdf_graph = processor.process_all_concepts(concept_ids=CONCEPT_IDS)

        concept_count = len(set(rdf_graph.subjects(RDF.type, SDO.DefinedTermSet)) & 
                            set(rdf_graph.subjects(RDF.type, vl.Identity)))

        version_count = len(set(rdf_graph.subjects(RDF.type, SDO.DefinedTermSet)) & 
                            set(rdf_graph.subjects(RDF.type, vl.Version)))

        print(f"\nProcessed {concept_count} concepts with {version_count} total versions")

        print("\nSerializing graph to ttl")
        turtle_data = rdf_graph.serialize(format="turtle")


        if args.batch_index > 0:
            output_file = f"batch_{args.batch_index}_{OUTPUT_FILE_NAME}"
        else:
            output_file = OUTPUT_FILE_NAME
            
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(turtle_data)

        print(f"\nttl file saved to {output_file}")
        print(f"Total triples generated: {len(rdf_graph)}")

    except Exception as e:
        print(f"\nERROR: Processing failed - {str(e)}")
        raise

if __name__ == "__main__":
    main()
