# -*- coding: utf-8 -*-
"""
Created on Tue Apr 25 09:24:13 2023

@author: U80827488
"""
# vgl: https://github.com/ckan/ckanext-dcat/blob/c285382e0c893a2dea7005729156f8bd3348ec54/examples/dataset.rdf
# https://dcat-ap.ch/releases/2.0/dcat-ap-ch.html#dataset-publisher
# https://ckan.opendata.swiss/catalog.ttl
# https://www.govdata.de/web/guest/metadatenschema

# Import the requirements modules
from rdflib import URIRef, BNode, Literal, Namespace
from rdflib.namespace import FOAF, DCTERMS, XSD, RDF, DCAT
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

from requests import get
import datetime;

# Voreinstellungen
dataset_identifier='DWELLING_MASTER_DATA'
headers = {'Content-Type': 'application/json', 'Accept': 'application/+json', 'Accept-encoding': 'json'}


ct = datetime.datetime.now()
print("current time:-", ct)


# Abrufen der Metadaten
url = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataset/identifier/' + dataset_identifier
r = get(url=url, headers=headers, verify=False)
r = r.json()

url_distribution = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Dataset/identifier/' + dataset_identifier + '/distributions'
d = get(url=url_distribution, headers=headers, verify=False)
d = d.json()
print(d.status_code)


dataset = URIRef('https://www.i14y.admin.ch/de/catalog/datasets/' + dataset_identifier)


from rdflib import Graph
g = Graph()

g.bind("vcard", VCARD)
g.add((dataset, RDF.type, DCAT.Dataset))

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
g.add((dataset, DCTERMS.identifier,  Literal(r['identifier'][0]) ))

# dct:publisher
publisher = BNode()
g.add((dataset,  DCTERMS.publisher, publisher))
g.add((publisher, RDF.type,  FOAF.Organization ))

for x,y in r['publisher']['name'].items():
    g.add((publisher, FOAF.name, Literal(y,  lang=x)))


# dcterms:title
for x,y in r['title'].items():
    g.add((dataset, DCTERMS.title,  Literal(y,  lang=x) ))
    
    
# dcat:distribution  # not completely implemented yet
for l in d:
    distribution = URIRef('https://www.i14y.admin.ch/de/catalog/datasets/' + dataset_identifier + '/distributions/' + l['id'])
    g.add((dataset,  DCAT.distribution, distribution)) 
    g.add((distribution, RDF.type,  DCAT.Distribution ))
    
    # dcat:accessURL
    g.add((distribution, DCAT.accessURL,  Literal(l['accessUrl'][0]['href'], datatype=XSD['anyURI'] ) ))
    
    # dct:license
if 'license' in r:
    for x, y in r['license'].items():
        g.add((dataset, DCTERMS.license, Literal(y, lang=x)))

    
   # dcatap:availability at distribution level (replace with actual key if different)
if 'availability' in l:
    g.add((distribution, DCTERMS.availability, Literal(l['availability'])))

    
    # dct:description
    for x,y in l['description'].items():
        g.add((distribution,  DCTERMS.description, Literal(y,  lang=x)))
    
    # dct:format
    g.add((distribution, DCTERMS.format,  Literal(l['format']['code'] ) ))
    
    # dct:rights
    if l['rights']:
        g.add((distribution, DCTERMS.rights,  Literal(l['rights'] ) ))
    
    # dct:title
    for x,y in l['title'].items():
        g.add((distribution,  DCTERMS.title, Literal(y,  lang=x)))  

    # dct:modified
    try:
        g.add((distribution, DCTERMS.modified,   Literal(d['modified'], datatype=XSD['datetime'])))
    except:
        print('modification date missing')
        
    # dcat:accessService HIER NOCH ACCESSSERVICE BESCHREIBEN WIE: https://www.w3.org/TR/vocab-dcat-3/#examples-data-service
    url_accessService = 'https://dcat.app.cfap02.atlantica.admin.ch/api/Distribution/' + l['id'] + '/accessServices'
    a = get(url=url_accessService, headers=headers, verify=False)
    try: 
        a = a.json()
        for b in a:
            url_dataservice= 'https://www.i14y.admin.ch/de/catalog/dataservices/' + str(b['id'])
            g.add((distribution, DCAT.accessService,  Literal(url_dataservice, datatype=XSD['anyURI'] ) ))
    except: 
        print('no access service')
    
    # dcat:byteSize
    try:
        g.add((distribution, DCAT.byteSize,  Literal(l['byteSize'] ) ))
    except:
        print('no byteSitze')
  
    # spdx:Checksum at distribution level
