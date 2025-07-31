# i14y concept mapping to lindas shared dimension

## File Structure

```
Concept_mapping/
├── src/
│   ├── versioning/          
│   │   ├── __init__.py      
│   │   ├── core.py      
│   │   ├── processor.py   
│   │   └── utils.py        
│   └── main.py
├── examples/  
│   ├── arp_ch_sd.ttl    
│   ├── sex_sd.ttl           
│   └── test_versioning.ttl          
├── README.md
├── requirements.txt
└── .gitignore
```

## Main components structure and functionalities

The main components are

- Core Modules (core.py):
    - GraphManager: Handles RDF graph creation and URI generation
    - CodeListManager: Manages hierarchical code list structures and version-identity relationships
    - ConceptMetadataManager: Handles concept scheme metadata 

- Processing Flow (processor.py):
    - The VersionProcessor handles the version processing pipeline: for each version, it creates both identity (persistent) and version-specific objects
    - Tracks changes between versions (additions, deletions, modifications)
      
## How to use the script

**1. Install dependencies:**
```bash
pip install -r requirements.txt
```

**2. Configure the script:**

Update `config.py` with yours configuration data, in particular you need to set: 

- You can either transform a list of concept based on statuses, in this case:
  - Set `USE_STATUSES = True`  # Set to False to use concept_ids
  - Define the statuses that you are interested in with the variable `STATUSES`
      
- Or you can transform a list of concept based on concept Ids, in this case:
  - Set `USE_STATUSES = False`
  - Define the ids that you are interested in, in the variable `CONCEPT_IDS`
    
- Set the name of the output file in the variable `OUTPUT_FILE_NAME`

**3. Run `main.py`.** 

## I14Y to LINDAS - Next steps notes 
In the last meeting 14.04.2025 (full presentation available in the repository) we have decided : 
- When I14Y concepts are ready, publish I14Y concepts without the type SharedDimension to avoid confusion for the user
- Manually check duplicates with already existing Shared dimension in LINDAS
- Add SharedDimension type for all concepts that are ready and do not have duplicates.

**Note for script future use**: To add the type SharedDimension to the Concepts autmatically via the script, uncomment the following line (inside the class `ConceptMetadataManager` and function `add_scheme_metadata`):
```
self.vm.graph.add((uri, RDF.type, meta.SharedDimension))   

```
