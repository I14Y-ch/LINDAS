from .versioning import VersionProcessor, CatalogManager
from .versioning.config import *
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from rdflib import RDF

def main():
    processor = VersionProcessor(BASE_URI)
    catalog = CatalogManager(processor.vm).create_catalog_description()

    try:
        if USE_STATUSES:
            print(f"\nFetching all CodeList concepts with statuses: {', '.join(STATUSES)}")
            rdf_graph = processor.process_all_concepts(registration_statuses=STATUSES)
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
