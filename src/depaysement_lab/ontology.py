from __future__ import annotations

import dataclasses
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .proto_v2 import (
    AGENCY_VERBS,
    CLOSURE_PHRASES,
    DEFAULT_CONCEPT_FIELDS,
    META_LEAK_PHRASES,
    REPAIR_CONNECTORS,
    REPAIR_META_TERMS,
    normalize_text,
    rough_tokens,
)
from .scorer_v07 import V07DepaysementScorer, image_relation_graph


# -----------------------------------------------------------------------------
# Audit-only ontology-collapse decomposition
# -----------------------------------------------------------------------------

ATMOSPHERE_TERMS = {
    "dusty", "dust", "faded", "worn", "forgotten", "damp", "wet", "murky", "gray", "grey",
    "rusted", "rusty", "weathered", "crumbling", "cracked", "peeling", "stale", "old", "antique",
    "abandoned", "forlorn", "lonely", "tired", "sleepy", "spectral", "ghostly", "shadowy",
    "moonlit", "lunar", "dim", "faint", "soft", "mist", "fog", "rain", "chill", "cold",
    "yellowed", "tarnished", "threadbare", "moth-eaten", "grimy", "stagnant", "hidden",
}

# This is intentionally audit-only. It is not a reward lexicon.
FIELD_EXTENSIONS: Dict[str, List[str]] = {
    "body": ["finger", "fingers", "bony", "eye", "eyes", "paw", "mouth", "knuckles", "face"],
    "architecture": ["platform", "counter", "sidewalk", "store", "window", "windows", "station", "facade"],
    "nature": ["vines", "vine", "garden", "puddle", "pigeon", "bird", "feather", "moss", "fog", "wind"],
    "machine": ["record", "vinyl", "music box", "air vent", "vent", "clock", "train", "harmonica", "crystal ball"],
    "domestic": ["umbrella", "coat", "book", "shoebox", "key", "chair", "suitcase", "box"],
    "bureaucracy": ["contract", "passport", "ticket", "itinerary", "parcel", "letter", "letters", "receipt"],
    "abstract": ["time", "promise", "memory", "nowhere", "departure", "redemption", "love"],
}

# Conservative repair-pressure markers: these are not always bad in poetry, but
# they are useful diagnostics for the assistant/narrative attempt to restore or
# explain ontology.
REPAIR_PRESSURE_EXTRA = {
    "symbolizes", "symbolises", "represents", "means", "meaning", "metaphor", "allegory",
    "lesson", "theme", "moral", "message", "reminder of", "testament to", "understanding",
    "redemption", "journey that began", "promised more than", "destined for", "finally",
    "everything made sense", "returned to", "in order to", "as a reminder", "the point",
}

# Inanimate subjects that often show up in these outputs. We keep this broad but
# do not use it as a generator reward.
INANIMATE_SUBJECT_TERMS = {
    "umbrella", "umbrellas", "music box", "box", "garden", "vines", "record", "jazz record",
    "vinyl", "blackboard", "air vent", "vent", "book", "photo", "passport photo", "contract",
    "crystal ball", "ball", "clock", "harmonica", "puddle", "paper", "letters", "parcel",
    "messenger service", "trash", "window", "windows", "station", "clock", "counter", "coat",
    "key", "ticket", "sign", "fog", "wind", "moonlight", "melody", "shadows", "stairs",
}

