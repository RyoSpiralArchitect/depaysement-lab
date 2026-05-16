#!/usr/bin/env python3
"""
Depaysement prototype v2
========================

本丸: デペイズマンを「高エントロピー生成」ではなく、
  - 異質な概念領域の隣接
  - 像として成立する関係構文
  - 現実修復 / 説明癖の抑制
  - 核イメージの残響と揺らぎ
  - positive / negative prompt bank による contrastive steering
として扱う。

v1 からの主な変更:
  1. keyword stuffing 対策: lexicon は弱い anchor に降格。raw count ではなく capped unique hits + stuffing penalty。
     さらに prompt bank contrast を追加し、例ベースの方向に逃がせる。
  2. 「ただ変な文」対策: image schema scoring を追加。
     空間・接触・所有/部分・変化・包含・交換の関係構文があると加点。
  3. context overlap penalty を廃止し、anchor resonance に変更。
     前文の核イメージを少し残すと加点、残しすぎ/捨てすぎは罰する。
  4. repair phrase を文脈化。
     「つまり」が説明/解釈に向かう時は罰し、作品内の声/接続詞として像を開く時は voice hinge として保持。
  5. positive / negative prompt bank expansion と、HF hidden-state steering vector 収集・注入を追加。

Dependency-free dummy run:
  python depaysement_proto_v2.py write --backend dummy --seed "A forgotten umbrella at the station" --steps 4 --trace

Rank one step:
  python depaysement_proto_v2.py rank --backend dummy --seed "A forgotten umbrella at the station" --candidates 12

Expand prompt bank:
  python depaysement_proto_v2.py expand-bank --backend dummy --out /mnt/data/depaysement_bank.json --positive 16 --negative 12

Collect layer-wise steering vectors with a local/remote Hugging Face model:
  python depaysement_proto_v2.py collect-vectors --model gpt2 --bank /mnt/data/depaysement_bank.json --out /mnt/data/depaysement_vectors.pt

Generate with activation steering:
  python depaysement_proto_v2.py write --backend hf --model gpt2 --vectors /mnt/data/depaysement_vectors.pt \
    --steer-alpha 1.2 --steer-layers 4,5,6,7 --seed "A forgotten umbrella at the station" --trace

Notes:
  - HF backend imports torch/transformers lazily. Dummy mode has no external dependencies.
  - Activation hooks are written generically for common CausalLM architectures, but some models may need layer-path tuning.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# -----------------------------------------------------------------------------
# Concept fields: weak anchors, not the whole scoring system.
# -----------------------------------------------------------------------------

DEFAULT_CONCEPT_FIELDS: Dict[str, List[str]] = {
    # English-first defaults. Japanese anchors were useful for the first prototype, but
    # small local models often degrade into semantic collage in Japanese. Keep the
    # default bank/vector geometry in English; load a Japanese lexicon explicitly when needed.
    "body": [
        "body", "eye", "eyes", "mouth", "tongue", "tooth", "teeth", "bone", "skin", "hair",
        "hand", "hands", "finger", "foot", "feet", "ear", "stomach", "lung", "lungs", "heart",
        "blood", "throat", "eyelid", "rib", "spine", "vein", "breath", "face",
    ],
    "architecture": [
        "station", "corridor", "room", "staircase", "stairs", "window", "door", "bridge", "city",
        "roof", "wall", "tower", "hospital", "theater", "hotel", "basement", "ceiling", "floor",
        "platform", "street", "hallway", "house", "apartment", "museum", "kitchen", "gate",
    ],
    "nature": [
        "sea", "rain", "moon", "sand", "forest", "fish", "bird", "snake", "cloud", "flower",
        "shell", "lake", "snow", "wind", "star", "volcano", "moss", "tide", "wave", "night",
        "river", "salt", "fog", "ash", "garden", "root", "leaf", "weather",
    ],
    "machine": [
        "elevator", "refrigerator", "fridge", "clock", "telephone", "radio", "train", "machine",
        "circuit", "signal", "bulb", "engine", "screen", "keyboard", "printer", "camera",
        "speaker", "wire", "switch", "lamp", "typewriter", "turnstile", "fan",
    ],
    "domestic": [
        "umbrella", "chair", "desk", "table", "key", "shoe", "shoes", "mirror", "bed", "plate",
        "curtain", "spoon", "coat", "bag", "drawer", "cup", "glass", "cabinet", "pillow",
        "blanket", "fork", "doorbell", "suitcase", "carpet",
    ],
    "abstract": [
        "memory", "time", "silence", "name", "shadow", "sadness", "prayer", "dream", "absence",
        "sleep", "promise", "voice", "forgetting", "fear", "desire", "season", "guilt",
        "waiting", "grief", "childhood", "distance", "secret", "future", "yesterday",
    ],
    "bureaucracy": [
        "document", "ticket", "stamp", "office", "certificate", "envelope", "number", "receipt",
        "contract", "map", "signature", "passport", "form", "folder", "ledger", "license",
        "file", "queue", "clerk", "counter", "seal", "invoice", "index",
    ],
}

# These are used only in local-span tests, not as raw-count reward.
INANIMATE_FIELDS = ["architecture", "nature", "machine", "domestic", "bureaucracy", "abstract"]
CONCRETE_FIELDS = ["body", "architecture", "nature", "machine", "domestic", "bureaucracy"]

AGENCY_VERBS = [
    "sleep", "sleeps", "slept", "cough", "coughs", "cry", "cries", "weep", "weeps",
    "watch", "watches", "pray", "prays", "speak", "speaks", "whisper", "whispers",
    "dream", "dreams", "forget", "forgets", "want", "wants", "wait", "waits",
    "breathe", "breathes", "laugh", "laughs", "think", "thinks", "sing", "sings",
    "kneel", "kneels", "remember", "remembers", "envy", "envies", "listen", "listens",
    "眠る", "咳", "泣く", "祈る", "夢を見", "呼吸", "笑う", "歌う",
]

# Repair is handled contextually. These words alone are not always bad.
REPAIR_CONNECTORS = [
    "therefore", "because", "so", "in other words", "that is", "thus", "consequently", "which means",
    "つまり", "なぜなら", "だから", "それゆえ", "したがって",
]
REPAIR_META_TERMS = [
    "reason", "symbol", "symbolizes", "symbolise", "symbolises", "meaning", "means", "metaphor",
    "represents", "representation", "explain", "explains", "interpretation", "conclusion", "lesson",
    "theme", "message", "psychology", "trauma", "moral", "allegory", "the point", "the image shows",
    "this shows", "this means", "stands for", "signifies", "about loneliness", "about memory",
    "理由", "これは", "象徴", "意味する", "比喩", "説明", "解釈", "結論", "教訓", "テーマ", "メッセージ",
]
CLOSURE_PHRASES = [
    "the end", "finally", "woke up", "awakens", "returned to reality", "back to reality", "resolved",
    "saved", "understood", "learned", "everything made sense", "and all was well", "closure",
    "終わり", "最後に", "目が覚め", "現実に戻", "解決", "救われ", "納得した",
]

# Assistant/chat models sometimes leak the instruction-following frame into the
# continuation: "Note:", "I've tried to...", "as per the instructions", etc.
# These are not merely repair phrases; they break the diegetic image entirely.
META_LEAK_PHRASES = [
    "note:", "(note:", "[note:", "author's note", "editor's note",
    "i've tried", "i have tried", "i tried", "i will", "i can", "here is", "here's",
    "as per the instructions", "per the instructions", "according to the instructions",
    "the instructions", "the prompt", "your prompt", "the user", "the request",
    "the fragment", "the continuation", "this continuation", "depaysement",
    "maintaining the atmosphere", "as requested", "i hope", "let me know",
    "assistant", "chatgpt", "language model",
    "注:", "（注:", "※", "指示", "プロンプト", "リクエスト", "解説すると",
]

META_LEAK_START_RE = re.compile(
    r"(?:^|\s|[([{])(?:note|author's note|editor's note)\s*[:：]|"
    r"(?:i['’]?ve tried|i have tried|i tried|as per the instructions|per the instructions|"
    r"according to the instructions|here is|here's|as requested|let me know|"
    r"maintaining the atmosphere|the prompt|the instructions|the user request)",
    flags=re.IGNORECASE | re.DOTALL,
)

# Pair bonuses: cross-domain adjacency priors.
#
# These are authorial/aesthetic priors, not theoretical consequences of
# dépaysement. For example, body × architecture is weighted highly here because
# this prototype often wants anatomical buildings and architectural bodies;
# another researcher may prefer nature × architecture or domestic × bureaucracy.
# v0.7 therefore keeps pair_distance weak by default and exposes
# --scorer-profile aesthetic/legacy when those priors should become active.
PAIR_BONUS: Dict[Tuple[str, str], float] = {
    ("body", "architecture"): 1.30,
    ("body", "machine"): 1.15,
    ("body", "bureaucracy"): 1.12,
    ("body", "abstract"): 1.00,
    ("nature", "machine"): 1.25,
    ("nature", "bureaucracy"): 1.15,
    ("domestic", "abstract"): 1.20,
    ("domestic", "nature"): 1.10,
    ("architecture", "abstract"): 1.15,
    ("machine", "abstract"): 1.05,
    ("architecture", "nature"): 0.95,
    ("domestic", "bureaucracy"): 0.90,
}
PAIR_BONUS.update({(b, a): v for (a, b), v in list(PAIR_BONUS.items())})

# Relation schema patterns. These try to answer: “is the image staged as a scene?”
RELATION_SCHEMA_PATTERNS: Dict[str, List[str]] = {
    "spatial": [
        r"\b(in|inside|outside|on|under|beneath|above|beside|near|behind|before|within|at|through|across|against|between|underneath|over|along|below|into)\b",
        r"\b(corridor|station|room|window|door|bridge|hospital|theater|basement|floor|ceiling|wall|platform|street|kitchen|museum|gate)\b.*\b(in|on|under|beside|near|against|through|inside)\b",
        r"(の上|の下|の中|内側|外側|隣|そば|奥|手前|背後)",
    ],
    "contact": [
        r"\b(touch|touches|touching|hold|holds|holding|carry|carries|carrying|attach|attached|sticks|rests|leans|bite|bites|biting|wet|wets|soak|soaks|tie|ties|bind|binds|press|presses|rub|rubs|kiss|kisses|pierce|pierces)\b",
        r"(触れ|抱え|噛む|貼ら|貼る|刺さ|挟ま|乗る|掛け|濡ら|結び)",
    ],
    "possession_part": [
        r"\b(with|has|have|bearing|carrying|wearing|owns?|keeps?|contains?)\b",
        r"\b(heart|tongue|lung|lungs|bone|shadow|name|voice|eye|eyes|hand|hands|teeth|key|ticket|mouth|skin) of\b",
        r"\b(of|inside) the (heart|tongue|lung|bone|shadow|name|voice|eye|hand|teeth|key|ticket|mouth|skin)\b",
        r"(を持つ|を宿し|を抱え|の(心臓|舌|肺|骨|影|名前|声|目|手|歯|鍵|切符))",
    ],
    "transformation": [
        r"\b(becomes?|became|turns? into|turned into|is|was|are|were|as|like|melts?|opens?|breaks?|grows?|shrinks?|unfolds?|dissolves?|hardens?|ripens?|changes? into)\b",
        r"(になる|になった|だった|である|として|のように|みたいに|変わる|溶け|開く|折れ|ほどけ|生える|育つ|縮む|膨らむ|裂け)",
    ],
    "containment": [
        r"\b(contains?|inside|enclosed|trapped|stored|folded into|wrapped|kept|sealed|locked|buried|hidden|packed)\b",
        r"\b(box|drawer|envelope|cabinet|pocket|jar|glass|folder|room|mouth|stomach)\b",
        r"(の中|に入|収ま|閉じ込|しまわれ|詰め|包ま|箱|引き出し)",
    ],
    "exchange_bureaucratic": [
        r"\b(submits?|submitted|stamps?|stamped|signed|called|named|exchanged|receives?|received|files?|filed|registers?|registered|approves?|approved|waits in line|queues?)\b",
        r"(渡す|提出|判子を?押|押され|署名|呼ばれ|名付け|交換|配る|受け取)",
    ],
}


# -----------------------------------------------------------------------------
# Prompt banks
# -----------------------------------------------------------------------------

DEFAULT_PROMPT_BANK: Dict[str, List[str]] = {
    "positive_depaysement": [
        "In the hospital corridor, the sea sleeps under a white sheet.",
        "The refrigerator coughs my grandmother's shadow into a glass.",
        "A ticket grows a tongue and stamps the moon at the station gate.",
        "The chair prays like a bird while the room opens its small heart.",
        "Inside the window, sand holds a clock and waits for the shoe's name.",
        "Beneath the bridge, a mirror breathes the city with the lungs of a fish.",
        "Snow signs the envelope while the desk grows a second bone.",
        "The umbrella becomes a small theater; rain's teeth sit in every seat.",
        "A passport lies under the bed, wearing the face of a sleeping river.",
        "At the office counter, a spoon receives a number and begins to rain.",
    ],
    "negative_realist_repair": [
        "The hospital corridor is quiet, and patients wait for their turn.",
        "Food is kept in the refrigerator at a low temperature.",
        "I showed my ticket at the gate and boarded the train.",
        "He sat in the chair and thought about his schedule for the day.",
        "This symbolizes loneliness and explains the protagonist's inner state.",
        "In other words, the scene means that memory is painful.",
        "Finally, he understood everything and returned to reality.",
        "The image represents childhood trauma and gives the story closure.",
    ],
    "negative_weird_noise": [
        "Purple purpled the purple because purple was purple.",
        "Umbrella, moon, bone, ticket, fish, window, stamp, tongue, sea, sea, sea.",
        "Meaning explodes without relation: chair salt invoice eyelid volcano.",
        "It was that because that was it and therefore it became that.",
        "po po po po po, shadow shadow shadow, ::::::, the end.",
        "A cloud of document of rib of moon of shoe of silence of bird.",
    ],
}


@dataclass
class PromptBank:
    positive_depaysement: List[str] = field(default_factory=lambda: list(DEFAULT_PROMPT_BANK["positive_depaysement"]))
    negative_realist_repair: List[str] = field(default_factory=lambda: list(DEFAULT_PROMPT_BANK["negative_realist_repair"]))
    negative_weird_noise: List[str] = field(default_factory=lambda: list(DEFAULT_PROMPT_BANK["negative_weird_noise"]))

    @classmethod
    def from_file(cls, path: Optional[str]) -> "PromptBank":
        if not path:
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            positive_depaysement=list(data.get("positive_depaysement", DEFAULT_PROMPT_BANK["positive_depaysement"])),
            negative_realist_repair=list(data.get("negative_realist_repair", DEFAULT_PROMPT_BANK["negative_realist_repair"])),
            negative_weird_noise=list(data.get("negative_weird_noise", DEFAULT_PROMPT_BANK["negative_weird_noise"])),
        )

    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "positive_depaysement": unique_preserve_order(self.positive_depaysement),
            "negative_realist_repair": unique_preserve_order(self.negative_realist_repair),
            "negative_weird_noise": unique_preserve_order(self.negative_weird_noise),
        }

    def write(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def negatives(self) -> List[str]:
        return list(self.negative_realist_repair) + list(self.negative_weird_noise)


# -----------------------------------------------------------------------------
# Lightweight contrastive scorer from prompt bank
# -----------------------------------------------------------------------------

class HashBankScorer:
    """Dependency-free lexical prompt-bank score, not semantic contrast.

    It uses signed character n-gram hashing: useful as a smoke-test and
    typo-tolerant lexical prior, but not a semantic contrast. v0.7 labels it
    as ``bank_lex`` and gives it low default weight. Use --embed-model for
    embedding-based bank contrast.
    """

    score_kind = "lex"

    score_kind = "lex"

    def __init__(self, bank: PromptBank, dims: int = 512, ngram_min: int = 2, ngram_max: int = 4):
        self.dims = dims
        self.ngram_min = ngram_min
        self.ngram_max = ngram_max
        self.pos = self._centroid(bank.positive_depaysement)
        self.neg = self._centroid(bank.negatives)

    def score(self, text: str) -> float:
        v = self._vec(text)
        return clamp(cosine(v, self.pos) - cosine(v, self.neg), -1.0, 1.0)

    def _centroid(self, texts: Sequence[str]) -> List[float]:
        if not texts:
            return [0.0] * self.dims
        acc = [0.0] * self.dims
        for t in texts:
            v = self._vec(t)
            for i, x in enumerate(v):
                acc[i] += x
        return l2_normalize([x / len(texts) for x in acc])

    def _vec(self, text: str) -> List[float]:
        s = re.sub(r"\s+", "", text.lower())
        v = [0.0] * self.dims
        if not s:
            return v
        for n in range(self.ngram_min, self.ngram_max + 1):
            if len(s) < n:
                continue
            for i in range(len(s) - n + 1):
                g = s[i : i + n]
                h = int(hashlib.blake2b(g.encode("utf-8"), digest_size=8).hexdigest(), 16)
                idx = h % self.dims
                sign = 1.0 if ((h >> 8) & 1) else -1.0
                v[idx] += sign
        return l2_normalize(v)


class HFEmbeddingBankScorer:
    """Optional semantic embedding bank scorer. Imports torch/transformers lazily."""

    score_kind = "embed"

    score_kind = "embed"

    def __init__(self, model_name: str, bank: PromptBank, device: Optional[str] = None):
        try:
            import torch  # type: ignore
            from transformers import AutoModel, AutoTokenizer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("HFEmbeddingBankScorer requires: pip install transformers torch") from e
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token or self.tokenizer.unk_token
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model.to(device)
        self.model.eval()
        self.pos = self._centroid(bank.positive_depaysement)
        self.neg = self._centroid(bank.negatives)

    def score(self, text: str) -> float:
        v = self._embed([text])[0]
        pos = float(self.torch.nn.functional.cosine_similarity(v[None, :], self.pos[None, :]).item())
        neg = float(self.torch.nn.functional.cosine_similarity(v[None, :], self.neg[None, :]).item())
        return clamp(pos - neg, -1.0, 1.0)

    def _centroid(self, texts: Sequence[str]):
        emb = self._embed(list(texts))
        return emb.mean(dim=0)

    def _embed(self, texts: List[str]):
        torch = self.torch
        with torch.no_grad():
            enc = self.tokenizer(texts, padding=True, truncation=True, return_tensors="pt").to(self.device)
            out = self.model(**enc)
            h = out.last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
            pooled = (h * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
            return torch.nn.functional.normalize(pooled, dim=-1)


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    total: float
    concept_dispersion: float = 0.0
    pair_distance: float = 0.0
    agency_inversion: float = 0.0
    ontology_leak: float = 0.0
    image_schema: float = 0.0
    image_integration: float = 0.0
    concrete_grounding: float = 0.0
    bank_contrast: float = 0.0
    bank_mode: str = "off"
    anchor_resonance: float = 0.0
    voice_hinge: float = 0.0
    anti_repair: float = 0.0
    anti_closure: float = 0.0
    anti_collapse: float = 0.0
    anti_repetition: float = 0.0
    anti_keyword_stuffing: float = 0.0
    anti_context_overfit: float = 0.0
    anti_context_orphan: float = 0.0
    anti_scene_failure: float = 0.0
    anti_semantic_collage: float = 0.0
    anti_image_fragmentation: float = 0.0
    anti_meta_leak: float = 0.0
    anti_unfinished: float = 0.0
    concept_tags: Tuple[str, ...] = ()
    relation_schemas: Tuple[str, ...] = ()
    shared_anchors: Tuple[str, ...] = ()
    image_graph: str = "-"

    def compact(self) -> str:
        parts = [
            f"total={self.total:.2f}",
            f"concepts={self.concept_dispersion:.2f}",
            f"pairs={self.pair_distance:.2f}",
            f"agency={self.agency_inversion:.2f}",
            f"leak={self.ontology_leak:.2f}",
            f"schema={self.image_schema:.2f}",
            f"integr={self.image_integration:.2f}",
            f"ground={self.concrete_grounding:.2f}",
            f"bank_{self.bank_mode}={self.bank_contrast:.2f}",
            f"anchor={self.anchor_resonance:.2f}",
            f"voice={self.voice_hinge:.2f}",
            f"repair={self.anti_repair:.2f}",
            f"close={self.anti_closure:.2f}",
            f"collapse={self.anti_collapse:.2f}",
            f"rep={self.anti_repetition:.2f}",
            f"stuff={self.anti_keyword_stuffing:.2f}",
            f"ctx_hi={self.anti_context_overfit:.2f}",
            f"ctx_zero={self.anti_context_orphan:.2f}",
            f"scene_fail={self.anti_scene_failure:.2f}",
            f"sema_col={self.anti_semantic_collage:.2f}",
            f"frag={self.anti_image_fragmentation:.2f}",
            f"meta={self.anti_meta_leak:.2f}",
            f"unfinished={self.anti_unfinished:.2f}",
            f"tags={','.join(self.concept_tags) or '-'}",
            f"schemas={','.join(self.relation_schemas) or '-'}",
            f"graph={self.image_graph}",
            f"shared={','.join(self.shared_anchors) or '-'}",
        ]
        return " | ".join(parts)


@dataclass
class DepaysementWeights:
    # v0.7 default is structure-first. Lexical concept fields and pair priors are
    # intentionally weak by default because otherwise a Magritte/Kafka-ish vocabulary
    # leaks into the definition of “depaysement”. Use --scorer-profile aesthetic or
    # legacy when you deliberately want those authorial priors.
    concept_dispersion: float = 0.10
    pair_distance: float = 0.18
    agency_inversion: float = 0.35
    ontology_leak: float = 0.70
    image_schema: float = 1.15
    image_integration: float = 1.35
    concrete_grounding: float = 0.25
    bank_contrast: float = 0.18
    anchor_resonance: float = 0.92
    voice_hinge: float = 0.25
    repair_penalty: float = 1.70
    closure_penalty: float = 1.15
    collapse_penalty: float = 2.00
    repetition_penalty: float = 0.85
    keyword_stuffing_penalty: float = 1.35
    context_overfit_penalty: float = 0.85
    context_orphan_penalty: float = 0.82
    scene_failure_penalty: float = 1.20
    semantic_collage_penalty: float = 1.45
    image_fragmentation_penalty: float = 1.25
    meta_leak_penalty: float = 2.80
    unfinished_penalty: float = 0.85


def weights_for_profile(profile: str, *, bank_mode: str = "off") -> DepaysementWeights:
    profile = (profile or "structural").lower()
    if profile == "legacy":
        return DepaysementWeights(
            concept_dispersion=0.70, pair_distance=1.10, agency_inversion=1.05, ontology_leak=0.90,
            image_schema=1.35, image_integration=0.20, concrete_grounding=0.55,
            bank_contrast=0.70 if bank_mode != "off" else 0.0, anchor_resonance=0.92, voice_hinge=0.30,
            semantic_collage_penalty=1.05, image_fragmentation_penalty=0.35,
        )
    if profile == "aesthetic":
        return DepaysementWeights(
            concept_dispersion=0.42, pair_distance=0.72, agency_inversion=0.82, ontology_leak=0.88,
            image_schema=1.25, image_integration=1.05, concrete_grounding=0.45,
            bank_contrast=0.42 if bank_mode == "lex" else (0.70 if bank_mode == "embed" else 0.0),
            semantic_collage_penalty=1.35, image_fragmentation_penalty=1.05,
        )
    if profile != "structural":
        raise ValueError(f"Unknown scorer profile: {profile!r}. Choose structural, aesthetic, or legacy.")
    w = DepaysementWeights()
    if bank_mode == "embed":
        w.bank_contrast = 0.62
    elif bank_mode == "off":
        w.bank_contrast = 0.0
    else:
        w.bank_contrast = 0.18
    return w


@dataclass
class DepaysementScorer:
    weights: DepaysementWeights = field(default_factory=DepaysementWeights)
    concept_fields: Mapping[str, Sequence[str]] = field(default_factory=lambda: DEFAULT_CONCEPT_FIELDS)
    bank_scorer: Optional[Any] = None
    lexicon_enabled: bool = True
    anchor_ideal: float = 0.26
    anchor_width: float = 0.34

    def score(self, text: str, context: str = "") -> ScoreBreakdown:
        clean = normalize_text(text)
        hits = self._concept_hits(clean) if self.lexicon_enabled else {}
        tags = tuple(sorted(hits.keys()))

        concept_component = min(len(tags), 4) / 4.0 if self.lexicon_enabled else 0.0
        pair_component = self._pair_distance(tags) if self.lexicon_enabled else 0.0
        agency_component = self._agency_inversion(clean, hits) if self.lexicon_enabled else 0.0
        schemas = relation_schemas(clean)
        graph = image_relation_graph(clean)
        ontology_component = self._ontology_leak(clean, tags)
        if not self.lexicon_enabled:
            ontology_component = max(ontology_component, structural_ontology_leak(clean, graph))
        image_component = image_schema_score(clean, schemas, has_concrete=bool(self._concrete_terms(hits)) or graph.object_count >= 2)
        integration_component = graph.integration_score()
        grounding_component = max(self._concrete_grounding(clean, hits), graph.grounding_score() if not self.lexicon_enabled else 0.0)
        bank_component = float(self.bank_scorer.score(clean)) if self.bank_scorer else 0.0
        bank_mode = getattr(self.bank_scorer, "score_kind", "off") if self.bank_scorer else "off"
        anchor_component, overfit, orphan, shared = self._anchor_resonance(context, clean)
        voice_component = voice_hinge_score(clean, schemas, hits, graph)

        repair = contextual_repair_penalty(clean, schemas, hits)
        closure = phrase_rate(clean, CLOSURE_PHRASES)
        collapse = collapse_penalty(clean)
        repetition = repetition_penalty(clean)
        stuffing = keyword_stuffing_penalty(clean, hits)
        scene_fail = scene_failure_penalty(pair_component, image_component, clean)
        sema_col = semantic_collage_penalty(clean, schemas, hits, graph)
        image_frag = graph.cluster_sprawl_penalty()
        meta_leak = meta_commentary_penalty(clean)
        unfinished = unfinished_fragment_penalty(clean)

        total = (
            self.weights.concept_dispersion * concept_component
            + self.weights.pair_distance * pair_component
            + self.weights.agency_inversion * agency_component
            + self.weights.ontology_leak * ontology_component
            + self.weights.image_schema * image_component
            + self.weights.image_integration * integration_component
            + self.weights.concrete_grounding * grounding_component
            + self.weights.bank_contrast * bank_component
            + self.weights.anchor_resonance * anchor_component
            + self.weights.voice_hinge * voice_component
            - self.weights.repair_penalty * repair
            - self.weights.closure_penalty * closure
            - self.weights.collapse_penalty * collapse
            - self.weights.repetition_penalty * repetition
            - self.weights.keyword_stuffing_penalty * stuffing
            - self.weights.context_overfit_penalty * overfit
            - self.weights.context_orphan_penalty * orphan
            - self.weights.scene_failure_penalty * scene_fail
            - self.weights.semantic_collage_penalty * sema_col
            - self.weights.image_fragmentation_penalty * image_frag
            - self.weights.meta_leak_penalty * meta_leak
            - self.weights.unfinished_penalty * unfinished
        )

        return ScoreBreakdown(
            total=total,
            concept_dispersion=concept_component,
            pair_distance=pair_component,
            agency_inversion=agency_component,
            ontology_leak=ontology_component,
            image_schema=image_component,
            image_integration=integration_component,
            concrete_grounding=grounding_component,
            bank_contrast=bank_component,
            bank_mode=bank_mode,
            anchor_resonance=anchor_component,
            voice_hinge=voice_component,
            anti_repair=-repair,
            anti_closure=-closure,
            anti_collapse=-collapse,
            anti_repetition=-repetition,
            anti_keyword_stuffing=-stuffing,
            anti_context_overfit=-overfit,
            anti_context_orphan=-orphan,
            anti_scene_failure=-scene_fail,
            anti_semantic_collage=-sema_col,
            anti_image_fragmentation=-image_frag,
            anti_meta_leak=-meta_leak,
            anti_unfinished=-unfinished,
            concept_tags=tags,
            relation_schemas=tuple(sorted(schemas)),
            shared_anchors=tuple(sorted(shared)),
            image_graph=graph.compact(),
        )

    def _concept_hits(self, text: str) -> Dict[str, List[str]]:
        low = text.lower()
        hits: Dict[str, List[str]] = {}
        for field_name, words in self.concept_fields.items():
            found = []
            for w in words:
                wl = w.lower()
                if is_valid_anchor(wl) and anchor_in_text(wl, low):
                    found.append(wl)
            if found:
                hits[field_name] = unique_preserve_order(found)
        return hits

    def _all_terms_for_fields(self, fields: Sequence[str]) -> List[str]:
        terms: List[str] = []
        for f in fields:
            terms.extend([w.lower() for w in self.concept_fields.get(f, []) if is_valid_anchor(w.lower())])
        return terms

    def _concrete_terms(self, hits: Mapping[str, Sequence[str]]) -> List[str]:
        out: List[str] = []
        for f in CONCRETE_FIELDS:
            out.extend(hits.get(f, []))
        return unique_preserve_order(out)

    def _pair_distance(self, tags: Sequence[str]) -> float:
        if len(tags) < 2:
            return 0.0
        vals = [PAIR_BONUS.get((a, b), 0.58) for a, b in combinations(tags, 2)]
        return clamp((sum(vals) / max(len(vals), 1)) / 1.30, 0.0, 1.0)

    def _agency_inversion(self, text: str, hits: Mapping[str, Sequence[str]]) -> float:
        if not hits:
            return 0.0
        inanimate_terms = set()
        for f in INANIMATE_FIELDS:
            inanimate_terms.update(hits.get(f, []))
        if not inanimate_terms:
            return 0.0
        spans = split_spans(text.lower())
        local_hits = 0
        for span in spans:
            if any(t in span for t in inanimate_terms) and any(v.lower() in span for v in AGENCY_VERBS):
                local_hits += 1
        return clamp(local_hits / 2.0, 0.0, 1.0)

    def _ontology_leak(self, text: str, tags: Sequence[str]) -> float:
        # Cross-category identity, becoming, role-shifting, or simile.
        patterns = [
            r".+は.+(になる|になった|だった|である|として|のように|みたいに)",
            r".+が.+(になる|になった|だった|である|として|のように|みたいに)",
            r".+\b(is|became|becomes|as|like|turns? into)\b.+",
        ]
        pat_hit = any(re.search(p, text, flags=re.IGNORECASE | re.DOTALL) for p in patterns)
        if pat_hit and len(tags) >= 2:
            return 1.0
        if pat_hit:
            return 0.45
        return 0.0

    def _concrete_grounding(self, text: str, hits: Mapping[str, Sequence[str]]) -> float:
        if not self.lexicon_enabled:
            # Fall back to relation density when no lexicon is used.
            return clamp(len(relation_schemas(text)) / 4.0, 0.0, 0.75)
        unique_concrete = len(self._concrete_terms(hits))
        # Cap hard: five concrete anchors are enough; more becomes stuffing risk.
        base = min(unique_concrete, 5) / 5.0
        # Relation particles and punctuation make it more like a staged image than a bag of nouns.
        staged_bonus = 0.12 if relation_schemas(text) else 0.0
        return clamp(base + staged_bonus, 0.0, 1.0)

    def _anchor_resonance(self, context: str, text: str) -> Tuple[float, float, float, List[str]]:
        if not context.strip():
            return 0.0, 0.0, 0.0, []
        c_terms = salient_terms(context, self.concept_fields if self.lexicon_enabled else None)
        t_terms = salient_terms(text, self.concept_fields if self.lexicon_enabled else None)
        if not c_terms:
            return 0.0, 0.0, 0.0, []
        shared = sorted(c_terms & t_terms)
        # Denominator uses context terms: how much of the old motif is retained.
        ratio = len(shared) / max(len(c_terms), 1)
        resonance = 0.0 if ratio == 0.0 else clamp(1.0 - abs(ratio - self.anchor_ideal) / self.anchor_width, 0.0, 1.0)
        # Too much: ordinary continuation / explanation / inertia.
        overfit = clamp((ratio - 0.58) / 0.42, 0.0, 1.0)
        # Too little: each sentence becomes a random postcard.
        orphan = 1.0 if ratio == 0.0 and len(c_terms) >= 1 else 0.0
        # If the new text has no salient terms at all, do not over-penalize as orphan; collapse/noise handles it.
        if not t_terms:
            orphan *= 0.45
        return resonance, overfit, orphan, shared


# -----------------------------------------------------------------------------
# Scoring helpers
# -----------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_spans(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[。．.!?！？\n]+", text) if s.strip()]


def unique_preserve_order(xs: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def relation_schemas(text: str) -> set:
    schemas = set()
    for name, patterns in RELATION_SCHEMA_PATTERNS.items():
        if any(re.search(p, text, flags=re.IGNORECASE | re.DOTALL) for p in patterns):
            schemas.add(name)
    return schemas



# -----------------------------------------------------------------------------
# Lexicon-free relation graph: staged-image integration
# -----------------------------------------------------------------------------

EN_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "while", "then", "now", "also", "still", "only",
    "this", "that", "these", "those", "it", "its", "their", "his", "her", "hers", "him", "them",
    "with", "without", "inside", "outside", "under", "over", "above", "below", "beside", "near",
    "next", "to", "from", "into", "onto", "on", "in", "at", "by", "for", "of", "as", "like",
    "is", "are", "was", "were", "be", "been", "being", "has", "have", "had", "having", "made",
    "makes", "make", "seems", "seem", "seemed", "seeming", "there", "where", "which", "whose",
    "when", "what", "who", "why", "how", "very", "faint", "small", "tiny", "miniature", "single",
    "forgotten", "discarded", "rusted", "dried", "gray", "grey", "blue", "white", "black", "red",
    "nearby", "surrounding", "surface", "object", "thing", "scene", "image", "fragment", "chaos",
}

RELATION_PREPOSITIONS = {
    "in", "inside", "outside", "on", "under", "beneath", "above", "beside", "near", "behind",
    "before", "within", "at", "through", "across", "against", "between", "underneath", "over",
    "along", "below", "into", "next to", "wrapped in", "tied to", "glued to", "attached to", "made of",
    "constructed from", "etched with", "smeared with", "filled with", "covered with", "tangled with",
    "suspended by", "spills from", "floats in",
}

RELATION_VERBS = {
    "touch", "touches", "touching", "hold", "holds", "holding", "carry", "carries", "carrying",
    "attach", "attached", "stick", "sticks", "rest", "rests", "resting", "lean", "leans", "leaning",
    "bite", "bites", "biting", "wet", "wets", "soak", "soaks", "tie", "ties", "tied", "bind",
    "binds", "press", "presses", "rub", "rubs", "kiss", "kisses", "pierce", "pierces", "become",
    "becomes", "became", "turn", "turns", "turned", "melt", "melts", "melted", "open", "opens",
    "break", "breaks", "grow", "grows", "shrink", "shrinks", "unfold", "unfolds", "dissolve", "dissolves",
    "harden", "hardens", "ripen", "ripens", "change", "changes", "contain", "contains", "spill", "spills",
    "entrap", "entraps", "entrapping", "float", "floats", "lie", "lies", "lying", "sleep", "sleeps", "breathe", "breathes",
    "etched", "scrawled", "glued", "wrapped", "tangled", "suspended",
}

CONTENT_VERBISH = RELATION_VERBS | {"seem", "seems", "seemed", "try", "tried", "continue", "maintain", "follow", "write", "generate"}

@dataclass
class ImageRelationGraph:
    object_terms: Tuple[str, ...] = ()
    edges: Tuple[Tuple[str, str, str], ...] = ()
    components: Tuple[Tuple[str, ...], ...] = ()
    of_chain_count: int = 0
    comma_clause_count: int = 0
    dangling_clause_count: int = 0

    @property
    def object_count(self) -> int:
        return len(self.object_terms)

    @property
    def relation_count(self) -> int:
        return len(self.edges)

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def giant_ratio(self) -> float:
        if not self.object_terms or not self.components:
            return 0.0
        return max(len(c) for c in self.components) / max(len(self.object_terms), 1)

    def relation_quantity_score(self) -> float:
        return clamp(self.relation_count / 3.0, 0.0, 1.0) if self.relation_count else 0.0

    def integration_score(self) -> float:
        if self.relation_count <= 0 or self.object_count <= 1:
            return 0.0
        relation_density = self.relation_quantity_score()
        giant = clamp((self.giant_ratio - 0.34) / 0.62, 0.0, 1.0)
        component_penalty = clamp((self.component_count - 1) / 4.0, 0.0, 1.0)
        return clamp(0.58 * giant + 0.42 * relation_density - 0.22 * component_penalty, 0.0, 1.0)

    def grounding_score(self) -> float:
        if self.object_count <= 0:
            return 0.0
        return clamp(0.42 * clamp(self.object_count / 5.0, 0.0, 1.0) + 0.58 * self.relation_quantity_score(), 0.0, 1.0)

    def cluster_sprawl_penalty(self) -> float:
        if self.object_count <= 4:
            return 0.0
        excess_objects = clamp((self.object_count - 7) / 8.0, 0.0, 1.0)
        weak_giant = clamp((0.78 - self.giant_ratio) / 0.58, 0.0, 1.0)
        many_components = clamp((self.component_count - 2) / 4.0, 0.0, 1.0)
        of_chain = clamp(self.of_chain_count / 3.0, 0.0, 1.0)
        dangling = clamp(self.dangling_clause_count / 3.0, 0.0, 1.0)
        return clamp(0.34 * excess_objects + 0.30 * weak_giant + 0.30 * many_components + 0.38 * of_chain + 0.26 * dangling, 0.0, 1.0)

    def compact(self) -> str:
        return f"objects={self.object_count},rels={self.relation_count},components={self.component_count},giant={self.giant_ratio:.2f},sprawl={self.cluster_sprawl_penalty():.2f}"


def _english_word_tokens(text: str) -> List[Tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[a-zA-Z][a-zA-Z'-]*", text)]


def _is_content_anchor(word: str) -> bool:
    w = word.strip("'-").lower()
    if len(w) < 3 or w in EN_STOPWORDS or w in CONTENT_VERBISH:
        return False
    if w.endswith("ing") and w[:-3] in CONTENT_VERBISH:
        return False
    if w.endswith("ed") and w[:-2] in CONTENT_VERBISH:
        return False
    return True


def _nearest_content_before(tokens: Sequence[Tuple[str, int, int]], pos: int, window: int = 8) -> Optional[str]:
    checked = 0
    for w, _s, e in reversed(tokens):
        if e > pos:
            continue
        checked += 1
        if _is_content_anchor(w):
            return w
        if checked >= window:
            break
    return None


def _nearest_content_after(tokens: Sequence[Tuple[str, int, int]], pos: int, window: int = 8) -> Optional[str]:
    checked = 0
    for w, s, _e in tokens:
        if s < pos:
            continue
        checked += 1
        if _is_content_anchor(w):
            return w
        if checked >= window:
            break
    return None


def image_relation_graph(text: str) -> ImageRelationGraph:
    low = text.lower()
    tokens = _english_word_tokens(low)
    object_terms = unique_preserve_order(w for w, _s, _e in tokens if _is_content_anchor(w))
    edges: List[Tuple[str, str, str]] = []
    for rel in sorted(RELATION_PREPOSITIONS, key=len, reverse=True):
        pat = r"(?<![a-z0-9])" + re.escape(rel) + r"(?![a-z0-9])"
        for m in re.finditer(pat, low):
            a = _nearest_content_before(tokens, m.start())
            b = _nearest_content_after(tokens, m.end())
            if a and b and a != b:
                edges.append((a, rel, b))
    for w, st, en in tokens:
        if w in RELATION_VERBS:
            a = _nearest_content_before(tokens, st)
            b = _nearest_content_after(tokens, en)
            if a and b and a != b:
                edges.append((a, w, b))
    for m in re.finditer(r"\b([a-z][a-z'-]*)'s\s+([a-z][a-z'-]*)\b", low):
        a, b = m.group(1), m.group(2)
        if _is_content_anchor(a) and _is_content_anchor(b) and a != b:
            edges.append((a, "possessive", b))
    edges = tuple(unique_preserve_order(edges))
    parent = {t: t for t in object_terms}
    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return parent.get(x, x)
    def union(a: str, b: str) -> None:
        if a not in parent or b not in parent:
            return
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for a, _rel, b in edges:
        union(a, b)
    comps: Dict[str, List[str]] = defaultdict(list)
    for t in object_terms:
        comps[find(t)].append(t)
    components = tuple(tuple(v) for v in comps.values())
    of_chain_count = len(re.findall(r"\b[a-z][a-z'-]+\s+of\s+[a-z][a-z'-]+", low))
    clauses = [c for c in re.split(r"[,;]|\bwhile\b|\balthough\b|\bwhereas\b", low) if c.strip()]
    dangling_clause_count = 0
    for c in clauses:
        ctoks = _english_word_tokens(c)
        c_content = [w for w, _s, _e in ctoks if _is_content_anchor(w)]
        if len(c_content) >= 2 and not relation_schemas(c) and not any(w in RELATION_VERBS for w, _s, _e in ctoks):
            dangling_clause_count += 1
    return ImageRelationGraph(tuple(object_terms), edges, components, of_chain_count, len(clauses), dangling_clause_count)


def structural_ontology_leak(text: str, graph: ImageRelationGraph) -> float:
    if graph.object_count < 2:
        return 0.0
    identity = bool(re.search(r"\b(is|was|are|were|becomes?|became|turns? into|turned into|as|like)\b", text, re.I))
    transformation = "transformation" in relation_schemas(text)
    if identity and transformation:
        return 0.75
    if identity or transformation:
        return 0.45
    return 0.0

def image_schema_score(text: str, schemas: set, has_concrete: bool) -> float:
    if not text.strip():
        return 0.0
    # Relation categories matter more than raw terms. At least one relation is needed for image staging.
    if not schemas:
        return 0.0
    # Spatial/contact/transformation are especially imagistic.
    high_value = len(schemas & {"spatial", "contact", "transformation", "containment"})
    other = len(schemas - {"spatial", "contact", "transformation", "containment"})
    base = min((0.34 * high_value + 0.20 * other), 0.95)
    if has_concrete:
        base += 0.14
    # Short phrases with a single relation can still be valid, but cap them lower.
    compact_len = len(re.sub(r"\s+", "", text))
    if compact_len < 14 and len(schemas) <= 1:
        base = min(base, 0.48)
    return clamp(base, 0.0, 1.0)


def phrase_rate(text: str, phrases: Sequence[str]) -> float:
    low = text.lower()
    hits = sum(1 for p in phrases if phrase_in_text(p, low))
    return clamp(hits / 2.0, 0.0, 1.0)


def contextual_repair_penalty(text: str, schemas: set, hits: Mapping[str, Sequence[str]]) -> float:
    """Penalize explanatory repair while preserving 'つまり' as a possible inner voice.

    Examples:
      - “つまり、これは孤独の比喩だった。” => high penalty
      - “つまり、傘は海の胃袋だった。” => low/no penalty + voice_hinge bonus
    """
    low = text.lower()
    spans = split_spans(low)
    if not spans:
        return 0.0
    penalty = 0.0
    for s in spans:
        connector = any(phrase_in_text(c, s) for c in REPAIR_CONNECTORS)
        meta = any(phrase_in_text(m, s) for m in REPAIR_META_TERMS)
        closureish = any(phrase_in_text(c, s) for c in CLOSURE_PHRASES)
        if meta:
            penalty += 0.72
        if connector and meta:
            penalty += 0.35
        elif connector:
            # connector without image schema is likely reasoning prose; with schema it may be a voice hinge.
            local_schemas = relation_schemas(s)
            local_concrete = any(any(term in s for term in terms) for terms in hits.values())
            if local_schemas and local_concrete:
                penalty += 0.04
            else:
                penalty += 0.22
        if closureish:
            penalty += 0.35
    return clamp(penalty, 0.0, 1.0)


def meta_leak_penalty(text: str) -> float:
    """Detect assistant/meta commentary leaking into the literary continuation."""
    low = text.lower().strip()
    if not low:
        return 0.0
    penalty = 0.0
    if META_LEAK_START_RE.search(text):
        penalty += 0.90
    phrase_hits = sum(1 for p in META_LEAK_PHRASES if phrase_in_text(p, low))
    if phrase_hits:
        penalty += min(0.85, 0.24 * phrase_hits)
    # Parenthesized meta after a good image is common with chat models. Parentheses
    # are not banned in general; they become suspicious when they include meta verbs.
    for inner in re.findall(r"[([{]([^(){}\[\]]{0,220})[)\]}]", text):
        inner_low = inner.lower()
        if any(phrase_in_text(p, inner_low) for p in META_LEAK_PHRASES) or re.search(
            r"\b(tried|continue|maintain|instruction|prompt|request|atmosphere|constraint)\b", inner_low
        ):
            penalty += 0.65
    # "I" statements are usually not diegetic in this experiment unless the seed is first-person.
    if re.search(r"\b(i['’]?ve|i have|i tried|i will|i can|i am|i'm)\b", low):
        penalty += 0.40
    return clamp(penalty, 0.0, 1.0)


def voice_hinge_score(text: str, schemas: set, hits: Mapping[str, Sequence[str]], graph: Optional[ImageRelationGraph] = None) -> float:
    low = text.lower()
    if not any(phrase_in_text(c, low) for c in REPAIR_CONNECTORS):
        return 0.0
    if any(phrase_in_text(m, low) for m in REPAIR_META_TERMS):
        return 0.0
    if not schemas:
        return 0.0
    has_anchor = any(hits.values()) or (graph is not None and graph.object_count >= 2 and graph.relation_count >= 1)
    if not has_anchor:
        return 0.0
    return 1.0

def char_ngrams(text: str, n: int = 3) -> List[str]:
    compact = re.sub(r"\s+", "", text)
    return [compact[i : i + n] for i in range(max(0, len(compact) - n + 1))]


def repetition_penalty(text: str) -> float:
    grams = char_ngrams(text, 3)
    if len(grams) < 8:
        return 0.0
    unique = len(set(grams))
    rep_ratio = 1.0 - unique / len(grams)
    repeated_wordish = 0.0
    tokens = rough_tokens(text)
    if tokens:
        counts = Counter(tokens)
        repeated_wordish = max((c - 1) for c in counts.values()) / max(len(tokens), 1)
    return clamp(rep_ratio * 1.7 + repeated_wordish * 1.2, 0.0, 1.0)


def collapse_penalty(text: str) -> float:
    if not text.strip():
        return 1.0
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 8:
        return 0.52
    symbol_ratio = sum(1 for c in compact if not (c.isalnum() or "ぁ" <= c <= "龯" or c in "、。,.!?！？ー—『』「」（）()")) / len(compact)
    repeated_char = 1.0 if re.search(r"(.)\1{4,}", compact) else 0.0
    punctuation_burst = 1.0 if re.search(r"[、。,.!?！？]{5,}", compact) else 0.0
    too_long_unbroken = 1.0 if len(compact) > 240 and not re.search(r"[。.!?！？]", compact) else 0.0
    alpha_noise = 1.0 if re.search(r"[a-zA-Z]{30,}", compact) else 0.0
    return clamp(symbol_ratio * 2.0 + 0.45 * repeated_char + 0.35 * punctuation_burst + 0.25 * too_long_unbroken + 0.25 * alpha_noise, 0.0, 1.0)


def keyword_stuffing_penalty(text: str, hits: Mapping[str, Sequence[str]]) -> float:
    if not hits:
        return 0.0
    low = text.lower()
    raw_hits = 0
    repeated_hits = 0
    for terms in hits.values():
        for t in terms:
            cnt = low.count(t)
            raw_hits += cnt
            if cnt > 1:
                repeated_hits += cnt - 1
    compact_len = max(len(re.sub(r"\s+", "", text)), 1)
    # For Japanese, term length varies, so use a softened density proxy.
    term_chars = sum(len(t) for terms in hits.values() for t in terms)
    density = term_chars / compact_len
    list_like = 1.0 if re.search(r"([^、,]{1,8}[、,]){5,}", text) else 0.0
    many_fields_no_schema = 1.0 if len(hits) >= 5 and not relation_schemas(text) else 0.0
    excess_raw = max(0, raw_hits - 7) / 8.0
    excess_density = max(0.0, density - 0.46) / 0.54
    repeat_component = min(repeated_hits / 5.0, 1.0)
    return clamp(0.35 * excess_raw + 0.28 * excess_density + 0.28 * repeat_component + 0.55 * list_like + 0.35 * many_fields_no_schema, 0.0, 1.0)


def scene_failure_penalty(pair_component: float, image_component: float, text: str) -> float:
    # Weird domains without staging relations are often just “strange sentence” / noun collage.
    if pair_component >= 0.55 and image_component <= 0.18:
        return clamp((0.55 - image_component) * 1.45, 0.0, 1.0)
    # Pure abstraction can sound surreal but has no image.
    abstract_only = bool(re.search(r"(記憶|時間|沈黙|意味|夢|不在|memory|time|silence|absence)", text, re.I)) and not relation_schemas(text)
    if abstract_only:
        return 0.35
    return 0.0


def semantic_collage_penalty(
    text: str,
    schemas: set,
    hits: Mapping[str, Sequence[str]],
    graph: Optional[ImageRelationGraph] = None,
) -> float:
    """Detect surreal-looking but image-poor collage.

    v0.7 checks lexicon-free object chains and relation-graph sprawl, so a text
    with many relation words can still be penalized when it does not cohere as
    one staged image.
    """
    low = text.lower().strip()
    if not low:
        return 1.0
    graph = graph or image_relation_graph(text)
    concept_terms = unique_preserve_order(t for terms in hits.values() for t in terms)
    concept_count = len(concept_terms)
    schema_count = len(schemas)
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]*", low)
    content = [w for w, _s, _e in _english_word_tokens(low) if _is_content_anchor(w)]
    verbish = re.findall(
        r"\b(is|are|was|were|becomes?|became|turns?|turned|touch(?:es|ed|ing)?|hold(?:s|ing)?|"
        r"sleep(?:s|ing)?|cough(?:s|ing)?|pray(?:s|ing)?|breathe(?:s|ing)?|open(?:s|ed|ing)?|"
        r"grow(?:s|ing)?|sign(?:s|ed|ing)?|stamp(?:s|ed|ing)?|wear(?:s|ing)?|receive(?:s|d|ing)?|"
        r"carry|carries|carrying|rest(?:s|ing)?|lean(?:s|ing)?|melt(?:s|ing)?|contain(?:s|ing)?|"
        r"tangle(?:s|d|ing)?|wrap(?:s|ped|ping)?|tie(?:s|d|ing)?|glue(?:s|d|ing)?|lie(?:s|d|ing)?)\b",
        low,
    )
    of_chain = 1.0 if re.search(r"\b(?:[a-z][a-z'-]+\s+(?:of|from|with|inside|next to)\s+){3,}[a-z][a-z'-]+\b", low) else 0.0
    comma_chain = 1.0 if re.search(r"(?:\b[a-z][a-z'-]+\b\s*[,;/]\s*){5,}", low) else 0.0
    many_domains_low_relation = 1.0 if concept_count >= 6 and schema_count <= 1 else 0.0
    nouns_without_action = 1.0 if max(concept_count, len(content)) >= 6 and len(verbish) <= 1 else 0.0
    density = max(concept_count, len(content)) / max(len(tokens), 1) if tokens else 0.0
    density_component = clamp((density - 0.34) / 0.42, 0.0, 1.0) if max(concept_count, len(content)) >= 5 else 0.0
    relation_but_fragmented = graph.cluster_sprawl_penalty()
    relation_overload = clamp((graph.relation_count - 5) / 8.0, 0.0, 1.0) if graph.object_count >= 8 else 0.0
    return clamp(
        0.28 * of_chain
        + 0.36 * comma_chain
        + 0.25 * many_domains_low_relation
        + 0.24 * nouns_without_action
        + 0.16 * density_component
        + 0.42 * relation_but_fragmented
        + 0.20 * relation_overload,
        0.0,
        1.0,
    )

def unfinished_fragment_penalty(text: str) -> float:
    clean = text.strip()
    if not clean:
        return 0.0
    if re.search(r"[。.!?！？][\'\"”’\)\]）】』」]*$", clean):
        return 0.0
    if clean.endswith((",", ";", ":", "、", "，", "；", "：", "-", "—")):
        return 0.60
    toks = rough_tokens(clean)
    if not toks:
        return 0.0
    last = toks[-1].lower()
    dangling = {
        "a", "an", "the", "of", "with", "by", "to", "in", "on", "under", "over", "from", "into",
        "inside", "outside", "while", "where", "which", "whose", "its", "their", "his", "her", "and", "or",
    }
    if last in dangling or len(last) <= 2:
        return 0.85
    if len(toks) >= 28 and not re.search(r"[。.!?！？]", clean):
        return 0.40
    return 0.18 if len(toks) >= 18 else 0.0


def rough_tokens(text: str) -> List[str]:
    low = text.lower()
    latin = re.findall(r"[a-zA-Z]{3,}", low)
    # Japanese fallback: split on punctuation/particles lightly. Not a tokenizer, just repetition detection.
    chunks = re.split(r"[\s、。,.!?！？『』「」（）()]+", low)
    jp = [c for c in chunks if 2 <= len(c) <= 10 and not re.fullmatch(r"[a-zA-Z]+", c)]
    return latin + jp


def contains_cjk_or_kana(s: str) -> bool:
    return any(("ぁ" <= ch <= "ん") or ("ァ" <= ch <= "ン") or ("一" <= ch <= "龯") for ch in s)


def anchor_in_text(anchor: str, text: str) -> bool:
    """Match English anchors as words, while preserving substring matching for CJK anchors."""
    if not anchor:
        return False
    if re.fullmatch(r"[a-z][a-z0-9' -]*", anchor):
        # Multi-word anchors are still bounded at both ends. This avoids sea/season, art/heart, etc.
        pattern = r"(?<![a-z0-9])" + re.escape(anchor) + r"(?![a-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return anchor in text


def phrase_in_text(phrase: str, text: str) -> bool:
    """Phrase match with word boundaries for Latin repair/closure phrases."""
    phrase = phrase.lower()
    if re.fullmatch(r"[a-z][a-z0-9' -]*", phrase):
        pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return phrase in text


def is_valid_anchor(s: str) -> bool:
    # Allow single-character Japanese nouns such as 傘, 雨, 魚, 歯, but avoid tiny Latin function words.
    return len(s) >= 2 or contains_cjk_or_kana(s)


def salient_terms(text: str, concept_fields: Optional[Mapping[str, Sequence[str]]] = None) -> set:
    low = text.lower()
    terms = set()
    if concept_fields:
        for words in concept_fields.values():
            for w in words:
                wl = w.lower()
                if is_valid_anchor(wl) and anchor_in_text(wl, low):
                    terms.add(wl)
    # Latin words, plus quoted Japanese-ish chunks as fallback motifs.
    for w in re.findall(r"[a-zA-Z]{4,}", low):
        terms.add(w)
    for q in re.findall(r"[「『](.*?)[」』]", text):
        if 1 <= len(q) <= 12:
            terms.add(q.lower())
    return terms


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def l2_normalize(v: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm <= 1e-12:
        return v
    return [x / norm for x in v]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) + 1e-12)


# -----------------------------------------------------------------------------
# Generators
# -----------------------------------------------------------------------------

class BaseGenerator:
    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        raise NotImplementedError


class DummyGenerator(BaseGenerator):
    """Dependency-free English-first surreal fragment generator for exercising the steering loop."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.objects = ["umbrella", "chair", "key", "mirror", "refrigerator", "ticket", "shoe", "clock", "envelope", "elevator", "desk", "spoon"]
        self.places = ["station", "hospital corridor", "basement", "theater", "city roof", "inside of a window", "bridge", "office counter", "platform"]
        self.natures = ["sea", "moon", "sand", "fish", "bird", "snake", "cloud", "snow", "moss", "tide", "rain", "river"]
        self.body = ["tongue", "bone", "heart", "skin", "eyelid", "throat", "blood", "hand", "lung", "mouth"]
        self.abstracts = ["memory", "time", "silence", "name", "shadow", "prayer", "forgetting", "sleep", "absence", "voice", "childhood"]
        self.verbs = ["sleeps", "coughs", "prays", "dreams", "breathes", "waits", "laughs", "forgets", "sings", "listens"]
        self.repairish = [
            "This symbolizes loneliness and explains the scene.",
            "In other words, the umbrella represents childhood trauma.",
            "Because every image has a reason, the meaning becomes clear.",
            "Finally he returned to reality and understood everything.",
        ]
        self.noiseish = [
            "Umbrella, moon, bone, ticket, fish, window, stamp, tongue, sea, sea, sea.",
            "Purple purpled the purple because purple was purple.",
            "Meaning explodes without relation: chair salt invoice eyelid volcano.",
            "A cloud of document of rib of moon of shoe of silence of bird.",
        ]

    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        out: List[str] = []
        motifs = extract_prompt_motifs(prompt)
        for _ in range(n):
            r = self.rng.random()
            if r < 0.11:
                out.append(self.rng.choice(self.repairish))
                continue
            if r < 0.17:
                out.append(self.rng.choice(self.noiseish))
                continue
            templates = [
                "In the {place}, the {obj} {verb}. A {ticket} made of {nature} is attached to its {body}.",
                "The {obj} {verb} like {nature}, soaking the {abstract} of the {place}.",
                "When the window of the {place} opens, {nature} with its {body} is called by the {obj}'s name.",
                "{abstract} is submitted as a {obj}; at the {place}, it {verb} on the desk.",
                "Inside the {machine}, {nature} {verb}, while only the {body} remembers {abstract}.",
                "The {obj} was the {place}. {nature} walked down its stairs and stamped {abstract}.",
                "In other words, the {obj} was the lung of {nature}; {abstract} is pasted to the wall of the {place}.",
                "On the floor of the {place}, the {machine} comes undone and {nature} with its {body} climbs out of the {obj}.",
                "The {obj} stands in the {place} with its {body}, and {nature} receives its shadow.",
                "A {obj} is locked inside a {machine}, wearing the {body} of {abstract}.",
            ]
            motif = self.rng.choice(motifs) if motifs and self.rng.random() < 0.68 else None
            if motif:
                templates.extend([
                    "Beside {motif}, the {obj} {verb}. A ticket made of {nature} is attached to its {body}.",
                    "{motif} {verb} like {nature}, soaking the {abstract} of the {place}.",
                    "On the floor of the {place}, {motif} comes undone and {nature} with its {body} climbs out.",
                    "In other words, {motif} was the lung of {nature}; {abstract} is pasted to the wall of the {place}.",
                ])
            else:
                motif = self.rng.choice(self.objects + self.places)
            template = self.rng.choice(templates)
            s = template.format(
                place=self.rng.choice(self.places),
                obj=self.rng.choice(self.objects),
                nature=self.rng.choice(self.natures),
                body=self.rng.choice(self.body),
                abstract=self.rng.choice(self.abstracts),
                verb=self.rng.choice(self.verbs),
                machine=self.rng.choice(["radio", "circuit", "signal", "bulb", "screen", "engine", "printer"]),
                ticket=self.rng.choice(["ticket", "stamp", "document", "receipt", "passport"]),
                motif=motif,
            )
            out.append(s)
        return out


