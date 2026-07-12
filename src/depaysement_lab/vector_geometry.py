"""Layer-wise geometry and offline composition for MLX steering vectors."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class VectorArchive:
    name: str
    path: Path
    vectors: Mapping[int, np.ndarray]
    metadata: Mapping[str, Any]


def parse_named_path(spec: str) -> Tuple[str, str]:
    name, separator, path = str(spec).partition("=")
    if not separator or not name.strip() or not path.strip():
        raise ValueError(f"Expected NAME=PATH, got {spec!r}")
    return name.strip(), path.strip()


def parse_named_float(spec: str) -> Tuple[str, float]:
    name, raw_value = parse_named_path(spec)
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"Expected NAME=FLOAT, got {spec!r}") from exc
    return name, value


def load_vector_archive(name: str, path: str | Path) -> VectorArchive:
    archive_path = _resolve_npz_path(path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Vector archive not found: {path}")
    with np.load(archive_path, allow_pickle=False) as payload:
        vectors = {
            int(key.split("_", 1)[1]): np.asarray(payload[key], dtype=np.float64).reshape(-1)
            for key in payload.files
            if key.startswith("layer_")
        }
    if not vectors:
        raise ValueError(f"No layer_<idx> vectors found in {archive_path}")
    metadata_path = Path(str(archive_path) + ".json")
    metadata: Mapping[str, Any] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return VectorArchive(name=name, path=archive_path, vectors=vectors, metadata=metadata)


def common_vector_layers(archives: Mapping[str, VectorArchive]) -> Tuple[int, ...]:
    if not archives:
        raise ValueError("At least one component archive is required")
    common = set.intersection(*(set(archive.vectors) for archive in archives.values()))
    if not common:
        raise ValueError("Component archives have no common layers")
    layers = tuple(sorted(common))
    for layer in layers:
        dimensions = {archive.vectors[layer].shape for archive in archives.values()}
        if len(dimensions) != 1:
            detail = {name: archive.vectors[layer].shape for name, archive in archives.items()}
            raise ValueError(f"Layer {layer} dimensions differ: {detail}")
    return layers


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denominator)


def unit_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a near-zero vector")
    return np.asarray(vector / norm, dtype=np.float32)


def project_from_subspace(
    target: np.ndarray,
    nuisance_vectors: Sequence[np.ndarray],
    *,
    rank_tolerance: float = 1e-8,
) -> Tuple[np.ndarray, Dict[str, float]]:
    target_array = np.asarray(target, dtype=np.float64).reshape(-1)
    target_norm = float(np.linalg.norm(target_array))
    if target_norm <= 1e-12:
        raise ValueError("Target vector is near zero")
    if not nuisance_vectors:
        return unit_vector(target_array), {
            "target_norm": target_norm,
            "projected_norm": target_norm,
            "retained_norm_ratio": 1.0,
            "nuisance_rank": 0,
        }
    matrix = np.column_stack([np.asarray(vector, dtype=np.float64).reshape(-1) for vector in nuisance_vectors])
    if matrix.shape[0] != target_array.shape[0]:
        raise ValueError("Target and nuisance vector dimensions differ")
    left, singular_values, _ = np.linalg.svd(matrix, full_matrices=False)
    scale = float(singular_values[0]) if singular_values.size else 0.0
    rank = int(np.sum(singular_values > max(rank_tolerance, scale * rank_tolerance)))
    basis = left[:, :rank]
    projected = target_array - basis @ (basis.T @ target_array) if rank else target_array.copy()
    projected_norm = float(np.linalg.norm(projected))
    if projected_norm <= 1e-8:
        raise ValueError("Projection removed the target vector almost entirely")
    return unit_vector(projected), {
        "target_norm": target_norm,
        "projected_norm": projected_norm,
        "retained_norm_ratio": projected_norm / target_norm,
        "nuisance_rank": rank,
    }


def factorize_vector_archives(
    *,
    component_paths: Mapping[str, str | Path],
    target_name: str,
    project_out: Sequence[str],
    coefficients: Mapping[str, float],
    out_projected: str | Path,
    out_composed: str | Path,
    report_dir: str | Path,
    out_random: Optional[str | Path] = None,
    random_seed: int = 20260713,
) -> Dict[str, Any]:
    archives = {name: load_vector_archive(name, path) for name, path in component_paths.items()}
    if target_name not in archives:
        raise ValueError(f"Unknown target component {target_name!r}")
    missing_nuisance = [name for name in project_out if name not in archives]
    if missing_nuisance:
        raise ValueError(f"Unknown project-out components: {', '.join(missing_nuisance)}")
    missing_support = [name for name in coefficients if name not in archives]
    if missing_support:
        raise ValueError(f"Unknown coefficient components: {', '.join(missing_support)}")
    layers = common_vector_layers(archives)
    projected_vectors: Dict[int, np.ndarray] = {}
    composed_vectors: Dict[int, np.ndarray] = {}
    random_vectors: Dict[int, np.ndarray] = {}
    projection_rows = []
    rng = np.random.default_rng(random_seed)

    for layer in layers:
        target = archives[target_name].vectors[layer]
        projected, projection = project_from_subspace(
            target,
            [archives[name].vectors[layer] for name in project_out],
        )
        composed = np.asarray(projected, dtype=np.float64)
        for name, coefficient in coefficients.items():
            composed += float(coefficient) * np.asarray(unit_vector(archives[name].vectors[layer]))
        projected_vectors[layer] = projected
        composed_vectors[layer] = unit_vector(composed)
        random_vectors[layer] = unit_vector(rng.normal(size=target.shape[0]))
        projection_rows.append({"layer": layer, **projection})

    cosine_rows = _cosine_rows(archives, layers)
    mean_cosines = _mean_cosine_matrix(cosine_rows, tuple(archives))
    metadata = {
        "format": "depaysement_lab.factorized_mlx_steering_vectors.v1",
        "target": target_name,
        "project_out": list(project_out),
        "coefficients": {name: float(value) for name, value in coefficients.items()},
        "component_paths": {name: str(archive.path) for name, archive in archives.items()},
        "common_layers": list(layers),
        "interpretation_boundary": (
            "Layer-wise orthogonalization is an intervention on measured directions, not evidence that "
            "the named functions are causally independent in the model."
        ),
    }
    projected_path = save_numpy_vector_archive(
        out_projected,
        projected_vectors,
        metadata={**metadata, "artifact": "projected_target"},
    )
    composed_path = save_numpy_vector_archive(
        out_composed,
        composed_vectors,
        metadata={**metadata, "artifact": "projected_target_plus_support"},
    )
    random_path = None
    if out_random:
        random_path = save_numpy_vector_archive(
            out_random,
            random_vectors,
            metadata={
                **metadata,
                "artifact": "unit_norm_random_control",
                "random_seed": int(random_seed),
            },
        )
    report = {
        **metadata,
        "outputs": {
            "projected": str(projected_path),
            "composed": str(composed_path),
            "random": str(random_path or ""),
        },
        "mean_cosine_matrix": mean_cosines,
        "layer_cosines": cosine_rows,
        "projection": projection_rows,
        "mean_retained_norm_ratio": float(
            np.mean([row["retained_norm_ratio"] for row in projection_rows])
        ),
    }
    write_vector_geometry_report(report, report_dir)
    return report


def save_numpy_vector_archive(
    path: str | Path,
    vectors: Mapping[int, np.ndarray],
    *,
    metadata: Mapping[str, Any],
) -> Path:
    out = _npz_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    arrays = {f"layer_{layer}": np.asarray(vector, dtype=np.float32) for layer, vector in vectors.items()}
    if not arrays:
        raise ValueError("No vectors to save")
    np.savez(out, **arrays)
    digest = _sha256_file(out)
    payload = dict(metadata)
    payload["vector_keys"] = sorted(arrays)
    payload["archive_sha256"] = digest
    Path(str(out) + ".json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    Path(str(out) + ".sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    return out


def write_vector_geometry_report(report: Mapping[str, Any], report_dir: str | Path) -> Dict[str, str]:
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "factorized_vector_geometry.json"
    csv_path = out / "factorized_vector_geometry.csv"
    markdown_path = out / "factorized_vector_geometry.md"
    plot_path = out / "factorized_vector_cosine.png"
    json_path.write_text(json.dumps(dict(report), indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["layer", "left", "right", "cosine"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report.get("layer_cosines", []))
    markdown_path.write_text(_format_vector_geometry_report(report), encoding="utf-8")
    _write_cosine_plot(report, plot_path)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
        "plot": str(plot_path),
    }


def _cosine_rows(
    archives: Mapping[str, VectorArchive],
    layers: Sequence[int],
) -> list[Dict[str, Any]]:
    names = tuple(archives)
    rows = []
    for layer in layers:
        for left_index, left in enumerate(names):
            for right in names[left_index:]:
                rows.append(
                    {
                        "layer": int(layer),
                        "left": left,
                        "right": right,
                        "cosine": cosine_similarity(
                            archives[left].vectors[layer],
                            archives[right].vectors[layer],
                        ),
                    }
                )
    return rows


def _mean_cosine_matrix(
    rows: Sequence[Mapping[str, Any]],
    names: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    values: Dict[Tuple[str, str], list[float]] = {}
    for row in rows:
        key = tuple(sorted((str(row["left"]), str(row["right"]))))
        values.setdefault(key, []).append(float(row["cosine"]))
    return {
        left: {
            right: float(np.mean(values[tuple(sorted((left, right)))]))
            for right in names
        }
        for left in names
    }


def _format_vector_geometry_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Factorized Steering Vector Geometry",
        "",
        f"Target: `{report.get('target', '')}`",
        f"Projected out: `{', '.join(report.get('project_out', [])) or 'none'}`",
        f"Common layers: `{report.get('common_layers', [])}`",
        f"Mean retained target norm: `{float(report.get('mean_retained_norm_ratio', 0.0)):.3f}`",
        "",
        "## Support Coefficients",
        "",
        "| component | coefficient |",
        "|---|---:|",
    ]
    coefficients = report.get("coefficients", {})
    if coefficients:
        lines.extend(f"| {name} | {float(value):.3f} |" for name, value in coefficients.items())
    else:
        lines.append("| none | 0.000 |")
    matrix = report.get("mean_cosine_matrix", {})
    names = list(matrix)
    lines.extend(
        [
            "",
            "## Mean Layer-wise Cosine",
            "",
            "| component | " + " | ".join(names) + " |",
            "|---|" + "---:|" * len(names),
        ]
    )
    for left in names:
        lines.append(
            f"| {left} | " + " | ".join(f"{float(matrix[left][right]):.3f}" for right in names) + " |"
        )
    lines.extend(
        [
            "",
            "## Projection By Layer",
            "",
            "| layer | nuisance rank | retained target norm |",
            "|---:|---:|---:|",
        ]
    )
    for row in report.get("projection", []):
        lines.append(
            f"| {int(row['layer'])} | {int(row['nuisance_rank'])} | "
            f"{float(row['retained_norm_ratio']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            str(report.get("interpretation_boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _write_cosine_plot(report: Mapping[str, Any], path: Path) -> None:
    import matplotlib.pyplot as plt

    matrix = report.get("mean_cosine_matrix", {})
    names = list(matrix)
    values = np.asarray([[float(matrix[left][right]) for right in names] for left in names])
    size = max(5.5, 1.05 * len(names) + 2.5)
    figure, axis = plt.subplots(figsize=(size, size))
    image = axis.imshow(values, cmap="coolwarm", vmin=-1.0, vmax=1.0)
    axis.set_xticks(range(len(names)), names, rotation=35, ha="right")
    axis.set_yticks(range(len(names)), names)
    axis.set_title("Mean layer-wise steering-vector cosine")
    for row_index in range(len(names)):
        for column_index in range(len(names)):
            value = values[row_index, column_index]
            color = "white" if abs(value) > 0.55 else "black"
            axis.text(column_index, row_index, f"{value:.2f}", ha="center", va="center", color=color)
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04, label="cosine")
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _resolve_npz_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.exists():
        return candidate
    with_suffix = _npz_path(candidate)
    return with_suffix


def _npz_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.suffix == ".npz" else Path(str(candidate) + ".npz")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
