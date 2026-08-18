"""DCAT RDF mapping matching the supplied C# dataset exporter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

from .config import DatasetConfig
from .turtle_writer import DatasetStreamingTurtleWriter

DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCATAP = Namespace("http://data.europa.eu/r5r/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
ORG = Namespace("http://www.w3.org/ns/org#")
SCHEMA = Namespace("http://schema.org/")
SPDX = Namespace("http://spdx.org/rdf/terms#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
SH = Namespace("http://www.w3.org/ns/shacl#")
INVALID_URI = URIRef("https://en.wikipedia.org/wiki/Uniform_Resource_Identifier")
ALLOWED_RESOURCE_SCHEMES = {"http", "https", "mailto", "ftp", "ftps", "sftp"}

class DatasetRdfMapper:
    def __init__(
        self,
        config: DatasetConfig,
        dataservice_is_public: Callable[[str], bool] | None = None,
    ):
        self.config = config
        self.dataservice_is_public = dataservice_is_public
        self._current_identifier = "dataset"
        self._bnode_occurrences = {}

    def _new_bnode(self, role: str, context: Any) -> BNode:
        canonical_context = json.dumps(
            context,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        context_hash = hashlib.blake2s(canonical_context.encode("utf-8"), digest_size=16).hexdigest()
        label = f"{role}-{context_hash}"
        occurrence = self._bnode_occurrences.get(label, 0) + 1
        self._bnode_occurrences[label] = occurrence
        return BNode(f"{self._current_identifier}-{label}-{occurrence}")
    def dataset_uri(self, identifier: str) -> URIRef:
        return URIRef(f"{self.config.dataset_uri_base}{identifier}")

    def dataset_structure_uri(self, identifier: str) -> URIRef:
        return URIRef(f"{self.config.dataset_uri_base}{identifier}/structure")

    def dataservice_uri(self, dataservice_id: str) -> URIRef:
        return URIRef(f"{self.config.dataservice_uri_base}{dataservice_id}")

    def agent_uri(self, agent_identifier: str) -> URIRef:
        normalized = str(agent_identifier).strip()
        return URIRef(f"{self.config.agent_uri_base}{quote(normalized, safe='-._~')}")

    def dataset_theme_uri(self, code: str) -> URIRef:
        safe_code = quote(code, safe="-._~")
        return URIRef(
            "https://register.ld.admin.ch/i14y/concept/"
            f"{self.config.dataset_theme_concept_identifier}/{safe_code}/version/"
            f"{self.config.dataset_theme_concept_version}"
        )

    @staticmethod
    def _values(value: Any) -> Iterable[Any]:
        return value or []

    @staticmethod
    def _non_empty(value: Any) -> bool:
        return value is not None and str(value).strip() != ""

    def _resource_uri(self, value: str | None) -> URIRef:
        if not self._non_empty(value):
            return INVALID_URI
        normalized = str(value).strip()
        parsed = urlparse(normalized)
        return URIRef(normalized) if parsed.scheme else INVALID_URI

    def _url_uri(self, value: str | None) -> URIRef:
        if not self._non_empty(value):
            return INVALID_URI
        normalized = str(value).strip()
        parsed = urlparse(normalized)
        return URIRef(normalized) if parsed.scheme.lower() in ALLOWED_RESOURCE_SCHEMES else INVALID_URI

    @staticmethod
    def _add_multilingual(graph: Graph, subject: Any, predicate: URIRef, values: Any) -> None:
        if not isinstance(values, dict):
            return
        for language, value in values.items():
            if value is not None and str(value).strip() != "":
                graph.add((subject, predicate, Literal(value, lang=language)))

    @staticmethod
    def _add_date(graph: Graph, subject: Any, predicate: URIRef, value: Any) -> None:
        normalized = DatasetRdfMapper._date_value(value)
        if normalized:
            graph.add((subject, predicate, Literal(normalized, datatype=XSD.date)))

    def _add_resources(
        self,
        graph: Graph,
        subject: Any,
        predicate: URIRef,
        resources: Iterable[dict[str, Any]],
        resource_type: URIRef,
    ) -> None:
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            target = self._url_uri(resource.get("uri"))
            graph.add((subject, predicate, target))
            graph.add((target, RDF.type, resource_type))

    def _add_contact_point(self, graph: Graph, dataset_uri: URIRef, vcard: dict[str, Any]) -> None:
        contact = self._new_bnode("contact", vcard)
        graph.add((dataset_uri, DCAT.contactPoint, contact))
        graph.add((contact, RDF.type, VCARD.Organization))
        self._add_multilingual(graph, contact, VCARD.fn, vcard.get("fn"))
        self._add_multilingual(graph, contact, VCARD.adrWork, vcard.get("hasAddress"))
        self._add_multilingual(graph, contact, VCARD.note, vcard.get("note"))
        if self._non_empty(vcard.get("hasEmail")):
            graph.add((contact, VCARD.hasEmail, Literal(vcard["hasEmail"])))
        if self._non_empty(vcard.get("hasTelephone")):
            graph.add((contact, VCARD.hasTelephone, Literal(vcard["hasTelephone"])))

    def _add_qualified_attributions(
        self, graph: Graph, dataset_uri: URIRef, attributions: Iterable[dict[str, Any]]
    ) -> None:
        for attribution in attributions:
            if not isinstance(attribution, dict):
                continue
            node = self._new_bnode("attribution", attribution)
            graph.add((dataset_uri, DCAT.qualifiedAttribution, node))
            graph.add((node, RDF.type, DCAT.Attribution))
            agent_identifier = (attribution.get("agent") or {}).get("identifier")
            if self._non_empty(agent_identifier):
                graph.add((node, DCAT.agent, Literal(agent_identifier)))
            role = (attribution.get("hadRole") or {}).get("uri")
            if role is not None:
                graph.add((node, DCAT.hadRole, self._resource_uri(role)))

    def _add_qualified_relations(
        self, graph: Graph, dataset_uri: URIRef, relations: Iterable[dict[str, Any]]
    ) -> None:
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            node = self._new_bnode("relation", relation)
            graph.add((dataset_uri, DCAT.qualifiedRelation, node))
            graph.add((node, RDF.type, DCAT.Relationship))
            related_uri = (relation.get("relation") or {}).get("uri")
            if related_uri is not None:
                graph.add((node, DCTERMS.relation, self._resource_uri(related_uri)))
            role = (relation.get("hadRole") or {}).get("uri")
            if role is not None:
                graph.add((node, DCAT.hadRole, self._resource_uri(role)))

    @staticmethod
    def _date_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        value = str(value)
        return value[:10] if len(value) >= 10 else value

    def _add_distribution(self, graph: Graph, dataset_uri: URIRef, distribution: dict[str, Any]) -> None:
        distribution_node = self._new_bnode(
            "distribution",
            distribution.get("id") or distribution.get("identifier") or distribution,
        )
        graph.add((dataset_uri, DCAT.distribution, distribution_node))
        graph.add((distribution_node, RDF.type, DCAT.Distribution))

        access_url = distribution.get("accessUrl") or {}
        self._add_resources(graph, distribution_node, DCAT.accessURL, [access_url], RDFS.Resource)

        availability = (distribution.get("availability") or {}).get("uri")
        if availability is not None:
            graph.add((distribution_node, DCATAP.availability, self._resource_uri(availability)))
        if distribution.get("byteSize") is not None:
            graph.add((distribution_node, DCAT.byteSize, Literal(str(Decimal(str(distribution["byteSize"]))), datatype=XSD.decimal)))
        if self._non_empty(distribution.get("rights")):
            graph.add((distribution_node, DCTERMS.rights, Literal(distribution["rights"])))

        checksum = distribution.get("checksum") or {}
        if checksum:
            checksum_node = self._new_bnode(
                "checksum",
                {
                    "distribution": distribution.get("id") or distribution.get("identifier"),
                    "checksum": checksum,
                },
            )
            graph.add((checksum_node, RDF.type, SPDX.Checksum))
            algorithm_uri = (checksum.get("algorithm") or {}).get("uri")
            if algorithm_uri is not None:
                graph.add((checksum_node, SPDX.algorithm, self._resource_uri(algorithm_uri)))
            if self._non_empty(checksum.get("checksumValue")):
                graph.add((checksum_node, SPDX.checksumValue, Literal(checksum["checksumValue"])))
            graph.add((distribution_node, SPDX.checksum, checksum_node))

        self._add_resources(graph, distribution_node, DCTERMS.conformsTo, self._values(distribution.get("conformsTo")), URIRef(f"{DCTERMS}standard"))
        for coverage in self._values(distribution.get("coverage")):
            coverage_date = self._date_value((coverage or {}).get("start"))
            if coverage_date:
                graph.add((distribution_node, DCTERMS.coverage, Literal(coverage_date)))
                break
        self._add_multilingual(graph, distribution_node, DCTERMS.description, distribution.get("description"))
        self._add_resources(graph, distribution_node, FOAF.page, self._values(distribution.get("documentation")), FOAF.Document)
        download_url = distribution.get("downloadUrl")
        if download_url:
            self._add_resources(graph, distribution_node, DCAT.downloadURL, [download_url], RDFS.Resource)
        format_uri = (distribution.get("format") or {}).get("uri")
        if format_uri is not None:
            graph.add((distribution_node, DCTERMS.format, self._resource_uri(format_uri)))
        if self._non_empty(distribution.get("identifier")):
            graph.add((distribution_node, DCTERMS.identifier, Literal(distribution["identifier"])))
        self._add_resources(graph, distribution_node, SCHEMA.image, self._values(distribution.get("images")), SCHEMA.url)
        for language in self._values(distribution.get("languages")):
            code = (language or {}).get("code")
            if self._non_empty(code):
                graph.add((distribution_node, DCTERMS.language, Literal(code)))
        license_uri = (distribution.get("license") or {}).get("uri")
        if license_uri is not None:
            graph.add((distribution_node, DCTERMS.license, self._resource_uri(license_uri)))
        media_type_uri = (distribution.get("mediaType") or {}).get("uri")
        if media_type_uri is not None:
            graph.add((distribution_node, DCAT.mediaType, self._resource_uri(media_type_uri)))
        self._add_date(graph, distribution_node, DCTERMS.modified, distribution.get("modified"))
        packaging_uri = (distribution.get("packagingFormat") or {}).get("uri")
        if packaging_uri is not None:
            graph.add((distribution_node, DCAT.packageFormat, self._resource_uri(packaging_uri)))
        self._add_date(graph, distribution_node, DCTERMS.issued, distribution.get("issued"))
        if self._non_empty(distribution.get("temporalResolution")):
            graph.add((distribution_node, DCAT.temporalResolution, Literal(distribution["temporalResolution"])))
        self._add_multilingual(graph, distribution_node, DCTERMS.title, distribution.get("title"))

        for service in self._values(distribution.get("accessServices")):
            service_id = (service or {}).get("id")
            if service_id and self.dataservice_is_public and self.dataservice_is_public(service_id):
                graph.add((distribution_node, DCAT.accessService, self.dataservice_uri(service_id)))

    def map_dataset(self, dataset: dict[str, Any], graph: Graph | None = None) -> Graph:
        identifiers = dataset.get("identifiers") or []
        if not identifiers or not self._non_empty(identifiers[0]):
            raise ValueError(f"Dataset {dataset.get('id', '<unknown>')} has no primary identifier")
        if graph is None:
            graph = Graph()
        self._current_identifier = str(identifiers[0])
        self._bnode_occurrences = {}
        self.bind_namespaces(graph)
        uri = self.dataset_uri(self._current_identifier)

        graph.add((uri, RDF.type, DCAT.Dataset))
        access_rights_uri = (dataset.get("accessRights") or {}).get("uri")
        graph.add((uri, DCAT.accessRights, self._resource_uri(access_rights_uri)))
        self._add_resources(graph, uri, DCTERMS.conformsTo, self._values(dataset.get("conformsTo")), URIRef(f"{DCTERMS}standard"))
        for vcard in self._values(dataset.get("contactPoints")):
            if isinstance(vcard, dict):
                self._add_contact_point(graph, uri, vcard)
        self._add_multilingual(graph, uri, DCTERMS.description, dataset.get("description"))
        self._add_resources(graph, uri, FOAF.page, self._values(dataset.get("documentation")), FOAF.Document)
        frequency_uri = (dataset.get("frequency") or {}).get("uri")
        if frequency_uri is not None:
            graph.add((uri, DCTERMS.accrualPeriodicity, self._resource_uri(frequency_uri)))
        graph.add((uri, DCTERMS.identifier, Literal(identifiers[0])))
        self._add_resources(graph, uri, SCHEMA.image, self._values(dataset.get("images")), SCHEMA.url)
        self._add_resources(graph, uri, DCTERMS.isReferencedBy, self._values(dataset.get("isReferencedBy")), RDFS.Resource)
        self._add_resources(graph, uri, DCTERMS.relation, self._values(dataset.get("relations")), RDFS.Resource)
        self._add_date(graph, uri, DCTERMS.issued, dataset.get("issued"))
        for keyword in self._values(dataset.get("keywords")):
            self._add_multilingual(graph, uri, DCAT.keyword, (keyword or {}).get("label"))
        landing_pages = list(self._values(dataset.get("landingPages")))
        if landing_pages:
            self._add_resources(graph, uri, DCAT.landingPage, [landing_pages[0]], FOAF.Document)
        for language in self._values(dataset.get("languages")):
            code = (language or {}).get("code")
            if self._non_empty(code):
                graph.add((uri, DCTERMS.language, Literal(code)))
        self._add_date(graph, uri, DCTERMS.modified, dataset.get("modified"))

        publisher = dataset.get("publisher") or {}
        if publisher:
            publisher_identifier = publisher.get("identifier")
            if not self._non_empty(publisher_identifier):
                raise ValueError(f"Dataset {self._current_identifier} publisher has no identifier")
            publisher_uri = self.agent_uri(str(publisher_identifier))
            graph.add((uri, DCTERMS.publisher, publisher_uri))
            graph.add((publisher_uri, RDF.type, FOAF.Agent))
            graph.add((publisher_uri, RDF.type, ORG.Organization))
            graph.add((publisher_uri, RDF.type, FOAF.Organization))
            self._add_multilingual(graph, publisher_uri, FOAF.name, publisher.get("name"))

        self._add_qualified_attributions(graph, uri, self._values(dataset.get("qualifiedAttributions")))
        self._add_qualified_relations(graph, uri, self._values(dataset.get("qualifiedRelations")))
        for spatial in self._values(dataset.get("spatial")):
            if self._non_empty(spatial):
                graph.add((uri, DCTERMS.spatial, Literal(spatial)))
        temporal_coverage = list(self._values(dataset.get("temporalCoverage")))
        if temporal_coverage:
            period = self._new_bnode("period", temporal_coverage[0])
            graph.add((uri, DCTERMS.temporal, period))
            graph.add((period, RDF.type, DCTERMS.PeriodOfTime))
            self._add_date(graph, period, SCHEMA.startDate, temporal_coverage[0].get("start"))
            self._add_date(graph, period, SCHEMA.endDate, temporal_coverage[0].get("end"))
        self._add_multilingual(graph, uri, DCTERMS.title, dataset.get("title"))
        for theme in self._values(dataset.get("themes")):
            theme_uri = (theme or {}).get("uri")
            theme_code = (theme or {}).get("code")
            if self._non_empty(theme_uri):
                graph.add((uri, DCAT.theme, self._resource_uri(theme_uri)))
            elif self._non_empty(theme_code):
                graph.add((uri, DCAT.theme, self.dataset_theme_uri(str(theme_code))))
            else:
                graph.add((uri, DCAT.theme, INVALID_URI))
        for distribution in self._values(dataset.get("distributions")):
            if isinstance(distribution, dict):
                self._add_distribution(graph, uri, distribution)
        return graph

    def add_catalog(self, graph: Graph, identifiers: Iterable[str]) -> None:
        """Optionally add a synthetic common catalogue; off by default in configuration."""
        self.bind_namespaces(graph)
        catalog = URIRef(self.config.catalog_uri)
        graph.add((catalog, RDF.type, DCAT.Catalog))
        graph.add((catalog, DCTERMS.title, Literal("i14y datasets", lang="en")))
        for identifier in identifiers:
            graph.add((catalog, DCAT.dataset, self.dataset_uri(identifier)))

    def add_structure_turtle(
        self,
        writer: DatasetStreamingTurtleWriter,
        identifier: str,
        structure_turtle: str | None,
    ) -> None:
        """Serialize one structure and index only NodeShapes plus external subjects.

        The graph only lives for this one structure. Blank nodes are emitted through
        the structure-specific skolem scope and are consequently covered by the
        dataset URI-prefix deletion.
        """
        if structure_turtle is None:
            return
        try:
            structure_graph = Graph().parse(data=structure_turtle, format="turtle")
        except Exception as error:
            raise ValueError(f"Dataset {identifier} has invalid structure Turtle") from error

        dataset_uri = self.dataset_uri(identifier)
        dataset_prefix = f"{dataset_uri}/"
        structure_uri = self.dataset_structure_uri(identifier)
        writer.add((dataset_uri, DCTERMS.conformsTo, structure_uri))
        writer.set_current_structure(identifier)

        def is_dataset_resource(node: Any) -> bool:
            return isinstance(node, URIRef) and (
                str(node) == str(dataset_uri) or str(node).startswith(dataset_prefix)
            )

        node_shapes = set(structure_graph.subjects(RDF.type, SH.NodeShape))
        external_subjects = {
            subject
            for subject in structure_graph.subjects()
            if isinstance(subject, URIRef) and not is_dataset_resource(subject)
        }
        parts = node_shapes | external_subjects
        for part in sorted(parts, key=lambda node: (type(node).__name__, str(node))):
            writer.add((structure_uri, DCTERMS.hasPart, part))
        for triple in structure_graph:
            writer.add(triple)
    @staticmethod
    def bind_namespaces(graph: Graph) -> None:
        graph.bind("dcat", DCAT)
        graph.bind("dcatap", DCATAP)
        graph.bind("dct", DCTERMS)
        graph.bind("foaf", FOAF)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("schema", SCHEMA)
        graph.bind("spdx", SPDX)
        graph.bind("vcard", VCARD)
        graph.bind("xsd", XSD)

    def write_dataset_turtle(
        self,
        datasets: Iterable[dict[str, Any]],
        output_path: str | Path,
        structure_turtle_for_dataset: Callable[[str], str | None] | None = None,
    ) -> int:
        """Write one dataset at a time; no rdflib Graph is retained for the batch."""
        count = 0
        with DatasetStreamingTurtleWriter(output_path, self.config.dataset_uri_base) as writer:
            self.bind_namespaces(writer)
            for dataset in datasets:
                identifiers = dataset.get("identifiers") or []
                if not identifiers or not self._non_empty(identifiers[0]):
                    raise ValueError(f"Dataset {dataset.get('id', '<unknown>')} has no primary identifier")
                identifier = str(identifiers[0])
                if structure_turtle_for_dataset is None:
                    structure_turtle = None
                else:
                    dataset_id = dataset.get("id")
                    if not self._non_empty(dataset_id):
                        raise ValueError(f"Dataset {identifier} has no i14y id")
                    structure_turtle = structure_turtle_for_dataset(str(dataset_id))
                writer.set_current_dataset(identifier)
                self.map_dataset(dataset, writer)
                self.add_structure_turtle(writer, identifier, structure_turtle)
                count += 1
        return count

    def write_catalog_turtle(self, identifiers: Iterable[str], output_path: str | Path) -> None:
        with DatasetStreamingTurtleWriter(output_path, self.config.dataset_uri_base) as writer:
            self.add_catalog(writer, identifiers)
