from rdflib import URIRef, Literal, Namespace, BNode, Graph
from rdflib.namespace import DCTERMS, XSD, RDF, SKOS, OWL, DCTERMS, PROV, FOAF, VOID
from .utils import is_valid_value
from .config import *


class GraphManager:
    def __init__(self, base_uri):
        self.base_uri = base_uri
        self.graph = Graph(bind_namespaces= "none")
        self._bind_namespaces()
        
    def _bind_namespaces(self):
        """Bind all required namespaces to the graph"""
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", Namespace("http://www.w3.org/2000/01/rdf-schema#"))
        self.graph.bind("rdfa", Namespace("https://www.w3.org/ns/rdfa#"))
        self.graph.bind("pav", PAV)
        self.graph.bind("xsd", XSD)
        self.graph.bind("skos", SKOS)
        self.graph.bind("owl", OWL)
        self.graph.bind("dcterms", DCTERMS)
        self.graph.bind("prov", PROV)
        self.graph.bind("meta", CUBELINK)
        self.graph.bind("xkos", XKOS)
        self.graph.bind("sh", SHACL)
        self.graph.bind("qudt", QUDT)
        self.graph.bind("vl", vl)
        self.graph.bind("oa", oa)
        self.graph.bind("datacite", dataCite)
        self.graph.bind("schema", SDO)
        self.graph.bind("adms", ADMS)
        self.graph.bind("foaf", FOAF)
    
    def create_uri(self, concept_name, code=None, version=None):
        """Generate URIs for identity and versions."""
        uri = f"{self.base_uri}{concept_name}"
        if code:
            uri += f"/{code}"
        if version:
            uri += f"/version/{version}"
        return URIRef(uri)


class CatalogManager:
    def __init__(self, graph_manager):
        self.vm = graph_manager
    
    def create_catalog_description(self):
        """Create metadata for the i14y catalog"""
        catalog_uri = URIRef("https://register.ld.admin.ch/.well-known/void/dataset/i14y")
        void_uri = URIRef("https://ld.admin.ch/.well-known/void")

        self.vm.graph.add((catalog_uri, RDF.type, SDO.DataCatalog))
        self.vm.graph.add((catalog_uri, RDF.type, VOID.DatasetDescription))
        self.vm.graph.add((catalog_uri, RDFA.uri, URIRef("https://register.ld.admin.ch/i14y/")))
        #self.vm.graph.add((catalog_uri, SDO.includedInDataCatalog, void_uri)) not used in LINDAS at the moment

        self.vm.graph.add((catalog_uri, DCTERMS.title, Literal("Data published on register.ld.admin.ch/i14y", lang="en")))
        self.vm.graph.add((catalog_uri, SDO.name, Literal("Data published on register.ld.admin.ch/i14y", lang="en")))
        self.vm.graph.add((catalog_uri, DCTERMS.description, Literal("This catalog contains data from I14Y. Specifically, it contains I14Y concepts made available as linked data.", lang="en")))
        self.vm.graph.add((catalog_uri, SDO.description, Literal("This catalog contains data from I14Y. Specifically, it contains I14Y concepts made available as linked data.", lang="en")))

        self.vm.graph.add((catalog_uri, DCTERMS.title, Literal("Données publiées sur register.ld.admin.ch/i14y", lang="fr")))
        self.vm.graph.add((catalog_uri, SDO.name, Literal("Données publiées sur register.ld.admin.ch/i14y", lang="fr")))
        self.vm.graph.add((catalog_uri, DCTERMS.description, Literal("Ce catalogue contient des données d'I14Y. Plus précisément, il contient des concepts I14Y mis à disposition sous forme de données liées.", lang="fr")))
        self.vm.graph.add((catalog_uri, SDO.description, Literal("Ce catalogue contient des données d'I14Y. Plus précisément, il contient des concepts I14Y mis à disposition sous forme de données liées.", lang="fr")))

        self.vm.graph.add((catalog_uri, DCTERMS.title, Literal("Dati pubblicati su register.ld.admin.ch/i14y", lang="it")))
        self.vm.graph.add((catalog_uri, SDO.name, Literal("Dati pubblicati su register.ld.admin.ch/i14y", lang="it")))
        self.vm.graph.add((catalog_uri, DCTERMS.description, Literal("Questo catalogo contiene dati da I14Y. Specificamente, contiene concetti I14Y resi disponibili come linked data.", lang="it")))
        self.vm.graph.add((catalog_uri, SDO.description, Literal("Questo catalogo contiene dati da I14Y. Specificamente, contiene concetti I14Y resi disponibili come linked data.", lang="it")))

        self.vm.graph.add((catalog_uri, DCTERMS.title, Literal("Daten veröffentlicht auf register.ld.admin.ch/i14y", lang="de")))
        self.vm.graph.add((catalog_uri, SDO.name, Literal("Daten veröffentlicht auf register.ld.admin.ch/i14y", lang="de")))
        self.vm.graph.add((catalog_uri, DCTERMS.description, Literal("Dieser Katalog enthält Daten von I14Y. Insbesondere enthält er I14Y-Konzepte, die als Linked Data verfügbar gemacht wurden.", lang="de")))
        self.vm.graph.add((catalog_uri, SDO.description, Literal("Dieser Katalog enthält Daten von I14Y. Insbesondere enthält er I14Y-Konzepte, die als Linked Data verfügbar gemacht wurden.", lang="de")))

        return catalog_uri

