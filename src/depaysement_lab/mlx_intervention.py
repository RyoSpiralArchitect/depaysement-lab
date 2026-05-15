"""MLX-specific activation collection and steering.

This module deliberately avoids importing MLX at module import time so the rest of
Depaysement Lab remains dependency-free.  The implementation is based on a
"swap-and-restore" layer wrapper rather than PyTorch-style forward hooks: common
mlx-lm models expose a transformer block sequence such as ``model.model.layers``;
we temporarily replace selected entries with lightweight proxy objects that can
capture and/or edit the first hidden-state tensor returned by each block.

The module is intentionally conservative:

* vector collection runs one prompt at a time, avoiding padding/masking ambiguity;
* generation-time injection defaults to ``decode_only`` so the prompt prefill is
  not rewritten unless explicitly requested;
* vector files are MLX/NumPy-style ``.npz`` archives with a JSON sidecar for
	  metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from .proto_v2 import PromptBank


# -----------------------------------------------------------------------------
# Runtime config
# -----------------------------------------------------------------------------


@dataclass
class MLXSteeringRuntimeConfig:
    """Generation-time MLX activation steering options.

    Parameters
    ----------
    vectors_path:
        Path to an MLX ``.npz`` vector file produced by ``collect_mlx_steering_vectors``.
    alpha:
        Strength of ``h <- h + alpha * v_layer``.  Zero disables steering.
    layers:
        Optional 0-based transformer block indices.  If omitted, all layers
        present in the vector file are used.
    position:
        ``"last"`` applies the vector to the last sequence position only;
        ``"all"`` applies it to every position in the current forward pass.
    apply_on:
        ``"decode_only"`` applies only when sequence length is 1, matching the
        usual cached decoding step; ``"all"`` also steers the prompt prefill;
        ``"prefill_only"`` is useful for diagnostics.
    """

    vectors_path: Optional[str] = None
    alpha: float = 0.0
    layers: Optional[List[int]] = None
    position: str = "last"
    apply_on: str = "decode_only"

    def enabled(self) -> bool:
        return bool(self.vectors_path) and abs(float(self.alpha)) > 1e-12


# -----------------------------------------------------------------------------
# Layer sequence discovery and patching
# -----------------------------------------------------------------------------


@dataclass
class LayerSequenceRef:
    path: str
    container: Any

    def __len__(self) -> int:
        return len(self.container)

    def get(self, idx: int) -> Any:
        return self.container[idx]

    def set(self, idx: int, value: Any) -> None:
        try:
            self.container[idx] = value
        except TypeError as e:  # tuple or immutable module container
            raise TypeError(
                f"Layer container at {self.path!r} is not mutable; MLX intervention needs a mutable "
                "layer sequence so it can swap wrappers in and restore originals."
            ) from e


_COMMON_LAYER_PATHS: Tuple[str, ...] = (
    "model.layers",
    "model.model.layers",
    "model.decoder.layers",
    "model.transformer.layers",
    "model.transformer.h",
    "language_model.model.layers",
    "transformer.layers",
    "transformer.h",
    "decoder.layers",
    "layers",
    "blocks",
    "h",
)

_CONTAINER_ATTRS: Tuple[str, ...] = (
    "model",
    "language_model",
    "transformer",
    "decoder",
    "backbone",
    "gpt_neox",
    "inner_model",
)

_LAYER_ATTRS: Tuple[str, ...] = ("layers", "blocks", "h")


def _resolve_attr_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not hasattr(cur, part):
            raise AttributeError(path)
        cur = getattr(cur, part)
    return cur


def _looks_like_layer_sequence(x: Any) -> bool:
    if isinstance(x, (str, bytes, dict)):
        return False
    if not hasattr(x, "__len__") or not hasattr(x, "__getitem__"):
        return False
    try:
        n = len(x)
    except Exception:
        return False
    if n <= 0 or n > 4096:
        return False
    try:
        first = x[0]
    except Exception:
        return False
    return callable(first)


def find_mlx_layer_sequence(model: Any) -> LayerSequenceRef:
    """Find a mutable sequence of transformer blocks in a common mlx-lm model.

    The function prefers explicit mlx-lm-style paths, then does a shallow search
    over common container names.  It raises a clear error instead of guessing a
    bad sequence.
    """

    for path in _COMMON_LAYER_PATHS:
        try:
            candidate = _resolve_attr_path(model, path)
        except AttributeError:
            continue
        if _looks_like_layer_sequence(candidate):
            return LayerSequenceRef(path=path, container=candidate)

    # Shallow fallback: model.<container>.<layer_attr>
    for cattr in _CONTAINER_ATTRS:
        if not hasattr(model, cattr):
            continue
        container = getattr(model, cattr)
        for lattr in _LAYER_ATTRS:
            if not hasattr(container, lattr):
                continue
            candidate = getattr(container, lattr)
            if _looks_like_layer_sequence(candidate):
                return LayerSequenceRef(path=f"{cattr}.{lattr}", container=candidate)

    # One additional level catches model.model.decoder.layers, etc.
    for cattr in _CONTAINER_ATTRS:
        if not hasattr(model, cattr):
            continue
        container = getattr(model, cattr)
        for cattr2 in _CONTAINER_ATTRS:
            if not hasattr(container, cattr2):
                continue
            container2 = getattr(container, cattr2)
            for lattr in _LAYER_ATTRS:
                if not hasattr(container2, lattr):
                    continue
                candidate = getattr(container2, lattr)
                if _looks_like_layer_sequence(candidate):
                    return LayerSequenceRef(path=f"{cattr}.{cattr2}.{lattr}", container=candidate)

    raise RuntimeError(
        "Could not find transformer layers for MLX intervention. Tried common paths such as "
        "model.layers, model.model.layers, transformer.h, and decoder.layers. "
        "Pass a model whose layers are exposed as a mutable sequence, or add its path to "
        "_COMMON_LAYER_PATHS in mlx_intervention.py."
    )


@dataclass
class MLXCaptureStore:
    """Per-forward activation capture store."""

    captures: Dict[int, Any] = field(default_factory=dict)

    def clear(self) -> None:
        self.captures.clear()

    def capture(self, layer_idx: int, hidden: Any) -> None:
        self.captures[layer_idx] = hidden


def _split_first_hidden(output: Any) -> Tuple[Any, Any]:
    """Return first hidden-like output and a reconstruction callable."""

    if isinstance(output, tuple) and output:
        first = output[0]

        def rebuild(new_first: Any) -> tuple:
            return (new_first, *output[1:])

        return first, rebuild
    if isinstance(output, list) and output:
        first = output[0]

        def rebuild(new_first: Any) -> list:
            return [new_first, *output[1:]]

        return first, rebuild

    def rebuild_identity(new_first: Any) -> Any:
        return new_first

    return output, rebuild_identity


def _shape_of(x: Any) -> Tuple[int, ...]:
    shape = getattr(x, "shape", None)
    if shape is None:
        return ()
    try:
        return tuple(int(s) for s in shape)
    except Exception:
        return tuple(shape)


def _seq_len(hidden: Any) -> int:
    shape = _shape_of(hidden)
    if len(shape) >= 2:
        # hidden is normally [batch, seq, dim], but [seq, dim] also works.
        return int(shape[-2])
    return 1


def _should_apply(apply_on: str, hidden: Any) -> bool:
    seq = _seq_len(hidden)
    if apply_on == "all":
        return True
    if apply_on == "decode_only":
        return seq <= 1
    if apply_on == "prefill_only":
        return seq > 1
    raise ValueError(f"Unknown MLX steering apply_on={apply_on!r}; expected decode_only, all, or prefill_only")


def _import_mx():
    try:
        import mlx.core as mx  # type: ignore
    except Exception as e:  # pragma: no cover - platform/dependency-specific
        raise RuntimeError("MLX intervention requires Apple MLX packages: pip install mlx-lm") from e
    return mx


def _to_mx_vector(mx: Any, vector: Any, dtype: Any = None) -> Any:
    module = getattr(type(vector), "__module__", "")
    if module.startswith("mlx"):
        v = vector
    else:
        v = mx.array(vector)
    if dtype is not None and hasattr(v, "astype"):
        try:
            v = v.astype(dtype)
        except Exception:
            pass
    return v


def _apply_vector_to_hidden(mx: Any, hidden: Any, vector: Any, alpha: float, position: str, layer_idx: int) -> Any:
    h_shape = _shape_of(hidden)
    if not h_shape or len(h_shape) < 2:
        return hidden
    v = _to_mx_vector(mx, vector, getattr(hidden, "dtype", None))
    v_shape = _shape_of(v)
    if not v_shape:
        return hidden
    if int(v_shape[-1]) != int(h_shape[-1]):
        raise ValueError(
            f"MLX steering vector dimension mismatch at layer {layer_idx}: "
            f"hidden dim={h_shape[-1]}, vector dim={v_shape[-1]}"
        )
    # Broadcast over every non-hidden dimension: [D] -> [1, ..., 1, D]
    v = mx.reshape(v, (1,) * (len(h_shape) - 1) + (h_shape[-1],))
    delta = float(alpha) * v

    if position == "all":
        return hidden + delta
    if position != "last":
        raise ValueError(f"Unknown MLX steering position={position!r}; expected last or all")

    if _seq_len(hidden) <= 1:
        return hidden + delta
    # Sequence axis is the penultimate axis for both [B, T, D] and [T, D].
    prefix = hidden[..., :-1, :]
    last = hidden[..., -1:, :] + delta
    return mx.concatenate([prefix, last], axis=-2)


class MLXPatchedLayer:
    """Proxy object that captures and/or edits a single transformer block output."""

    def __init__(
        self,
        layer: Any,
        layer_idx: int,
        *,
        collector: Optional[MLXCaptureStore] = None,
        vector: Optional[Any] = None,
        alpha: float = 0.0,
        position: str = "last",
        apply_on: str = "decode_only",
    ):
        self._layer = layer
        self._layer_idx = int(layer_idx)
        self._collector = collector
        self._vector = vector
        self._alpha = float(alpha)
        self._position = position
        self._apply_on = apply_on

    def __getattr__(self, name: str) -> Any:
        return getattr(self._layer, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        output = self._layer(*args, **kwargs)
        hidden, rebuild = _split_first_hidden(output)
        if self._collector is not None:
            self._collector.capture(self._layer_idx, hidden)
        if self._vector is not None and abs(self._alpha) > 1e-12 and _should_apply(self._apply_on, hidden):
            mx = _import_mx()
            hidden = _apply_vector_to_hidden(mx, hidden, self._vector, self._alpha, self._position, self._layer_idx)
            output = rebuild(hidden)
        return output

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"MLXPatchedLayer(layer_idx={self._layer_idx}, layer={self._layer!r})"


class MLXLayerPatch:
    """Context manager that temporarily swaps transformer blocks with wrappers."""

    def __init__(
        self,
        model: Any,
        *,
        layers: Optional[Sequence[int]] = None,
        collector: Optional[MLXCaptureStore] = None,
        vectors: Optional[Mapping[int, Any]] = None,
        alpha: float = 0.0,
        position: str = "last",
        apply_on: str = "decode_only",
    ):
        self.model = model
        self.requested_layers = None if layers is None else sorted({int(x) for x in layers})
        self.collector = collector
        self.vectors = {int(k): v for k, v in (vectors or {}).items()}
        self.alpha = float(alpha)
        self.position = position
        self.apply_on = apply_on
        self.ref: Optional[LayerSequenceRef] = None
        self.originals: Dict[int, Any] = {}
        self.patched_layers: List[int] = []

    def _selected_layers(self, n_layers: int) -> List[int]:
        if self.requested_layers is not None:
            selected = self.requested_layers
        elif self.vectors:
            selected = sorted(self.vectors.keys())
        else:
            selected = list(range(n_layers))
        return [i for i in selected if 0 <= i < n_layers]

    def __enter__(self) -> "MLXLayerPatch":
        self.ref = find_mlx_layer_sequence(self.model)
        selected = self._selected_layers(len(self.ref))
        for idx in selected:
            vector = self.vectors.get(idx)
            # For generation-time steering, skip layers that have no vector.
            if self.vectors and vector is None and self.collector is None:
                continue
            original = self.ref.get(idx)
            wrapper = MLXPatchedLayer(
                original,
                idx,
                collector=self.collector,
                vector=vector,
                alpha=self.alpha,
                position=self.position,
                apply_on=self.apply_on,
            )
            self.originals[idx] = original
            self.ref.set(idx, wrapper)
            self.patched_layers.append(idx)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self.ref is not None:
            for idx, original in self.originals.items():
                self.ref.set(idx, original)
        self.originals.clear()
        self.patched_layers.clear()
        return False


# -----------------------------------------------------------------------------
# Tokenization / capture / vector collection
# -----------------------------------------------------------------------------


def _apply_chat_template_if_needed(tokenizer: Any, text: str, chat_template: bool) -> str:
    if not chat_template:
        return text
    tmpl = getattr(tokenizer, "apply_chat_template", None)
    if tmpl is None:
        return text
    try:
        return tmpl([{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True)
    except TypeError:
        # Some tokenizers do not expose tokenize=; fall back to prior mlx-lm README style.
        rendered = tmpl([{"role": "user", "content": text}], add_generation_prompt=True)
        if isinstance(rendered, str):
            return rendered
        return text


def encode_prompt_mlx(
    tokenizer: Any,
    text: str,
    *,
    chat_template: bool = False,
    max_length: Optional[int] = None,
) -> Any:
    """Encode a prompt as an MLX int32 array with shape [1, seq]."""

    mx = _import_mx()
    rendered = _apply_chat_template_if_needed(tokenizer, text, chat_template)
    ids: Any
    if hasattr(tokenizer, "encode"):
        try:
            ids = tokenizer.encode(rendered, add_special_tokens=True)
        except TypeError:
            ids = tokenizer.encode(rendered)
    else:
        encoded = tokenizer(rendered, add_special_tokens=True)
        ids = encoded["input_ids"] if isinstance(encoded, Mapping) else encoded
    if hasattr(ids, "tolist"):
        ids = ids.tolist()
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    ids = [int(x) for x in ids]
    if max_length is not None and max_length > 0 and len(ids) > max_length:
        ids = ids[-int(max_length) :]
    if not ids:
        raise ValueError("Tokenizer produced an empty prompt; cannot collect MLX activations")
    return mx.array([ids], dtype=mx.int32)


def _array_leaves(x: Any) -> List[Any]:
    if hasattr(x, "shape") and hasattr(x, "dtype"):
        return [x]
    if isinstance(x, (tuple, list)):
        out: List[Any] = []
        for item in x:
            out.extend(_array_leaves(item))
        return out
    if isinstance(x, dict):
        out = []
        for item in x.values():
            out.extend(_array_leaves(item))
        return out
    return []


def capture_prompt_hidden_mlx(
    model: Any,
    tokenizer: Any,
    prompt: str,
    *,
    layers: Optional[Sequence[int]] = None,
    chat_template: bool = False,
    max_length: Optional[int] = None,
) -> Dict[int, Any]:
    """Run one prompt and capture selected block outputs."""

    mx = _import_mx()
    collector = MLXCaptureStore()
    input_ids = encode_prompt_mlx(tokenizer, prompt, chat_template=chat_template, max_length=max_length)
    with MLXLayerPatch(model, layers=layers, collector=collector):
        output = model(input_ids)
        leaves = _array_leaves(output) + list(collector.captures.values())
        if leaves:
            mx.eval(*leaves)
    return dict(collector.captures)


def _pool_hidden_mlx(mx: Any, hidden: Any, token_strategy: str) -> Any:
    shape = _shape_of(hidden)
    if len(shape) < 2:
        raise ValueError(f"Expected hidden state with rank >=2, got shape={shape}")
    if token_strategy == "last":
        pooled = hidden[..., -1, :]
        # Remove batch or extra axes by averaging everything except hidden dim.
        if len(_shape_of(pooled)) > 1:
            pooled = mx.mean(pooled, axis=tuple(range(len(_shape_of(pooled)) - 1)))
        return pooled.astype(mx.float32)
    if token_strategy == "mean":
        axes = tuple(range(len(shape) - 1))
        return mx.mean(hidden, axis=axes).astype(mx.float32)
    raise ValueError(f"Unknown token_strategy={token_strategy!r}; expected mean or last")


def hidden_means_mlx(
    model: Any,
    tokenizer: Any,
    prompts: Sequence[str],
    *,
    layers: Optional[Sequence[int]] = None,
    token_strategy: str = "mean",
    chat_template: bool = False,
    max_length: Optional[int] = None,
    verbose: bool = False,
) -> Dict[int, Any]:
    """Compute per-layer mean activations for a set of prompts."""

    mx = _import_mx()
    sums: Dict[int, Any] = {}
    counts: Dict[int, int] = {}
    prompts = [p for p in prompts if str(p).strip()]
    if not prompts:
        raise ValueError("No prompts supplied for MLX hidden mean collection")
    for i, prompt in enumerate(prompts, 1):
        if verbose:
            print(f"[mlx collect] {i}/{len(prompts)} {prompt[:72]}")
        captures = capture_prompt_hidden_mlx(
            model,
            tokenizer,
            prompt,
            layers=layers,
            chat_template=chat_template,
            max_length=max_length,
        )
        for layer_idx, hidden in captures.items():
            pooled = _pool_hidden_mlx(mx, hidden, token_strategy)
            if layer_idx not in sums:
                sums[layer_idx] = pooled
                counts[layer_idx] = 1
            else:
                sums[layer_idx] = sums[layer_idx] + pooled
                counts[layer_idx] += 1
        if captures:
            mx.eval(*sums.values())
    if not sums:
        raise RuntimeError("No MLX activations were captured; layer discovery may have failed")
    means = {layer_idx: sums[layer_idx] / max(counts[layer_idx], 1) for layer_idx in sorted(sums)}
    mx.eval(*means.values())
    return means


# -----------------------------------------------------------------------------
# Vector file IO
# -----------------------------------------------------------------------------


def _npz_path(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix != ".npz":
        p = Path(str(p) + ".npz")
    return p


def _resolve_npz_path(path: str | Path) -> Path:
    p = Path(path)
    if p.exists():
        return p
    p2 = _npz_path(p)
    if p2.exists():
        return p2
    return p


def _metadata_path(npz_path: Path) -> Path:
    return Path(str(npz_path) + ".json")


def save_mlx_steering_vectors(
    path: str | Path,
    vectors: Mapping[int, Any],
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Save layer vectors as ``layer_<idx>`` arrays in an ``.npz`` file."""

    mx = _import_mx()
    out = _npz_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    arrays = {f"layer_{int(layer_idx)}": vector for layer_idx, vector in vectors.items()}
    if not arrays:
        raise ValueError("No MLX steering vectors to save")
    mx.savez(str(out), **arrays)
    meta = dict(metadata or {})
    meta.setdefault("format", "depaysement_lab.mlx_steering_vectors.v1")
    meta.setdefault("vector_keys", sorted(arrays))
    _metadata_path(out).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_mlx_steering_vectors(path: str | Path) -> Dict[int, Any]:
    """Load MLX steering vectors from an ``.npz`` archive."""

    mx = _import_mx()
    p = _resolve_npz_path(path)
    if not p.exists():
        raise FileNotFoundError(f"MLX steering vector file not found: {path}")
    data = mx.load(str(p))
    if not isinstance(data, MutableMapping):
        raise ValueError(f"Expected {p} to contain a dict-like NPZ archive, got {type(data).__name__}")
    vectors: Dict[int, Any] = {}
    for key, value in data.items():
        if not str(key).startswith("layer_"):
            continue
        layer_idx = int(str(key).split("_", 1)[1])
        vectors[layer_idx] = value
    if not vectors:
        raise ValueError(f"No layer_<idx> vectors found in {p}")
    return vectors


