"""Read file content and native metadata without judging task completion."""

import re
from zipfile import ZipFile

from lxml import etree

from .hashing import sha256_file
from .review_evidence import prepare_file_evidence
from .view_safety import ordinary_file


def read_file(path, artifact):
    path = ordinary_file(path)
    digest = sha256_file(path)
    if path.suffix.lower() == ".docx":
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        parts = {}
        with ZipFile(path) as package:
            infos = package.infolist()
            if len(infos) > 10000 or sum(i.file_size for i in infos) > 100_000_000:
                raise ValueError("Office package expansion budget exceeded")
            for name in package.namelist():
                if name == "word/document.xml" or re.fullmatch(
                    r"word/(?:header\d+|footer\d+|footnotes|comments)\.xml", name
                ):
                    raw = package.read(name)
                    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                        raise ValueError("XML entity declarations unsupported")
                    root = etree.fromstring(
                        raw, etree.XMLParser(resolve_entities=False, no_network=True)
                    )
                    parts[name] = {
                        "paragraphs": [
                            {
                                "text": "".join(
                                    p.xpath(
                                        ".//w:t/text()|.//w:delText/text()",
                                        namespaces=ns,
                                    )
                                ),
                                "xml": etree.tostring(
                                    p, encoding="unicode", with_tail=False
                                ),
                            }
                            for p in root.xpath(".//w:p", namespaces=ns)
                        ],
                        "annotations": [
                            {
                                "attributes": dict(n.attrib),
                                "text": "".join(n.itertext()),
                            }
                            for n in root
                            if n.tag.rsplit("}", 1)[-1] in {"comment", "footnote"}
                        ],
                    }
        result = {
            "artifact": artifact,
            "file": str(path),
            "sha256": digest,
            "parts": parts,
            "limitations": [
                "Native XML/text observations;visual layout requires rendering."
            ],
        }
    else:
        result = prepare_file_evidence(path, artifact)
    if sha256_file(path) != digest:
        raise ValueError("file changed during observation")
    return result
