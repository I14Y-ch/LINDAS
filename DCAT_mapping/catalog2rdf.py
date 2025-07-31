# -*- coding: utf-8 -*-
"""
Created on Wed May  3 08:02:09 2023

@author: U80827488
"""

# vgl: https://github.com/ckan/ckanext-dcat/blob/c285382e0c893a2dea7005729156f8bd3348ec54/examples/dataset.rdf
# https://dcat-ap.ch/releases/2.0/dcat-ap-ch.html#dataset-publisher
# https://ckan.opendata.swiss/catalog.ttl
# https://www.govdata.de/web/guest/metadatenschema
# https://test.lindas.admin.ch/sparql/#

# Import the requirements modules
from rdflib import URIRef, BNode, Literal, Namespace
from rdflib.namespace import FOAF, DCTERMS, XSD, RDF, DCAT, RDFS, SDO, PROV
import urllib3
from requests import Session
from requests.auth import HTTPBasicAuth
from requests import get
import datetime;

SPDX = Namespace("http://spdx.org/rdf/terms/#")
DCATAP = Namespace("http://data.europa.eu/r5r/")
schema_org = Namespace("http://schema.org/")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


#######################################
# Set environement and fetch data
#######################################

# Voreinstellungen
headers = {'Content-Type': 'application/json', 'Accept': 'application/+json', 'Accept-encoding': 'json'}


ct = datetime.datetime.now()
print("current time:-", ct)


uri_ref = 'https://register.ld.admin.ch/i14y/'

# Abrufen der Metadaten


url_dataset = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataset'
r = get(url=url_dataset, headers=headers, verify=False)
print(r.status_code)
datasets = r.json()

url_distribution = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Distribution'
d = get(url=url_distribution, headers=headers, verify=False)
distributions = d.json()
print(d.status_code)

url_Dataservice = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataservice'
d = get(url=url_Dataservice, headers=headers, verify=False)
Dataservices = d.json()
print(d.status_code)




from rdflib import Graph
g = Graph()
g.bind("vcard", VCARD)
catalog = URIRef(uri_ref)
g.add((catalog, RDF.type, DCAT.Catalog))


###################################
# DATASETS
###################################

for r in datasets:
    

