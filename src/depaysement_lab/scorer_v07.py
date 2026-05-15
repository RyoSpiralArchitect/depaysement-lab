from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .proto_v2 import (
    AGENCY_VERBS,
    CLOSURE_PHRASES,
    CONCRETE_FIELDS,
    DEFAULT_CONCEPT_FIELDS,
    HFEmbeddingBankScorer,
    HashBankScorer,
    INANIMATE_FIELDS,
    PAIR_BONUS,
    PromptBank,
    REPAIR_CONNECTORS,
    REPAIR_META_TERMS,
    anchor_in_text,
    clamp,
    collapse_penalty,
    image_schema_score,
    is_valid_anchor,
    keyword_stuffing_penalty,
    meta_leak_penalty as meta_commentary_penalty,
    normalize_text,
    phrase_in_text,
    phrase_rate,
    relation_schemas,
    repetition_penalty,
    salient_terms,
    scene_failure_penalty,
    split_spans,
    unfinished_fragment_penalty,
    unique_preserve_order,
)


# -----------------------------------------------------------------------------
# Relation graph: lexicon-free staged-image integration
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
    "morass", "cryptic", "messages", "faded", "plastic", "frayed", "electrical", "around",
    "deceased", "shut", "abandoned", "wrapped", "tangled", "glued", "constructed", "etched", "scrawled", "smeared",
    "deceased", "wrapped", "constructed", "tangled", "glued", "shut", "around", "scrawled", "etched",
}

RELATION_PREPOSITIONS = {
    "in", "inside", "outside", "on", "under", "beneath", "above", "beside", "near", "behind",
    "before", "within", "at", "through", "across", "against", "between", "underneath", "over",
    "along", "below", "into", "of", "next to", "wrapped in", "tied to", "glued to", "attached to", "made of",
    "constructed from", "etched with", "smeared with", "filled with", "covered with", "tangled with",
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
    "tangle", "tangles", "tangled", "wrap", "wraps", "wrapped", "glue", "glues", "glued",
    "construct", "constructs", "constructed", "etch", "etched", "scrawl", "scrawled",
    "wear", "wears", "wearing", "lock", "locks", "locked", "remember", "remembers", "remembering",
}

CONTENT_VERBISH = RELATION_VERBS | {"seem", "seems", "seemed", "try", "tried", "continue", "maintain", "follow", "write", "generate"}


@dataclass
class ImageRelationGraph:
    """A cheap graph of staged-image anchors and relations.

    This is deliberately not a parser. It exists to separate relation quantity
    from relation integration: a sentence can contain many relation words and still
    be a loose object chain.
    """

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
        object_component = clamp(self.object_count / 5.0, 0.0, 1.0)
        relation_component = self.relation_quantity_score()
        return clamp(0.42 * object_component + 0.58 * relation_component, 0.0, 1.0)

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
        return (
            f"objects={self.object_count},rels={self.relation_count},"
            f"components={self.component_count},giant={self.giant_ratio:.2f},"
            f"sprawl={self.cluster_sprawl_penalty():.2f}"
        )


def _normalize_word_token(word: str) -> str:
    w = word.lower().strip("'-")
    if w.endswith("'s"):
        w = w[:-2]
    return w


def _english_word_tokens(text: str) -> List[Tuple[str, int, int]]:
    return [(_normalize_word_token(m.group(0)), m.start(), m.end()) for m in re.finditer(r"[a-zA-Z][a-zA-Z'-]*", text)]


def _is_content_anchor(word: str) -> bool:
    w = _normalize_word_token(word)
    if len(w) < 3:
        return False
    if w in EN_STOPWORDS or w in CONTENT_VERBISH:
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

    for w, s, e in tokens:
        if w in RELATION_VERBS:
            a = _nearest_content_before(tokens, s)
            b = _nearest_content_after(tokens, e)
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

    return ImageRelationGraph(
        object_terms=tuple(object_terms),
        edges=edges,
        components=components,
        of_chain_count=of_chain_count,
        comma_clause_count=len(clauses),
        dangling_clause_count=dangling_clause_count,
    )


# -----------------------------------------------------------------------------
# Structural-first scorer
# -----------------------------------------------------------------------------

