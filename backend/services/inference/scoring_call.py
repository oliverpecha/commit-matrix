"""Unified inference pipeline and row formatting for CommitMatrix commit scoring."""
import json
import logging
import os
import re
from typing import Optional

from backend.services.inference.llm_gateway import execute_inference
from backend.services.inference.schema_enforcer import RubricSpec, parse_and_validate
from backend.services.inference.prompt_assembly import build_prompt

logger = logging.getLogger(__name__)


def execute_commit_inference(
    sys_prompt: str,
    user_prompt: str,
    model_name: str,
    rate_limits,
    aimd,
    rubric_spec: Optional[RubricSpec] = None,
) -> dict:
    """Canonical single-source inference-and-validation pipeline.
    
    Executes model inference via llm_gateway and validates through schema_enforcer,
    computing all derived fields (tot, score_pct, tier, danger_flag) application-side.
    """
    if rubric_spec is None:
        rubric_spec = RubricSpec(sys_prompt)
    
    raw_content = execute_inference(model_name, sys_prompt, user_prompt, rate_limits, aimd)
    return parse_and_validate(raw_content, rubric_spec)


# Canonical alias
run_inference = execute_commit_inference


def format_commit_row(
    topo_id: int,
    parts: list,
    result: dict,
    rubric_spec: RubricSpec,
    model_name: str,
    arch_tree_signature: str = None,
    arch_gen: int = None,
) -> tuple[list[str], list]:
    """Canonical CSV headers and row constructor ensuring identical schema across workers."""
    hash_full = parts[0] if len(parts) > 0 else ""
    date_str = parts[1] if len(parts) > 1 else ""
    author = parts[2] if len(parts) > 2 else ""
    subject = parts[3] if len(parts) > 3 else ""
    diff = parts[4] if len(parts) > 4 else ""
    hash_short = hash_full[:7]

    m_type = re.match(r"^([a-zA-Z_-]+)(?:\(([^)]+)\))?:", subject)
    if m_type:
        commit_type = m_type.group(1).lower()
        commit_scope = m_type.group(2) or ""
    else:
        commit_type = "chore"
        commit_scope = ""

    additions = diff.count("\n+") - diff.count("\n+++")
    deletions = diff.count("\n-") - diff.count("\n---")

    tier_label = result.get("tier", "➖ MINOR")
    clean_tier = tier_label.split()[1] if len(tier_label.split()) > 1 else tier_label

    headers = [
        "#", "Date", "Type", "Scope", "Subject", "Tier", "Total", "ScorePct",
        "Danger", "Debt", "Additions", "Deletions", "Hash", "TreeSig", "ArchGen",
        "Model", "RubricVersion"
    ]
    row = [
        topo_id,
        date_str,
        commit_type,
        commit_scope,
        subject,
        clean_tier,
        result.get("tot", 0),
        result.get("score_pct", 0.0),
        str(result.get("danger_flag", False)).upper(),
        result.get("debt_direction", "neutral"),
        f"+{additions}",
        f"-{deletions}",
        hash_short,
        arch_tree_signature or "",
        arch_gen if arch_gen is not None else "",
        model_name,
        result.get("rubric_version", rubric_spec.version or "1.0"),
    ]

    axes = result.get("axes", {})
    for k in rubric_spec.axes_keys:
        if k in axes:
            headers.append(k)
            row.append(axes[k])

    touches = result.get("touches", {})
    for k in sorted(touches.keys()):
        headers.append(k)
        row.append(touches[k])

    return headers, row