# <https://register.ld.admin.ch/i14y/catalog/i14ycontentlist> <http://www.w3.org/ns/dcat#Dataset>  <https://nummer1DeinerListeVonDatensets>,<https://nummer2DeinerListeVonDatensets> , ...... , <https://nummernDeinerListeVonDatensets>. 
 

    
    dataset = URIRef(uri_ref + 'catalog/datasets/' + r['identifier'][0])

    g.add((catalog,  DCAT.Dataset, dataset))
    
    g.add((dataset, RDF.type, DCAT.Dataset))
    g.add((dataset, RDF.type, SDO.Dataset))

    
    # dcat:contactPoint # not completely implemented yet
    contact_details = BNode()
    g.add((dataset,  DCAT.contactPoint, contact_details))
    g.add((contact_details, RDF.type,  VCARD.Organization ))
    
    for x,y in r['contactPoint'][0]['fn'].items():
        g.add((contact_details, VCARD.fn, Literal(y,  lang=x)))
        
    for x,y in r['contactPoint'][0]['adrWork'].items():
        g.add((contact_details, VCARD.adr, Literal(y,  lang=x)))
    
    for x,y in r['contactPoint'][0]['note'].items():
        g.add((contact_details, VCARD.note, Literal(y,  lang=x)))
        
    for x,y in r['contactPoint'][0]['org'].items():
        g.add((contact_details, VCARD.org, Literal(y,  lang=x)))
    
    g.add((contact_details, VCARD.hasEmail, Literal(r['contactPoint'][0]['emailInternet'])))
    
    g.add((contact_details, VCARD.hasTelephone, Literal(r['contactPoint'][0]['telWorkVoice'])))
    
    # not completely implemented yet
    
    
    # dcterms:description
    for x,y in r['description'].items():
        g.add((dataset, DCTERMS.description,  Literal(y,  lang=x) ))
    
    # dcterms:identifier
    g.add((dataset, DCTERMS.identifier,  Literal(r['identifier'][0]) )) #do we have to add other identifiers?
    
    # dct:publisher
    publisher = BNode()
    g.add((dataset,  DCTERMS.publisher, publisher))
    g.add((publisher, RDF.type,  FOAF.Agent ))
    
    for x,y in r['publisher']['name'].items():
        g.add((publisher, FOAF.name, Literal(y,  lang=x)))
    
    
    # dcterms:title
    for x,y in r['title'].items():
        g.add((dataset, DCTERMS.title,  Literal(y,  lang=x) ))
        
    
        
    url_distribution = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataset/identifier/' + r['identifier'][0] + '/distributions'
    d = get(url=url_distribution, headers=headers, verify=False)
    d = d.json()   
    
    for l in d:
        distribution = URIRef(uri_ref + 'catalog/datasets/' + r['identifier'][0] + '/distributions/' + l['id'])
        g.add((dataset,  DCAT.distribution, distribution)) 
        g.add((distribution, RDF.type,  DCAT.Distribution ))
        
        
        
    
    
    # 	dcat:keyword
    for l in r['keyword']:
      for x,y in l.items():
        g.add((dataset, DCAT.keyword,  Literal(y,  lang=x) ))
          
    # 	dcat:landingPage
    try:
        landingPage=URIRef(r['landingPage'][0]['href'])
        g.add((dataset, DCAT.landingPage,  landingPage  ))
        g.add((landingPage, RDF.type,  FOAF.Document ))
        
        # g.add((dataset, DCAT.landingPage,  Literal(r['landingPage'][0]['href'], datatype=XSD['anyURI'] )  ))
    except:
        print('landingPage missing') 
    
    # 	dct:issued
    try:
        g.add((dataset, DCTERMS.issued,   Literal(r['issued'], datatype=XSD['date'])))
    except:
        print('issued missing') 
    
    # 	dct:spatial
    for l in r['spatial']:
        g.add((dataset, DCTERMS.spatial, Literal(l)))
        
    
    # 	dct:temporal
    temporal = BNode()
    g.add((dataset,  DCTERMS.temporal, temporal))
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
        g.add((dataset, DCAT.theme,  Literal(y,  lang=x) ))   
    
    # 	dct:modified
    try:
        g.add((dataset, DCTERMS.modified,   Literal(r['modified'], datatype=XSD['datetime'])))
    except:
        print('modification date missing')
    
    # dct:accessRights
    for  x,y in r['accessRights']['name'].items():
        g.add((dataset, DCAT.accessRights,  Literal(y,  lang=x) ))   
    
    # 	dct:conformsTo
    for l in r['conformsTo']:
        conformsTo = URIRef(l['href'].strip())
        g.add((dataset, DCTERMS.conformsTo, conformsTo))
        g.add((conformsTo, RDF.type, DCTERMS.Standard))
        
        
    # documentation
    for l in r['documentation']:
        documentation = URIRef(l['href'].strip())
        g.add((dataset, FOAF.page, documentation  ))
        g.add((documentation, RDF.type, FOAF.Document))
    
    # Property: frequency, 	dct:accrualPeriodicity
    ######################### not implemented yet
    for l in r['frequency']:
        frequency = URIRef(l['href'].strip())
        g.add((dataset, DCTERMS.accrualPeriodicity, frequency))
        g.add((frequency, RDF.type, DCTERMS.accrualPeriodicity))
    
    # image
    for l in r['image']:
        image = URIRef(l['href'].strip())
        g.add((dataset, schema_org.image, image))
        g.add((image, RDF.type, schema_org.url))
    
    # is referenced by
    for l in r['isReferencedBy']:
        isReferencedBy = URIRef(l['href'].strip())
        g.add((dataset, DCTERMS.isReferencedBy, isReferencedBy))
        g.add((isReferencedBy, RDF.type, RDFS.Resource))
    
    # dct:language
    for l in r['language']:
        g.add((dataset, DCTERMS.language, Literal(l)))
    
    # qualified attribution
    for l in r['qualifiedAttribution']:
        qualifiedAttribution = URIRef(l['href'].strip())
        g.add((dataset, PROV.qualifiedAttribution, qualifiedAttribution))
        g.add((qualifiedAttribution, RDF.type, PROV.Attribution))
    
    # qualified relation
    qualified_relation = BNode()
    g.add((dataset,  DCAT.qualifiedRelation, qualified_relation))
    g.add((qualified_relation, RDF.type,  DCAT.Relationship ))
    g.add((qualified_relation, DCTERMS.relation,  URIRef('https://www.i14y.admin.ch/' + 'catalog/datasets/' + r['identifier'][0] )))
    g.add((qualified_relation, DCAT.hadRole,  URIRef('https://schema.org/sameAs' )))
    
    # related resource
    for l in r['relation']:
        relation = URIRef(l['href'].strip())
        g.add((dataset, DCTERMS.relation, relation))
        g.add((relation, RDF.type, RDFS.Resource))
    
