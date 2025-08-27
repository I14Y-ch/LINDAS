from rdflib import Namespace

# Toggle between using statuses or concept_ids
USE_STATUSES = False # Set to False to use concept_ids

# If using statuses
# One of the following: Candidate, Recorded, Qualified, Standard, PreferredStandard, Superseded, Retired
STATUSES = ["Candidate"]

#Use this variable to esclude specific Ids: 
# 21.08.2025: I have removed NOGA single hierarchy concepts (NOGA Section, ...) they are duplicates of NOGA
# 21.08.2025: I have removed Isco Jobs related concept
# 22.08.2025: I have removed EprAgentRole codelist (08dd632d-aee2-333d-b1e4-505385fde8ff) because it gets an internal error 500 when retrieving codelist entries from I14Y
EXCLUDED_IDS = [ "08dd20cc-3ee5-c17a-8d8b-c1664c3421a6", "08dc74b4-30d4-be8d-ba53-91a1201ac86b", "08dceec4-b3f0-1285-b8d0-b005fabcf87c", "08d92cdc-c97d-acd7-9952-56dd375b0777", "08d92cdc-827b-5021-8242-f4166fb122b0", "08d92cdc-03c1-103f-8fec-a24aafeaedd3", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d92cdc-4e4a-5b21-9e0e-a50ffe3f4a16", "08d94603-f490-f094-9fe5-8012ca56d812", "08d94604-db03-1909-a097-569cb9836253", "08d94604-f12a-5d82-b6b4-fdc55b9b4750", "08d94604-e058-62a2-aa25-53f84b974201", "08d94604-e5ac-f859-9ed7-f51fe87baa25", "08da9d6a-bc1f-d917-bb12-5c78e7b8bc0f"] 

# If using specific concept IDs
CONCEPT_IDS = [
  "08dd632d-a98d-34ff-9252-123e46d6f053",
  "08dd632d-abd6-c1fd-9468-533a88e19499",
  "08dd632d-ac4d-977f-a53b-ec0b1af269f8",
  "08dd632d-aca1-b77d-80c2-3e6b677753f9",
  "08dd632d-ad55-7a02-b041-ae0059ba8d79",
  "08dd632d-adf6-96f1-9850-7ef00f059f80",
  "08dd632d-aa6b-ffb2-a78b-fbff93d4f167",
  "08dd632d-b449-6c4f-bff5-38488abd5b6f",
  "08dd632d-aada-98dd-bbc2-21ad33bd1565",
  "08dd632d-ab2e-9938-8e31-4fb07a28b4a3",
  "08dd632d-ab82-6614-a9a4-c9842737aa2f",
  "08dd632d-b23a-ec97-8812-886854f69afd",
  "08dd632d-b378-e759-84d8-f04d0168890c",
  "08dd632d-b2f7-197a-889f-18e7a917dd67",
  "08dd632d-b2a2-0ed2-941d-fffb2bea1af5",
  "08dd632d-b3c5-ed64-a995-369c44b38c06",
  "08dd632d-ada3-bda0-be32-f270bf291810",
  "08db65be-d31f-e3e7-b9fa-c642c099f4d1",
  "08dc0def-b1f8-220a-8737-6c46ce923cf5",
  "08db556b-0d39-b605-8d37-23276586388c",
  "08dd75a2-0404-ce6f-b6d8-b302a873a635",
  "08dd4b4d-a4eb-73e3-8062-bcf156c6cf35",
  "08dd50de-ea53-b497-8a45-39bd23beff61",
  "08dca65f-2d5e-9e75-8a13-48b8ecd20149",
  "08dd5635-7148-69a6-a6b9-b4602d4d33c5",
  "08dd50e5-da95-bba3-9ec9-f99d769eec6d",
  "08dcabe2-1734-ca16-9dfe-262056c9c124",
  "08dd50e7-1680-fbf8-afeb-aebe0b019720",
  "5df63d53-d916-4bc6-b486-1ec9d8e1c25d",
  "08dd5638-ec2c-32cd-a47b-949ae24a90bf",
  "08dd5633-e660-9405-93ec-f0493e991309",
  "08dc7ef4-e871-d36f-ade1-d11f8e073447"
]

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






















