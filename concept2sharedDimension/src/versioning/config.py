from rdflib import Namespace

# Toggle between using statuses or concept_ids
USE_STATUSES = True  # Set to False to use concept_ids

# If using statuses
# One of the following: Incomplete, Candidate, Recorded, Qualified, Standard, PreferredStandard, Superseded, Retired
STATUSES = ["Recorded"]

#Use this variable to esclude specific Ids: 
# 21.08.2025: I have removed NOGA single hierarchy concepts (NOGA Section, ...) they are duplicates of NOGA
# 21.08.2025: I have removed Isco Jobs related concept
# 22.08.2025: I have removed EprAgentRole codelist (08dd632d-aee2-333d-b1e4-505385fde8ff) because it gets an internal error 500 when retrieving codelist entries from I14Y
EXCLUDED_IDS = [ "08dd20cc-3ee5-c17a-8d8b-c1664c3421a6", "08dc74b4-30d4-be8d-ba53-91a1201ac86b", "08dceec4-b3f0-1285-b8d0-b005fabcf87c", "08d92cdc-c97d-acd7-9952-56dd375b0777", "08d92cdc-827b-5021-8242-f4166fb122b0", "08d92cdc-03c1-103f-8fec-a24aafeaedd3", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d94603-f490-f094-9fe5-8012ca56d812", "08d94604-db03-1909-a097-569cb9836253", "08d94604-f12a-5d82-b6b4-fdc55b9b4750", "08d94604-e058-62a2-aa25-53f84b974201", "08d94604-e5ac-f859-9ed7-f51fe87baa25", "08da9d6a-bc1f-d917-bb12-5c78e7b8bc0f"] 

# If using specific concept IDs
CONCEPT_IDS = ['08dd28d2-a693-5049-a3fe-0ee83005b61b']

# Output file name
OUTPUT_FILE_NAME = "output.ttl"


# namespace for the URI construction
BASE_URI = "https://register.ld.admin.ch/i14y/"

# Constants for API configuration 
#API_TOKEN = "" # not necessary for prod and public concepts
BASE_API_URL = "https://api.i14y.admin.ch/api/public/v1/concepts/"
VERSION_API_URL = "https://dcat.app.cfap02.atlantica.admin.ch/api/Concepts/"

# namespace
SDO = Namespace("http://schema.org/")
CUBELINK = Namespace("https://cube.link/meta/")
XKOS = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")
SHACL = Namespace("http://www.w3.org/ns/shacl#")
QUDT = Namespace("https://qudt.org/schema/qudt/")
vl = Namespace("https://version.link/#")
oa = Namespace("https://www.w3.org/ns/oa#")
dataCite = Namespace("https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/#")
ADMS = Namespace("https://www.w3.org/TR/vocab-adms/#adms_")
RDFA = Namespace("https://www.w3.org/ns/rdfa#")
PAV = Namespace("http://purl.org/pav/")


















