from requests import Session
# Import the requirements modules
from requests import get, Session
from requests.auth import HTTPBasicAuth
import json
from rdflib import Graph
from requests import Session
from rdflib import URIRef, Literal, Namespace, BNode
from rdflib.namespace import FOAF, DCTERMS, XSD, RDF, DCAT, RDFS, SDO, PROV, OWL
from i14yToolbox.utils import set_staging_environment, get_json_response
CUBELINK = Namespace("https://cube.link/meta/")
XKOS = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")
SHACL = Namespace("http://www.w3.org/ns/shacl#")
QUDT = Namespace("https://qudt.org/schema/qudt/")
schema_org = Namespace("http://schema.org/")
SPDX = Namespace("http://spdx.org/rdf/terms/#")
DCATAP = Namespace("http://data.europa.eu/r5r/")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
CPSV = Namespace('https://semiceu.github.io/CPSV-AP/releases/3.2.0/#')
CV = Namespace('https://semiceu.github.io/CPSV-AP/releases/3.2.0/#')


#######################################
# Set environement and fetch data
#######################################

headers = {'Content-Type': 'application/json', 'Accept': 'application/+json', 'Accept-encoding': 'json'}


uri_ref = 'https://register.ld.admin.ch/i14y/'

url_publicServices= 'https://dcat.app.cfap02.atlantica.admin.ch/api/PublicService'
r = get(url=url_publicServices, headers=headers, verify=False)
print(r.status_code)
publicServices = r.json()

url_channels= 'https://dcat.app.cfap02.atlantica.admin.ch/api/Channel'
d = get(url=url_channels, headers=headers, verify=False)
channels = d.json()
print(d.status_code)



from rdflib import Graph
g = Graph()
g.bind("vcard", VCARD)
catalog = URIRef(uri_ref)
g.add((catalog, RDF.type, DCAT.Catalog))
###################################
# PUBLIC SERVICES
###################################
for r in publicServices:
    publicService = URIRef(uri_ref + 'catalog/publicService/' + r['identifier'][0])

    g.add((catalog,  CPSV.PublicService, publicService))
    
    g.add((publicService, RDF.type, CPSV.PublicService))

    # dcterms:description
    for x,y in r['description'].items():
        g.add((publicService, DCTERMS.description,  Literal(y,  lang=x) ))
    
    # dcterms:identifier
    g.add((publicService, DCTERMS.identifier,  Literal(r['identifier'][0]) )) #do we have to add other identifiers?
    g.add((catalog, schema_org.identifier, Literal(publicService['data']['identifier'])))
    
    # dct:publisher
    publisher = BNode()
    g.add((publicService,  DCTERMS.publisher, publisher))
    g.add((publisher, RDF.type,  FOAF.Agent ))
    
    for x,y in r['publisher']['name'].items():
        g.add((publisher, FOAF.name, Literal(y,  lang=x)))
    
    
    # dcterms:title
    for x,y in r['title'].items():
        g.add((publicService, DCTERMS.title,  Literal(y,  lang=x) ))

    # 	dct:spatial
    for l in r['spatial']:
        g.add((publicService, DCTERMS.spatial, Literal(l)))
        
    # 	dct:temporal
    temporal = BNode()
    g.add((publicService,  DCTERMS.temporal, temporal))
    g.add((temporal, RDF.type,  DCTERMS.PeriodOfTime ))
    try:
        g.add((temporal, XSD.startDate,   Literal(r['temporalCoverage'][0]['start'], datatype=XSD['date'])))
    except:
        print('start date missing')   
    try:
        g.add((temporal, XSD.endDate,   Literal(r['temporalCoverage'][0]['end'], datatype=XSD['date'])))
    except:
        print('end date missing')
      
    # dcat:theme
    for l in r['theme']:
      for x,y in l['name'].items():
        g.add((publicService, CV.thematicArea,  Literal(y,  lang=x) ))   
    
    # dct:language
    for l in r['language']:
        g.add((publicService, DCTERMS.language, Literal(l)))

    for l in r['benötig']:
        g.add((publicService, DCTERMS.requires, Literal(l)))
    

    #Keywords      
    if publicService['data']['keywords']:
        for keyword_dict in publicService['data']['keywords']:
            for lang, word in keyword_dict.items():
                g.add((catalog, DCAT.keywords, Literal(word, lang=lang)))


    #cv has competent authotity

    #cv sector

    #cv realtedService

    #cv is Described at

   # g.add((catalog, OWL.sameAs, URIRef(i14y_concept_url)))
###################################
# Channels
###################################


for r in channels: 
    channel = URIRef(uri_ref + 'catalog/channel/' + r['identifier'][0])
    g.add((catalog,  CPSV.Channel, publicService))
    
    g.add((publicService, RDF.type, CPSV.Channel))

    # dcterms:description
    for x,y in r['description'].items():
        g.add((channel, DCTERMS.description,  Literal(y,  lang=x) ))
    
    # dcterms:identifier
    g.add((channel, DCTERMS.identifier,  Literal(r['identifier'][0]) )) #do we have to add other identifiers?
    g.add((catalog, schema_org.identifier, Literal(channel['data']['identifier'])))
 
    
    # dcterms:title
    for x,y in r['title'].items():
        g.add((channel, DCTERMS.title,  Literal(y,  lang=x) ))


    #dct type
    for x,y in r['type'].items():
        g.add((channel, DCTERMS.type,  Literal(y,  lang=x) ))


    #cv owened by
    owner = BNode()
    g.add((publicService,  CV.ownedby, owner))
    g.add((owner, RDF.type,  FOAF.Agent ))
    
    for x,y in r['publisher']['name'].items():
        g.add((owner, FOAF.name, Literal(y,  lang=x)))

    #g.add((catalog, OWL.sameAs, URIRef(i14y_concept_url)))
###################################
