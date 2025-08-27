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
  "08dc7ef4-e871-d36f-ade1-d11f8e073447",
  "08dd355a-db74-74f8-b36e-619e3614e364",
  "08dd3ec4-1417-9745-8b15-d386b0e448f9",
  "08dd347b-8c3b-64d9-96b7-42ad25adb8c2",
  "08dd5657-6a07-26e8-a0c5-ed3129c4727f",
  "08dca714-3c5e-6cb1-9f9c-1a1bd280af27",
  "08d9a901-e207-567d-a869-0aacd87842c2",
  "08da7ae1-d49c-9e96-8804-a22d083934c1",
  "08db76e7-2e85-81e1-a1d1-fa8c4c83befc",
  "08dc969f-a6e4-5628-add9-2d204a12276c",
  "08d97dad-a14e-c6a5-9f42-d7ad1df34dfc",
  "08dc5df4-c2c7-1f17-9774-6a0acae02a8c",
  "08dc5df8-5771-adb3-822e-5e7aef856710",
  "08dc5e0c-2399-d5d5-a41a-78c07f50d7ff",
  "08dc5def-7ce7-d1d8-b09c-e211172a5ac8",
  "08d97dc5-fb0e-7d8a-8d67-d2b236e017b1",
  "08dc5e14-3b6f-11c5-8307-afc5bb62d5b7",
  "08dd87e4-2729-7764-a0ce-758107bab20d",
  "08dd72b9-faa1-28e3-a7a8-fd3234a7ce9a",
  "08dca1a3-c2c7-14c5-b70e-3f784356c235",
  "08dc5ea5-c4ea-ef10-81db-d77b9d1d47b9",
  "08d9407c-8319-7542-848f-29f7c94368da",
  "08d9407c-88f5-81a3-9b49-5a0e52dcd7b3",
  "08db76ea-fb32-07de-b24a-a5ed4f4f375d",
  "08db76ea-fe40-252a-bdae-ff923897c0ca",
  "08db76ea-ff1e-eaae-b90e-9e9e931e4960",
  "08db76ea-fdb5-5c39-9897-530d11869ed2",
  "08d97de1-8fee-8bb5-b31d-dc08f36e84f6",
  "08db76eb-07b5-5822-ad05-304bb42ea7d2",
  "08db76eb-0734-1d8e-9750-c27d221f28c0",
  "08da39b0-0b59-6998-92c5-025dbc4aa744",
  "08d97e99-9267-f800-9cc4-8f9e9860f728",
  "08db358d-0e60-5412-9a53-e10ff2933aa0",
  "08dd2e3a-d99e-d56f-9c1c-5a7c5733f1a6",
  "08dcecf6-bc5a-ba99-9dc3-7fff9b8b3752",
  "08dc1121-4ee7-5439-8f9e-cb37db77c486",
  "08da5e98-50b3-dba1-bb9b-e48eeabaf216",
  "08da3a56-dc1a-d2da-8520-9d913cfafa3c",
  "08da3a59-0b66-e5e9-b59e-37788df1beff",
  "08da3a5a-beac-d73c-9483-021a7fc448bb",
  "08da3a59-f28a-26ef-9414-c8d78b5bb1ec",
  "08da58dc-4dc8-f9cb-b6f2-7d16b3fa0cde",
  "08d97e9a-6563-0f72-afe7-5015064bdd8b",
  "08da3a5b-424b-8670-9e9d-24729916e767",
  "08db76eb-06da-3458-8639-7c9ee7439106",
  "08db76eb-0636-4af6-9c79-f2abbec942eb",
  "08db76ea-f888-191e-9ab0-0fb5c32f90c3",
  "08db76ea-f939-b5dc-a7fd-a2e7edef7bfa",
  "08db76ea-f9df-ec08-9d7a-29e5a5222d43",
  "08db76eb-19b4-1ef1-8bed-455e077ec046",
  "08da3a5b-ed75-c5fa-a5f4-daeb750e41ca",
  "08da3c7b-da84-fa5f-992b-1b02fe06ecb6",
  "08d97e9c-4604-aebb-b81d-d2ade3ca67f5",
  "08da2469-30c0-08a4-9cec-0111ba31a20e",
  "08d97de2-3ad9-47ab-b379-eaa2566abba3",
  "08d97ea0-40aa-c153-a614-31c2362cd9e4",
  "08d97eaa-595c-b452-b483-c00c9732ea46",
  "08d97ea1-2bcf-effe-9851-1e82a7cce3bf",
  "08d97ea2-617d-3dc5-b876-5e466b5e6858",
  "08d97eab-99be-1402-8079-f4879ff60dc0",
  "08da3c7c-f914-206d-a433-5819a4911413",
  "08db76eb-1b4d-a6fe-82ac-0f6b1eb7f0c8",
  "08db76ea-fc6b-27a9-8430-16d4e8e9a756",
  "08db76ea-fb7e-03a5-af86-56f1dcd65a39",
  "08db0288-0e2c-bd20-82f9-0946e80c8bdd",
  "08dd2e54-00fb-efc5-b7cd-14f5c7d2272d",
  "08dc27c5-dcf1-8d73-9379-12b31beae206",
  "08da3c7e-2594-9e3d-88f9-df313b9f7d4b"
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























