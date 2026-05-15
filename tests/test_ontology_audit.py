from depaysement_lab.ontology import OntologyAuditor, audit_run_files


def test_identity_melt_beats_plain_object_description():
    auditor = OntologyAuditor()
    melt = auditor.audit_text("The music box, now a garden, wraps vines around the clock.")
    plain = auditor.audit_text("The music box sits beside the clock in a dusty room.")
    assert melt.identity_melt_count >= 1
    assert melt.ontology_collapse_density > plain.ontology_collapse_density


def test_repair_pressure_detects_explanation():
    auditor = OntologyAuditor()
    repaired = auditor.audit_text("In other words, this symbolizes loneliness and gives the scene meaning.")
    image = auditor.audit_text("In other words, the umbrella was the lung of the sea.")
    assert repaired.repair_pressure > image.repair_pressure


def test_audit_run_files_accepts_write_run_json(tmp_path):
    p = tmp_path / "run.json"
    p.write_text(
        '{"seed":"A forgotten umbrella at the station","final_text":"x",'
        '"steps":[{"step":1,"picked":{"text":"The music box, now a garden, wraps vines around the clock."}}]}',
        encoding="utf-8",
    )
    report = audit_run_files([str(p)])
    assert len(report.runs) == 1
    assert report.runs[0].aggregate["total_identity_melt_count"] >= 1
