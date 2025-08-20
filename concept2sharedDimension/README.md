# i14y concept mapping to lindas shared dimension

## File Structure

```
Concept_mapping/
├── src/
│   ├── versioning/          
│   │   ├── __init__.py
│   │   ├── config.py    
│   │   ├── core.py      
│   │   ├── processor.py   
│   │   └── utils.py        
│   └── main.py
├── examples/            
│   └── noga_output.ttl          
└── README.md
```

## Main components structure and functionalities

The main components are

- Core Modules (core.py):
    - GraphManager: Handles RDF graph creation and URI generation
    - CatalogManager: describe the i14y catalog based on void
    - CodeListManager: Manages hierarchical code list structures and version-identity relationships
    - ConceptMetadataManager: Handles concept scheme metadata 

- Processing Flow (processor.py):
    - The VersionProcessor handles the version processing pipeline: for each version, it creates both identity (persistent) and version-specific objects
      
- utils.py: utility functions (API calls, ...)
  
- config.py: configuration file
      
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

**Note for script future use**: To add the type SharedDimension to the Concepts autmatically via the script, uncomment the following line (inside the class `ConceptMetadataManager` and function `add_scheme_metadata`):

```
self.vm.graph.add((uri, RDF.type, meta.SharedDimension))   

```
## github Action - workflow
In the folder `.github/workflows` you can find the `main.yml` file with the istructions to automatically update the I14Y graph on LINDAS. At the moment (31.07.2025) the synchronisation takes place automatically every week (monday at midnight). Synchronisation can also be triggered manually if necessary. 

The authentication is done via github secrets STARDOG_USERNAME and STARDOG_PASSWORD_TEST (the instructions are set for the test environement, if you want to change on prod you just need to modify:
- the `STARDOG_URL: 'https://stardog-test.cluster.ldbar.ch/lindas'` in `env` (in the `main.yml` file)
- the call for the right secret for `STARDOG_PASSWORD: ${{ secrets.STARDOG_PASSWORD_TEST }}`  (in the `main.yml` file) in the "Clear Stardog graph" step and "Upload to Stardog" step.

## LINDAS publication: some notes

In this repository it's stored a Jupyter notebook named [*stardog_queries_examples.ipynb*](https://github.com/I14Y-ch/LINDAS/blob/9675b7e044e4607322d0e67806172c5d66ae2ad7/stardog_queries_examples.ipynb) that contains some python examples that demonstrates how to make requests to the stardog database (upload, update, retrieve and delete). 

LINDAS uses three environement for different workflow stages:
- TEST: Development & experimental work, BASE API URL: https://stardog-test.cluster.ldbar.ch/lindas
- INT: Pre-production validation, BASE API URL: https://stardog-int.cluster.ldbar.ch/lindas	
- PROD: Production, BASE API URL: https://stardog.cluster.ldbar.ch/lindas

The i14y graph in which all data at the moment is published is: https://lindas.admin.ch/fso/i14y.

## URI creation

The URI created for the publication in RDF of I14Y concept is constructed as follow:

| Object    | URI |  Name | 
| -------- | ------- | ------- |
| Concept / Defined term set identity |https://register.ld.admin.ch/i14y/[concept_identifier] | [concept name] + " (identitiy)"|
| Concept / Defined term set version |https://register.ld.admin.ch/i14y/[concept_identifier]/version/[version_number] | [concept name] + " (version " + [version number] ")"|
| Code / Defined term identity |https://register.ld.admin.ch/i14y/[concept_identifier]/[code_identifier] | [code name] + " (identitiy)" |
| Code / Defined term version |https://register.ld.admin.ch/i14y/[concept_identifier]/[code_identifier]/version/[version_number]| [code name] + " (version " + [version number] ")"|