@dataclass
class SteeringRuntimeConfig:
    vectors_path: Optional[str] = None
    alpha: float = 0.0
    layers: Optional[List[int]] = None
    position: str = "last"  # last or all


class HFGenerator(BaseGenerator):
    """Optional Hugging Face backend. Imports are delayed so dummy mode stays dependency-free."""

    def __init__(self, model_name: str, device: Optional[str] = None, steering: Optional[SteeringRuntimeConfig] = None):
        try:
            import torch  # type: ignore
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("HF backend requires: pip install transformers torch") from e

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token or self.tokenizer.unk_token
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model.to(device)
        self.model.eval()
        self.steering = steering or SteeringRuntimeConfig()
        self._loaded_vectors: Optional[Dict[int, Any]] = None
        if self.steering.vectors_path:
            self._loaded_vectors = load_steering_vectors(self.steering.vectors_path, self.device)

    def generate(self, prompt: str, n: int, temperature: float, top_p: float, max_new_tokens: int) -> List[str]:
        torch = self.torch
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        hook_cm = contextlib.nullcontext()
        if self._loaded_vectors and self.steering.alpha != 0.0:
            hook_cm = SteeringHookManager(
                self.model,
                vectors=self._loaded_vectors,
                alpha=self.steering.alpha,
                layers=self.steering.layers,
                position=self.steering.position,
            )
        with torch.no_grad(), hook_cm:
            outputs = self.model.generate(
                **inputs,
                do_sample=True,
                temperature=max(0.05, temperature),
                top_p=top_p,
                num_return_sequences=n,
                max_new_tokens=max_new_tokens,
                repetition_penalty=1.06,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
        results = []
        for d in decoded:
            cont = d[len(prompt) :] if d.startswith(prompt) else d
            cont = cleanup_continuation(cont)
            results.append(cont)
        return results


GENERATED_CONTROL_TOKENS: Tuple[str, ...] = (
    "<|eot_id|>",
    "<|end_of_text|>",
    "<|begin_of_text|>",
    "<|im_end|>",
    "</s>",
    "<s>",
)


def cleanup_continuation(text: str) -> str:
    text = text.strip()
    for token in GENERATED_CONTROL_TOKENS:
        text = text.replace(token, " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    # Remove common prompt echo artifacts and labels.
    text = re.sub(r"^(続き|Continuation|Continue|Next image|New fragment)[:：]\s*", "", text, flags=re.I).strip()
    # If chat models append meta commentary after an otherwise good image, keep the
    # image and cut the commentary. Example: "... nearby. (Note: I've tried...)"
    m = META_LEAK_START_RE.search(text)
    if m:
        prefix = text[: m.start()].rstrip()
        text = prefix if prefix else ""
    # Also cut common line-level notes that do not start at char 0.
    text = re.split(r"(?im)^\s*(?:note|author's note|editor's note)\s*[:：]", text)[0].strip()
    # Keep at most two complete sentences/fragments.
    spans = re.split(r"(?<=[。.!?！？])\s+", text)
    if len(spans) > 2:
        text = " ".join(spans[:2])
    # If max_tokens cuts a second sentence halfway, drop the dangling tail after the
    # last sentence boundary. If there is no boundary at all, keep the open fragment.
    last_punct = max(text.rfind(p) for p in ".!?。！？") if text else -1
    if last_punct >= 24 and last_punct < len(text) - 1:
        tail = text[last_punct + 1 :].strip()
        if tail and len(tail.split()) >= 2:
            text = text[: last_punct + 1]
    # Very long unpunctuated continuation becomes hard to score as a local image.
    compact = re.sub(r"\s+", "", text)
    if len(compact) > 260 and not re.search(r"[。.!?！？]", compact):
        text = text[:260].rstrip(" ,;:-")
    return text.strip()


def extract_prompt_motifs(prompt: str) -> List[str]:
    m = re.search(r"(?:Core motif to retain|核イメージとして残す語):\s*(.*?)(?:\.|。)", prompt)
    if not m:
        return []
    raw = m.group(1)
    return [x.strip() for x in re.split(r"[/,、]", raw) if x.strip()]


# -----------------------------------------------------------------------------
# Steering engine
# -----------------------------------------------------------------------------

SELECT_OBJECTIVES: Tuple[str, ...] = ("depaysement", "frontier", "banded-frontier", "hybrid", "pareto")


@dataclass
class SelectorConfig:
    objective: str = "depaysement"
    frontier_weight: float = 1.0
    ontology_weight: float = 0.35
    unfinished_weight: float = 0.80
    repair_weight: float = 0.60
    repetition_weight: float = 0.30
    sprawl_weight: float = 0.20
    ontology_min: float = 0.20
    ontology_max: float = 0.60
    readability_min: float = 0.55
    frontier_quality_min: float = 0.20
    repair_max: float = 0.45
    unfinished_max: float = 0.50

    def __post_init__(self) -> None:
        if self.objective not in SELECT_OBJECTIVES:
            raise ValueError(f"unknown select objective: {self.objective!r}")

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class Candidate:
    text: str
    score: ScoreBreakdown
    selector_score: Optional[float] = None
    selector_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "text": self.text,
            "score": dataclasses.asdict(self.score),
            "score_compact": self.score.compact(),
        }
        if self.selector_score is not None:
            out["selector_score"] = self.selector_score
        if self.selector_metrics:
            out["selector_metrics"] = dict(self.selector_metrics)
        return out


@dataclass
class StepRecord:
    step: int
    mode: str
    motifs: Tuple[str, ...]
    picked: Candidate
    candidates: List[Candidate] = field(default_factory=list)
    prompt: str = ""

    def to_dict(self, *, include_candidates: bool = True, include_prompt: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "step": self.step,
            "mode": self.mode,
            "motifs": list(self.motifs),
            "picked": self.picked.to_dict(),
        }
        if include_candidates:
            out["candidates"] = [c.to_dict() for c in self.candidates]
        if include_prompt:
            out["prompt"] = self.prompt
        return out


@dataclass
class WriteRun:
    seed: str
    final_text: str
    steps: List[StepRecord]
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_candidates: bool = True, include_prompt: bool = False) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "final_text": self.final_text,
            "config": self.config,
            "steps": [s.to_dict(include_candidates=include_candidates, include_prompt=include_prompt) for s in self.steps],
        }