if 'checksum' in l:
    g.add((distribution, URIRef("https://spdx.org/rdf/terms#Checksum"), Literal(l['checksum'])))

    
    # dct:coverage (for spatial or thematic coverage)
if 'coverage' in r:
    g.add((dataset, DCTERMS.coverage, Literal(r['coverage'])))

    
    # Documentation 	foaf:page
    for m in l['documentation']:
        try:
            g.add((distribution, FOAF.page, Literal(m['href'], datatype=XSD['anyURI'])  ))
        except:
            print('no documentation')
    
    # dcat:downloadURL
    try:
        g.add((distribution, DCAT.downloadURL,  Literal(l['downloadUrl'][0]['href'], datatype=XSD['anyURI'] ) ))
    except:
        print('no downloadUrl')
        
    # dct:identifier for each distribution
    g.add((distribution, DCTERMS.identifier, Literal(l['id'])))

    
    # schema:image
    # not implemented yet
    
    # dct:language
    for m in l['language']:
        g.add((distribution, DCTERMS.language, Literal(m)  ))
    
    # linked schemas dct:conformsTo
    for m in l['conformsTo']:
        try:
            g.add((distribution, DCTERMS.conformsTo, Literal(m['href'] )))
        except:
            print('no linked schemas')
            
    # dcat:mediaType
if 'mediaType' in l:
    g.add((distribution, DCAT.mediaType, Literal(l['mediaType'])))

    
    # dcat:packageFormat
if 'packageFormat' in l:
    g.add((distribution, URIRef("http://www.w3.org/ns/dcat#packageFormat"), Literal(l['packageFormat'])))

    
    # release date 	dct:issued
    g.add((distribution, DCTERMS.issued,   Literal(l['releaseDate'], datatype=XSD['date'])))
    
    # dcat:temporalResolution (replace 'temporalResolution' with the correct key)
if 'temporalResolution' in l:
    g.add((distribution, DCAT.temporalResolution, Literal(l['temporalResolution'])))

    
    
    
# not completely implemented yet


# 	dcat:keyword
for l in r['keyword']:
  for x,y in l.items():
    g.add((dataset, DCAT.keyword,  Literal(y,  lang=x) ))
      
# 	dcat:landingPage
g.add((dataset, DCAT.landingPage,  Literal(r['landingPage'][0]['href'], datatype=XSD['anyURI'] )  ))

# 	dct:issued
g.add((dataset, DCTERMS.issued,   Literal(r['issued'], datatype=XSD['date'])))


# dct:spatial
spatial = BNode()
g.add((dataset, DCTERMS.spatial, spatial))
g.add((spatial, RDF.type, DCTERMS.Location))
g.add((spatial, DCTERMS.name, Literal(r['spatial']['name'])))


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
    g.add((dataset, DCTERMS.conformsTo, Literal(l['href'] )))
    
# documentation
for l in r['documentation']:
    g.add((dataset, FOAF.page, Literal(l['href'])  ))

# Property: frequency, 	dct:accrualPeriodicity
# not implemented yet

# image
# not implemented yet

# is referenced by
# not implemented yet

# dct:language
for l in r['language']:
    g.add((dataset, DCTERMS.language, Literal(l)  ))

# qualified attribution
# not implemented yet

# qualified relation
# not implemented yet

# related resource
# not implemented yet

#################### hier weiter ###############



# print(g.serialize(format='json-ld'))
# print(g.serialize(format='ttl'))
print(g.serialize(format='pretty-xml'))

myfile = open(dataset_identifier+".rdf", "w",  encoding='utf-8')
myfile.write(g.serialize(format='pretty-xml'))
myfile.close()


myfile = open(dataset_identifier+".ttl", "w",  encoding='utf-8')
myfile.write(g.serialize(format='ttl'))
myfile.close()