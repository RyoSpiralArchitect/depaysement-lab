from depaysement_lab.mlx_intervention import (
    MLXCaptureStore,
    MLXLayerPatch,
    _checksum_path,
    _sha256_file,
    find_mlx_layer_sequence,
)


class FakeLayer:
    def __init__(self, idx):
        self.idx = idx

    def __call__(self, h):
        return (h + [self.idx], f"kv{self.idx}")


class FakeInner:
    def __init__(self):
        self.layers = [FakeLayer(0), FakeLayer(1), FakeLayer(2)]


class FakeModel:
    def __init__(self):
        self.model = FakeInner()

    def __call__(self, h):
        for layer in self.model.layers:
            out = layer(h)
            h = out[0] if isinstance(out, tuple) else out
        return h


def test_find_mlx_layer_sequence_prefers_model_layers():
    model = FakeModel()
    ref = find_mlx_layer_sequence(model)
    assert ref.path == "model.layers"
    assert len(ref) == 3


def test_layer_patch_captures_and_restores():
    model = FakeModel()
    original = list(model.model.layers)
    collector = MLXCaptureStore()
    with MLXLayerPatch(model, layers=[1], collector=collector) as patch:
        assert patch.patched_layers == [1]
        out = model([])
        assert out == [0, 1, 2]
        assert collector.captures[1] == [0, 1]
    assert model.model.layers == original


def test_checksum_helpers_are_npz_sidecars(tmp_path):
    path = tmp_path / "vectors.npz"
    path.write_bytes(b"depaysement-vector-bytes")
    expected = "10f4bb9591cf081c1c8a989c142829d844376571beccb154a544c059d4aaf4cd"

    assert _sha256_file(path) == expected
    assert _checksum_path(path) == tmp_path / "vectors.npz.sha256"