@dataclass
class DepaysementEngine:
    generator: BaseGenerator
    scorer: DepaysementScorer = field(default_factory=DepaysementScorer)
    rng: random.Random = field(default_factory=random.Random)
    motif_jitter: float = 0.38
    selector: SelectorConfig = field(default_factory=SelectorConfig)
    _selector_auditor: Any = field(default=None, init=False, repr=False)

    def write(
        self,
        seed: str,
        steps: int = 5,
        mode: str = "depaysement",
        candidates_per_step: int = 12,
        temperature: float = 1.05,
        top_p: float = 0.92,
        max_new_tokens: int = 120,
        choose: str = "softmax",
        trace: bool = False,
        prompt_style: str = "scene",
    ) -> str:
        return self.write_run(
            seed=seed,
            steps=steps,
            mode=mode,
            candidates_per_step=candidates_per_step,
            temperature=temperature,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
            choose=choose,
            trace=trace,
            prompt_style=prompt_style,
            keep_candidates=0,
        ).final_text

    def write_run(
        self,
        seed: str,
        steps: int = 5,
        mode: str = "depaysement",
        candidates_per_step: int = 12,
        temperature: float = 1.05,
        top_p: float = 0.92,
        max_new_tokens: int = 120,
        choose: str = "softmax",
        trace: bool = False,
        prompt_style: str = "scene",
        keep_candidates: int = 0,
        include_prompt: bool = False,
    ) -> WriteRun:
        text = seed.strip()
        records: List[StepRecord] = []
        config = {
            "steps": steps,
            "mode": mode,
            "candidates_per_step": candidates_per_step,
            "temperature": temperature,
            "top_p": top_p,
            "max_new_tokens": max_new_tokens,
            "choose": choose,
            "prompt_style": prompt_style,
            "motif_jitter": self.motif_jitter,
            "select_objective": self.selector.objective,
            "selector": self.selector.to_dict(),
        }
        for step in range(1, steps + 1):
            prompt = ""
            motifs: List[str] = []
            stored_candidates: List[Candidate] = []
            if mode == "automatic":
                prompt = build_automatic_prompt(text)
                candidates = self.generator.generate(
                    prompt,
                    n=max(1, candidates_per_step),
                    temperature=max(temperature, 1.45),
                    top_p=max(top_p, 0.95),
                    max_new_tokens=max_new_tokens,
                )
                candidate_objs = [Candidate(c, self.scorer.score(c, context=text)) for c in candidates if c.strip()]
                picked = self.rng.choice(candidate_objs) if candidate_objs else Candidate("", self.scorer.score("", context=text))
                stored_candidates = candidate_objs[:keep_candidates] if keep_candidates > 0 else []
            else:
                motifs = self._pick_motifs(text)
                prompt = build_depaysement_prompt(text, motifs=motifs, style=prompt_style)
                raw = self.generator.generate(
                    prompt,
                    n=candidates_per_step,
                    temperature=temperature,
                    top_p=top_p,
                    max_new_tokens=max_new_tokens,
                )
                scored = [Candidate(c, self.scorer.score(c, context=text)) for c in raw if c.strip()]
                if not scored:
                    break
                ranked = self._rank_candidates_for_selection(scored, context=text)
                picked = self._pick(ranked, choose=choose, score_fn=self._pick_score)
                stored_candidates = list(ranked[:keep_candidates]) if keep_candidates > 0 else []

            if trace:
                print(f"\n--- step {step} picked ---")
                print(picked.text)
                print(picked.score.compact())

            records.append(
                StepRecord(
                    step=step,
                    mode=mode,
                    motifs=tuple(motifs),
                    picked=picked,
                    candidates=stored_candidates,
                    prompt=prompt if include_prompt else "",
                )
            )
            text = join_text(text, picked.text)
        return WriteRun(seed=seed.strip(), final_text=text, steps=records, config=config)

    def rank(self, seed: str, n: int = 12, temperature: float = 1.05, top_p: float = 0.92, max_new_tokens: int = 120, prompt_style: str = "scene") -> List[Candidate]:
        motifs = self._pick_motifs(seed)
        prompt = build_depaysement_prompt(seed, motifs=motifs, style=prompt_style)
        raw = self.generator.generate(prompt, n=n, temperature=temperature, top_p=top_p, max_new_tokens=max_new_tokens)
        scored = [Candidate(c, self.scorer.score(c, context=seed)) for c in raw if c.strip()]
        scored.sort(key=lambda c: c.score.total, reverse=True)
        return scored

    def _rank_candidates_for_selection(self, candidates: Sequence[Candidate], *, context: str) -> List[Candidate]:
        objective = self.selector.objective
        ranked = list(candidates)
        if objective == "depaysement":
            ranked.sort(key=lambda c: c.score.total, reverse=True)
            return ranked

        for candidate in ranked:
            self._attach_selector_metrics(candidate, context=context)

        if objective == "pareto":
            return self._pareto_ranked_candidates(ranked)

        ranked.sort(key=self._pick_score, reverse=True)
        return ranked

    def _attach_selector_metrics(self, candidate: Candidate, *, context: str) -> None:
        from .frontier import clean_generated_text, readable_frontier_score

        cfg = self.selector
        auditor = self._get_selector_auditor()
        text = clean_generated_text(candidate.text)
        clean_context = clean_generated_text(context)
        metrics = auditor.audit_text(text, context=clean_context)
        frontier, quality = readable_frontier_score(metrics)
        ontology = float(metrics.ontology_collapse_density)
        readability = float(metrics.syntax_readability_proxy)
        repair = float(metrics.repair_pressure)
        unfinished = float(metrics.unfinished)
        repetition = max(0.0, -_score_attr(candidate.score, "anti_repetition"))
        sprawl = max(
            float(metrics.graph_fragmentation),
            max(0.0, -_score_attr(candidate.score, "anti_cluster_sprawl")),
            max(0.0, -_score_attr(candidate.score, "anti_image_fragmentation")),
        )
        ontology_band = _selector_bandpass(ontology, cfg.ontology_min, cfg.ontology_max)
        ontology_band_score = ontology * ontology_band
        penalty = (
            cfg.unfinished_weight * unfinished
            + cfg.repair_weight * repair
            + cfg.repetition_weight * repetition
            + cfg.sprawl_weight * sprawl
        )
        readability_deficit = max(0.0, cfg.readability_min - readability)
        frontier_quality_deficit = max(0.0, cfg.frontier_quality_min - quality)
        ontology_below = max(0.0, cfg.ontology_min - ontology)
        ontology_above = max(0.0, ontology - cfg.ontology_max)
        repair_excess = max(0.0, repair - cfg.repair_max)
        unfinished_excess = max(0.0, unfinished - cfg.unfinished_max)
        band_violation = (
            1.50 * ontology_below
            + 1.10 * ontology_above
            + 0.90 * readability_deficit
            + 0.70 * frontier_quality_deficit
            + cfg.repair_weight * repair_excess
            + cfg.unfinished_weight * unfinished_excess
            + 0.30 * repetition
            + 0.30 * sprawl
        )
        hybrid_score = (
            float(candidate.score.total)
            + cfg.frontier_weight * frontier
            + cfg.ontology_weight * ontology_band_score
            - penalty
            - 0.50 * readability_deficit
            - 0.25 * frontier_quality_deficit
            - 0.20 * (1.0 - ontology_band)
        )
        eligible = (
            cfg.ontology_min <= ontology <= cfg.ontology_max
            and readability >= cfg.readability_min
            and quality >= cfg.frontier_quality_min
            and repair <= cfg.repair_max
            and unfinished <= cfg.unfinished_max
        )
        banded_frontier_score = (
            (1.0 if eligible else 0.0)
            + cfg.frontier_weight * frontier
            + 0.15 * ontology_band_score
            - band_violation
        )

        if cfg.objective == "frontier":
            selector_score = frontier
        elif cfg.objective == "banded-frontier":
            selector_score = banded_frontier_score
        else:
            selector_score = hybrid_score
        candidate.selector_score = float(selector_score)
        candidate.selector_metrics = {
            "objective": cfg.objective,
            "selector_score": float(selector_score),
            "banded_frontier_score": float(banded_frontier_score),
            "hybrid_score": float(hybrid_score),
            "depaysement_score": float(candidate.score.total),
            "readable_ontology_frontier": float(frontier),
            "frontier_quality": float(quality),
            "ontology_collapse_density": ontology,
            "ontology_below_band": float(ontology_below),
            "ontology_above_band": float(ontology_above),
            "ontology_bandpass": float(ontology_band),
            "ontology_band_score": float(ontology_band_score),
            "syntax_readability_proxy": readability,
            "readability_deficit": float(readability_deficit),
            "frontier_quality_deficit": float(frontier_quality_deficit),
            "graph_integration": float(metrics.graph_integration),
            "graph_fragmentation": float(metrics.graph_fragmentation),
            "repair_pressure": repair,
            "repair_excess": float(repair_excess),
            "unfinished": unfinished,
            "unfinished_excess": float(unfinished_excess),
            "repetition_pressure": float(repetition),
            "sprawl_pressure": float(sprawl),
            "selector_penalty": float(penalty),
            "band_violation": float(band_violation),
            "selector_eligible": bool(eligible),
            "identity_melt_score": float(metrics.identity_melt_score),
            "affordance_corruption_score": float(metrics.affordance_corruption_score),
            "category_bleeding_score": float(metrics.category_bleeding_score),
        }

    def _get_selector_auditor(self):
        if self._selector_auditor is None:
            from .ontology import OntologyAuditor

            self._selector_auditor = OntologyAuditor(scorer=self.scorer)
        return self._selector_auditor

    def _pareto_ranked_candidates(self, candidates: Sequence[Candidate]) -> List[Candidate]:
        pool = [c for c in candidates if c.selector_metrics.get("selector_eligible")]
        if not pool:
            pool = list(candidates)
        front: List[Candidate] = []
        for candidate in pool:
            if not any(other is not candidate and _selector_dominates(other, candidate) for other in pool):
                candidate.selector_metrics["pareto_front"] = True
                front.append(candidate)
        front_ids = {id(c) for c in front}
        rest = [c for c in candidates if id(c) not in front_ids]
        for candidate in rest:
            candidate.selector_metrics["pareto_front"] = False
        front.sort(key=self._pick_score, reverse=True)
        rest.sort(key=self._pick_score, reverse=True)
        return front + rest

    def _pick_score(self, candidate: Candidate) -> float:
        if self.selector.objective != "depaysement" and candidate.selector_score is not None:
            return float(candidate.selector_score)
        return float(candidate.score.total)

    def _pick(
        self,
        candidates: Sequence[Candidate],
        choose: str = "softmax",
        *,
        score_fn: Optional[Callable[[Candidate], float]] = None,
    ) -> Candidate:
        score_fn = score_fn or (lambda c: float(c.score.total))
        if choose == "best":
            return candidates[0]
        if choose == "random_top3":
            return self.rng.choice(list(candidates[: min(3, len(candidates))]))
        # Softmax over top-k to avoid always selecting the same kind of surrealism.
        top = list(candidates[: min(6, len(candidates))])
        scores = [score_fn(c) for c in top]
        m = max(scores)
        exps = [math.exp((s - m) / 0.62) for s in scores]
        z = sum(exps)
        r = self.rng.random()
        acc = 0.0
        for c, e in zip(top, exps):
            acc += e / z
            if r <= acc:
                return c
        return top[-1]

    def _pick_motifs(self, context: str) -> List[str]:
        terms = sorted(salient_terms(context, self.scorer.concept_fields if self.scorer.lexicon_enabled else None))
        if not terms:
            return []
        # Jitter: sometimes keep no motif, sometimes one, rarely two.
        r = self.rng.random()
        if r < self.motif_jitter:
            return []
        if r > 0.92 and len(terms) >= 2:
            return self.rng.sample(terms, 2)
        return [self.rng.choice(terms)]


