import importlib.util
import json
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_arxiv_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_arxiv_bundle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_bundle_rewrites_graphics_and_is_deterministic(tmp_path):
    paper = tmp_path / "paper"
    assets = tmp_path / "assets"
    paper.mkdir()
    assets.mkdir()
    figure = assets / "frontier_plot.png"
    figure.write_bytes(b"not-a-real-png-but-sufficient-for-the-bundler")
    source = paper / "draft.tex"
    source.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\begin{document}\n"
        "\\includegraphics[width=0.8\\linewidth]{../assets/frontier_plot.png}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    out_dir = paper / "arxiv_submission"
    archive = paper / "arxiv_submission.zip"
    first = MODULE.build_bundle(source, out_dir, archive, tmp_path)
    first_archive_hash = first["archive_sha256"]
    second = MODULE.build_bundle(source, out_dir, archive, tmp_path)

    assert first_archive_hash == second["archive_sha256"]
    assert "../" not in (out_dir / "main.tex").read_text(encoding="utf-8")
    assert (out_dir / "figures" / "frontier_plot.png").read_bytes() == figure.read_bytes()
    with zipfile.ZipFile(archive) as bundled:
        assert bundled.namelist() == ["figures/frontier_plot.png", "main.tex"]

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "depaysement-lab-arxiv-bundle-v1"
    assert manifest["files"]["main.tex"]


def test_build_bundle_rejects_external_tex_dependencies(tmp_path):
    source = tmp_path / "draft.tex"
    source.write_text("\\input{sections/results}\n", encoding="utf-8")

    try:
        MODULE.build_bundle(source, tmp_path / "out", tmp_path / "out.zip", tmp_path)
    except ValueError as error:
        assert "Unsupported external TeX dependencies" in str(error)
    else:
        raise AssertionError("external TeX dependency should be rejected")
