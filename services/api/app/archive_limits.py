"""Bound XLSX expansion and worksheet iteration before handing bytes to openpyxl."""

import io
import re
import struct
import zipfile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from openpyxl import load_workbook as open_workbook
from openpyxl.utils.cell import range_boundaries

MAX_MEMBERS = 2048
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_WORKSHEETS = 32
MAX_ROWS = 50000
MAX_COLUMNS = 512
MAX_CELLS = 200000
MAX_XML_ELEMENTS = 1000000


def validate_workbook_archive(content: bytes) -> None:
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("Workbook compressed content exceeds resource limit")
    # Bound the directory before ZipFile allocates one Python object per advertised member.
    end = content.rfind(b"PK\x05\x06", max(0, len(content) - 65557))
    if end < 0 or len(content) - end < 22:
        raise ValueError("Workbook has no valid ZIP directory")
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from(
        "<4s4H2LH", content, end
    )
    if disk or directory_disk or disk_count != count or end + 22 + comment != len(content):
        raise ValueError("Multipart or malformed workbook archives are unsupported")
    if count > MAX_MEMBERS or size > 2 * 1024 * 1024 or offset == 0xFFFFFFFF:
        raise ValueError("Workbook archive directory exceeds resource limit; ZIP64 is unsupported")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_MEMBERS:
                raise ValueError("Workbook has too many archive entries")
            names, expanded, sheets, cells, elements = set(), 0, 0, 0, 0
            for member in members:
                name = member.orig_filename
                parts = name.rstrip("/").split("/")
                if (
                    "\\" in name
                    or "\x00" in name
                    or ":" in name
                    or any(part in {"", ".", ".."} for part in parts)
                    or name.casefold() in names
                ):
                    raise ValueError("Workbook archive has unsafe or duplicate entry names")
                names.add(name.casefold())
                if member.flag_bits & 1:
                    raise ValueError("Encrypted workbook archives are unsupported")
                if (
                    member.file_size > MAX_MEMBER_BYTES
                    or member.file_size > max(1, member.compress_size) * MAX_COMPRESSION_RATIO
                ):
                    raise ValueError("Workbook archive exceeds expansion limits")
                expanded += member.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    raise ValueError("Workbook expanded content exceeds resource limit")
                if member.is_dir():
                    continue
                with archive.open(member) as source:
                    data = source.read(MAX_MEMBER_BYTES + 1)
                if len(data) != member.file_size or len(data) > MAX_MEMBER_BYTES:
                    raise ValueError("Workbook archive size does not match its content")
                worksheet = False
                row_count = 0
                xml_content = data.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(
                    b"<"
                ) or data.startswith((b"\xff\xfe", b"\xfe\xff", b"\x00<", b"<\x00"))
                if not name.casefold().endswith((".xml", ".rels")) and not xml_content:
                    continue
                root = True
                for event, element in ElementTree.iterparse(
                    io.BytesIO(data),
                    events=("start", "end"),
                    forbid_dtd=True,
                    forbid_entities=True,
                    forbid_external=True,
                ):
                    if event == "start":
                        if root:
                            root = False
                            worksheet = element.tag.rsplit("}", 1)[-1] == "worksheet"
                            if worksheet:
                                sheets += 1
                                if sheets > MAX_WORKSHEETS:
                                    raise ValueError("Workbook has too many worksheets")
                        continue
                    elements += 1
                    if elements > MAX_XML_ELEMENTS:
                        raise ValueError("Workbook XML exceeds resource limit")
                    tag = element.tag.rsplit("}", 1)[-1]
                    if worksheet and tag in {"dimension", "c"}:
                        ref = element.attrib.get("ref" if tag == "dimension" else "r")
                        if ref:
                            left, top, right, bottom = range_boundaries(ref)
                            if (
                                any(value is None for value in (left, top, right, bottom))
                                or bottom > MAX_ROWS
                                or right > MAX_COLUMNS
                            ):
                                raise ValueError(
                                    "Workbook worksheet dimensions exceed resource limit"
                                )
                        if tag == "c":
                            cells += 1
                            if cells > MAX_CELLS:
                                raise ValueError("Workbook has too many populated cells")
                    if worksheet and tag == "row":
                        row_count += 1
                        row = element.attrib.get("r", "1")
                        if (
                            row_count > MAX_ROWS
                            or len(element) > MAX_COLUMNS
                            or not re.fullmatch(r"[1-9][0-9]{0,4}", row)
                            or int(row) > MAX_ROWS
                        ):
                            raise ValueError("Workbook row index exceeds resource limit")
                    element.clear()
    except (zipfile.BadZipFile, RuntimeError, DefusedXmlException, ElementTree.ParseError) as exc:
        raise ValueError("Workbook archive is malformed or contains unsafe XML") from exc


def load_workbook(source, **kwargs):
    content = source if isinstance(source, bytes) else source.getvalue()
    validate_workbook_archive(content)
    return open_workbook(io.BytesIO(content), **kwargs)
