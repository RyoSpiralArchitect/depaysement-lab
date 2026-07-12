#!/usr/bin/env python3
"""Build a deterministic, self-contained arXiv source bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


GRAPHICS_RE = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)([^}]+)(\})")
EXTERNAL_TEX_RE = re.compile(
    r"\\(?:input|include|bibliography|addbibresource)(?:\[[^\]]*\])?\{([^}]+)\}"
)
PORTABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_+.,=/\-]+$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def write_deterministic_zip(archive_path: Path, files: list[tuple[Path, str]]) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_name in sorted(files, key=lambda item: item[1]):
            if not PORTABLE_NAME_RE.fullmatch(archive_name):
                raise ValueError(f"arXiv-incompatible archive path: {archive_name}")
            info = zipfile.ZipInfo(archive_name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())


def build_bundle(
    tex_path: Path,
    out_dir: Path,
    archive_path: Path,
    repo_root: Path,
) -> dict[str, object]:
    tex_path = tex_path.resolve()
    out_dir = out_dir.resolve()
    archive_path = archive_path.resolve()
    repo_root = repo_root.resolve()

    if not tex_path.is_file():
        raise FileNotFoundError(f"TeX source not found: {tex_path}")
    if tex_path.is_relative_to(out_dir):
        raise ValueError("Output directory cannot contain the source TeX file")

    source_text = tex_path.read_text(encoding="utf-8")
    external_dependencies = EXTERNAL_TEX_RE.findall(source_text)
    if external_dependencies:
        joined = ", ".join(external_dependencies)
        raise ValueError(f"Unsupported external TeX dependencies: {joined}")

    source_to_target: dict[Path, Path] = {}
    target_to_source: dict[Path, Path] = {}

    def replace_graphic(match: re.Match[str]) -> str:
        raw_path = match.group(2).strip()
        source = (tex_path.parent / raw_path).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Referenced figure not found: {raw_path} -> {source}")

        target = Path("figures") / source.name
        previous = target_to_source.get(target)
        if previous is not None and previous != source:
            target = Path("figures") / f"{source.stem}_{sha256_path(source)[:8]}{source.suffix}"

        source_to_target[source] = target
        target_to_source[target] = source
        return f"{match.group(1)}{target.as_posix()}{match.group(3)}"

    bundled_text = GRAPHICS_RE.sub(replace_graphic, source_text)
    if "../" in bundled_text:
        raise ValueError("Bundle still contains a parent-relative path")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "figures").mkdir(parents=True)

    bundled_tex = out_dir / "main.tex"
    bundled_tex.write_text(bundled_text, encoding="utf-8")
    for source, target in source_to_target.items():
        destination = out_dir / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    archive_files = [(bundled_tex, "main.tex")]
    archive_files.extend((out_dir / target, target.as_posix()) for target in target_to_source)
    write_deterministic_zip(archive_path, archive_files)

    file_hashes = {
        archive_name: sha256_path(source)
        for source, archive_name in sorted(archive_files, key=lambda item: item[1])
    }
    manifest: dict[str, object] = {
        "format": "depaysement-lab-arxiv-bundle-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository_commit": git_commit(repo_root),
        "source_tex": str(tex_path.relative_to(repo_root)),
        "source_tex_sha256": sha256_path(tex_path),
        "archive": archive_path.name,
        "archive_sha256": sha256_path(archive_path),
        "files": file_hashes,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex", type=Path, help="Main local TeX manuscript")
    parser.add_argument("--out-dir", type=Path, required=True, help="Bundle directory")
    parser.add_argument("--archive", type=Path, required=True, help="Output zip archive")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_bundle(args.tex, args.out_dir, args.archive, args.repo_root)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