AFFORDANCE_CORRUPTION_VERBS = set(AGENCY_VERBS) | {
    "attract", "attracts", "attracted", "hum", "hums", "hummed", "promise", "promises", "promised",
    "deliver", "delivers", "delivered", "wait", "waits", "waited", "crawl", "crawls", "crawled",
    "gaze", "gazes", "gazed", "wrap", "wraps", "wrapped", "open", "opens", "opened",
    "stir", "stirs", "stirred", "yawn", "yawns", "yawned", "inhale", "inhales", "inhaled",
    "listen", "listens", "listened", "sing", "sings", "sang", "exhale", "exhales", "exhaled",
    "cradle", "cradles", "cradled", "escape", "escapes", "escaped", "whisper", "whispers",
    "suck", "sucks", "sucked", "holds", "hold", "bearing", "bear", "bears", "waits",
}
# Passive relation verbs are common scene glue; they only become interesting when
# handled by the relation graph, not as affordance corruption.
AFFORDANCE_CORRUPTION_VERBS -= {"wrap", "wraps", "wrapped", "open", "opens", "opened"}

IDENTITY_MELT_PATTERNS: Tuple[re.Pattern[str], ...] = (
    # music box, now a garden / conductor, now a hunching figure.
    # The target must usually begin with an article; otherwise phrases like
    # "now long and spectral" or "now faded" are attribute drift, not identity melt.
    re.compile(
        r"\b(?P<src>[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,4})\s*,\s*now\s+(?P<dst>(?:a|an|the)\s+[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,5})",
        re.I,
    ),
    # X becomes/turns/melts/condenses into Y.
    re.compile(
        r"\b(?P<src>[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,4})\s+(?:becomes?|became|turns?\s+into|turned\s+into|melt(?:s|ed)?\s+into|dissolves?\s+into|condenses?\s+into|materializes?\s+as|unfolds?\s+into)\s+(?P<dst>(?:a|an|the)?\s*[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,5})",
        re.I,
    ),
)


@dataclass
class OntologyEvent:
    kind: str
    text: str
    source: str = ""
    target: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class OntologyMetrics:
    text: str
    token_count: int
    identity_melt_count: int
    identity_melt_density_per_100: float
    identity_melt_score: float
    affordance_corruption_count: int
    affordance_corruption_density_per_100: float
    affordance_corruption_score: float
    category_bleeding_score: float
    category_bleeding_clause_count: int
    concept_field_distribution: Dict[str, float]
    concept_field_entropy: float
    atmospheric_density_per_100: float
    atmosphere_terms: List[str]
    atmospheric_conservation: float
    repair_pressure: float
    repair_markers: List[str]
    narrative_anti_resolution: float
    syntax_readability_proxy: float
    ontology_collapse_density: float
    readable_surreal_frontier: float
    meta_leak: float
    unfinished: float
    graph_fragmentation: float
    graph_integration: float
    relation_quantity: float
    object_count: int
    relation_count: int
    identity_melt_events: List[Dict[str, Any]] = field(default_factory=list)
    affordance_corruption_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def compact(self) -> str:
        return (
            f"ont={self.ontology_collapse_density:.3f} | "
            f"id={self.identity_melt_score:.3f}/{self.identity_melt_count} | "
            f"aff={self.affordance_corruption_score:.3f}/{self.affordance_corruption_count} | "
            f"bleed={self.category_bleeding_score:.3f} | "
            f"repair={self.repair_pressure:.3f} | "
            f"read={self.syntax_readability_proxy:.3f} | "
            f"atm={self.atmospheric_conservation:.3f} | "
            f"frontier={self.readable_surreal_frontier:.3f}"
        )


@dataclass
class RunOntologyAudit:
    name: str
    path: str
    seed: str
    final_text: str
    steps: List[Dict[str, Any]]
    aggregate: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class OntologyAuditReport:
    runs: List[RunOntologyAudit]
    comparisons: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runs": [r.to_dict() for r in self.runs],
            "comparisons": self.comparisons,
            "notes": list(self.notes),
        }


