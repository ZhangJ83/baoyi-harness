import json
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from agent.events import EventBus, EventKind
from agent.office_ir import build_content_ir
from agent.session import Session, StopReason, TurnOutcome


def test_event_bus_is_observability_only_and_unsubscribable():
    bus = EventBus()
    seen = []
    bus.subscribe(lambda event: (_ for _ in ()).throw(RuntimeError("ui failed")))
    unsubscribe = bus.subscribe(seen.append)
    bus.publish(EventKind.CONTROLLER_DECISION, action="produce_candidate")
    unsubscribe()
    bus.publish(EventKind.TURN_COMPLETED)
    assert len(seen) == 1
    assert seen[0].payload["action"] == "produce_candidate"


def test_typed_session_records_turn_outcome():
    session = Session()
    outcome = TurnOutcome("done", StopReason.FINISHED, tool_calls=3, phase="deliver")
    session.append(outcome)
    assert session.turns == [outcome]
    assert outcome.stop_reason is StopReason.FINISHED


def test_content_ir_batches_html_markdown_and_csv_with_hashes():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.md").write_text("# Decision\nShip it", encoding="utf-8")
        (root / "b.html").write_text("<h1>Revenue</h1><p>42%</p><script>ignore()</script>", encoding="utf-8")
        (root / "c.csv").write_text("metric,value\nARR,42", encoding="utf-8")
        result = build_content_ir([root / "a.md", root / "b.html", root / "c.csv"]).to_dict()
    assert result["schema"] == "xiaopu-content-ir-v1"
    assert len(result["sources"]) == 3
    assert "Decision" in result["sources"][0]["text"]
    assert "ignore()" not in result["sources"][1]["text"]
    assert "ARR | 42" in result["sources"][2]["text"]
    assert all(len(row["sha256"]) == 64 for row in result["sources"])


def test_content_ir_model_brief_balances_sources_and_preserves_corrections():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "long.html").write_text("<h1>Report</h1>" + "noise " * 4000 + "<p>H-117 actual 42%</p>", encoding="utf-8")
        (root / "correction.md").write_text("# Correction\n- forecast must not be shown as actual", encoding="utf-8")
        ir = build_content_ir([root / "long.html", root / "correction.md"])
        brief = ir.to_model_dict(max_total_chars=1800)

        assert brief["schema"] == "xiaopu-content-brief-v1"
        assert len(brief["sources"]) == 2
        assert "forecast must not be shown as actual" in brief["sources"][1]["excerpt"]
        assert len(json.dumps(brief)) < len(json.dumps(ir.to_dict()))


def test_content_ir_xlsx_resolves_shared_strings_and_sheet_name():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "metrics.xlsx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Metrics" sheetId="1" r:id="rId1"/></sheets></workbook>',
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Revenue</t></si></sst>',
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">'
                '<c r="A1" t="s"><v>0</v></c><c r="B1"><v>42</v></c>'
                '</row></sheetData></worksheet>',
            )
        source = build_content_ir([path]).sources[0]
        assert "[Sheet: Metrics]" in source.text
        assert "A1=Revenue" in source.text
        assert "B1=42" in source.text