def _score_attr(score: Any, name: str) -> float:
    return float(getattr(score, name, 0.0) or 0.0)


def _selector_bandpass(value: float, low: float, high: float) -> float:
    value = clamp(float(value), 0.0, 1.0)
    low = clamp(float(low), 0.0, 1.0)
    high = clamp(float(high), 0.0, 1.0)
    if high <= low:
        return 1.0 if value >= low else clamp(value / max(low, 1e-12), 0.0, 1.0)
    if low <= value <= high:
        return 1.0
    if value < low:
        return clamp(value / max(low, 1e-12), 0.0, 1.0)
    return clamp((1.0 - value) / max(1.0 - high, 1e-12), 0.0, 1.0)


def _selector_dominates(left: Candidate, right: Candidate) -> bool:
    lm = left.selector_metrics
    rm = right.selector_metrics
    left_good = (
        float(lm.get("depaysement_score", 0.0)),
        float(lm.get("readable_ontology_frontier", 0.0)),
        float(lm.get("ontology_band_score", 0.0)),
    )
    right_good = (
        float(rm.get("depaysement_score", 0.0)),
        float(rm.get("readable_ontology_frontier", 0.0)),
        float(rm.get("ontology_band_score", 0.0)),
    )
    left_bad = (
        float(lm.get("unfinished", 0.0)),
        float(lm.get("repair_pressure", 0.0)),
        float(lm.get("repetition_pressure", 0.0)),
        float(lm.get("sprawl_pressure", 0.0)),
    )
    right_bad = (
        float(rm.get("unfinished", 0.0)),
        float(rm.get("repair_pressure", 0.0)),
        float(rm.get("repetition_pressure", 0.0)),
        float(rm.get("sprawl_pressure", 0.0)),
    )
    no_worse = all(left >= right for left, right in zip(left_good, right_good)) and all(
        left <= right for left, right in zip(left_bad, right_bad)
    )
    strictly_better = any(left > right for left, right in zip(left_good, right_good)) or any(
        left < right for left, right in zip(left_bad, right_bad)
    )
    return no_worse and strictly_better