@dataclass
class V07ScoreBreakdown:
    total: float
    concept_dispersion: float = 0.0
    pair_distance: float = 0.0
    agency_inversion: float = 0.0
    aesthetic_prior: float = 0.0
    ontology_leak: float = 0.0
    image_schema: float = 0.0
    relation_quantity: float = 0.0
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
    anti_cluster_sprawl: float = 0.0
    anti_meta_leak: float = 0.0
    anti_unfinished: float = 0.0
    concept_tags: Tuple[str, ...] = ()
    relation_schemas: Tuple[str, ...] = ()
    relation_objects: Tuple[str, ...] = ()
    relation_edges: Tuple[Tuple[str, str, str], ...] = ()
    relation_components: Tuple[Tuple[str, ...], ...] = ()
    shared_anchors: Tuple[str, ...] = ()

    def compact(self) -> str:
        parts = [
            f"total={self.total:.2f}",
            f"concepts={self.concept_dispersion:.2f}",
            f"pairs={self.pair_distance:.2f}",
            f"agency={self.agency_inversion:.2f}",
            f"aesthetic={self.aesthetic_prior:.2f}",
            f"leak={self.ontology_leak:.2f}",
            f"schema={self.image_schema:.2f}",
            f"rel_q={self.relation_quantity:.2f}",
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
            f"sprawl={self.anti_cluster_sprawl:.2f}",
            f"meta={self.anti_meta_leak:.2f}",
            f"unfinished={self.anti_unfinished:.2f}",
            f"tags={','.join(self.concept_tags) or '-'}",
            f"schemas={','.join(self.relation_schemas) or '-'}",
            f"objects={','.join(self.relation_objects[:10]) or '-'}",
            f"shared={','.join(self.shared_anchors) or '-'}",
        ]
        return " | ".join(parts)


@dataclass
class V07Weights:
    # Lexicon prior weights are multiplied by lexicon_prior_scale.
    concept_dispersion: float = 0.70
    pair_distance: float = 1.10
    agency_inversion: float = 1.05
    ontology_leak: float = 0.90
    image_schema: float = 1.05
    relation_quantity: float = 0.75
    image_integration: float = 1.45
    concrete_grounding: float = 0.70
    bank_contrast: float = 0.18
    anchor_resonance: float = 0.92
    voice_hinge: float = 0.30
    repair_penalty: float = 1.70
    closure_penalty: float = 1.15
    collapse_penalty: float = 2.00
    repetition_penalty: float = 0.85
    keyword_stuffing_penalty: float = 1.35
    context_overfit_penalty: float = 0.85
    context_orphan_penalty: float = 0.82
    scene_failure_penalty: float = 1.20
    semantic_collage_penalty: float = 1.15
    cluster_sprawl_penalty: float = 1.30
    meta_leak_penalty: float = 2.80
    unfinished_penalty: float = 0.85


