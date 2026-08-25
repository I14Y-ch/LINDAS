# LINDAS i14y SPARQL examples

These examples query the i14y graph:

`https://lindas.admin.ch/fso/i14y`

Replace the values in the `VALUES` blocks before running a query.

## Retrieve one concept version subgraph

This returns only the RDF subgraph owned by the selected concept version. It includes the shared publisher as a leaf, but does not traverse the concept identity, other versions or external resources such as a dataset structure or another concept.

```sparql
PREFIX cube:   <https://cube.link/meta/>
PREFIX dct:    <http://purl.org/dc/terms/>
PREFIX oa:     <https://www.w3.org/ns/oa#>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <http://schema.org/>
PREFIX sh:     <http://www.w3.org/ns/shacl#>
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX vl:     <https://version.link/>
PREFIX xkos:   <http://rdf-vocabulary.ddialliance.org/xkos#>

CONSTRUCT { ?s ?p ?o }
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    VALUES (?identifier ?version) {
      ("legalForm" "1.2.0")
    }

    BIND(
      IRI(CONCAT(
        "https://register.ld.admin.ch/i14y/concept/",
        ?identifier,
        "/version/",
        ?version
      ))
      AS ?root
    )
    BIND(
      CONCAT("https://register.ld.admin.ch/i14y/concept/", ?identifier)
      AS ?conceptBase
    )

    {
      ?root (
        schema:hasPart|schema:hasDefinedTerm|schema:member|schema:isPartOf|
        schema:inDefinedTermSet|
        skos:member|skos:broader|skos:narrower|skos:topConceptOf|skos:inScheme|
        xkos:level|
        cube:inHierarchy|cube:hierarchyRoot|cube:nextInHierarchy|
        sh:property|
        dct:subject|dct:conformsTo|
        oa:hasBody|
        rdf:rest
      )* ?s .

      FILTER(
        isIRI(?s) &&
        STRSTARTS(STR(?s), ?conceptBase)
      )
    }
    UNION
    {
      # Include the shared publisher without traversing from it.
      ?root dct:publisher ?s .
      FILTER(
        isIRI(?s) &&
        STRSTARTS(STR(?s), "https://register.ld.admin.ch/i14y/agent/")
      )
    }

    ?s ?p ?o .
  }
}
```

## Retrieve a dataset subgraph by identifier

This returns the local dataset graph, including distributions, the optional structure and its locally owned nodes. It includes the shared publisher as a leaf and deliberately does not expand external references such as themes, concepts or download URLs.

```sparql
PREFIX dcat:   <http://www.w3.org/ns/dcat#>
PREFIX dct:    <http://purl.org/dc/terms/>
PREFIX foaf:   <http://xmlns.com/foaf/0.1/>
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <http://schema.org/>
PREFIX sh:     <http://www.w3.org/ns/shacl#>

CONSTRUCT { ?s ?p ?o }
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    VALUES ?identifier {
      "CH_KT_BL_dataset_12300"
    }

    BIND(
      IRI(CONCAT(
        "https://register.ld.admin.ch/i14y/dataset/",
        ?identifier
      ))
      AS ?dataset
    )

    {
      BIND(?dataset AS ?s)
    }
    UNION
    {
      # Start from local resources directly linked to the dataset.
      ?dataset ?rootPredicate ?start .
      FILTER(
        isIRI(?start) &&
        STRSTARTS(STR(?start), STR(?dataset))
      )

      # Traverse only the locally owned subgraph.
      ?start
        !(rdf:type|dct:publisher|dct:conformsTo|dcat:theme|
          dcat:accessRights|dcat:accessService|dcat:accessURL|
          dcat:downloadURL|dcat:landingPage|dct:relation|
          dct:isReferencedBy|foaf:page|schema:image|sh:path|
          sh:class|sh:datatype|owl:imports)* ?s .

      FILTER(
        isIRI(?s) &&
        STRSTARTS(STR(?s), STR(?dataset))
      )
    }
    UNION
    {
      # Include the shared publisher without traversing from it.
      ?dataset dct:publisher ?s .
      FILTER(
        isIRI(?s) &&
        STRSTARTS(STR(?s), "https://register.ld.admin.ch/i14y/agent/")
      )
    }

    ?s ?p ?o .
  }
}
```

## List all concept identities

```sparql
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?concept ?identifier
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?concept a schema:DefinedTermSet, vl:Identity ;
             schema:identifier ?identifier .
  }
}
ORDER BY ?identifier
```

## List all datasets

```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct:  <http://purl.org/dc/terms/>

SELECT ?dataset ?identifier
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?dataset a dcat:Dataset ;
             dct:identifier ?identifier .
  }
}
ORDER BY ?identifier
```

## List concept versions with a given registration status

For example to list all concept versions with status "Standard"

```sparql
PREFIX adms:   <http://www.w3.org/ns/adms#>
PREFIX pav:    <http://purl.org/pav/>
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?conceptVersion ?identifier ?version
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    VALUES ?status {
      "Standard"
    }

    ?conceptVersion a schema:DefinedTermSet, vl:Version ;
                    schema:identifier ?identifier ;
                    pav:version ?version ;
                    adms:status ?status .
  }
}
ORDER BY ?identifier ?version
```

The available i14y statuses are:

- `Qualified`
- `Standard`
- `PreferredStandard`
- `Retired`
- `Candidate`
- `Superseded`
- `Recorded`

## List the current NOGA codes

This uses the NOGA concept identity and therefore returns the current code identities.

```sparql
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?code ?codeIdentifier
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?concept a schema:DefinedTermSet, vl:Identity ;
             schema:identifier "nogaCode" ;
             schema:hasDefinedTerm ?code .

    ?code a schema:DefinedTerm, vl:Identity ;
          schema:identifier ?codeIdentifier .
  }
}
ORDER BY ?codeIdentifier
```

## List every exported version of one code

This query lists the representation of code `G` in every exported version of the `nogaCode` concept.

```sparql
PREFIX pav:    <http://purl.org/pav/>
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?conceptVersion ?conceptVersionNumber ?codeVersion
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?conceptVersion a schema:DefinedTermSet, vl:Version ;
                    schema:identifier "nogaCode" ;
                    pav:version ?conceptVersionNumber ;
                    schema:hasDefinedTerm ?codeVersion .

    ?codeVersion a schema:DefinedTerm, vl:Version ;
                 schema:identifier "G" .
  }
}
ORDER BY ?conceptVersionNumber
```

## Retrieve the current version of one code

The first query follows the current concept version. It returns no result when the code is no longer in the current CodeList.

```sparql
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?currentCodeVersion
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?conceptVersion a schema:DefinedTermSet, vl:Version ;
                    schema:identifier "nogaCode" ;
                    schema:hasDefinedTerm ?currentCodeVersion .

    ?currentCodeVersion a schema:DefinedTerm, vl:Version ;
                        schema:identifier "G" .

    FILTER NOT EXISTS {
      ?conceptVersion vl:successor ?newerConceptVersion .
    }
  }
}
```

The following equivalent lookup uses the current code identity and its direct `vl:Version` link:

```sparql
PREFIX schema: <http://schema.org/>
PREFIX vl:     <https://version.link/>

SELECT ?currentCodeVersion
WHERE {
  GRAPH <https://lindas.admin.ch/fso/i14y> {
    ?concept a schema:DefinedTermSet, vl:Identity ;
             schema:identifier "nogaCode" ;
             schema:hasDefinedTerm ?codeIdentity .

    ?codeIdentity a schema:DefinedTerm, vl:Identity ;
                  schema:identifier "G" ;
                  vl:Version ?currentCodeVersion .
  }
}
```