class OntologyAuditor:
    """Audit ontology collapse without turning it into the generator reward.

    These metrics deliberately decompose several failure/interest modes:

    * identity melt: X remains referentially present while becoming Y.
    * affordance corruption: an object keeps its name but gains impossible actions.
    * category bleeding: multiple concept fields seep into one clause/image.
    * atmospheric conservation: adjectives/material atmosphere persists while objects mutate.
    * repair pressure: explicit explanation/closure attempts.

    The heuristics are intentionally transparent. They are not theoretical ground
    truth and should be calibrated against human ratings.
    """

    def __init__(self, scorer: Optional[V07DepaysementScorer] = None):
        self.scorer = scorer or V07DepaysementScorer(lexicon_enabled=False, lexicon_prior_scale=0.0)
        self.field_terms = merge_field_terms(DEFAULT_CONCEPT_FIELDS, FIELD_EXTENSIONS)

    def audit_text(self, text: str, *, context: str = "") -> OntologyMetrics:
        clean = normalize_text(text)
        toks = rough_tokens(clean)
        token_count = max(1, len(toks))
        score = self.scorer.score(clean, context=context)
        graph = image_relation_graph(clean)

        id_events = identity_melt_events(clean)
        aff_events = affordance_corruption_events(clean)
        fields = concept_field_distribution_audit(clean, self.field_terms)
        field_entropy = normalized_entropy(fields)
        bleed_score, bleed_clauses = category_bleeding(clean, self.field_terms)
        atmosphere_terms = sorted(atmosphere_hits(clean))
        atmosphere_density = 100.0 * len(atmosphere_terms) / token_count
        atm_conservation = atmosphere_conservation(clean, context=context)
        repair_markers = repair_pressure_markers(clean)
        repair_pressure = min(1.0, len(repair_markers) / max(2.0, token_count / 55.0))
        narrative_anti_resolution = max(0.0, 1.0 - repair_pressure)
        unfinished = max(0.0, -float(score.anti_unfinished))
        meta = max(0.0, -float(score.anti_meta_leak))
        collapse_pen = max(0.0, -float(score.anti_collapse))
        rep_pen = max(0.0, -float(score.anti_repetition))
        syntax_readability = clamp01(1.0 - (0.80 * collapse_pen + 0.70 * unfinished + 0.35 * rep_pen + 1.00 * meta))

        id_density = 100.0 * len(id_events) / token_count
        aff_density = 100.0 * len(aff_events) / token_count
        scale = max(1.0, token_count / 55.0)
        id_score = clamp01(len(id_events) / scale)
        aff_score = clamp01(len(aff_events) / scale)
        ontology = clamp01(0.55 * id_score + 0.25 * aff_score + 0.20 * bleed_score)
        frag = graph_fragmentation(graph)
        frontier = clamp01(ontology * syntax_readability * (1.0 - repair_pressure) * (0.55 + 0.45 * graph.integration_score()))

        return OntologyMetrics(
            text=text,
            token_count=token_count,
            identity_melt_count=len(id_events),
            identity_melt_density_per_100=id_density,
            identity_melt_score=id_score,
            affordance_corruption_count=len(aff_events),
            affordance_corruption_density_per_100=aff_density,
            affordance_corruption_score=aff_score,
            category_bleeding_score=bleed_score,
            category_bleeding_clause_count=bleed_clauses,
            concept_field_distribution=fields,
            concept_field_entropy=field_entropy,
            atmospheric_density_per_100=atmosphere_density,
            atmosphere_terms=atmosphere_terms,
            atmospheric_conservation=atm_conservation,
            repair_pressure=repair_pressure,
            repair_markers=repair_markers,
            narrative_anti_resolution=narrative_anti_resolution,
            syntax_readability_proxy=syntax_readability,
            ontology_collapse_density=ontology,
            readable_surreal_frontier=frontier,
            meta_leak=meta,
            unfinished=unfinished,
            graph_fragmentation=frag,
            graph_integration=graph.integration_score(),
            relation_quantity=graph.relation_quantity_score(),
            object_count=graph.object_count,
            relation_count=graph.relation_count,
            identity_melt_events=[e.to_dict() for e in id_events],
            affordance_corruption_events=[e.to_dict() for e in aff_events],
        )

    def audit_run(self, run: Mapping[str, Any], *, name: str = "run", path: str = "") -> RunOntologyAudit:
        seed = str(run.get("seed") or "")
        final_text = str(run.get("final_text") or "")
        rows: List[Dict[str, Any]] = []
        running_context = seed
        for idx, step in enumerate(run.get("steps", []) or [], 1):
            picked = step.get("picked", {}) if isinstance(step, Mapping) else {}
            text = str(picked.get("text") or step.get("text") or "")
            context = str(step.get("context_before") or running_context)
            m = self.audit_text(text, context=context)
            rows.append({
                "step": int(step.get("step") or idx),
                "text": text,
                "metrics": m.to_dict(),
                "compact": m.compact(),
            })
            running_context = join_like(running_context, text)
        aggregate = aggregate_ontology_rows(rows)
        return RunOntologyAudit(name=name, path=path, seed=seed, final_text=final_text, steps=rows, aggregate=aggregate)