def build_depaysement_prompt(context: str, motifs: Optional[Sequence[str]] = None, style: str = "scene") -> str:
    motifs = list(motifs or [])
    if motifs:
        motif_line = "Keep this motif physically present if possible: " + " / ".join(motifs) + ". Shift its domain.\n"
    else:
        motif_line = "You may keep one concrete object from the fragment; do not reset into a random new postcard.\n"

    if style == "legacy":
        return (
            "Continue the fragment in English.\n"
            "Mode: depaysement. Place heterogeneous things in the same visible scene.\n"
            "Do not explain, symbolize, moralize, or resolve. Avoid ordinary realistic repair.\n"
            "Make the image legible through at least one concrete relation: space, contact, possession, containment, exchange, or transformation.\n"
            "A phrase like 'in other words' is allowed only when it opens a new image, not when it explains the image.\n"
            f"{motif_line}"
            f"Fragment:\n{context.strip()}\n"
            "Continuation, one or two sentences only. Return only the continuation text; no notes, commentary, labels, or parentheses explaining the task:\n"
        )

    # Default: scene-only prompt. This avoids naming the artistic theory inside the
    # prompt, because small/chat models tend to leak instruction-frame words such as
    # "Note:" or "as per the instructions" into the continuation.
    return (
        "Write the next visible image in English.\n"
        "Output only the continuation text. No Note:, no commentary, no labels, no analysis, no mention of instructions.\n"
        "Use one complete sentence, or two short complete sentences. Avoid unfinished endings.\n"
        "Let unlike things share one concrete place. Make the image legible through space, contact, possession, containment, exchange, or transformation.\n"
        "Do not explain what anything means. Do not summarize. Do not resolve.\n"
        f"{motif_line}"
        f"Fragment:\n{context.strip()}\n"
        "Next image:\n"
    )

