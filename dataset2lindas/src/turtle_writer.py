"""Streaming Turtle serialization for i14y datasets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote

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
        self.current_skolem_uri_base: str | None = None

    def bind(self, _prefix: str, _uri: URIRef) -> None:
        """Expose the rdflib Graph.bind shape used by the mapper.

        Terms are intentionally serialized as full IRIs, so prefixes do not need to
        be retained or emitted.
        """

    def set_current_dataset(self, identifier: str) -> None:
        self.current_dataset_identifier = identifier
        self.current_skolem_uri_base = (
            f"{self.dataset_uri_base}{identifier}/.well-known/genid/"
        )
    def set_current_structure(self, identifier: str) -> None:
        """Scope skolem IRIs to a single dataset structure."""
        self.current_dataset_identifier = identifier
        self.current_skolem_uri_base = (
            f"{self.dataset_uri_base}{identifier}/structure/.well-known/genid/"
        )
    def add(self, triple: tuple[object, object, object]) -> None:
        subject, predicate, object_ = triple
        self._stream.write(
            f"{self._format_node(subject)} {self._format_node(predicate)} "
            f"{self._format_node(object_)} .\n"
        )

    def _skolemize(self, node: BNode) -> URIRef:
        if self.current_skolem_uri_base is None:
            raise RuntimeError("Set a dataset or structure scope before writing blank nodes")
        canonical = f"{self.current_skolem_uri_base}\0{node}"
        digest = hashlib.blake2s(canonical.encode("utf-8"), digest_size=16).hexdigest()
        return URIRef(f"{self.current_skolem_uri_base}{digest}")
    @staticmethod
    def _repair_utf8_mojibake(value: str) -> str:
        """Repair UTF-8 bytes that i14y exported as Latin-1 characters.

        For example, ``Ã¶`` is repaired to ``ö`` and ``Ã`` followed by
        the C1 control ``U+0096`` is repaired to ``Ö``. The repair is only
        attempted for the usual mojibake markers, so normal Unicode IRIs stay
        unchanged.
        """
        has_mojibake_marker = "Ã" in value or "Â" in value
        has_control = any(0x7F <= ord(character) <= 0x9F for character in value)
        if not has_mojibake_marker and not has_control:
            return value
        try:
            return value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            return value

    @staticmethod
    def _escape_iri(value: str) -> str:
        """Repair i14y mojibake and escape any remaining invalid IRI characters."""
        value = DatasetStreamingTurtleWriter._repair_utf8_mojibake(value)
        escaped: list[str] = []
        position = 0
        forbidden = '<>"{}|\\^`'
        while position < len(value):
            character = value[position]
            if (
                character == "%"
                and position + 2 < len(value)
                and all(char in "0123456789abcdefABCDEF" for char in value[position + 1:position + 3])
            ):
                escaped.append(value[position:position + 3])
                position += 3
                continue
            if ord(character) <= 0x20 or 0x7F <= ord(character) <= 0x9F or character in forbidden:
                escaped.append(quote(character, safe=""))
            else:
                escaped.append(character)
            position += 1
        return "".join(escaped)
    def _format_node(self, node: object) -> str:
        if isinstance(node, URIRef):
            return f"<{self._escape_iri(str(node))}>"
        if isinstance(node, BNode):
            return f"<{self._skolemize(node)}>"
        if isinstance(node, Literal):
            return self._format_literal(node)
        return f'"{str(node)}"'

    @staticmethod
    def _format_literal(literal: Literal) -> str:
        value = DatasetStreamingTurtleWriter._repair_utf8_mojibake(str(literal))
        value = value.replace("\r\n", "\n").replace("\r", "\n")
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