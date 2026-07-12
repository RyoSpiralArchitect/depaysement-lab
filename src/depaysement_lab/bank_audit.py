"""Literal audit of tracked attractor terms in contrastive prompt banks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .ontology import SOFT_STYLE_CLICHE_TERMS, STOCK_PROP_ATTRACTOR_TERMS, wordish_pattern


BANK_PARTITIONS = (
    "positive_depaysement",
    "negative_realist_repair",
    "negative_weird_noise",
)


def audit_bank_lexical_overlap(bank_path: str | Path) -> Dict[str, Any]:
    path = Path(bank_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    term_groups = {
        "stock_prop_attractor": sorted(STOCK_PROP_ATTRACTOR_TERMS),
        "soft_style_cliche": sorted(SOFT_STYLE_CLICHE_TERMS),
    }
    partitions = {}
    hit_rows = []
    for partition in BANK_PARTITIONS:
        prompts = [str(value) for value in payload.get(partition, [])]
        partition_groups = {}
        for group, terms in term_groups.items():
            hits = []
            for prompt_index, prompt in enumerate(prompts, start=1):
                for term in terms:
                    if wordish_pattern(term).search(prompt.lower()):
                        row = {
                            "partition": partition,
                            "group": group,
                            "prompt_index": prompt_index,
                            "term": term,
                            "prompt": prompt,
                        }
                        hits.append(row)
                        hit_rows.append(row)
            partition_groups[group] = {
                "hit_count": len(hits),
                "unique_terms": sorted({row["term"] for row in hits}),
                "hits": hits,
            }
        partitions[partition] = {
            "prompt_count": len(prompts),
            "groups": partition_groups,
        }
    positive = partitions["positive_depaysement"]["groups"]
    return {
        "bank_path": str(path),
        "term_groups": term_groups,
        "partitions": partitions,
        "hit_rows": hit_rows,
        "positive_direct_overlap": {
            group: int(result["hit_count"])
            for group, result in positive.items()
        },
        "interpretation_boundary": [
            "Zero exact overlap rules out direct lexical copying only for the tracked terms and current bank version.",
            "It does not rule out semantic, stylistic, phrase-level, or corpus-mediated contamination.",
            "A contrastive vector may still point toward a broader stock-surreal generation regime.",
        ],
    }


def write_bank_lexical_audit(report: Mapping[str, Any], out_prefix: str | Path) -> Dict[str, str]:
    prefix = Path(out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = Path(str(prefix) + ".json")
    markdown_path = Path(str(prefix) + ".md")
    json_path.write_text(json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(format_bank_lexical_audit(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def format_bank_lexical_audit(report: Mapping[str, Any]) -> str:
    lines = [
        "# Prompt-Bank Literal Attractor Audit",
        "",
        f"Bank: `{report.get('bank_path', '')}`",
        "",
        "## Partition Summary",
        "",
        "| partition | prompts | stock hits | soft-style hits |",
        "|---|---:|---:|---:|",
    ]
    for partition in BANK_PARTITIONS:
        row = report.get("partitions", {}).get(partition, {})
        groups = row.get("groups", {})
        lines.append(
            f"| {partition} | {int(row.get('prompt_count', 0))} | "
            f"{int(groups.get('stock_prop_attractor', {}).get('hit_count', 0))} | "
            f"{int(groups.get('soft_style_cliche', {}).get('hit_count', 0))} |"
        )
    lines.extend(["", "## Exact Hits", ""])
    hits: Sequence[Mapping[str, Any]] = report.get("hit_rows", [])
    if not hits:
        lines.append("No tracked exact phrase hits.")
    else:
        for row in hits:
            lines.append(
                f"- `{row['partition']}` / `{row['group']}` / `{row['term']}`: {row['prompt']}"
            )
    lines.extend(["", "## Interpretation Boundary", ""])
    lines.extend(f"- {note}" for note in report.get("interpretation_boundary", []))
    return "\n".join(lines).rstrip() + "\n"