def build_automatic_prompt(context: str) -> str:
    return (
        "Continue the fragment in English like automatic writing. Do not explain. Do not polish.\n"
        "Let association move quickly, but keep some grammar.\n"
        f"Fragment:\n{context.strip()}\n"
        "Continuation:\n"
    )


def join_text(a: str, b: str) -> str:
    a = a.rstrip()
    b = b.strip()
    if not b:
        return a
    if not a:
        return b
    if a.endswith(("。", ".", "!", "?", "！", "？", "\n")):
        return a + " " + b
    return a + " " + b


# -----------------------------------------------------------------------------
# Prompt bank expansion
# -----------------------------------------------------------------------------

@dataclass
class BankExpansionResult:
    bank: PromptBank
    positive_ranked: List[Candidate]
    negative_ranked: List[str]


class BankExpander:
    def __init__(self, generator: BaseGenerator, scorer: DepaysementScorer, rng: random.Random):
        self.generator = generator
        self.scorer = scorer
        self.rng = rng

    def expand(self, bank: PromptBank, positive_n: int, negative_n: int, temperature: float, top_p: float, max_new_tokens: int) -> BankExpansionResult:
        pos_prompt = self._positive_expansion_prompt(bank)
        raw_pos = self.generator.generate(pos_prompt, n=max(positive_n * 3, positive_n), temperature=temperature, top_p=top_p, max_new_tokens=max_new_tokens)
        pos_candidates = self._extract_fragments(raw_pos)
        pos_ranked = [Candidate(t, self.scorer.score(t, context="")) for t in pos_candidates]
        pos_ranked.sort(key=lambda c: c.score.total, reverse=True)
        positive_new = [c.text for c in pos_ranked if c.score.image_schema > 0.25 and c.score.anti_scene_failure > -0.45]
        positive_new = unique_preserve_order(positive_new)[:positive_n]

        neg_prompt = self._negative_expansion_prompt(bank)
        raw_neg = self.generator.generate(neg_prompt, n=max(negative_n * 3, negative_n), temperature=max(temperature, 1.15), top_p=top_p, max_new_tokens=max_new_tokens)
        neg_candidates = self._extract_fragments(raw_neg)
        # Keep only genuine negatives: repair-ish, realist/low-image, closure, or noisy noun-collage.
        # This prevents a strong generator from accidentally adding good depaysement examples to the negative bank.
        neg_ranked_all = sorted(unique_preserve_order(neg_candidates), key=self._negative_priority, reverse=True)
        neg_ranked = [n for n in neg_ranked_all if self._is_negative_candidate(n)]
        negative_new = neg_ranked[:negative_n]

        negative_repair_new = []
        negative_noise_new = []
        for n in negative_new:
            hits_n = self.scorer._concept_hits(n)
            schemas_n = relation_schemas(n)
            if collapse_penalty(n) >= 0.35 or keyword_stuffing_penalty(n, hits_n) > 0.35 or semantic_collage_penalty(n, schemas_n, hits_n) > 0.35:
                negative_noise_new.append(n)
            elif contextual_repair_penalty(n, schemas_n, hits_n) > 0.20 or phrase_rate(n, CLOSURE_PHRASES) > 0.15:
                negative_repair_new.append(n)
            else:
                # Low-image realist examples belong here too.
                negative_repair_new.append(n)

        out = PromptBank(
            positive_depaysement=unique_preserve_order(bank.positive_depaysement + positive_new),
            negative_realist_repair=unique_preserve_order(bank.negative_realist_repair + negative_repair_new),
            negative_weird_noise=unique_preserve_order(bank.negative_weird_noise + negative_noise_new),
        )
        return BankExpansionResult(out, pos_ranked[: max(positive_n, 8)], neg_ranked[: max(negative_n, 8)])

    @staticmethod
    def _positive_expansion_prompt(bank: PromptBank) -> str:
        examples = "\n".join(f"- {x}" for x in bank.positive_depaysement[:8])
        return (
            "Write multiple one-sentence depaysement fragments in English, in the direction of the examples.\n"
            "Constraints: heterogeneous objects must share one visible scene; include a spatial/contact/possession/containment/exchange/transformation relation; avoid explanation and closure.\n"
            "Do not output a bare noun collage.\n"
            f"Examples:\n{examples}\n"
            "New fragments:\n"
        )

    @staticmethod
    def _negative_expansion_prompt(bank: PromptBank) -> str:
        examples = "\n".join(f"- {x}" for x in (bank.negative_realist_repair + bank.negative_weird_noise)[:8])
        return (
            "Write multiple English fragments that fail as depaysement.\n"
            "Failure types: realistic repair, symbolic explanation, closure, or semantic collage with no staged image.\n"
            f"Examples:\n{examples}\n"
            "New failed fragments:\n"
        )

    @staticmethod
    def _extract_fragments(raw: Sequence[str]) -> List[str]:
        out: List[str] = []
        for blob in raw:
            # Split bullet lists and then sentence-like chunks.
            parts = re.split(r"\n+|(?:^|\n)\s*[-*・]\s*", blob)
            for p in parts:
                p = p.strip(" \t-・*0123456789.．)）")
                if not p:
                    continue
                spans = re.split(r"(?<=[。.!?！？])\s+", p)
                for s in spans:
                    s = s.strip()
                    if 6 <= len(re.sub(r"\s+", "", s)) <= 160:
                        out.append(s)
        return unique_preserve_order(out)

    def _is_negative_candidate(self, text: str) -> bool:
        hits = self.scorer._concept_hits(text)
        schemas = relation_schemas(text)
        dep = self.scorer.score(text, context="")
        repair = contextual_repair_penalty(text, schemas, hits)
        closure = phrase_rate(text, CLOSURE_PHRASES)
        collapse = collapse_penalty(text)
        stuff = keyword_stuffing_penalty(text, hits)
        sema = semantic_collage_penalty(text, schemas, hits)
        low_image_realist = dep.total < 1.20 and dep.image_schema < 0.28
        return repair > 0.20 or closure > 0.15 or collapse > 0.28 or stuff > 0.35 or sema > 0.35 or dep.anti_scene_failure < -0.45 or low_image_realist

    def _negative_priority(self, text: str) -> float:
        hits = self.scorer._concept_hits(text)
        schemas = relation_schemas(text)
        repair = contextual_repair_penalty(text, schemas, hits)
        closure = phrase_rate(text, CLOSURE_PHRASES)
        collapse = collapse_penalty(text)
        stuff = keyword_stuffing_penalty(text, hits)
        sema = semantic_collage_penalty(text, schemas, hits)
        dep = self.scorer.score(text, context="")
        low_image = 1.0 if dep.image_schema < 0.28 else 0.0
        return repair + closure + collapse + stuff + sema + 0.35 * low_image - 0.22 * dep.total