@dataclass
class V07DepaysementScorer:
    weights: V07Weights = field(default_factory=V07Weights)
    concept_fields: Mapping[str, Sequence[str]] = field(default_factory=lambda: DEFAULT_CONCEPT_FIELDS)
    bank_scorer: Optional[Any] = None
    lexicon_enabled: bool = True
    lexicon_prior_scale: float = 0.18
    anchor_ideal: float = 0.26
    anchor_width: float = 0.34

    def score(self, text: str, context: str = "") -> V07ScoreBreakdown:
        clean = normalize_text(text)
        hits = self._concept_hits(clean) if self.lexicon_enabled else {}
        tags = tuple(sorted(hits.keys()))
        graph = image_relation_graph(clean)
        bank_mode = getattr(self.bank_scorer, "score_kind", "off") if self.bank_scorer else "off"

        concept_component = min(len(tags), 4) / 4.0 if self.lexicon_enabled else 0.0
        pair_component = self._pair_distance(tags) if self.lexicon_enabled else 0.0
        agency_component = self._agency_inversion(clean, hits) if self.lexicon_enabled else 0.0
        lexicon_prior = self.lexicon_prior_scale * (
            self.weights.concept_dispersion * concept_component
            + self.weights.pair_distance * pair_component
            + self.weights.agency_inversion * agency_component
        )

        schemas = relation_schemas(clean)
        ontology_component = self._ontology_leak(clean, tags, graph)
        image_component = image_schema_score(clean, schemas, has_concrete=bool(graph.object_terms or self._concrete_terms(hits)))
        relation_quantity = graph.relation_quantity_score()
        integration_component = graph.integration_score()
        grounding_component = graph.grounding_score() if graph.object_terms else self._concrete_grounding(clean, hits)
        bank_component = float(self.bank_scorer.score(clean)) if self.bank_scorer else 0.0
        anchor_component, overfit, orphan, shared = self._anchor_resonance(context, clean)
        voice_component = self._voice_hinge(clean, schemas, hits, graph)

        repair = self._contextual_repair_penalty(clean, schemas, hits)
        closure = phrase_rate(clean, CLOSURE_PHRASES)
        collapse = collapse_penalty(clean)
        repetition = repetition_penalty(clean)
        stuffing = keyword_stuffing_penalty(clean, hits)
        scene_fail = scene_failure_penalty(pair_component, image_component, clean)
        sema_col = semantic_collage_penalty_v07(clean, schemas, hits, graph)
        cluster_sprawl = graph.cluster_sprawl_penalty()
        meta_leak = meta_commentary_penalty(clean)
        unfinished = unfinished_fragment_penalty(clean)

        total = (
            lexicon_prior
            + self.weights.ontology_leak * ontology_component
            + self.weights.image_schema * image_component
            + self.weights.relation_quantity * relation_quantity
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
            - self.weights.cluster_sprawl_penalty * cluster_sprawl
            - self.weights.meta_leak_penalty * meta_leak
            - self.weights.unfinished_penalty * unfinished
        )

        return V07ScoreBreakdown(
            total=total,
            concept_dispersion=concept_component,
            pair_distance=pair_component,
            agency_inversion=agency_component,
            aesthetic_prior=lexicon_prior,
            ontology_leak=ontology_component,
            image_schema=image_component,
            relation_quantity=relation_quantity,
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
            anti_cluster_sprawl=-cluster_sprawl,
            anti_meta_leak=-meta_leak,
            anti_unfinished=-unfinished,
            concept_tags=tags,
            relation_schemas=tuple(sorted(schemas)),
            relation_objects=graph.object_terms,
            relation_edges=graph.edges,
            relation_components=graph.components,
            shared_anchors=tuple(sorted(shared)),
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

    def _ontology_leak(self, text: str, tags: Sequence[str], graph: ImageRelationGraph) -> float:
        patterns = [
            r".+は.+(になる|になった|だった|である|として|のように|みたいに)",
            r".+が.+(になる|になった|だった|である|として|のように|みたいに)",
            r".+\b(is|became|becomes|as|like|turns? into)\b.+",
        ]
        pat_hit = any(re.search(p, text, flags=re.IGNORECASE | re.DOTALL) for p in patterns)
        if pat_hit and len(tags) >= 2:
            return 1.0
        if pat_hit and graph.object_count >= 2:
            return 0.72
        if pat_hit:
            return 0.45
        return 0.0

    def _concrete_grounding(self, text: str, hits: Mapping[str, Sequence[str]]) -> float:
        if not self.lexicon_enabled:
            return clamp(len(relation_schemas(text)) / 4.0, 0.0, 0.75)
        unique_concrete = len(self._concrete_terms(hits))
        base = min(unique_concrete, 5) / 5.0
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
        ratio = len(shared) / max(len(c_terms), 1)
        resonance = 0.0 if ratio == 0.0 else clamp(1.0 - abs(ratio - self.anchor_ideal) / self.anchor_width, 0.0, 1.0)
        overfit = clamp((ratio - 0.58) / 0.42, 0.0, 1.0)
        orphan = 1.0 if ratio == 0.0 and len(c_terms) >= 1 else 0.0
        if not t_terms:
            orphan *= 0.45
        return resonance, overfit, orphan, shared

    def _contextual_repair_penalty(self, text: str, schemas: set, hits: Mapping[str, Sequence[str]]) -> float:
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
                local_schemas = relation_schemas(s)
                local_graph = image_relation_graph(s)
                local_concrete = local_graph.object_count >= 2 or any(any(term in s for term in terms) for terms in hits.values())
                penalty += 0.04 if local_schemas and local_concrete else 0.22
            if closureish:
                penalty += 0.35
        return clamp(penalty, 0.0, 1.0)

    def _voice_hinge(self, text: str, schemas: set, hits: Mapping[str, Sequence[str]], graph: ImageRelationGraph) -> float:
        low = text.lower()
        if not any(phrase_in_text(c, low) for c in REPAIR_CONNECTORS):
            return 0.0
        if any(phrase_in_text(m, low) for m in REPAIR_META_TERMS):
            return 0.0
        if not schemas:
            return 0.0
        has_anchor = any(hits.values()) or (graph.object_count >= 2 and graph.relation_count >= 1)
        return 1.0 if has_anchor else 0.0


def semantic_collage_penalty_v07(
    text: str,
    schemas: set,
    hits: Optional[Mapping[str, Sequence[str]]] = None,
    graph: Optional[ImageRelationGraph] = None,
) -> float:
    low = text.lower().strip()
    if not low:
        return 1.0
    hits = hits or {}
    graph = graph or image_relation_graph(text)
    lexical_terms = unique_preserve_order(t for terms in hits.values() for t in terms)
    concept_count = max(len(lexical_terms), graph.object_count)
    schema_count = len(schemas)
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]*", low)
    verbish = re.findall(
        r"\b(is|are|was|were|becomes?|became|turns?|turned|touch(?:es|ed|ing)?|hold(?:s|ing)?|"
        r"sleep(?:s|ing)?|cough(?:s|ing)?|pray(?:s|ing)?|breathe(?:s|ing)?|open(?:s|ed|ing)?|"
        r"grow(?:s|ing)?|sign(?:s|ed|ing)?|stamp(?:s|ed|ing)?|wear(?:s|ing)?|receive(?:s|d|ing)?|"
        r"carry|carries|carrying|rest(?:s|ing)?|lean(?:s|ing)?|melt(?:s|ing)?|contain(?:s|ing)?|"
        r"tangled|tied|wrapped|glued|spills?|lies?|floats?|etched|scrawled)\b",
        low,
    )
    of_chain = 1.0 if re.search(r"\b(?:[a-z][a-z'-]+\s+of\s+){2,}[a-z][a-z'-]+\b", low) else 0.0
    comma_chain = 1.0 if re.search(r"(?:\b[a-z][a-z'-]+\b\s*[,;/]\s*){5,}", low) else 0.0
    many_domains_low_relation = 1.0 if concept_count >= 7 and schema_count <= 1 else 0.0
    nouns_without_action = 1.0 if concept_count >= 6 and len(verbish) <= 1 else 0.0
    density = concept_count / max(len(tokens), 1) if tokens else 0.0
    density_component = clamp((density - 0.34) / 0.42, 0.0, 1.0) if concept_count >= 5 else 0.0
    graph_sprawl = graph.cluster_sprawl_penalty()
    weak_integration = clamp(0.58 - graph.integration_score(), 0.0, 1.0) if concept_count >= 6 and graph.relation_count >= 2 else 0.0
    relation_overload = clamp((graph.relation_count - 5) / 8.0, 0.0, 1.0) if graph.object_count >= 8 else 0.0
    return clamp(
        0.28 * of_chain
        + 0.36 * comma_chain
        + 0.28 * many_domains_low_relation
        + 0.24 * nouns_without_action
        + 0.16 * density_component
        + 0.58 * graph_sprawl
        + 0.30 * weak_integration
        + 0.20 * relation_overload,
        0.0,
        1.0,
    )


