import os
from rdflib import Namespace

# Toggle between using statuses or concept_ids
USE_STATUSES = True # Set to False to use concept_ids

# If using statuses
# One of the following: Candidate, Recorded, Qualified, Standard, PreferredStandard, Superseded, Retired
STATUSES = ["Qualified",  "Standard", "PreferredStandard"] # "Recorded"

# Use this variable to esclude specific Ids:
# 21.08.2025: I have removed NOGA single hierarchy concepts (NOGA Section, ...) they are duplicates of NOGA
# 21.08.2025: I have removed Isco Jobs related concept
# 22.08.2025: I have removed EprAgentRole codelist (08dd632d-aee2-333d-b1e4-505385fde8ff) because it gets an internal error 500 when retrieving codelist entries from I14Y
# [ "08dd632d-aee2-333d-b1e4-505385fde8ff", "08dd20cc-3ee5-c17a-8d8b-c1664c3421a6", "08dc74b4-30d4-be8d-ba53-91a1201ac86b", "08dceec4-b3f0-1285-b8d0-b005fabcf87c", "08d92cdc-c97d-acd7-9952-56dd375b0777", "08d92cdc-827b-5021-8242-f4166fb122b0", "08d92cdc-03c1-103f-8fec-a24aafeaedd3", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d94603-f490-f094-9fe5-8012ca56d812", "08d94604-db03-1909-a097-569cb9836253", "08d94604-f12a-5d82-b6b4-fdc55b9b4750", "08d94604-e058-62a2-aa25-53f84b974201", "08d94604-e5ac-f859-9ed7-f51fe87baa25", "08da9d6a-bc1f-d917-bb12-5c78e7b8bc0f"]
# Those ids are for testing incremental import, TODO: remove them
# LINDAS_testConcept: 0c4f39ae-8217-42ba-882f-2a0ca35129b2
EXCLUDED_IDS = ["0c4f39ae-8217-42ba-882f-2a0ca35129b2","08dbd475-4eb5-d54c-9877-a44b5598e96e", "08dbf0ae-69e8-4cb6-b660-983acf60cf62", "08dc23e1-34e0-de58-8181-b8736ba536a7", "08dc23db-ce0c-6a92-9716-4f1f482fc414", "08dc23de-ca54-4f1b-bd37-27fdf75391ea", "08dbdf8d-017b-c4e0-954d-3ee7307096d3"]
# If using specific concept IDs
CONCEPT_IDS = []#["08dd28d2-a693-5049-a3fe-0ee83005b61b"]

# Output file name
OUTPUT_FILE_NAME = "output.ttl"
DEBUG_INCLUDE_CODE_VERSIONS = True

LINDAS_QUERY_URL = os.environ.get("LINDAS_QUERY_URL", "https://test.lindas.admin.ch/query")
CLEAR_GRAPH = os.environ.get("CLEAR_GRAPH", "false") == "true"
TARGET_GRAPH = os.environ.get("TARGET_GRAPH", "https://lindas.admin.ch/fso/i14y")

# namespace for the URI construction
BASE_URI = "https://register.ld.admin.ch/i14y/concept/"

SKOLEM_IDENTITY_BASE_URI = BASE_URI + "{concept_identifier}/.well-known/genid/{hash}"
SKOLEM_VERSION_BASE_URI = BASE_URI + "{concept_identifier}/.well-known/genid/{hash}/version/{version}"

# Constants for API configuration
# API_TOKEN = "" # not necessary for prod and public concepts
BASE_API_URL = os.environ.get("BASE_API_URL", "https://api-a.i14y.admin.ch/api/public/v1/concepts/")

# namespace
SDO = Namespace("http://schema.org/")
CUBELINK = Namespace("https://cube.link/meta/")
XKOS = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")
SHACL = Namespace("http://www.w3.org/ns/shacl#")
QUDT = Namespace("https://qudt.org/schema/qudt/")
vl = Namespace("https://version.link/")
oa = Namespace("https://www.w3.org/ns/oa#")
dataCite = Namespace("https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/#")
ADMS = Namespace("https://www.w3.org/TR/vocab-adms/#adms_")
RDFA = Namespace("https://www.w3.org/ns/rdfa#")
PAV = Namespace("http://purl.org/pav/")
