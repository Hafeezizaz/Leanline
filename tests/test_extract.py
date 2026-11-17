import pytest

from leanline.extract import extract_file
from leanline.extract.logs import parse_log, signature
from leanline.extract.markdown import extract_markdown


def test_sections_follow_headings():
    ex = extract_markdown("# A\nintro\n## B\nbody b\n## C\nbody c\n")
    assert [s.heading_path for s in ex.sections] == ["A", "A > B", "A > C"]


def test_heading_inside_code_fence_is_ignored():
    ex = extract_markdown("# A\n```\n# not a heading\n```\nafter\n")
    assert [s.heading_path for s in ex.sections] == ["A"]
    assert "# not a heading" in ex.sections[0].text


def test_terms_and_links_found():
    ex = extract_markdown(
        '# Glossary\n**Widget**: a small thing\nThe "Gizmo" means a device.\n'
        "See [details](#details) and Section 2.1 for more.\n"
    )
    assert {t for t, _ in ex.terms} == {"Widget", "Gizmo"}
    targets = {t for _, t in ex.links}
    assert "#details" in targets and "2.1" in targets


def test_long_section_is_split_into_parts():
    ex = extract_markdown("# Big\n" + "word " * 1200)
    assert len(ex.sections) >= 2
    assert ex.sections[0].heading_path == "Big (part 1)"


def test_plain_text_without_headings_gets_one_section():
    ex = extract_markdown("just some text\nmore text", kind="text")
    assert [s.heading_path for s in ex.sections] == ["(text)"]


LOG = """2026-01-01 10:00:00 INFO Started job 1
2026-01-01 10:00:01 INFO Started job 2
2026-01-01 10:00:02 ERROR Failed to connect to 10.0.0.1:5432
Traceback (most recent call last):
  File "x.py", line 1, in <module>
ConnectionError: refused
2026-01-01 10:00:03 ERROR Failed to connect to 10.0.0.2:5432
2026-01-01 10:00:04 WARNING Disk at 91%
"""


def test_signature_normalises_numbers_and_ips():
    a = signature("2026-01-01 10:00:02 ERROR Failed to connect to 10.0.0.1:5432")
    b = signature("2026-02-03 11:11:11 ERROR Failed to connect to 10.9.9.9:80")
    assert a == b == "Failed to connect to <IP>"


def test_parse_log_groups_and_levels():
    data = parse_log(LOG)
    assert data.level_counts == {"INFO": 2, "ERROR": 2, "WARN": 1}
    assert len(data.groups) == 3
    err = next(g for g in data.groups if g.level == "ERROR")
    assert err.count == 2
    assert "Traceback" in err.sample and "ConnectionError" in err.sample
    assert data.first_ts == "2026-01-01 10:00:00"
    assert data.last_ts == "2026-01-01 10:00:04"


def test_log_extraction_creates_error_section(tmp_path):
    p = tmp_path / "app.log"
    p.write_text(LOG, encoding="utf-8")
    ex = extract_file(p)
    paths = [s.heading_path for s in ex.sections]
    assert paths[0] == "Summary"
    assert any(x.startswith("ERROR x2") for x in paths)


def test_unsupported_extension_raises(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"\x00")
    with pytest.raises(ValueError):
        extract_file(p)


def test_docx_extraction(tmp_path):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_heading("Policy", 1)
    d.add_heading("Leave", 2)
    d.add_paragraph("Employees get 20 days of leave.")
    d.save(str(tmp_path / "p.docx"))
    ex = extract_file(tmp_path / "p.docx")
    assert [s.heading_path for s in ex.sections] == ["Policy > Leave"]
    assert "20 days" in ex.sections[0].text


def test_pptx_extraction(tmp_path):
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Roadmap"
    slide.placeholders[1].text = "Ship phase one"
    prs.save(str(tmp_path / "d.pptx"))
    ex = extract_file(tmp_path / "d.pptx")
    assert ex.sections[0].heading_path.startswith("Slide 1")
    assert any("Ship phase one" in s.text for s in ex.sections)


def _make_pdf(path, text):
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs.append(b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")
    out = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1) + b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(out)


def test_pdf_extraction(tmp_path):
    pytest.importorskip("pypdf")
    p = tmp_path / "t.pdf"
    _make_pdf(p, "Hello PDF world")
    ex = extract_file(p)
    assert ex.sections[0].heading_path == "Page 1"
    assert "Hello" in ex.sections[0].text
