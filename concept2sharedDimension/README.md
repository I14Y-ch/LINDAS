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

### Workflow Logic

1. **Get Concepts Job** (`get-concepts`):
   - Retrieves all concept IDs the specified statuses
   - Calculates the number of batches needed based on the `BATCH_SIZE` environment variable
   - Creates a job matrix for parallel processing of batches
   - Outputs the list of concept IDs and batch configuration

2. **Process Batches Job** (`process-batches`):
   - Processes concepts to generate RDF triples in Turtle format
   - Uploads each batch's output as a separate artifact for later combination

3. **Combine and Upload Job** (`combine-and-upload`):
   - Downloads all batch artifacts after all batches complete
   - Combines the RDF files from all batches into a single file
   - Handles RDF prefix deduplication to ensure valid Turtle syntax
   - Clears the existing Stardog graph
   - Uploads the combined RDF data to the target Stardog graph

### Environment Configuration

The authentication is done via GitHub secrets `STARDOG_USERNAME` and `STARDOG_PASSWORD_TEST`. The instructions are set for the test environment. To change to production:

1. Modify the `STARDOG_URL` in the `env` section of `main.yml`:
   ```yaml
   env:
     STARDOG_URL: 'https://stardog-prod.cluster.ldbar.ch/lindas'  # Change from test to prod
   ```

2. Update the password secret references in both the "Clear Stardog Graph" and "Upload to Stardog" steps:
   ```yaml
   env:
     STARDOG_PASSWORD: ${{ secrets.STARDOG_PASSWORD_PROD }}  # Change from TEST to PROD
   ```

### Customization

You can adjust the batch size by modifying the `BATCH_SIZE` environment variable:
```yaml
env:
  BATCH_SIZE: '30'  # Increase for fewer larger batches, decrease for more smaller batches
```

The status filter for concepts can be modified in the Python configuration to control which concepts are processed.

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





