from depaysement_lab.mlx_intervention import MLXCaptureStore, MLXLayerPatch, find_mlx_layer_sequence


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