###################################
# DATASERVICES
###################################
q=0
for r in Dataservices:
    print('Dataservice ' + str(q) )
    q=q+1
    
    Dataservice = URIRef(uri_ref + 'catalog/Dataservices/' + r['id'])

    g.add((catalog,  DCAT.Dataservice, Dataservice))
    g.add((Dataservice, RDF.type, DCAT.Dataservice))

    # dcat:endpointURL
    for l in r['endpointUrl']:
        endpointUrl = URIRef(l['href'].strip())
        g.add((Dataservice, DCAT.endpointURL, endpointUrl ))
        g.add((endpointUrl, RDF.type, RDFS.Resource))
        
           


    # dcat:contactPoint # not completely implemented yet
    contact_details = BNode()
    g.add((Dataservice,  DCAT.contactPoint, contact_details))
    g.add((contact_details, RDF.type,  VCARD.Organization ))
    
    for x,y in r['contactPoint'][0]['fn'].items():
        g.add((contact_details, VCARD.fn, Literal(y,  lang=x)))
        
    for x,y in r['contactPoint'][0]['adrWork'].items():
        g.add((contact_details, VCARD.adr, Literal(y,  lang=x)))
    
    for x,y in r['contactPoint'][0]['note'].items():
        g.add((contact_details, VCARD.note, Literal(y,  lang=x)))
        
    for x,y in r['contactPoint'][0]['org'].items():
        g.add((contact_details, VCARD.org, Literal(y,  lang=x)))
    
    g.add((contact_details, VCARD.hasEmail, Literal(r['contactPoint'][0]['emailInternet'])))
    
    g.add((contact_details, VCARD.hasTelephone, Literal(r['contactPoint'][0]['telWorkVoice'])))
    
    # dct:publisher
    publisher = BNode()
    g.add((Dataservice,  DCTERMS.publisher, publisher))
    g.add((publisher, RDF.type,  FOAF.Organization ))
    
    
    for x,y in r['publisher']['name'].items():
        g.add((publisher, FOAF.name, Literal(y,  lang=x)))
        
    
    # dcterms:title
    for x,y in r['title'].items():
        g.add((Dataservice, DCTERMS.title,  Literal(y,  lang=x) ))
        
        
    # dcterms:description
    for x,y in r['description'].items():
        g.add((Dataservice, DCTERMS.description,  Literal(y,  lang=x) )) 
        
    
        
    # dcat:endpointDescription
    for l in r['endpointDescription']:
        g.add((Dataservice, DCAT.endpointDescription, Literal(l['href'])  ))
        
        
    # dct:license
    for l in r['license']:
        license = URIRef(l['href'].strip())
        g.add((Dataservice, DCTERMS.license, license))
        g.add((license, RDF.type, DCTERMS.LicenseDocument))
    
    # dcat:servesDataset
    url_servesDataset = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataservice/' + r['id'] +'/servesDatasets'
    d = get(url=url_servesDataset, headers=headers, verify=False)
    if d.status_code<400:
        d = d.json()     
        for l in d:
            servesDataset = URIRef(uri_ref + 'catalog/datasets/' + l['identifier'][0])
            g.add((Dataservice,  DCAT.servesDataset, servesDataset))
            g.add((servesDataset, RDF.type,  DCAT.Dataset ))
        
    
    # dct:accessRights
    for  x,y in r['accessRights']['name'].items():
        accessRights = Literal(y,  lang=x)
        g.add((Dataservice, DCAT.accessRights,  accessRights ))   
    
    # documentation
    for l in r['documentation']:
        g.add((Dataservice, FOAF.page, Literal(l['href'])  ))
        
        
    # dcat:keyword    
    for l in r['keyword']:
      for x,y in l.items():
        g.add((Dataservice, DCAT.keyword,  Literal(y,  lang=x) ))
    
        
    # dcat:landingPage    
    try:
        # g.add((Dataservice, DCAT.landingPage,  Literal(r['landingPage'][0]['href'], datatype=XSD['anyURI'] )  ))
        landingPage=URIRef(r['landingPage'][0]['href'])
        g.add((Dataservice, DCAT.landingPage,  landingPage  ))
        g.add((landingPage, RDF.type,  FOAF.Document ))
    except:
        print('landingPage missing') 
        
    # qualified relation
    qualified_relation = BNode()
    g.add((Dataservice,  DCAT.qualifiedRelation, qualified_relation))
    g.add((qualified_relation, RDF.type,  DCAT.Relationship ))
    g.add((qualified_relation, DCTERMS.relation,  URIRef('https://www.i14y.admin.ch/' + 'catalog/Dataservices/' + r['id'] )))
    g.add((qualified_relation, DCAT.hadRole,  URIRef('https://schema.org/sameAs') ))