class CodeListManager:
    def __init__(self, version_manager):
        self.vm = version_manager
        self.level_depths = {}
        self.levels_dict = {}  
        self.levels_info_all = []


    def add_versioning_relationships(self, version_uri, identity_uri):
        """Connect a version to its identity"""
        self.vm.graph.add((version_uri, vl.identity, identity_uri))
        self.vm.graph.add((identity_uri, vl.version, version_uri))
    

    def mark_as_deprecated(self, identity_uri, valid_to=None):
        """Mark an identity as deprecated"""
        self.vm.graph.add((identity_uri, RDF.type, vl.Deprecated))
        if valid_to:
            self.vm.graph.add((
                identity_uri, 
                SDO.validUntil, 
                Literal(valid_to, datatype=XSD.date)
            ))


    def _calculate_depth(self, entry, concept_data):
        """Calculate depth level based on parentCode relationships."""
        if 'parentCode' not in entry:
            return 1
        parent_code = entry['parentCode']
        if parent_code in self.level_depths:
            return self.level_depths[parent_code] + 1
        parent_entry = next(
            (item for item in concept_data['codeListEntries'] 
            if item['code'] == parent_code), 
            None
        )
        return 1 + (self._calculate_depth(parent_entry, concept_data) if parent_entry else 0)
    

    def _create_all_level(self, ontology_uri, concept_data, is_version):
        """Create the top-level 'All' classification level"""
        if is_version:
            all_uri = self.vm.create_uri(concept_data['identifier'], "all", concept_data['version'])
        else:
            all_uri = self.vm.create_uri(concept_data['identifier'], "all")
        
        self.vm.graph.add((all_uri, RDF.type, XKOS.ClassificationLevel))
        self.vm.graph.add((all_uri, SDO.inDefinedTermSet, ontology_uri))
        self.vm.graph.add((all_uri, SKOS.prefLabel, Literal("All", lang="en")))
        
        hierarchy = BNode()
        self.vm.graph.add((ontology_uri, CUBELINK.inHierarchy, hierarchy))
        self.vm.graph.add((hierarchy, RDF.type, CUBELINK.Hierarchy))
        
        hierarchy_name = (
            f"Version Hierarchy - {concept_data['identifier']} v{concept_data['version']}" 
            if is_version else 
            f"Identity Hierarchy - {concept_data['identifier']}"
        )
        
        self.vm.graph.add((hierarchy, SDO.name, Literal(hierarchy_name)))
        self.vm.graph.add((hierarchy, CUBELINK.hierarchyRoot, all_uri))
        
        return all_uri


    def _process_level_metadata(self, level_uri, level_title, level_depth, ontology_uri):
        """Add metadata for a classification level"""
        self.vm.graph.add((level_uri, RDF.type, XKOS.ClassificationLevel))
        self.vm.graph.add((level_uri, SDO.inDefinedTermSet, ontology_uri))
        self.vm.graph.add((level_uri, XKOS.depth, Literal(level_depth, datatype=XSD.integer)))
        
        for lang, title in level_title.items():
            if is_valid_value(title):
                self.vm.graph.add((level_uri, SKOS.prefLabel, Literal(title, lang=lang)))
                self.vm.graph.add((level_uri, SDO.name, Literal(title, lang=lang)))
       

    def _process_entry(self, entry, concept_data, ontology_uri, all_uri, is_version):
        """Process entry with version-identity handling and level management"""
        if is_version:
            entry_uri = self.vm.create_uri(concept_data['identifier'], entry['code'], concept_data['version'])

            identity_uri = self.vm.create_uri(concept_data['identifier'], entry['code'])
            # self.vm.graph.add((entry_uri, vl.identity, identity_uri))
            # self.vm.graph.add((identity_uri, vl.version, entry_uri))
        else:
            entry_uri = self.vm.create_uri(concept_data['identifier'], entry['code'])
      
        if (not is_version) and hasattr(self.vm, 'deleted_entries') and entry['code'] in self.vm.deleted_entries:
            return


        level_depth = self._calculate_depth(entry, concept_data)
        self.level_depths[entry['code']] = level_depth
        
        if is_version:
            level_uri = self.vm.create_uri(concept_data['identifier'], f'level_{level_depth}', concept_data['version'] )
        else:
            level_uri = self.vm.create_uri( concept_data['identifier'],  f'level_{level_depth}')
    
        self.levels_dict.setdefault(level_depth, []).append(entry)
        
       
        level_title = {
            'en': f"Level {level_depth}",
            'it': f"Livello {level_depth}",
            'de': f"Ebene {level_depth}",
            'fr': f"Niveau {level_depth}"
        }


        if 'annotations' in entry:
            self.add_annotations(entry_uri, entry['annotations'])
        #in some cases it is used text (multilingual string) in other title (not multilingual)
            for annotation in entry.get('annotations', []):
    
                if annotation.get('type') == 'HIER_LEVEL':
            
                    if 'text' in annotation and is_valid_value(annotation['text']):
                        level_title = {
                            lang: annotation['text'].get(lang, level_title[lang]) 
                            for lang in level_title
                            if is_valid_value(annotation['text'].get(lang, level_title[lang]))
                        }
            
                    elif 'title' in annotation and is_valid_value(annotation['title']):
                
                        level_title = {lang: annotation['title'] for lang in level_title}


        if not any(level['uri'] == level_uri for level in self.levels_info_all):
            self.levels_info_all.append({
                'uri': level_uri, 
                'title': level_title, 
                'depth': level_depth
            })
            self._process_level_metadata(level_uri, level_title, level_depth, ontology_uri)
        
    
        self.vm.graph.add((entry_uri, XKOS.belongsTo, level_uri))
        self.vm.graph.add((entry_uri, XKOS.level, level_uri))
        self.vm.graph.add((level_uri, XKOS.contains, entry_uri))
        self.vm.graph.add((level_uri, SKOS.member, entry_uri))
        
  
        self._add_entry_metadata(entry_uri, entry, ontology_uri, all_uri, is_version)
        
 
        if 'parentCode' in entry:
            self._handle_parent_relationship(entry, concept_data, entry_uri, is_version)
        else:
            # If no parent, link to the all_uri as top concept
            self.vm.graph.add((entry_uri, SKOS.topConceptOf, ontology_uri))
            self.vm.graph.add((entry_uri, SKOS.broader, all_uri))
            self.vm.graph.add((all_uri, SKOS.narrower, entry_uri))
        

        if 'codeListEntryValueMaxLength' in concept_data or 'codeListEntryValueType' in concept_data:
            constraint_bnode = BNode()
            self.vm.graph.add((entry_uri, SHACL.property, constraint_bnode))
            self.vm.graph.add((constraint_bnode, SHACL.path, SKOS.notation))
            
            if 'codeListEntryValueType' in concept_data:
                value_type = concept_data['codeListEntryValueType']
                if value_type == "String":
                    self.vm.graph.add((constraint_bnode, SHACL.datatype, XSD.string))
                elif value_type == "Number":
                    self.vm.graph.add((constraint_bnode, SHACL.datatype, XSD.decimal)) 
            
            # if 'codeListEntryValueMaxLength' in concept_data:
            #     max_len = int(concept_data['codeListEntryValueMaxLength'])
            #     self.vm.graph.add((constraint_bnode, SHACL.maxLength, Literal(max_len, datatype=XSD.integer)))


    def _add_entry_metadata(self, entry_uri, entry, ontology_uri, all_uri, is_version):
        """Add all metadata for a single entry"""
        self.vm.graph.add((entry_uri, RDF.type, SKOS.Concept))
        self.vm.graph.add((entry_uri, RDF.type, SDO.DefinedTerm))
        self.vm.graph.add((entry_uri, RDF.type, vl.Version if is_version else vl.Identity))
        
        self.vm.graph.add((entry_uri, SKOS.inScheme, ontology_uri))
        self.vm.graph.add((entry_uri, SDO.inDefinedTermSet, ontology_uri))
        self.vm.graph.add((ontology_uri, SDO.hasDefinedTerm, entry_uri))
        self.vm.graph.add((all_uri, SKOS.member, entry_uri))
    
        for lang, name in entry['name'].items():
            if is_valid_value(name):
                self.vm.graph.add((entry_uri, SKOS.prefLabel, Literal(name, lang=lang)))
                self.vm.graph.add((entry_uri, SDO.name, Literal(name, lang=lang)))
                self.vm.graph.add((entry_uri, DCTERMS.title, Literal(name, lang=lang)))
        
        self.vm.graph.add((entry_uri, SDO.identifier, Literal(entry['code'])))
        self.vm.graph.add((entry_uri, SKOS.notation, Literal(entry['code'])))
        self.vm.graph.add((entry_uri, DCTERMS.identifier, Literal(entry['code'])))
        self.vm.graph.add((entry_uri, SDO.termCode, Literal(entry['code'])))

        for lang, desc in entry.get("description", {}).items():
            if is_valid_value(desc):
                self.vm.graph.add((entry_uri, SDO.description, Literal(desc, lang=lang)))
                self.vm.graph.add((entry_uri, DCTERMS.description, Literal(desc, lang=lang)))
                self.vm.graph.add((entry_uri, SKOS.definition, Literal(desc, lang=lang)))


    def _handle_parent_relationship(self, entry, concept_data, entry_uri, is_version):
        """Handle parent-child relationships between entries"""
        if is_version:
            parent_uri = self.vm.create_uri(concept_data['identifier'], entry['parentCode'],  concept_data['version'])
        else:
            parent_uri = self.vm.create_uri(concept_data['identifier'],  entry['parentCode'])
        
        relationships = [
            (entry_uri, SKOS.broader, parent_uri),
            (entry_uri, SDO.isPartOf, parent_uri),
            (entry_uri, XKOS.isPartOf, parent_uri),
            (parent_uri, SKOS.narrower, entry_uri),
            (parent_uri, SDO.hasPart, entry_uri),
            (parent_uri, XKOS.hasPart, entry_uri)
        ]
        
        for s, p, o in relationships:
            self.vm.graph.add((s, p, o))


    def add_annotations(self, concept_uri, annotations):
        """Handle annotations with special treatment for XKOS predicates"""
        annotation_predicates = {
            "INCLUDES": XKOS.coreContentNote,
            "INCLUDES_ALSO": XKOS.additionalContentNote,
            "EXCLUDES": XKOS.exclusionNote,
            "SCOPE_NOTE": XKOS.scopeNote, 
            "VALID_FROM": SDO.validFrom 
        }

        for annotation in annotations:
            annotation_type = annotation.get('type')
            text_data = annotation.get('text', {})

            # Skip HIER_LEVEL annotations as they're handled in _process_entry
            if annotation_type == 'HIER_LEVEL':
                continue

            # Handle special XKOS predicates
            if annotation_type in annotation_predicates:
                for lang, text in text_data.items():
                    if is_valid_value(text):
                        self.vm.graph.add(
                            (concept_uri, annotation_predicates[annotation_type], 
                            Literal(text, lang=lang))
                        )
                continue  # Skip the rest of the loop for these annotation types

            # Handle all other annotation types with full annotation structure
            annotation_node = BNode()
            self.vm.graph.add((annotation_node, RDF.type, oa.Annotation))
            self.vm.graph.add((annotation_node, oa.hasTarget, concept_uri))
            self.vm.graph.add((concept_uri, DCTERMS.hasPart, annotation_node))
            self.vm.graph.add((concept_uri, SDO.hasPart, annotation_node))

            body_node = BNode()
            self.vm.graph.add((annotation_node, oa.hasBody, body_node))

            first_text_added = False
            # Add text values if present
            for lang, text in text_data.items():
                if is_valid_value(text):
                    if not first_text_added:
                        self.vm.graph.add((body_node, RDF.type, URIref("http://www.w3.org/2011/content#ContentAsText")))
                        self.vm.graph.add((body_node, DCTERMS.format, Literal("text/plain")))
                        first_text_added = True
                    self.vm.graph.add((body_node, RDF.value, Literal(text.strip(), lang=lang)))


            # Add title if present
            title = annotation.get("title")
            if is_valid_value(title):
                self.vm.graph.add((body_node, DCTERMS.title, Literal(title)))
                self.vm.graph.add((body_node, SDO.name, Literal(title)))

            # Add identifier if present
            if annotation.get("identifier"): 
                self.vm.graph.add((body_node, DCTERMS.identifier, Literal(annotation["identifier"])))
                self.vm.graph.add((body_node, SDO.identifier, Literal(annotation["identifier"])))

            # Add type if present
            if annotation.get("type"):
                self.vm.graph.add((body_node, DCTERMS.type, Literal(annotation["type"])))

            # Add URI if present
            if annotation.get("uri"):
                annotation_uri = annotation["uri"].strip()
                if annotation_uri:  
                    self.vm.graph.add((body_node, oa.hasTarget, URIRef(annotation_uri)))

