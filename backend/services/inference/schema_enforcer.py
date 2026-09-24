import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# =========================================================================
# Tier Strategy Configuration
#
# Option 1: Tight Floor (Recommended / Active Default)
#   Minor:   [4, 7)   — Shrinks failure to bottom ~8% (scores 4, 5, 6).
#   Core:    [7, 14)  — Broad cluster holding ~76–84% of standard performers.
#   Pivotal: [14, 20] — High-effort tier reserved for top ~8–16%.
#
# Option 2: High Bar (Strict Excellence)
#   Minor:   [4, 8)   — Enforces 8 as hard baseline (~15% unachievers).
#   Core:    [8, 15)  — Bulk performance (~76–81%).
#   Pivotal: [15, 20] — Restricts top tier to elite top ~4–9%.
#
# Option 3: Asymmetric Funnel
#   Minor:   [4, 6.5) — True non-participation bucket (~5–6%).
#   Core:    [6.5, 13) — Wide middle corridor (~69–79%).
#   Pivotal: [13, 20] — Maintains original 13 cutoff while lifting normal output.
# =========================================================================
TIER_DISTRIBUTIONS = {
    "tight_floor": {
        "name": "Tight Floor",
        "pivotal": 14.0,
        "core": 7.0,
        "comment": "Minor: < 7, Core: [7, 14), Pivotal: >= 14"
    },
    "high_bar": {
        "name": "High Bar",
        "pivotal": 15.0,
        "core": 8.0,
        "comment": "Minor: < 8, Core: [8, 15), Pivotal: >= 15"
    },
    "asymmetric": {
        "name": "Asymmetric",
        "pivotal": 13.0,
        "core": 6.5,
        "comment": "Minor: < 6.5, Core: [6.5, 13), Pivotal: >= 13"
    }
}

DEFAULT_TIER_DISTRIBUTION = os.environ.get("TIER_DISTRIBUTION", "tight_floor").strip().lower()

def compute_tier(tot: float, strategy_name: str = None) -> str:
    key = (strategy_name or DEFAULT_TIER_DISTRIBUTION).lower()
    strategy = TIER_DISTRIBUTIONS.get(key, TIER_DISTRIBUTIONS["tight_floor"])
    if tot >= strategy["pivotal"]:
        return "Pivotal"
    elif tot >= strategy["core"]:
        return "Core"
    return "Minor"

class RubricSpec:
    def __init__(self, sys_prompt: str):
        axes_match = re.search(r'Axes:\s*(\d+)', sys_prompt, re.IGNORECASE)
        self.axis_count = int(axes_match.group(1)) if axes_match else 4
        
        self.axes_keys = re.findall(r'"([A-Z])":', sys_prompt)
        if not self.axes_keys:
            self.axes_keys = ["C", "O", "R", "D"]
            
        self.max_score = self.axis_count * 4
        self.danger_flag_logic = self._parse_danger_flag(sys_prompt)
        
        version_match = re.search(r'\*\*Version:\*\*\s*([\d\.]+)', sys_prompt, re.IGNORECASE)
        self.version = version_match.group(1) if version_match else "1.0"
        
    def _parse_danger_flag(self, text):
        match = re.search(r'`?danger_flag:\s*true`?\s*if\s*([A-Z])\s*(=|>=)\s*(\d+)(?:\s*AND\s*([A-Z])\s*(=|<=)\s*(\d+))?', text, re.IGNORECASE)
        if match:
            conds = [(match.group(1).upper(), match.group(2), int(match.group(3)))]
            if match.group(4):
                conds.append((match.group(4).upper(), match.group(5), int(match.group(6))))
            return conds
        return []
        
    def compute_danger(self, axes_values):
        if not self.danger_flag_logic:
            return False
        for axis, op, val in self.danger_flag_logic:
            actual = axes_values.get(axis)
            if actual is None:
                return False
            if op == ">=" and not (actual >= val):
                return False
            elif op == "<=" and not (actual <= val):
                return False
            elif op == "=":
                if val >= 3 and actual < val:
                    return False
                elif val <= 1 and actual > val:
                    return False
                elif 1 < val < 3 and actual != val:
                    return False
        return True

def parse_and_validate(raw_content: str, rubric_spec: RubricSpec) -> dict:
    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if not json_match:
            raise ValueError("No valid JSON found in LLM response.")
        result = json.loads(json_match.group(0))

    raw_axes = result.get("axes", {})
    if not raw_axes:
        raw_axes = {k: v for k, v in result.items() if len(k) == 1 and k.isupper()}
    
    if not raw_axes:
        raise ValueError("Missing axes in response.")

    axes = {}
    for k in rubric_spec.axes_keys:
        if k not in raw_axes:
            raise ValueError(f"Missing required axis {k}")
        
        v = raw_axes[k]
        if isinstance(v, bool):
            raise ValueError(f"Axis {k} is a boolean, must be integer.")
        if isinstance(v, float):
            raise ValueError(f"Axis {k} is a float ({v}), must be integer.")
        if v is None:
            raise ValueError(f"Axis {k} is null, must be integer.")
        try:
            v_str = str(v).strip()
            if "." in v_str:
                raise ValueError
            v_int = int(v_str)
        except (ValueError, TypeError):
            raise ValueError(f"Axis {k} must be integer, got {type(v).__name__}: {v}")
            
        if not (1 <= v_int <= 4):
            raise ValueError(f"Axis {k} value {v_int} out of bounds (1-4).")
            
        axes[k] = v_int

    touches = {}
    def _validate_touch(val, key_name):
        if isinstance(val, bool):
            raise ValueError(f"touches field {key_name} is boolean ({val}), must be integer intensity (0-4).")
        if isinstance(val, float):
            raise ValueError(f"touches field {key_name} is float ({val}), must be integer intensity (0-4).")
        if val is None:
            raise ValueError(f"touches field {key_name} is null, must be integer intensity (0-4).")
        try:
            val_str = str(val).strip()
            if "." in val_str:
                raise ValueError
            v_int = int(val_str)
        except (ValueError, TypeError):
            raise ValueError(f"touches field {key_name} must be integer intensity (0-4), got {type(val).__name__}: {val}")
        if not (0 <= v_int <= 4):
            raise ValueError(f"touches field {key_name} value {v_int} out of bounds (0-4).")
        return v_int

    for k, v in result.items():
        if k.startswith("touches_"):
            touches[k] = _validate_touch(v, k)
            
    if "touches" in result and isinstance(result["touches"], dict):
        for k, v in result["touches"].items():
            norm_k = k if k.startswith("touches_") else f"touches_{k}"
            touches[norm_k] = _validate_touch(v, norm_k)

    debt_direction = str(result.get("debt_direction", "neutral")).lower()
    if debt_direction not in ["increases", "neutral", "reduces"]:
        debt_direction = "neutral"

    tot = sum(axes.values())
    score_pct = round(tot / rubric_spec.max_score * 100, 1)
    
    # Fully application-computed tiers using configurable strategy (default: tight_floor)
    tier = compute_tier(tot)
        
    if tier == "Pivotal": tier_label = "🔺 PIVOTAL"
    elif tier == "Core": tier_label = "🟦 CORE"
    else: tier_label = "➖ MINOR"

    danger_flag = rubric_spec.compute_danger(axes)

    return {
        "axes": axes,
        "tot": tot,
        "score_pct": float(score_pct),
        "tier": tier_label,
        "danger_flag": danger_flag,
        "debt_direction": debt_direction,
        "touches": touches,
        "rationale": result.get("rationale", ""),
        "rubric_version": rubric_spec.version
    }
