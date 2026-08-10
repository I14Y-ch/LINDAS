"""Streaming Turtle serialization for i14y datasets."""

from __future__ import annotations

import hashlib
from pathlib import Path

from rdflib import BNode, Literal, URIRef


class DatasetStreamingTurtleWriter:
    """Append RDF triples immediately with dataset-scoped stable skolem IRIs.

    The mapper creates deterministic blank-node labels.  This writer turns them into
    IRIs below the current dataset URI, so a whole dataset subgraph can be removed
    from its primary identifier without traversing RDF blank nodes.
    """

    def __init__(self, filename: str | Path, dataset_uri_base: str):
        self.filename = Path(filename)
        self._stream = self.filename.open("w", encoding="utf-8")
        self.dataset_uri_base = dataset_uri_base
        self.current_dataset_identifier: str | None = None

    def bind(self, _prefix: str, _uri: URIRef) -> None:
        """Expose the rdflib Graph.bind shape used by the mapper.

        Terms are intentionally serialized as full IRIs, so prefixes do not need to
        be retained or emitted.
        """

    def set_current_dataset(self, identifier: str) -> None:
        self.current_dataset_identifier = identifier

    def add(self, triple: tuple[object, object, object]) -> None:
        subject, predicate, object_ = triple
        self._stream.write(
            f"{self._format_node(subject)} {self._format_node(predicate)} "
            f"{self._format_node(object_)} .\n"
        )
    def _skolemize(self, node: BNode) -> URIRef:
        if self.current_dataset_identifier is None:
            raise RuntimeError("Set the current dataset before writing blank nodes")
        canonical = f"{self.current_dataset_identifier}\0{node}"
        digest = hashlib.blake2s(canonical.encode("utf-8"), digest_size=16).hexdigest()
        return URIRef(
            f"{self.dataset_uri_base}{self.current_dataset_identifier}/.well-known/genid/{digest}"
        )

    def _format_node(self, node: object) -> str:
        if isinstance(node, URIRef):
            return f"<{node}>"
        if isinstance(node, BNode):
            return f"<{self._skolemize(node)}>"
        if isinstance(node, Literal):
            return self._format_literal(node)
        return f'"{str(node)}"'

    @staticmethod
    def _format_literal(literal: Literal) -> str:
        value = str(literal).replace("\r\n", "\n").replace("\r", "\n")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        rendered = f'"{escaped}"'
        if literal.language:
            return f"{rendered}@{literal.language}"
        if literal.datatype:
            return f"{rendered}^^<{literal.datatype}>"
        return rendered

    def close(self) -> None:
        self._stream.close()

    def __enter__(self) -> "DatasetStreamingTurtleWriter":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()