# -----------------------------------------------------------------------------
# Activation steering vectors for Hugging Face CausalLMs
# -----------------------------------------------------------------------------

def collect_steering_vectors(
    model_name: str,
    bank: PromptBank,
    out_path: str,
    device: Optional[str] = None,
    batch_size: int = 4,
    layers: Optional[List[int]] = None,
    token_strategy: str = "mean",
) -> None:
    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("collect-vectors requires: pip install transformers torch") from e

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    pos_prompts = list(bank.positive_depaysement)
    neg_prompts = list(bank.negatives)
    pos_means = _hidden_means(model, tokenizer, pos_prompts, device, batch_size, token_strategy)
    neg_means = _hidden_means(model, tokenizer, neg_prompts, device, batch_size, token_strategy)

    # hidden_states[0] is embeddings; module layer i roughly maps to hidden_states[i+1].
    n_module_layers = min(len(pos_means), len(neg_means)) - 1
    if layers is None:
        selected = list(range(n_module_layers))
    else:
        selected = [layer for layer in layers if 0 <= layer < n_module_layers]

    vectors: Dict[int, Any] = {}
    norms: Dict[int, float] = {}
    for module_layer in selected:
        v = pos_means[module_layer + 1] - neg_means[module_layer + 1]
        norm = float(torch.linalg.vector_norm(v).item())
        norms[module_layer] = norm
        if norm > 1e-12:
            v = v / norm
        vectors[module_layer] = v.detach().cpu()

    payload = {
        "vectors": vectors,
        "metadata": {
            "model_name": model_name,
            "token_strategy": token_strategy,
            "num_positive": len(pos_prompts),
            "num_negative": len(neg_prompts),
            "module_layer_indexing": "0-based transformer block index; vector computed from hidden_states[layer+1]",
            "norms_before_unit_normalization": norms,
        },
        "positive_depaysement": pos_prompts,
        "negative_prompts": neg_prompts,
    }
    torch.save(payload, out_path)


def _hidden_means(model: Any, tokenizer: Any, prompts: List[str], device: str, batch_size: int, token_strategy: str):
    import torch  # type: ignore

    layer_sums: Optional[List[Any]] = None
    count = 0
    with torch.no_grad():
        for start in range(0, len(prompts), batch_size):
            batch = prompts[start : start + batch_size]
            enc = tokenizer(batch, padding=True, truncation=True, return_tensors="pt").to(device)
            out = model(**enc, output_hidden_states=True, use_cache=False)
            hidden_states = out.hidden_states
            mask = enc["attention_mask"].to(hidden_states[0].dtype)
            batch_layer_means = []
            for h in hidden_states:
                if token_strategy == "last":
                    lengths = enc["attention_mask"].sum(dim=1).clamp_min(1) - 1
                    idx = lengths[:, None, None].expand(-1, 1, h.shape[-1])
                    pooled = h.gather(dim=1, index=idx).squeeze(1)
                else:
                    pooled = (h * mask[:, :, None]).sum(dim=1) / mask.sum(dim=1).clamp_min(1)[:, None]
                batch_layer_means.append(pooled.mean(dim=0))
            if layer_sums is None:
                layer_sums = [x.detach().clone() * len(batch) for x in batch_layer_means]
            else:
                for i, x in enumerate(batch_layer_means):
                    layer_sums[i] += x.detach() * len(batch)
            count += len(batch)
    assert layer_sums is not None
    return [x / max(count, 1) for x in layer_sums]


def load_steering_vectors(path: str, device: str) -> Dict[int, Any]:
    import torch  # type: ignore
    payload = torch.load(path, map_location=device)
    raw = payload.get("vectors", payload)
    vectors: Dict[int, Any] = {}
    for k, v in raw.items():
        vectors[int(k)] = v.to(device)
    return vectors


class SteeringHookManager:
    """Context manager that injects layer-wise vectors into common HF transformer blocks."""

    def __init__(self, model: Any, vectors: Dict[int, Any], alpha: float, layers: Optional[List[int]] = None, position: str = "last"):
        self.model = model
        self.vectors = vectors
        self.alpha = alpha
        self.layers = layers
        self.position = position
        self.handles: List[Any] = []

    def __enter__(self):
        modules = infer_transformer_layers(self.model)
        selected = self.layers if self.layers is not None else sorted(self.vectors.keys())
        for idx in selected:
            if idx < 0 or idx >= len(modules) or idx not in self.vectors:
                continue
            module = modules[idx]
            vec = self.vectors[idx]
            handle = module.register_forward_hook(self._make_hook(vec))
            self.handles.append(handle)
        return self

    def __exit__(self, exc_type, exc, tb):
        for h in self.handles:
            h.remove()
        self.handles.clear()
        return False

    def _make_hook(self, vec: Any):
        alpha = self.alpha
        position = self.position

        def hook(module: Any, inputs: Tuple[Any, ...], output: Any):
            return add_vector_to_layer_output(output, vec, alpha, position)

        return hook