def load_concept_fields_v07(path: Optional[str]) -> Dict[str, List[str]]:
    if not path:
        return dict(DEFAULT_CONCEPT_FIELDS)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(k): list(v) for k, v in data.items()}


def make_bank_scorer_v07(args: argparse.Namespace, bank: PromptBank) -> Optional[Any]:
    if getattr(args, "no_bank_score", False):
        return None
    embed_model = getattr(args, "embed_model", None)
    mode = getattr(args, "bank_score_mode", "auto") or "auto"
    if mode == "off":
        return None
    if mode == "embed" or (mode == "auto" and embed_model):
        if not embed_model:
            raise ValueError("--bank-score-mode embed requires --embed-model")
        return HFEmbeddingBankScorer(embed_model, bank, device=getattr(args, "device", None))
    if mode == "hash":
        scorer = HashBankScorer(bank)
        setattr(scorer, "score_kind", "lex")
        return scorer
    # v0.7 structural default: no lexical hash fallback unless explicitly requested.
    return None


def make_scorer_v07(args: argparse.Namespace) -> V07DepaysementScorer:
    bank = PromptBank.from_file(getattr(args, "bank", None))
    concept_fields = load_concept_fields_v07(getattr(args, "lexicon", None))
    bank_scorer = make_bank_scorer_v07(args, bank)
    weights = V07Weights()
    profile = getattr(args, "scorer_profile", "structural")
    bank_mode = getattr(bank_scorer, "score_kind", "off") if bank_scorer else "off"
    if bank_mode == "embed":
        weights.bank_contrast = 0.62
    elif bank_mode == "lex":
        weights.bank_contrast = 0.18
    else:
        weights.bank_contrast = 0.0
    if getattr(args, "bank_weight", None) is not None:
        weights.bank_contrast = float(getattr(args, "bank_weight"))
    default_lexicon_scale = 0.0 if profile == "structural" else 0.18
    raw_lexicon_scale = getattr(args, "lexicon_prior_scale", None)
    lexicon_scale = float(default_lexicon_scale if raw_lexicon_scale is None else raw_lexicon_scale)
    if getattr(args, "enable_lexicon", False):
        lexicon_scale = 0.18 if lexicon_scale == 0.0 else lexicon_scale
    lexicon_enabled = not bool(getattr(args, "disable_lexicon", False)) and lexicon_scale > 0.0
    if not lexicon_enabled:
        lexicon_scale = 0.0
    return V07DepaysementScorer(
        weights=weights,
        concept_fields=concept_fields,
        bank_scorer=bank_scorer,
        lexicon_enabled=lexicon_enabled,
        lexicon_prior_scale=lexicon_scale,
    )