###################################
# DISTRIBUTION
###################################

# dcat:distribution  # not completely implemented yet


for l in distributions:
    distribution = URIRef(uri_ref + 'catalog/datasets/' + l['datasetIdentifier'][0] + '/distributions/' + l['id'])
    g.add((distribution, RDF.type,  DCAT.Distribution ))
    
    # dcat:accessURL
    accessURL= URIRef(l['accessUrl'][0]['href'].strip())
    g.add((distribution, DCAT.accessURL,  accessURL ))
    g.add((accessURL, RDF.type,  RDFS.Resource ))

    # dct:license
    if 'license' in l:
        license = URIRef(l['license']['uri'].strip())
        g.add((distribution, DCTERMS.license, license))
        g.add((license, RDF.type, DCTERMS.LicenseDocument))
    
    # dcatap:availability
    for x,y in l['availability'].items():
        g.add((distribution,  DCATAP.availability, Literal(y,  lang=x)))

    # dcatap:availability
    if 'availabilityVocabulary' in l:
        for x, y in l['availabilityVocabulary']['name'].items():
            g.add((distribution, DCATAP.availability, Literal(y, lang=x)))

    
    # dct:description
    for x,y in l['description'].items():
        g.add((distribution,  DCTERMS.description, Literal(y,  lang=x)))
    
    # dct:format
    g.add((distribution, DCTERMS.format,  Literal(l['format']['code'] ) ))
    
    # dct:rights
    if 'rights' in l:
     g.add((distribution, DCTERMS.rights,  Literal(l['rights']['code'] ) ))
    
    # dct:title
    for x,y in l['title'].items():
        g.add((distribution,  DCTERMS.title, Literal(y,  lang=x)))  

    # dct:modified
    if 'modified' in l:
        g.add((distribution, DCTERMS.modified, Literal(l['modified'], datatype=XSD.dateTime)))

    # release date 	dct:issued
    if 'releaseDate' in l:
        g.add((distribution, DCTERMS.issued, Literal(l['releaseDate'], datatype=XSD.dateTime)))

        
    # dcat:accessService HIER NOCH ACCESSSERVICE BESCHREIBEN WIE: https://www.w3.org/TR/vocab-dcat-3/#examples-data-service
    url_accessService = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Distribution/' + l['id'] + '/accessServices'
    a = get(url=url_accessService, headers=headers, verify=False)
    try: 
        a = a.json()
        for b in a:
            Dataservice= URIRef(uri_ref + 'catalog/Dataservices/' + str(b['id']))
            g.add((distribution, DCAT.accessService,  Dataservice ))
            g.add((Dataservice, RDF.type,  DCAT.Dataservice ))  #mettere oppure no? 
    except: 
        print('no access service')
    
    # dcat:byteSize
    try:
        g.add((distribution, DCAT.byteSize,  Literal(l['byteSize'], datatype=XSD.integer) ))
    except:
        print('no byteSitze')
      
    # spdx:Checksum
    if 'checksum' in l:
        g.add((distribution, SPDX.checksumValue, Literal(l['checksum']['checksumValue'])))
        algorithm_URL = URIRef(l['checksum']['algorithm']['uri'].strip())
        g.add((distribution, SPDX.ChecksumAlgorithm, algorithm_URL))

    
    # dct:coverage
    # let see after today how to implement it 
    if 'coverage' in l: 
        coverage_location = URIRef(l['coverage']['location'].strip())
        g.add((distribution, DCTERMS.coverage.Location, coverage_location)) # URI taken from GEONames.org or MDR
        g.add(distribution, DCTERMS.coverage.PeriodOfTime, Literal(l['coverage']['PeriodOfTime'], datatype=XSD.dateTime)) # dct: Start Date
        g.add(distribution, DCTERMS.coverage.PeriodOfTime, Literal(l['coverage']['PeriodOfTime'], datatype=XSD.dateTime)) # dct: end Date
    
    # Documentation 	foaf:page
    for m in l['documentation']:
        try:
            documentation = URIRef(m['href'].strip())
            g.add((distribution, FOAF.page, documentation  ))
            g.add((documentation, RDF.type,  FOAF.Document ))
        except:
            print('no documentation')
    
    # dcat:downloadURL
    try:
        downloadURL = URIRef(l['downloadUrl'][0]['href'].strip())
        g.add((distribution, DCAT.downloadURL, downloadURL))
        g.add((downloadURL, RDF.type, RDFS.Resource))
    except:
        print('no downloadUrl')
        
    # dct:identifier
    if 'identifier' in l: 
        g.add((distribution, DCTERMS.identifier, Literal(l['identifier'])))
    
    # schema:image
    for l in r['image']:
        image = URIRef(l['href'].strip())
        g.add((distribution, schema_org.image, image))
        g.add((image, RDF.type, schema_org.url))
    
    # dct:language
    for m in l['language']:
        g.add((distribution, DCTERMS.language, Literal(m)))
    
    # linked schemas dct:conformsTo
    for m in l['conformsTo']:
        try:
            conformsTo= URIRef(m['href'].strip() )
            g.add((distribution, DCTERMS.conformsTo, conformsTo))
            g.add((conformsTo, RDF.type, DCTERMS.Standard ))
        except:
            print('no linked schemas')

        # dcat:mediaType
    if 'mediaType' in l:
        g.add((distribution, DCAT.mediaType, Literal(l['mediaType']['code'])))

    # packaging format dcat:packageFormat
    if 'packagingFormat' in l:
        g.add((distribution, DCAT.packageFormat, Literal(l['packagingFormat']['code'])))
    
    # dcat:temporalResolution
    if 'temporalResolution' in l:
     g.add((distribution, DCTERMS.temporalResolution, Literal(l['temporalResolution'])))
    
###################################
# Write to file
###################################

# print(g.serialize(format='json-ld'))
# print(g.serialize(format='ttl'))
# print(g.serialize(format='pretty-xml'))

myfile = open('C:/Users/U80877014/Documents/LINDAS/catalog'+".rdf", "w",  encoding='utf-8')
myfile.write(g.serialize(format='pretty-xml'))
myfile.close()


myfile = open('C:/Users/U80877014/Documents/LINDAS/catalog'+".ttl", "w",  encoding='utf-8')
myfile.write(g.serialize(format='ttl'))
myfile.close()


