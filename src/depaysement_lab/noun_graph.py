"""Heuristic noun co-occurrence graph for frontier artifacts.

The goal is not syntactic noun extraction.  It is a transparent instrument for
checking whether high-frontier text repeatedly travels through the same object
hubs, such as music boxes, books, keys, clocks, dolls, and doors.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from .frontier import FrontierAuditReport, clean_generated_text, truncate


NOUN_PHRASES: Tuple[str, ...] = tuple(
    sorted(
        {
            "antique music box",
            "blue mug",
            "brass key",
            "bus stop",
            "cash register",
            "delivery label",
            "elevator button",
            "faded photograph",
            "greenhouse",
            "harmonium",
            "leather-bound book",
            "music box",
            "paper flower",
            "paper rose",
            "plastic folder",
            "pocket watch",
            "porcelain doll",
            "station clock",
            "ticket stub",
            "wooden key",
        },
        key=lambda term: (-len(term), term),
    )
)

NOUN_TERMS: Tuple[str, ...] = tuple(
    sorted(
        {
            "automaton",
            "ballerina",
            "bird",
            "birdcage",
            "book",
            "box",
            "bus",
            "button",
            "cabinet",
            "clock",
            "counter",
            "drawer",
            "doll",
            "door",
            "folder",
            "fog",
            "flower",
            "fridge",
            "garden",
            "hand",
            "harmonica",
            "key",
            "kettle",
            "label",
            "lace",
            "letter",
            "map",
            "mechanism",
            "mirror",
            "mist",
            "moon",
            "mug",
            "note",
            "paper",
            "photograph",
            "photo",
            "receipt",
            "register",
            "room",
            "rose",
            "satchel",
            "spreadsheet",
            "teacup",
            "teapot",
            "ticket",
            "umbrella",
            "vine",
            "vines",
            "watch",
            "window",
        }
    )
)

ORDINARY_ANCHOR_TERMS: Tuple[str, ...] = (
    "receipt",
    "spreadsheet",
    "bus",
    "fridge",
    "drawer",
    "elevator button",
    "button",
    "mug",
    "delivery label",
    "label",
    "counter",
    "folder",
)

STOCK_HUB_TERMS: Tuple[str, ...] = (
    "music box",
    "antique music box",
    "porcelain doll",
    "leather-bound book",
    "pocket watch",
    "harmonium",
    "teapot",
    "birdcage",
    "doll",
    "book",
    "key",
    "clock",
    "watch",
)


@dataclass
class NounGraphDocument:
    run_name: str
    condition: str
    path: str
    step: int
    candidate_index: int
    picked: bool
    frontier: float
    readability: float
    ontology: float
    unfinished: float
    stock_prop: float
    anchor: float
    text: str
    terms: List[str]


@dataclass
class NounGraphReport:
    documents: List[NounGraphDocument]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    hub_examples: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "settings": dict(self.settings),
            "documents": [doc.__dict__ for doc in self.documents],
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "hub_examples": dict(self.hub_examples),
        }


def build_noun_graph_report(
    frontier_report: FrontierAuditReport,
    *,
    top_k: int = 24,
    max_nodes: int = 120,
    frontier_band_ratio: float = 0.60,
    frontier_band_width: float = 0.08,
    dedupe_texts: bool = True,
) -> NounGraphReport:
    rows = [row for run in frontier_report.runs for row in run.rows]
    max_frontier = max((float(row.readable_ontology_frontier) for row in rows), default=0.0)
    band_min = 0.0
    if max_frontier > 0.0:
        band_min = max(0.0, max_frontier * float(frontier_band_ratio), max_frontier - float(frontier_band_width))

    documents: List[NounGraphDocument] = []
    seen_texts: set[str] = set()
    for row in rows:
        if float(row.readable_ontology_frontier) < band_min:
            continue
        text_key = re.sub(r"\s+", " ", row.text.strip().lower())
        if dedupe_texts and text_key in seen_texts:
            continue
        seen_texts.add(text_key)
        terms = extract_noun_terms(row.text)
        if len(terms) < 2:
            continue
        m = row.metrics
        documents.append(
            NounGraphDocument(
                run_name=row.run_name,
                condition=row.condition,
                path=row.path,
                step=int(row.step),
                candidate_index=int(row.candidate_index),
                picked=bool(row.picked),
                frontier=float(row.readable_ontology_frontier),
                readability=float(m.get("syntax_readability_proxy", 0.0)),
                ontology=float(m.get("ontology_collapse_density", 0.0)),
                unfinished=float(m.get("unfinished", 0.0)),
                stock_prop=float(m.get("stock_prop_attractor_score", 0.0)),
                anchor=float(m.get("ordinary_anchor_retention", 0.0)),
                text=row.text,
                terms=terms,
            )
        )

    node_docs: Dict[str, List[NounGraphDocument]] = defaultdict(list)
    edge_weights: Counter[Tuple[str, str]] = Counter()
    for doc in documents:
        unique_terms = sorted(set(doc.terms))
        for term in unique_terms:
            node_docs[term].append(doc)
        for idx, left in enumerate(unique_terms):
            for right in unique_terms[idx + 1 :]:
                edge_weights[(left, right)] += 1

    weighted_degree: Counter[str] = Counter()
    neighbors: Dict[str, set[str]] = defaultdict(set)
    for (left, right), weight in edge_weights.items():
        weighted_degree[left] += weight
        weighted_degree[right] += weight
        neighbors[left].add(right)
        neighbors[right].add(left)

    candidate_nodes = sorted(
        node_docs,
        key=lambda term: (weighted_degree[term], len(node_docs[term]), mean(doc.frontier for doc in node_docs[term])),
        reverse=True,
    )[: max(1, int(max_nodes))]
    candidate_set = set(candidate_nodes)
    betweenness = approximate_betweenness({term: neighbors[term] & candidate_set for term in candidate_nodes})

    max_degree = max((float(weighted_degree[term]) for term in candidate_nodes), default=1.0)
    max_betweenness = max((float(v) for v in betweenness.values()), default=1.0)
    nodes: List[Dict[str, Any]] = []
    for term in candidate_nodes:
        docs = node_docs[term]
        degree_norm = float(weighted_degree[term]) / max_degree if max_degree else 0.0
        between_norm = float(betweenness.get(term, 0.0)) / max_betweenness if max_betweenness else 0.0
        mean_frontier = mean(doc.frontier for doc in docs)
        mean_unfinished = mean(doc.unfinished for doc in docs)
        mean_anchor = mean(doc.anchor for doc in docs)
        label = noun_node_label(
            term,
            degree_norm=degree_norm,
            betweenness_norm=between_norm,
            mean_frontier=mean_frontier,
            mean_unfinished=mean_unfinished,
            mean_anchor=mean_anchor,
        )
        nodes.append(
            {
                "term": term,
                "label": label,
                "frequency": len(docs),
                "weighted_degree": int(weighted_degree[term]),
                "degree_norm": degree_norm,
                "betweenness": float(betweenness.get(term, 0.0)),
                "betweenness_norm": between_norm,
                "mean_frontier": mean_frontier,
                "max_frontier": max(doc.frontier for doc in docs),
                "mean_readability": mean(doc.readability for doc in docs),
                "mean_ontology": mean(doc.ontology for doc in docs),
                "mean_unfinished": mean_unfinished,
                "mean_stock_prop": mean(doc.stock_prop for doc in docs),
                "mean_anchor": mean_anchor,
                "picked_frequency": sum(1 for doc in docs if doc.picked),
            }
        )
    nodes.sort(key=lambda node: (float(node["betweenness_norm"]), float(node["degree_norm"]), float(node["mean_frontier"])), reverse=True)

    edges = [
        {
            "source": left,
            "target": right,
            "weight": weight,
        }
        for (left, right), weight in edge_weights.most_common(max(1, int(top_k) * 4))
        if left in candidate_set and right in candidate_set
    ]

    hub_examples: Dict[str, List[Dict[str, Any]]] = {}
    for node in nodes[: max(0, int(top_k))]:
        term = str(node["term"])
        docs = sorted(node_docs[term], key=lambda doc: doc.frontier, reverse=True)[:3]
        hub_examples[term] = [
            {
                "run_name": doc.run_name,
                "condition": doc.condition,
                "step": doc.step,
                "candidate_index": doc.candidate_index,
                "picked": doc.picked,
                "frontier": doc.frontier,
                "terms": doc.terms,
                "text": doc.text,
            }
            for doc in docs
        ]

    return NounGraphReport(
        documents=documents,
        nodes=nodes,
        edges=edges,
        hub_examples=hub_examples,
        settings={
            "frontier_max": float(max_frontier),
            "frontier_band_min": float(band_min),
            "frontier_band_ratio": float(frontier_band_ratio),
            "frontier_band_width": float(frontier_band_width),
            "source_candidate_count": len(rows),
            "band_document_count": len(documents),
            "dedupe_texts": bool(dedupe_texts),
            "max_nodes": int(max_nodes),
        },
    )


def extract_noun_terms(text: str) -> List[str]:
    clean = clean_generated_text(text).lower()
    terms: List[str] = []
    consumed: set[str] = set()
    for phrase in NOUN_PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"s?\b", clean):
            terms.append(phrase)
            consumed.update(phrase.split())
    for term in NOUN_TERMS:
        if term in consumed:
            continue
        if re.search(r"\b" + re.escape(term) + r"s?\b", clean):
            terms.append(term)
    seen: set[str] = set()
    out: List[str] = []
    for term in terms:
        normalized = singularize_noun_term(term)
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def singularize_noun_term(term: str) -> str:
    parts = term.split()
    if not parts:
        return term
    last = parts[-1]
    if last.endswith("ies") and len(last) > 4:
        last = last[:-3] + "y"
    elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
        last = last[:-1]
    return " ".join([*parts[:-1], last])


def noun_node_label(
    term: str,
    *,
    degree_norm: float,
    betweenness_norm: float,
    mean_frontier: float,
    mean_unfinished: float,
    mean_anchor: float,
) -> str:
    if term in ORDINARY_ANCHOR_TERMS or any(part in ORDINARY_ANCHOR_TERMS for part in term.split()):
        return "ordinary_anchor"
    high_bridge = degree_norm >= 0.25 or betweenness_norm >= 0.25
    if term in STOCK_HUB_TERMS:
        if high_bridge and mean_unfinished <= 0.25 and mean_frontier > 0.0:
            return "stock_transport_hub"
        if mean_unfinished > 0.25:
            return "stock_loop_node"
        return "stock_surreal_node"
    if high_bridge and mean_frontier > 0.0 and mean_unfinished <= 0.25:
        return "semantic_transport_hub"
    if mean_unfinished > 0.35:
        return "degenerate_loop_node"
    if mean_anchor >= 0.50:
        return "scene_expansion_node"
    return "peripheral_node"


def approximate_betweenness(graph: Mapping[str, Iterable[str]]) -> Dict[str, float]:
    """Brandes betweenness centrality for a small unweighted graph."""

    nodes = list(graph.keys())
    betweenness = {node: 0.0 for node in nodes}
    for source in nodes:
        stack: List[str] = []
        predecessors: Dict[str, List[str]] = {node: [] for node in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        distance = dict.fromkeys(nodes, -1)
        sigma[source] = 1.0
        distance[source] = 0
        queue: deque[str] = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for neighbor in graph.get(vertex, []):
                if neighbor not in distance:
                    continue
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[vertex] + 1
                if distance[neighbor] == distance[vertex] + 1:
                    sigma[neighbor] += sigma[vertex]
                    predecessors[neighbor].append(vertex)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            vertex = stack.pop()
            for predecessor in predecessors[vertex]:
                if sigma[vertex]:
                    delta[predecessor] += (sigma[predecessor] / sigma[vertex]) * (1.0 + delta[vertex])
            if vertex != source:
                betweenness[vertex] += delta[vertex]
    for node in betweenness:
        betweenness[node] /= 2.0
    return betweenness


def format_noun_graph_report(report: NounGraphReport, *, top_k: int = 24) -> str:
    settings = report.settings
    lines: List[str] = [
        "# Frontier Noun Graph",
        "",
        "Heuristic noun/co-occurrence graph for candidates in the observed frontier band.",
        "",
        "## Band",
        (
            f"frontier_max={float(settings.get('frontier_max', 0.0)):.3f} | "
            f"frontier_band_min={float(settings.get('frontier_band_min', 0.0)):.3f} | "
            f"band_documents={int(settings.get('band_document_count', 0))} / "
            f"{int(settings.get('source_candidate_count', 0))}"
        ),
        "",
    ]
    label_counts = Counter(str(node.get("label", "")) for node in report.nodes)
    if label_counts:
        lines.extend(["## Node Labels", ""])
        for label, count in label_counts.most_common():
            lines.append(f"- {label}: {count}")
        lines.append("")

    lines.extend(["## Top Hub Candidates", ""])
    for node in report.nodes[: max(0, int(top_k))]:
        lines.append(
            "- {term} [{label}] freq={freq} degree={degree} between={between:.3f} "
            "mean_frontier={frontier:.3f} max_frontier={max_frontier:.3f} "
            "unfinished={unfinished:.3f} anchor={anchor:.3f}".format(
                term=node["term"],
                label=node["label"],
                freq=node["frequency"],
                degree=node["weighted_degree"],
                between=float(node["betweenness_norm"]),
                frontier=float(node["mean_frontier"]),
                max_frontier=float(node["max_frontier"]),
                unfinished=float(node["mean_unfinished"]),
                anchor=float(node["mean_anchor"]),
            )
        )
    lines.append("")

    if report.edges:
        lines.extend(["## Top Co-Occurrence Edges", ""])
        for edge in report.edges[: max(0, int(top_k))]:
            lines.append(f"- {edge['source']} <-> {edge['target']}: {edge['weight']}")
        lines.append("")

    if report.hub_examples:
        lines.extend(["## Hub Examples", ""])
        for node in report.nodes[: max(0, min(int(top_k), 12))]:
            term = str(node["term"])
            examples = report.hub_examples.get(term, [])
            if not examples:
                continue
            lines.extend([f"### {term} ({node['label']})", ""])
            for ex in examples[:2]:
                lines.extend(
                    [
                        (
                            f"condition={ex['condition']} | step={ex['step']} | "
                            f"candidate={ex['candidate_index']} | picked={int(bool(ex['picked']))} | "
                            f"frontier={float(ex['frontier']):.3f}"
                        ),
                        "",
                        "```text",
                        truncate(str(ex["text"]), 520),
                        "```",
                        "",
                    ]
                )
    lines.extend(
        [
            "## Notes",
            "- This graph uses a transparent phrase/object lexicon, not a full POS tagger.",
            "- High centrality can indicate a semantic transport hub or a degenerate loop; inspect examples before interpreting it.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_noun_graph_json(report: NounGraphReport, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_noun_graph_nodes_csv(report: NounGraphReport, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "term",
        "label",
        "frequency",
        "weighted_degree",
        "degree_norm",
        "betweenness",
        "betweenness_norm",
        "mean_frontier",
        "max_frontier",
        "mean_readability",
        "mean_ontology",
        "mean_unfinished",
        "mean_stock_prop",
        "mean_anchor",
        "picked_frequency",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for node in report.nodes:
            writer.writerow({field: node.get(field, "") for field in fields})


def mean(vals: Iterable[float]) -> float:
    vals = [float(v) for v in vals]
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))