def add_vector_to_layer_output(output: Any, vec: Any, alpha: float, position: str = "last") -> Any:
    import torch  # type: ignore

    def add_to_tensor(t):
        if not torch.is_tensor(t) or t.shape[-1] != vec.shape[-1]:
            return t
        v = vec.to(device=t.device, dtype=t.dtype).view(1, 1, -1)
        if position == "all":
            return t + alpha * v
        # clone to avoid in-place changes that can upset autograd/generate internals
        out = t.clone()
        out[:, -1:, :] = out[:, -1:, :] + alpha * v
        return out

    if torch.is_tensor(output):
        return add_to_tensor(output)
    if isinstance(output, tuple) and output:
        first = add_to_tensor(output[0])
        return (first,) + output[1:]
    if isinstance(output, list) and output:
        out = list(output)
        out[0] = add_to_tensor(out[0])
        return out
    return output


def infer_transformer_layers(model: Any) -> List[Any]:
    """Find the main ModuleList of transformer blocks for common HF CausalLMs."""
    import torch  # type: ignore

    cfg = getattr(model, "config", None)
    expected = None
    for attr in ["num_hidden_layers", "n_layer", "num_layers"]:
        if cfg is not None and hasattr(cfg, attr):
            expected = int(getattr(cfg, attr))
            break

    candidates = []
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.ModuleList):
            length = len(module)
            score = 0
            lname = name.lower()
            if expected is not None and length == expected:
                score += 5
            if any(k in lname for k in ["layers", "h", "block", "blocks"]):
                score += 2
            if any(k in lname for k in ["transformer", "model", "decoder", "gpt_neox"]):
                score += 1
            if length >= 2:
                candidates.append((score, length, name, module))
    if not candidates:
        raise RuntimeError("Could not infer transformer layer ModuleList. Provide model-specific hook code.")
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return list(candidates[0][3])


# -----------------------------------------------------------------------------
# CLI utilities
# -----------------------------------------------------------------------------

def make_bank_scorer(args: argparse.Namespace, bank: PromptBank) -> Optional[Any]:
    if getattr(args, "no_bank_score", False):
        return None
    embed_model = getattr(args, "embed_model", None)
    if embed_model:
        return HFEmbeddingBankScorer(embed_model, bank, device=getattr(args, "device", None))
    return HashBankScorer(bank)


def load_concept_fields(path: Optional[str]) -> Dict[str, List[str]]:
    if not path:
        return dict(DEFAULT_CONCEPT_FIELDS)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(k): list(v) for k, v in data.items()}


def make_scorer(args: argparse.Namespace) -> DepaysementScorer:
    bank = PromptBank.from_file(getattr(args, "bank", None))
    concept_fields = load_concept_fields(getattr(args, "lexicon", None))
    bank_scorer = make_bank_scorer(args, bank)
    bank_mode = getattr(bank_scorer, "score_kind", "off") if bank_scorer else "off"
    profile = getattr(args, "scorer_profile", "structural")
    weights = weights_for_profile(profile, bank_mode=bank_mode)
    if getattr(args, "bank_weight", None) is not None:
        weights.bank_contrast = float(args.bank_weight)
    lexicon_mode = getattr(args, "lexicon_mode", None)
    if lexicon_mode is None:
        lexicon_mode = "off" if profile == "structural" else "weak"
    if getattr(args, "disable_lexicon", False):
        lexicon_mode = "off"
    return DepaysementScorer(
        weights=weights,
        concept_fields=concept_fields,
        bank_scorer=bank_scorer,
        lexicon_enabled=(lexicon_mode != "off"),
    )

def make_generator(args: argparse.Namespace, rng: random.Random) -> BaseGenerator:
    if args.backend == "dummy":
        return DummyGenerator(rng)
    if args.backend == "hf":
        layers = parse_layer_list(getattr(args, "steer_layers", None))
        steering = SteeringRuntimeConfig(
            vectors_path=getattr(args, "vectors", None),
            alpha=float(getattr(args, "steer_alpha", 0.0) or 0.0),
            layers=layers,
            position=getattr(args, "steer_position", "last"),
        )
        return HFGenerator(args.model, device=args.device, steering=steering)
    raise ValueError(f"Unknown backend: {args.backend}")


def parse_layer_list(s: Optional[str]) -> Optional[List[int]]:
    if not s:
        return None
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def add_common_generation_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--backend", choices=["dummy", "hf"], default="dummy")
    p.add_argument("--model", default="gpt2", help="HF model id for --backend hf")
    p.add_argument("--device", default=None, help="cpu / cuda / auto(None)")
    p.add_argument("--bank", default=None, help="prompt bank JSON; defaults to built-in bank")
    p.add_argument("--lexicon", default=None, help="optional concept lexicon JSON")
    p.add_argument("--disable-lexicon", action="store_true", help="turn off concept lexicon features; relation/bank scoring remains")
    p.add_argument("--no-bank-score", action="store_true", help="disable prompt-bank contrast score")
    p.add_argument("--embed-model", default=None, help="optional HF encoder for semantic bank contrast")
    p.add_argument("--vectors", default=None, help="steering vectors .pt for HF generation")
    p.add_argument("--steer-alpha", type=float, default=0.0)
    p.add_argument("--steer-layers", default=None, help="comma/range list, e.g. 4,5,6 or 4-8")
    p.add_argument("--steer-position", choices=["last", "all"], default="last")
    p.add_argument("--random-seed", type=int, default=7)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Depaysement steering prototype v2")
    sub = parser.add_subparsers(dest="command", required=True)

    w = sub.add_parser("write", help="multi-step depaysement / automatic writing")
    add_common_generation_args(w)
    w.add_argument("--seed", default="駅に忘れられた傘が")
    w.add_argument("--mode", choices=["depaysement", "automatic"], default="depaysement")
    w.add_argument("--steps", type=int, default=5)
    w.add_argument("--candidates", type=int, default=12)
    w.add_argument("--temperature", type=float, default=1.05)
    w.add_argument("--top-p", type=float, default=0.92)
    w.add_argument("--max-new-tokens", type=int, default=70)
    w.add_argument("--choose", choices=["best", "softmax", "random_top3"], default="softmax")
    w.add_argument("--motif-jitter", type=float, default=0.38, help="probability of dropping motif carry-over")
    w.add_argument("--trace", action="store_true")

    r = sub.add_parser("rank", help="rank candidates for one continuation step")
    add_common_generation_args(r)
    r.add_argument("--seed", default="駅に忘れられた傘が")
    r.add_argument("--candidates", type=int, default=12)
    r.add_argument("--temperature", type=float, default=1.05)
    r.add_argument("--top-p", type=float, default=0.92)
    r.add_argument("--max-new-tokens", type=int, default=70)

    e = sub.add_parser("expand-bank", help="generate/rerank positive and negative prompt-bank examples")
    add_common_generation_args(e)
    e.add_argument("--out", required=True)
    e.add_argument("--positive", type=int, default=24)
    e.add_argument("--negative", type=int, default=16)
    e.add_argument("--temperature", type=float, default=1.12)
    e.add_argument("--top-p", type=float, default=0.94)
    e.add_argument("--max-new-tokens", type=int, default=80)
    e.add_argument("--trace", action="store_true")

    c = sub.add_parser("collect-vectors", help="collect layer-wise positive-negative activation steering vectors")
    c.add_argument("--model", required=True)
    c.add_argument("--bank", default=None)
    c.add_argument("--out", required=True)
    c.add_argument("--device", default=None)
    c.add_argument("--batch-size", type=int, default=4)
    c.add_argument("--layers", default=None, help="comma/range list; default all")
    c.add_argument("--token-strategy", choices=["mean", "last"], default="mean")

    s = sub.add_parser("score", help="score a single fragment")
    s.add_argument("text", nargs="?", default="傘は小さな劇場になり、その座席に雨の歯が並んでいる。")
    s.add_argument("--context", default="")
    s.add_argument("--bank", default=None)
    s.add_argument("--lexicon", default=None)
    s.add_argument("--disable-lexicon", action="store_true")
    s.add_argument("--no-bank-score", action="store_true")
    s.add_argument("--embed-model", default=None)
    s.add_argument("--device", default=None)

    b = sub.add_parser("show-bank", help="print or write the default/current prompt bank")
    b.add_argument("--bank", default=None)
    b.add_argument("--out", default=None)

    sub.add_parser("intervention-sketch", help="print internal-intervention sketch")
    return parser


def cmd_write(args: argparse.Namespace) -> None:
    rng = random.Random(args.random_seed)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    engine = DepaysementEngine(generator=generator, scorer=scorer, rng=rng, motif_jitter=args.motif_jitter)
    result = engine.write(
        seed=args.seed,
        steps=args.steps,
        mode=args.mode,
        candidates_per_step=args.candidates,
        temperature=args.temperature,
        top_p=args.top_p,
        max_new_tokens=args.max_new_tokens,
        choose=args.choose,
        trace=args.trace,
    )
    print("\n=== result ===")
    print(result)


def cmd_rank(args: argparse.Namespace) -> None:
    rng = random.Random(args.random_seed)
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    engine = DepaysementEngine(generator=generator, scorer=scorer, rng=rng)
    ranked = engine.rank(args.seed, n=args.candidates, temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens)
    for i, c in enumerate(ranked, 1):
        print(f"\n#{i} {c.score.compact()}\n{c.text}")


def cmd_expand_bank(args: argparse.Namespace) -> None:
    rng = random.Random(args.random_seed)
    bank = PromptBank.from_file(args.bank)
    # Use a temporary scorer with current bank; after expansion the saved bank becomes the new contrast source.
    generator = make_generator(args, rng)
    scorer = make_scorer(args)
    expander = BankExpander(generator, scorer, rng)
    result = expander.expand(bank, positive_n=args.positive, negative_n=args.negative, temperature=args.temperature, top_p=args.top_p, max_new_tokens=args.max_new_tokens)
    result.bank.write(args.out)
    print(f"Wrote prompt bank: {args.out}")
    print(f"positive_depaysement={len(result.bank.positive_depaysement)}")
    print(f"negative_realist_repair={len(result.bank.negative_realist_repair)}")
    print(f"negative_weird_noise={len(result.bank.negative_weird_noise)}")
    if args.trace:
        print("\nTop positive candidates:")
        for c in result.positive_ranked[:10]:
            print(f"- {c.text} :: {c.score.compact()}")
        print("\nTop negative candidates:")
        for n in result.negative_ranked[:10]:
            print(f"- {n}")


def cmd_collect_vectors(args: argparse.Namespace) -> None:
    bank = PromptBank.from_file(args.bank)
    layers = parse_layer_list(args.layers)
    collect_steering_vectors(
        model_name=args.model,
        bank=bank,
        out_path=args.out,
        device=args.device,
        batch_size=args.batch_size,
        layers=layers,
        token_strategy=args.token_strategy,
    )
    print(f"Wrote steering vectors: {args.out}")


def cmd_score(args: argparse.Namespace) -> None:
    scorer = make_scorer(args)
    score = scorer.score(args.text, context=args.context)
    print(score.compact())


def cmd_show_bank(args: argparse.Namespace) -> None:
    bank = PromptBank.from_file(args.bank)
    data = bank.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote prompt bank: {args.out}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def print_intervention_sketch() -> None:
    print(
        """
Internal-intervention pipeline:

  A. External shell first
     Generate K continuations -> score with depaysement scorer -> reject collapse / repair / closure -> sample top candidates.
     This keeps activation steering from degenerating into mere noise.

  B. Prompt-bank expansion
     1. Start with positive_depaysement examples and negative_realist_repair / negative_weird_noise examples.
     2. Expand positive examples using the generator.
     3. Rerank by image_schema + cross-domain adjacency + anti-repair + anti-collapse.
     4. Expand/keep negatives as realist repair, explanation, closure, or noun-collage collapse.

  C. Layer-wise vector collection
     For every transformer block l:
       v_l = mean_hidden_l(positive_depaysement) - mean_hidden_l(negative_prompts)
       v_l <- normalize(v_l)
     In this script, module layer l maps to hidden_states[l+1].

  D. Generation-time injection
     During generation:
       h_l <- h_l + alpha * v_l
     Default hook applies to the last token position to avoid rewriting the whole prompt.

  E. Practical sweep
     Try alpha in [0.4, 0.8, 1.2, 1.8].
     Try middle layers first, e.g. 1/3 to 2/3 of depth.
     Keep the external scorer active while sweeping.
""".strip()
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "write":
        cmd_write(args)
    elif args.command == "rank":
        cmd_rank(args)
    elif args.command == "expand-bank":
        cmd_expand_bank(args)
    elif args.command == "collect-vectors":
        cmd_collect_vectors(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "show-bank":
        cmd_show_bank(args)
    elif args.command == "intervention-sketch":
        print_intervention_sketch()
    else:
        parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()

meta_commentary_penalty = meta_leak_penalty
