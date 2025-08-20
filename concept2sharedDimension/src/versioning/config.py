from rdflib import Namespace

# Toggle between using statuses or concept_ids
USE_STATUSES = False  # Set to False to use concept_ids

# If using statuses
STATUSES = ['Standard', 'Qualified', 'PreferredStandard']

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


