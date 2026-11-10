#!/usr/bin/env python3
"""Run one GridCraft UI journey against the pinned monthly budget workbook."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
import time
from xml.etree import ElementTree as ET
from zipfile import ZipFile


MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
OFFICE_REL = OFFICE_REL_NS + "/"
LOOKUP_CELLS = {"Dashboard": 11, "Monthly Summary": 6000}
SHEET_METADATA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"


def normalized_xlsx(path: Path) -> bytes:
    """Hash package content while normalizing the known LOOKUP metadata and width defaults."""
    members = normalized_xlsx_members(path)
    return b"".join(name.encode() + b"\0" + members[name] + b"\0" for name in sorted(members))


def normalized_xlsx_members(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    workbook = ET.fromstring(members["xl/workbook.xml"])
    relationships = ET.fromstring(members["xl/_rels/workbook.xml.rels"])
    targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships}

    lookup_cells: dict[str, set[str]] = {}
    marked_cells: dict[str, set[str]] = {}
    sheet_members: dict[str, str] = {}
    metadata_users: set[str] = set()
    for sheet in workbook.find(MAIN_NS + "sheets"):
        name = sheet.attrib["name"]
        target = targets[sheet.attrib["{" + OFFICE_REL_NS + "}id"]]
        member = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
        sheet_members[name] = member
        root = ET.fromstring(members[member])
        for cell in root.findall(".//" + MAIN_NS + "sheetData/" + MAIN_NS + "row/" + MAIN_NS + "c"):
            address = cell.attrib.get("r", "")
            formula = cell.find(MAIN_NS + "f")
            if cell.get("cm") is not None:
                metadata_users.add(name + "!" + address)
            if formula is None or "LOOKUP" not in (formula.text or "").upper():
                continue
            if "1/" not in (formula.text or "").replace(" ", ""):
                raise ValueError(f"unexpected LOOKUP formula shape at {name}!{address}")
            lookup_cells.setdefault(name, set()).add(address)
            attrs = formula.attrib
            if attrs == {"t": "array", "ref": address} and cell.get("cm") == "1":
                marked_cells.setdefault(name, set()).add(address)
            elif attrs or cell.get("cm") is not None:
                raise ValueError(f"unexpected metadata on LOOKUP cell {name}!{address}: {cell.attrib}, {attrs}")

    if {name: len(cells) for name, cells in lookup_cells.items()} != LOOKUP_CELLS:
        raise ValueError(f"expected LOOKUP cells {LOOKUP_CELLS}, found { {k: len(v) for k, v in lookup_cells.items()} }")
    expected_users = {name + "!" + address for name, cells in lookup_cells.items() for address in cells}
    if metadata_users not in (set(), expected_users):
        raise ValueError("array metadata marks cells outside the known LOOKUP formulas")
    has_metadata = "xl/metadata.xml" in members
    if has_metadata:
        validate_metadata(members["xl/metadata.xml"])
        if marked_cells != lookup_cells or metadata_users != expected_users:
            raise ValueError("XLSX metadata does not cover exactly the known LOOKUP cells")
        relation_matches = [
            rel for rel in relationships
            if rel.attrib.get("Type") == OFFICE_REL + "sheetMetadata" and rel.attrib.get("Target") == "metadata.xml"
        ]
        if len(relation_matches) != 1:
            raise ValueError("expected one relationship to the LOOKUP array metadata part")
        members["xl/_rels/workbook.xml.rels"] = remove_relationship(
            members["xl/_rels/workbook.xml.rels"], relation_matches[0].attrib["Id"]
        )
        members["[Content_Types].xml"] = remove_metadata_content_type(members["[Content_Types].xml"])
        del members["xl/metadata.xml"]
    else:
        if marked_cells or metadata_users:
            raise ValueError("LOOKUP formula markers have no corresponding metadata part")
        if any(rel.attrib.get("Type") == OFFICE_REL + "sheetMetadata" for rel in relationships):
            raise ValueError("unexpected sheet metadata relationship")
        types = ET.fromstring(members["[Content_Types].xml"])
        if any(item.attrib.get("PartName") == "/xl/metadata.xml" for item in types):
            raise ValueError("unexpected metadata content type")

    for name, addresses in lookup_cells.items():
        member = sheet_members[name]
        members[member] = normalize_lookup_cells(members[member], marked_cells.get(name, set()))
    for name, member in sheet_members.items():
        members[member] = normalize_sheet_format(members[member], name)

    return members


def validate_metadata(data: bytes) -> None:
    expected_sha = "cfa14130b5c003532eaa837b979e958a2aef6ec617ddcc94342871588e82c928"
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("the workbook metadata part is not the known LOOKUP array marker payload")
    root = ET.fromstring(data)
    if root.tag != MAIN_NS + "metadata" or [child.tag for child in root] != [
        MAIN_NS + "metadataTypes",
        MAIN_NS + "futureMetadata",
        MAIN_NS + "cellMetadata",
    ]:
        raise ValueError("unexpected worksheet metadata root")
    metadata_types = root.findall(MAIN_NS + "metadataTypes/" + MAIN_NS + "metadataType")
    future = root.findall(MAIN_NS + "futureMetadata")
    cell_metadata = root.findall(MAIN_NS + "cellMetadata")
    dynamic = root.findall(".//{http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray}dynamicArrayProperties")
    records = root.findall(".//" + MAIN_NS + "cellMetadata/" + MAIN_NS + "bk/" + MAIN_NS + "rc")
    if (
        [item.attrib.get("name") for item in metadata_types] != ["XLDAPR"]
        or [item.attrib.get("name") for item in future] != ["XLDAPR"]
        or [item.attrib.get("count") for item in future] != ["1"]
        or len(dynamic) != 1
        or dynamic[0].attrib != {"fDynamic": "1", "fCollapsed": "0"}
        or [item.attrib.get("count") for item in cell_metadata] != ["1"]
        or len(records) != 1
        or records[0].attrib != {"t": "1", "v": "0"}
    ):
        raise ValueError("unexpected array metadata payload")


def remove_relationship(data: bytes, relationship_id: str) -> bytes:
    pattern = re.compile(
        rb'<Relationship\b(?=[^>]*\bId="' + re.escape(relationship_id.encode())
        + rb'")(?=[^>]*\bType="' + re.escape((OFFICE_REL + "sheetMetadata").encode())
        + rb'")(?=[^>]*\bTarget="metadata.xml")[^>]*/>'
    )
    updated, count = pattern.subn(b"", data)
    if count != 1:
        raise ValueError("could not remove exactly the LOOKUP array metadata relationship")
    return updated


def remove_metadata_content_type(data: bytes) -> bytes:
    pattern = re.compile(
        rb'<Override\b(?=[^>]*\bPartName="/xl/metadata.xml")'
        + rb'(?=[^>]*\bContentType="' + re.escape(SHEET_METADATA_TYPE.encode()) + rb'")[^>]*/>'
    )
    updated, count = pattern.subn(b"", data)
    if count != 1:
        raise ValueError("could not remove exactly the LOOKUP array metadata content type")
    return updated


def normalize_lookup_cells(data: bytes, addresses: set[str]) -> bytes:
    if not addresses:
        return data
    pattern = re.compile(rb'(<c\b[^>]*\br="([^"]+)"[^>]*>)(.*?)(</c>)', re.DOTALL)
    seen: set[str] = set()

    def normalize(match: re.Match[bytes]) -> bytes:
        opening, encoded_address, body, closing = match.groups()
        address = encoded_address.decode("ascii")
        if address not in addresses:
            return match.group()
        opening, removed = re.subn(rb'\s+cm="1"', b"", opening, count=1)
        if removed != 1:
            raise ValueError(f"missing cm=1 marker at {address}")
        formula = re.search(rb"<f\b[^>]*>", body)
        if formula is None:
            raise ValueError(f"LOOKUP formula is missing at {address}")
        body = body[:formula.start()] + b"<f>" + body[formula.end():]
        seen.add(address)
        return opening + body + closing

    updated = pattern.sub(normalize, data)
    if seen != addresses:
        raise ValueError(f"expected LOOKUP metadata cells {sorted(addresses)}, found {sorted(seen)}")
    return updated


def normalize_sheet_format(data: bytes, sheet_name: str) -> bytes:
    pattern = re.compile(rb"<sheetFormatPr\b[^>]*/>")
    matches = list(pattern.finditer(data))
    if len(matches) != 1:
        raise ValueError(f"expected one sheetFormatPr element, found {len(matches)}")
    match = matches[0]
    attrs = dict(re.findall(rb'([A-Za-z_:][\w:.-]*)="([^"]*)"', match.group()))
    if sheet_name in {"Expense Trends", "Expense Charts"}:
        if attrs.get(b"baseColWidth") == b"10" and b"defaultColWidth" not in attrs:
            if attrs != {b"baseColWidth": b"10", b"defaultRowHeight": b"15"}:
                raise ValueError(f"unexpected default column width for {sheet_name}: {attrs}")
            return data
        elif attrs.get(b"defaultColWidth") == b"11.421875" and b"baseColWidth" not in attrs:
            # Upstream stores the computed default width for the input's base width of 10.
            if attrs != {b"defaultColWidth": b"11.421875", b"defaultRowHeight": b"15"}:
                raise ValueError(f"unexpected default column width for {sheet_name}: {attrs}")
            normalized = b'<sheetFormatPr baseColWidth="10" defaultRowHeight="15"/>'
        else:
            raise ValueError(f"unexpected default column width for {sheet_name}: {attrs}")
    else:
        if attrs == {b"baseColWidth": b"8", b"defaultRowHeight": b"15"}:
            return data
        if attrs != {b"defaultRowHeight": b"15"}:
            raise ValueError(f"unexpected base column width for {sheet_name}: {attrs}")
        normalized = b'<sheetFormatPr baseColWidth="8" defaultRowHeight="15"/>'
    return data[:match.start()] + normalized + data[match.end():]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: gridcraft_budget_journey.py WORKBOOK ACTION", file=sys.stderr)
        return 2
    workbook, action = sys.argv[1:]
    snapshot = Path(os.environ["CARGO_TARGET_DIR"]) / "release/examples/snapshot"
    if not snapshot.is_file():
        print(f"missing GridCraft snapshot binary: {snapshot}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gridcraft-budget-journey-") as tmp:
        root = Path(tmp)
        png = root / "screen.png"
        args = [str(snapshot), "--in", workbook, "--size", "1440x900", "--scale", "1"]
        saved = None
        if action == "open":
            commands = [("edit.goTo", {"reference": "Dashboard!A1"})]
        elif action == "edit-recalc":
            commands = [
                ("edit.goTo", {"reference": "Entries!E779"}),
                ("cell.set", {"cell": "E779", "input": "99.99"}),
                ("edit.goTo", {"reference": "Monthly Summary!A2"}),
            ]
        elif action == "scroll":
            commands = [("edit.goTo", {"reference": "Entries!A779"})]
        elif action == "save":
            saved = root / "saved.xlsx"
            commands = [
                ("edit.goTo", {"reference": "Dashboard!A1"}),
                ("file.saveAs", {"path": str(saved)}),
            ]
        else:
            print(f"unknown GridCraft journey action: {action}", file=sys.stderr)
            return 2
        for command, params in commands:
            args.extend(("--cmd", f"{command}={json.dumps(params, separators=(',', ':'))}"))
        args.append(str(png))

        started = time.monotonic_ns()
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        elapsed = time.monotonic_ns() - started
        if result.returncode:
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        if action == "edit-recalc" and saved is None:
            # Verify the measured edit/recalc using a second, untimed replay that saves its
            # workbook. This checks formula results without including save or image raster
            # identity in the edit/recalc timing.
            saved = root / "verified.xlsx"
            verify_png = root / "verify.png"
            verify_args = args[:-1] + [
                "--cmd",
                f"file.saveAs={json.dumps({'path': str(saved)}, separators=(',', ':'))}",
                str(verify_png),
            ]
            verification = subprocess.run(verify_args, capture_output=True, text=True, check=False)
            if verification.returncode:
                sys.stderr.write(verification.stdout)
                sys.stderr.write(verification.stderr)
                return verification.returncode
            if not saved.is_file():
                print("GridCraft edit/recalc verification completed without an XLSX", file=sys.stderr)
                return 1
        if not png.is_file():
            print("GridCraft snapshot completed without a PNG", file=sys.stderr)
            return 1
        identity = hashlib.sha256(normalized_xlsx(saved)) if action == "edit-recalc" and saved is not None else hashlib.sha256(png.read_bytes())
        if saved is not None:
            if not saved.is_file():
                print("GridCraft output verification completed without an XLSX", file=sys.stderr)
                return 1
            if action != "edit-recalc":
                identity.update(normalized_xlsx(saved))
        print(f"CRAFT_JOURNEY_NS={elapsed}")
        print(f"CRAFT_OUTPUT_SHA256={identity.hexdigest()}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