def collect_mlx_steering_vectors(
    *,
    model_name: str,
    bank: PromptBank,
    out_path: str | Path,
    layers: Optional[Sequence[int]] = None,
    token_strategy: str = "mean",
    chat_template: bool = False,
    tokenizer_config: Optional[Mapping[str, Any]] = None,
    trust_remote_code: bool = False,
    max_length: Optional[int] = None,
    verbose: bool = False,
) -> Path:
    """Collect positive-minus-negative MLX steering vectors and save them.

    The vector definition mirrors the Hugging Face path:

    ``v_l = mean_hidden_l(positive_depaysement) - mean_hidden_l(negative_repair/noise)``

    then each vector is unit-normalized before saving.
    """

    try:
        from mlx_lm import load  # type: ignore
    except Exception as e:  # pragma: no cover - platform/dependency-specific
        raise RuntimeError("MLX vector collection requires mlx-lm: pip install mlx-lm") from e
    mx = _import_mx()

    kwargs: Dict[str, Any] = {}
    if tokenizer_config:
        kwargs["tokenizer_config"] = dict(tokenizer_config)
    if trust_remote_code:
        kwargs.setdefault("tokenizer_config", {})["trust_remote_code"] = True
    model, tokenizer = load(model_name, **kwargs)

    # Validate discovery early and clip requested layer list to actual depth.
    layer_ref = find_mlx_layer_sequence(model)
    n_layers = len(layer_ref)
    if layers is None:
        selected = list(range(n_layers))
    else:
        selected = [int(x) for x in layers if 0 <= int(x) < n_layers]
    if not selected:
        raise ValueError(f"No valid MLX layers selected. Model has {n_layers} layers; requested={layers}")

    pos_prompts = list(bank.positive_depaysement)
    neg_prompts = list(bank.negative_realist_repair) + list(bank.negative_weird_noise)
    if not pos_prompts or not neg_prompts:
        raise ValueError("Prompt bank must contain positive_depaysement and negative prompts")

    if verbose:
        print(f"[mlx collect] model={model_name}")
        print(f"[mlx collect] layer_path={layer_ref.path} n_layers={n_layers} selected={selected}")
        print(f"[mlx collect] positives={len(pos_prompts)} negatives={len(neg_prompts)} strategy={token_strategy}")

    pos_means = hidden_means_mlx(
        model,
        tokenizer,
        pos_prompts,
        layers=selected,
        token_strategy=token_strategy,
        chat_template=chat_template,
        max_length=max_length,
        verbose=verbose,
    )
    neg_means = hidden_means_mlx(
        model,
        tokenizer,
        neg_prompts,
        layers=selected,
        token_strategy=token_strategy,
        chat_template=chat_template,
        max_length=max_length,
        verbose=verbose,
    )

    vectors: Dict[int, Any] = {}
    norms: Dict[int, float] = {}
    for layer_idx in selected:
        if layer_idx not in pos_means or layer_idx not in neg_means:
            continue
        v = pos_means[layer_idx] - neg_means[layer_idx]
        norm_arr = mx.sqrt(mx.sum(v * v))
        mx.eval(norm_arr)
        norm = float(norm_arr.item())
        norms[layer_idx] = norm
        if norm > 1e-12:
            v = v / norm_arr
        vectors[layer_idx] = v.astype(mx.float32)
    if not vectors:
        raise RuntimeError("No MLX steering vectors were computed")

    metadata = {
        "model_name": model_name,
        "token_strategy": token_strategy,
        "num_positive": len(pos_prompts),
        "num_negative": len(neg_prompts),
        "layer_path": layer_ref.path,
        "n_layers": n_layers,
        "selected_layers": sorted(vectors),
        "norms_before_unit_normalization": {str(k): v for k, v in norms.items()},
        "position_default": "last",
        "apply_on_default": "decode_only",
    }
    return save_mlx_steering_vectors(out_path, vectors, metadata=metadata)