def merge_field_terms(*maps: Mapping[str, Sequence[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    seen: Dict[str, set[str]] = defaultdict(set)
    for mapping in maps:
        for field_name, terms in mapping.items():
            for raw in terms:
                term = str(raw).lower().strip()
                if not term:
                    continue
                if term not in seen[field_name]:
                    seen[field_name].add(term)
                    out[field_name].append(term)
    return dict(out)


def wordish_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.lower())
    # For one-token terms, allow simple plural s where harmless.
    if "\\ " not in escaped and " " not in term:
        escaped = escaped + r"s?"
    return re.compile(rf"(?<![a-z]){escaped}(?![a-z])", re.I)


def concept_field_distribution_audit(text: str, field_terms: Mapping[str, Sequence[str]]) -> Dict[str, float]:
    low = normalize_text(text).lower()
    counts: Counter[str] = Counter()
    for field_name, terms in field_terms.items():
        for term in terms:
            if wordish_pattern(str(term)).search(low):
                counts[field_name] += 1
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {k: float(v) / total for k, v in sorted(counts.items())}


def normalized_entropy(dist: Mapping[str, float]) -> float:
    vals = [float(v) for v in dist.values() if v > 0]
    if len(vals) <= 1:
        return 0.0
    h = -sum(v * math.log(v, 2) for v in vals)
    return float(h / math.log(len(vals), 2))


def split_clauses(text: str) -> List[str]:
    return [c.strip() for c in re.split(r"[.;:!?]+|\s+(?:while|as|where|when|before|after)\s+|,\s+", text) if c.strip()]


def category_bleeding(text: str, field_terms: Mapping[str, Sequence[str]]) -> Tuple[float, int]:
    clauses = split_clauses(text)
    if not clauses:
        return 0.0, 0
    rich = 0
    degrees: List[float] = []
    for c in clauses:
        fields = concept_field_distribution_audit(c, field_terms)
        n = len(fields)
        if n >= 2:
            rich += 1
            degrees.append(min(1.0, (n - 1) / 3.0) * (0.5 + 0.5 * normalized_entropy(fields)))
    if not degrees:
        return 0.0, 0
    # Reward density of mixed clauses and their internal field entropy.
    return clamp01((sum(degrees) / len(degrees)) * min(1.0, rich / max(1.0, len(clauses) / 2.0))), rich


def identity_melt_events(text: str) -> List[OntologyEvent]:
    low = normalize_text(text)
    events: List[OntologyEvent] = []
    seen = set()
    for pat in IDENTITY_MELT_PATTERNS:
        for m in pat.finditer(low):
            src = clean_np(m.group("src"))
            dst = clean_np(m.group("dst"))
            if not src or not dst or src == dst:
                continue
            # Avoid pure adjectival "now long and spectral" where no new class appears.
            if not looks_nominal_shift(dst):
                continue
            key = (src.lower(), dst.lower(), m.start())
            if key in seen:
                continue
            seen.add(key)
            events.append(OntologyEvent("identity_melt", m.group(0).strip(), source=src, target=dst))
    return events


def clean_np(s: str) -> str:
    s = re.sub(r"\b(?:a|an|the|its|his|her|their|now|also|as|which|where|while|into|onto|on|in|at|by|with|from|to|around|above|below|beneath|beside|near|gently|slowly|softly)\b", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:'\"()[]")
    return s


def looks_nominal_shift(dst: str) -> bool:
    words = [w for w in re.split(r"\s+", dst.lower()) if w]
    if not words:
        return False
    # If the target is only qualities/adverbs, treat it as attribute drift, not identity melt.
    quality = {
        "long", "slowly", "soft", "spectral", "bony", "dusty", "faded", "worn", "awake", "open",
        "ethereal", "lunar", "gentle", "melancholic", "weathered", "faint", "damp", "gray", "grey",
    }
    if all(w.strip("-,") in quality for w in words):
        return False
    return True


def affordance_corruption_events(text: str) -> List[OntologyEvent]:
    low = normalize_text(text).lower()
    events: List[OntologyEvent] = []
    seen = set()
    subjects = sorted(INANIMATE_SUBJECT_TERMS, key=len, reverse=True)
    verbs = sorted(AFFORDANCE_CORRUPTION_VERBS, key=len, reverse=True)
    # Search in local windows: subject followed by a verb within about 10 tokens.
    for subj in subjects:
        subj_re = wordish_pattern(subj)
        for sm in subj_re.finditer(low):
            window = low[sm.end(): sm.end() + 110]
            for verb in verbs:
                vm = wordish_pattern(verb).search(window)
                if not vm:
                    continue
                before = window[: vm.start()]
                # Do not let a new clause change the subject: "clock, as the conductor opens...".
                if re.search(r"[.!?;:]|\b(?:as|while|where|when|which|that)\b", before):
                    continue
                span = low[sm.start(): sm.end() + vm.end()].strip()
                key = (span, verb)
                if key in seen:
                    continue
                seen.add(key)
                conf = 0.8
                events.append(OntologyEvent("affordance_corruption", span, source=subj, target=verb, confidence=conf))
                break
    # Cap duplicate-heavy outputs; density still records count but not runaway duplicate windows.
    return events[:12]


def atmosphere_hits(text: str) -> set[str]:
    low = normalize_text(text).lower()
    return {t for t in ATMOSPHERE_TERMS if wordish_pattern(t).search(low)}


def atmosphere_conservation(text: str, *, context: str = "") -> float:
    here = atmosphere_hits(text)
    if not here:
        return 0.0
    prev = atmosphere_hits(context)
    if not prev:
        # In a single isolated text, density still matters; conservation is weaker.
        return min(0.45, len(here) / 10.0)
    return len(here & prev) / max(1, len(here | prev))


def repair_pressure_markers(text: str) -> List[str]:
    low = normalize_text(text).lower()
    markers: List[str] = []
    phrases = set(REPAIR_META_TERMS) | set(REPAIR_CONNECTORS) | set(CLOSURE_PHRASES) | set(META_LEAK_PHRASES) | REPAIR_PRESSURE_EXTRA
    for raw in sorted(phrases, key=len, reverse=True):
        phrase = str(raw).lower().strip()
        if not phrase or len(phrase) < 3:
            continue
        if phrase in {"so", "this", "that", "because"}:
            continue
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", low):
            markers.append(phrase)
    return unique(markers)


def graph_fragmentation(graph: Any) -> float:
    weak_integration = 1.0 - float(graph.integration_score())
    return clamp01(0.55 * float(graph.cluster_sprawl_penalty()) + 0.45 * weak_integration)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def unique(xs: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def join_like(a: str, b: str) -> str:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a:
        return b
    if not b:
        return a
    return a + " " + b


def aggregate_ontology_rows(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"n_steps": 0}
    metric_keys = [
        "ontology_collapse_density", "identity_melt_score", "identity_melt_density_per_100",
        "affordance_corruption_score", "affordance_corruption_density_per_100", "category_bleeding_score",
        "atmospheric_conservation", "atmospheric_density_per_100", "repair_pressure",
        "narrative_anti_resolution", "syntax_readability_proxy", "readable_surreal_frontier",
        "graph_fragmentation", "graph_integration", "relation_quantity", "unfinished", "meta_leak",
    ]
    out: Dict[str, Any] = {"n_steps": len(rows)}
    for key in metric_keys:
        vals = [float(r["metrics"].get(key, 0.0)) for r in rows]
        out[f"mean_{key}"] = sum(vals) / len(vals)
        out[f"max_{key}"] = max(vals)
    out["total_identity_melt_count"] = sum(int(r["metrics"].get("identity_melt_count", 0)) for r in rows)
    out["total_affordance_corruption_count"] = sum(int(r["metrics"].get("affordance_corruption_count", 0)) for r in rows)
    # Collapse acceleration: last half minus first half.
    vals = [float(r["metrics"].get("ontology_collapse_density", 0.0)) for r in rows]
    mid = max(1, len(vals) // 2)
    first = sum(vals[:mid]) / len(vals[:mid])
    second = sum(vals[mid:]) / len(vals[mid:]) if vals[mid:] else first
    out["ontology_collapse_acceleration"] = second - first
    out["phenomenon_label"] = ontology_label(out)
    return out


def ontology_label(agg: Mapping[str, Any]) -> str:
    ont = float(agg.get("mean_ontology_collapse_density", 0.0))
    read = float(agg.get("mean_syntax_readability_proxy", 0.0))
    repair = float(agg.get("mean_repair_pressure", 0.0))
    unfinished = float(agg.get("mean_unfinished", 0.0))
    if read < 0.55 or unfinished > 0.45:
        return "readability_or_truncation_failure"
    if ont > 0.25 and repair < 0.35 and read > 0.55:
        return "coherent_ontology_destabilization"
    if ont > 0.45 and repair >= 0.35:
        return "ontology_destabilization_with_repair_pressure"
    if ont <= 0.22 and read > 0.70:
        return "coherent_but_ontologically_stable"
    return "mixed_ontology_drift"


def load_run_records(path: str) -> List[Tuple[str, Mapping[str, Any]]]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        out = []
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                out.append((f"{p.name}#{i}", json.loads(line)))
        return out
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [(f"{p.name}#{i+1}", item) for i, item in enumerate(data) if isinstance(item, Mapping)]
    if isinstance(data, Mapping) and "runs" in data:
        out = []
        for key, run in data.get("runs", {}).items():
            if isinstance(run, Mapping):
                out.append((f"{p.name}:{key}", run))
        return out
    return [(p.name, data)]


def audit_run_files(paths: Sequence[str], *, scorer: Optional[V07DepaysementScorer] = None) -> OntologyAuditReport:
    auditor = OntologyAuditor(scorer=scorer)
    runs: List[RunOntologyAudit] = []
    for path in paths:
        for name, run in load_run_records(path):
            runs.append(auditor.audit_run(run, name=name, path=path))
    comparisons = compare_audits(runs)
    notes = [
        "Ontology metrics are audit-only heuristics, not generator rewards.",
        "identity_melt detects X->Y persistence; affordance_corruption detects object/action mismatch; category_bleeding is a lexical field audit.",
        "readable_surreal_frontier approximates high ontology collapse with high readability and low repair pressure.",
    ]
    return OntologyAuditReport(runs=runs, comparisons=comparisons, notes=notes)


def compare_audits(runs: Sequence[RunOntologyAudit]) -> List[Dict[str, Any]]:
    comps: List[Dict[str, Any]] = []
    if len(runs) < 2:
        return comps
    # Pairwise deltas; positive delta means second run has more of the metric.
    keys = [
        "mean_ontology_collapse_density", "ontology_collapse_acceleration", "mean_identity_melt_score",
        "mean_affordance_corruption_score", "mean_category_bleeding_score", "mean_repair_pressure",
        "mean_syntax_readability_proxy", "mean_atmospheric_conservation", "mean_readable_surreal_frontier",
    ]
    base = runs[0]
    for other in runs[1:]:
        delta = {k: float(other.aggregate.get(k, 0.0)) - float(base.aggregate.get(k, 0.0)) for k in keys}
        comps.append({
            "a": base.name,
            "b": other.name,
            "delta_b_minus_a": delta,
            "interpretation": compare_interpretation(delta),
        })
    return comps


def compare_interpretation(delta: Mapping[str, float]) -> str:
    ont = delta.get("mean_ontology_collapse_density", 0.0)
    repair = delta.get("mean_repair_pressure", 0.0)
    read = delta.get("mean_syntax_readability_proxy", 0.0)
    acc = delta.get("ontology_collapse_acceleration", 0.0)
    if ont > 0.08 and read > -0.15 and repair <= 0.10:
        if acc > 0.05:
            return "second run shows ontology collapse acceleration while preserving readability and avoiding extra repair pressure"
        return "second run shows denser identity/ontology destabilization while preserving readability within the audit window"
    if ont > 0.08 and repair > 0.10:
        return "second run destabilizes ontology but also increases repair/explanation pressure"
    if ont < -0.08:
        return "second run is more ontologically stable or less displaced"
    return "small or mixed ontology delta"


def format_report(report: OntologyAuditReport, *, show_events: bool = False) -> str:
    lines: List[str] = []
    for run in report.runs:
        a = run.aggregate
        lines.append(f"## {run.name}")
        lines.append(
            " | ".join([
                f"label={a.get('phenomenon_label')}",
                f"ont={a.get('mean_ontology_collapse_density', 0.0):.3f}",
                f"accel={a.get('ontology_collapse_acceleration', 0.0):+.3f}",
                f"id={a.get('mean_identity_melt_score', 0.0):.3f}",
                f"aff={a.get('mean_affordance_corruption_score', 0.0):.3f}",
                f"bleed={a.get('mean_category_bleeding_score', 0.0):.3f}",
                f"repair={a.get('mean_repair_pressure', 0.0):.3f}",
                f"read={a.get('mean_syntax_readability_proxy', 0.0):.3f}",
                f"frontier={a.get('mean_readable_surreal_frontier', 0.0):.3f}",
            ])
        )
        for row in run.steps:
            m = row["metrics"]
            lines.append(f"  step {row['step']}: {row['compact']}")
            if show_events:
                events = m.get("identity_melt_events", [])[:4] + m.get("affordance_corruption_events", [])[:4]
                for ev in events:
                    src = ev.get("source") or ""
                    tgt = ev.get("target") or ""
                    if src or tgt:
                        lines.append(f"    - {ev.get('kind')}: {src} -> {tgt}  [{ev.get('text')}]")
                    else:
                        lines.append(f"    - {ev.get('kind')}: {ev.get('text')}")
        lines.append("")
    if report.comparisons:
        lines.append("## comparisons")
        for c in report.comparisons:
            delta = c.get("delta_b_minus_a", {})
            lines.append(f"{c.get('b')} - {c.get('a')}: {c.get('interpretation')}")
            lines.append(
                "  " + " | ".join(
                    f"{k.replace('mean_', '')}={float(v):+.3f}" for k, v in delta.items()
                )
            )
    if report.notes:
        lines.append("")
        lines.append("## notes")
        lines.extend(f"- {n}" for n in report.notes)
    return "\n".join(lines).rstrip() + "\n"
