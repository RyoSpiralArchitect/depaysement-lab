import json

import numpy as np

from depaysement_lab.vector_geometry import (
    factorize_vector_archives,
    load_vector_archive,
    parse_named_float,
    parse_named_path,
    project_from_subspace,
)


def _write_archive(path, layers):
    np.savez(path, **{f"layer_{layer}": vector for layer, vector in layers.items()})


def test_named_specs_and_projection():
    assert parse_named_path("transition=vectors.npz") == ("transition", "vectors.npz")
    assert parse_named_float("anchor=0.25") == ("anchor", 0.25)

    projected, report = project_from_subspace(
        np.asarray([1.0, 1.0, 0.0]),
        [np.asarray([1.0, 0.0, 0.0])],
    )

    assert np.allclose(projected, [0.0, 1.0, 0.0], atol=1e-6)
    assert report["nuisance_rank"] == 1
    assert np.isclose(report["retained_norm_ratio"], 1.0 / np.sqrt(2.0))


def test_factorized_archives_are_runtime_compatible(tmp_path):
    transition = tmp_path / "transition.npz"
    hygiene = tmp_path / "hygiene.npz"
    anchor = tmp_path / "anchor.npz"
    _write_archive(
        transition,
        {
            6: np.asarray([1.0, 1.0, 0.0]),
            7: np.asarray([1.0, 0.0, 1.0]),
        },
    )
    _write_archive(
        hygiene,
        {
            6: np.asarray([1.0, 0.0, 0.0]),
            7: np.asarray([1.0, 0.0, 0.0]),
        },
    )
    _write_archive(
        anchor,
        {
            6: np.asarray([0.0, 0.0, 1.0]),
            7: np.asarray([0.0, 1.0, 0.0]),
        },
    )

    report = factorize_vector_archives(
        component_paths={
            "transition": transition,
            "hygiene": hygiene,
            "anchor": anchor,
        },
        target_name="transition",
        project_out=["hygiene"],
        coefficients={"anchor": 0.5},
        out_projected=tmp_path / "projected.npz",
        out_composed=tmp_path / "composed.npz",
        out_random=tmp_path / "random.npz",
        report_dir=tmp_path / "report",
        random_seed=17,
    )

    projected = load_vector_archive("projected", tmp_path / "projected.npz")
    composed = load_vector_archive("composed", tmp_path / "composed.npz")
    assert np.allclose(projected.vectors[6], [0.0, 1.0, 0.0], atol=1e-6)
    assert np.allclose(composed.vectors[6], [0.0, 2.0 / np.sqrt(5.0), 1.0 / np.sqrt(5.0)])
    assert np.isclose(np.linalg.norm(composed.vectors[7]), 1.0)
    assert report["common_layers"] == [6, 7]
    assert (tmp_path / "random.npz.json").exists()
    payload = json.loads((tmp_path / "report" / "factorized_vector_geometry.json").read_text())
    assert payload["target"] == "transition"
    assert (tmp_path / "report" / "factorized_vector_cosine.png").exists()
