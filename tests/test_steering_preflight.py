from argparse import Namespace

import pytest

from depaysement_lab.cli import prepare_steering_args


def _args(tmp_path, **kw):
    base = dict(
        backend="mlx",
        model="mlx-community/Llama-3.2-3B-Instruct-4bit",
        vectors=str(tmp_path / "missing_vectors.npz"),
        steer_alpha=0.6,
        disable_steering=False,
        strict_steering=False,
        steer_layers="4-18",
        chat_template=True,
    )
    base.update(kw)
    return Namespace(**base)


def test_missing_mlx_vectors_disable_steering_without_crash(tmp_path):
    args = _args(tmp_path)
    prepare_steering_args(args, stream=None)
    assert args.vectors is None
    assert args.steer_alpha == 0.0
    assert "Steering vector file not found" in args._steering_preflight_note
    assert args._steering_preflight_usable is False


def test_missing_mlx_vectors_can_be_strict(tmp_path):
    args = _args(tmp_path, strict_steering=True)
    with pytest.raises(FileNotFoundError):
        prepare_steering_args(args, stream=None)


def test_mlx_vectors_resolve_npz_suffix(tmp_path):
    vec = tmp_path / "vectors.npz"
    vec.write_bytes(b"not a real npz, only preflight existence matters")
    args = _args(tmp_path, vectors=str(tmp_path / "vectors"))
    prepare_steering_args(args, stream=None)
    assert args.vectors == str(vec)
    assert args.steer_alpha == 0.6
    assert args._steering_preflight_usable is True
    assert args._steering_preflight_note is None


def test_unsupported_backend_disables_activation_steering(tmp_path):
    vec = tmp_path / "vectors.npz"
    vec.write_bytes(b"x")
    args = _args(tmp_path, backend="ollama", vectors=str(vec))
    prepare_steering_args(args, stream=None)
    assert args.vectors is None
    assert args.steer_alpha == 0.0
    assert "not available" in args._steering_preflight_note