class ConceptMetadataManager:
    def __init__(self, version_manager):
        self.vm = version_manager
    
    def add_scheme_metadata(self, uri, concept_data, linked_uri=None, is_version=None):
        """Add metadata to identity and version objects."""
        self.vm.graph.add((uri, RDF.type, SKOS.ConceptScheme))
        self.vm.graph.add((uri, RDF.type, SDO.DefinedTermSet))
        #self.vm.graph.add((uri, RDF.type, meta.SharedDimension))     # uncomment this line to define Concepts as Shared Dimensions
        self.vm.graph.add((uri, RDF.type, vl.Version if is_version else vl.Identity))

        self.vm.graph.add((uri, PAV.version, Literal(concept_data['version'])))
        
        # SHACL property for cube creator
        shacl_property = BNode()
        self.vm.graph.add((uri, SHACL.property, shacl_property))
        self.vm.graph.add((shacl_property, QUDT.scaleType, URIRef('http://qudt.org/schema/qudt/Nominal')))
   
        self.vm.graph.add((uri, DCTERMS.identifier, Literal(concept_data["identifier"])))
        self.vm.graph.add((uri, SDO.identifier, Literal(concept_data["identifier"])))
        
        self.vm.graph.add((uri, SDO.validFrom, Literal(concept_data["validFrom"], datatype=XSD.date)))
        if 'validTo' in concept_data:
            self.vm.graph.add((uri, SDO.validUntil, Literal(concept_data["validTo"], datatype=XSD.date)))
        
        for lang, publisher_name in concept_data["publisher"]["name"].items():
            if  is_valid_value(publisher_name):
                self.vm.graph.add((uri, DCTERMS.publisher, Literal(publisher_name, lang=lang)))

        #added Version and identity to the name of the Concept to differentiate        
        modified_names = {}
        for lang, name in concept_data["name"].items():
            if is_valid_value(name):
                suffix = f" (version {concept_data['version']})" if is_version else " (identity)"
                modified_names[lang] = f"{name}{suffix}"
                for lang, name in modified_names.items():
                    if name and str(name).strip(): 
                        self.vm.graph.add((uri, SKOS.prefLabel, Literal(name, lang=lang)))
                        self.vm.graph.add((uri, SDO.name, Literal(name, lang=lang)))
                        self.vm.graph.add((uri, DCTERMS.title, Literal(name, lang=lang)))
                    
        
        for lang, desc in concept_data["description"].items():
            if  is_valid_value(desc):
                self.vm.graph.add((uri, SDO.description, Literal(desc, lang=lang)))
                self.vm.graph.add((uri, DCTERMS.description, Literal(desc, lang=lang)))
                self.vm.graph.add((uri, SKOS.definition, Literal(desc, lang=lang)))
        
        if concept_data.get("keywords"):
            for keyword_dict in concept_data["keywords"]:
                for lang, word in keyword_dict.items():
                    if  is_valid_value(word):
                        self.vm.graph.add((uri, SDO.keywords, Literal(word, lang=lang)))
        
        if "registrationStatus" in concept_data:
            self.vm.graph.add((uri, ADMS.status, Literal(concept_data["registrationStatus"])))
            
        i14y_url = f"https://www.i14y.admin.ch/en/concepts/{concept_data['id']}/description"
        self.vm.graph.add((uri, PROV.wasDerivedFrom, URIRef(i14y_url)))
        self.vm.graph.add((uri, PROV.hadPrimarySource, URIRef(i14y_url)))
        
        if "themes" in concept_data:
            for theme in concept_data["themes"]:
                self._add_theme(uri, theme, concept_data['id'])
        
        if concept_data.get('conformsTo'):
            for conformsTo_dict in concept_data['conformsTo']:
                self._add_conforms_to(uri, conformsTo_dict)
        
        # connect Concept to I14Y catalog
        catalog_uri = URIRef("https://register.ld.admin.ch/i14y/.well-known/void")
        self.vm.graph.add((uri, SDO.includedInDataCatalog, catalog_uri))
        self.vm.graph.add((catalog_uri, SDO.dataset, uri))
        self.vm.graph.add((catalog_uri, FOAF.topic, uri))
    

    def _add_theme(self, concept_uri, theme, concept_id):
        """Add themes to concept"""
        theme_bnode = BNode()
        theme_uri = f"https://www.i14y.admin.ch/catalog/concepts/{concept_id}/content/{theme['code']}"
        
        self.vm.graph.add((theme_bnode, DCTERMS.identifier, URIRef(theme_uri)))
        self.vm.graph.add((theme_bnode, SDO.identifier, URIRef(theme_uri)))
        
        for lang, theme_name in theme["name"].items():
            if  is_valid_value(theme_name):
                self.vm.graph.add((theme_bnode, SKOS.prefLabel, Literal(theme_name, lang=lang)))
                self.vm.graph.add((theme_bnode, SDO.name, Literal(theme_name, lang=lang)))
        
        self.vm.graph.add((concept_uri, DCTERMS.subject, theme_bnode))
    

    def _add_conforms_to(self, concept_uri, conformsTo_dict):
        """Add conformsTo information to concept"""
        conformTo_bnode = BNode()
        uri_ct = conformsTo_dict.get('uri')
        
        if uri_ct:
            self.vm.graph.add((conformTo_bnode, DCTERMS.identifier, URIRef(uri_ct)))
            self.vm.graph.add((conformTo_bnode, SDO.identifier, URIRef(uri_ct)))
            
            if 'label' in conformsTo_dict:
                for lang, name in conformsTo_dict["label"].items():
                    if  is_valid_value(name):
                        self.vm.graph.add((conformTo_bnode, SKOS.prefLabel, Literal(name, lang=lang)))
                        self.vm.graph.add((conformTo_bnode, SDO.name, Literal(name, lang=lang)))
            
            self.vm.graph.add((concept_uri, DCTERMS.conformsTo, conformTo_bnode))


    def add_concept_hierarchy(self, concept_uri, concept_data, is_version=False, level_depths=None, levels_dict=None, levels_info_all=None):
        """Add hierarchy structure for the concept including XKOS levels"""
        if level_depths is None:
            level_depths = {}
        if levels_dict is None:
            levels_dict = {}
        if levels_info_all is None:
            levels_info_all = []
        
        # Create 'All' level
        if is_version:
            all_uri = self.vm.create_uri(concept_data['identifier'], "all", concept_data['version'])
        else:
            all_uri = self.vm.create_uri(concept_data['identifier'], "all")
        
        self.vm.graph.add((all_uri, RDF.type, XKOS.ClassificationLevel))
        self.vm.graph.add((all_uri, SDO.inDefinedTermSet, concept_uri))
        self.vm.graph.add((all_uri, SKOS.prefLabel, Literal("All", lang="en")))
        
        # Create hierarchy structure
        hierarchy = BNode()
        self.vm.graph.add((concept_uri, CUBELINK.inHierarchy, hierarchy))
        self.vm.graph.add((hierarchy, RDF.type, CUBELINK.Hierarchy))
        
        hierarchy_name = (
            f"Version Hierarchy - {concept_data['identifier']} v{concept_data['version']}" 
            if is_version else 
            f"Identity Hierarchy - {concept_data['identifier']}"
        )
        
        self.vm.graph.add((hierarchy, SDO.name, Literal(hierarchy_name)))
        self.vm.graph.add((hierarchy, SKOS.prefLabel, Literal(hierarchy_name)))
        self.vm.graph.add((hierarchy, CUBELINK.hierarchyRoot, all_uri))
        
        if level_depths:
            self._add_xkos_level_information(concept_uri, all_uri, level_depths, levels_dict, levels_info_all, is_version, concept_data)
        
        return all_uri


    def _add_xkos_level_information(self, concept_uri, all_uri, level_depths, levels_dict, levels_info_all, is_version, concept_data):
        """Add XKOS level information to the concept scheme"""
        max_level_depth = max(level_depths.values(), default=1)
        self.vm.graph.add((concept_uri, XKOS.numberOfLevels, Literal(max_level_depth, datatype=XSD.integer)))
        
        sorted_levels = sorted(levels_info_all, key=lambda x: x['depth'])
        previous_level_uri = all_uri
        
        # Link the concept scheme to all levels (only for the current type - version or identity)
        self.vm.graph.add((concept_uri, XKOS.hasPart, all_uri))
        self.vm.graph.add((concept_uri, dataCite.haspart, all_uri))
        self.vm.graph.add((concept_uri, SDO.hasPart, all_uri))
        
        for level in sorted_levels:
            level_uri = URIRef(level['uri'])
            
            # Only process levels that match current type (version or identity)
            if is_version == ('version' in str(level_uri)):
          
                self.vm.graph.add((concept_uri, XKOS.levels, level_uri))
                self.vm.graph.add((concept_uri, XKOS.hasPart, level_uri))
                self.vm.graph.add((concept_uri, dataCite.haspart, level_uri))
                self.vm.graph.add((concept_uri, SDO.hasPart, level_uri))
            
                self.vm.graph.add((level_uri, RDF.type, XKOS.ClassificationLevel))
                self.vm.graph.add((level_uri, XKOS.depth, Literal(level['depth'], datatype=XSD.integer)))

                for lang, title in level['title'].items():
                    if  is_valid_value(title):
                        self.vm.graph.add((level_uri, SKOS.prefLabel, Literal(title, lang=lang)))
                        self.vm.graph.add((level_uri, SDO.name, Literal(title, lang=lang)))
                
                for entry in levels_dict.get(level['depth'], []):
                    if is_version:
                        entry_uri = self.vm.create_uri(concept_data['identifier'],  entry['code'], concept_data['version'])
                    else:
                        entry_uri = self.vm.create_uri(concept_data['identifier'], entry['code'])
                    
                    self.vm.graph.add((level_uri, SKOS.member, entry_uri))
                   
                if previous_level_uri and (is_version == ('version' in str(previous_level_uri))):
                    self.vm.graph.add((previous_level_uri, CUBELINK.nextInHierarchy, level_uri))
                previous_level_uri = level_uri
        
        # Link from 'All' to first level of same type if exists
        matching_levels = [level for level in sorted_levels 
                        if is_version == ('version' in str(URIRef(level['uri'])))]
        
        if matching_levels:
            first_level_uri = URIRef(matching_levels[0]['uri'])
            self.vm.graph.add((all_uri, CUBELINK.nextInHierarchy, first_level_uri))

