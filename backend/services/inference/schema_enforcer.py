import json
import logging
import re

logger = logging.getLogger(__name__)

class RubricSpec:
    def __init__(self, sys_prompt: str):
        axes_match = re.search(r'Axes:\s*(\d+)', sys_prompt, re.IGNORECASE)
        self.axis_count = int(axes_match.group(1)) if axes_match else 4
        
        self.axes_keys = re.findall(r'"([A-Z])":', sys_prompt)
        if not self.axes_keys:
            self.axes_keys = ["C", "O", "R", "D"]
            
        self.max_score = self.axis_count * 3
        self.danger_flag_logic = self._parse_danger_flag(sys_prompt)
        
        version_match = re.search(r'\*\*Version:\*\*\s*([\d\.]+)', sys_prompt, re.IGNORECASE)
        self.version = version_match.group(1) if version_match else "1.0"
        
    def _parse_danger_flag(self, text):
        match = re.search(r'`?danger_flag:\s*true`?\s*if\s*([A-Z])\s*=\s*(\d+)(?:\s*AND\s*([A-Z])\s*=\s*(\d+))?', text, re.IGNORECASE)
        if match:
            conds = [(match.group(1).upper(), int(match.group(2)))]
            if match.group(3):
                conds.append((match.group(3).upper(), int(match.group(4))))
            return conds
        return []
        
    def compute_danger(self, axes_values):
        if not self.danger_flag_logic:
            return False
        for axis, val in self.danger_flag_logic:
            if axes_values.get(axis) != val:
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
        try:
            v_int = int(v)
        except (ValueError, TypeError):
            raise ValueError(f"Axis {k} must be integer, got {type(v)}: {v}")
            
        if not (1 <= v_int <= 4):
            raise ValueError(f"Axis {k} value {v_int} out of bounds (1-4).")
            
        axes[k] = v_int

    touches = {}
    def _validate_touch(val, key_name):
        if isinstance(val, bool):
            return 1 if val else 0
        try:
            v_int = int(val)
        except (ValueError, TypeError):
            raise ValueError(f"touches field {key_name} must be integer intensity (0-4), got {type(val)}: {val}")
        if not (0 <= v_int <= 4):
            raise ValueError(f"touches field {key_name} value {v_int} out of bounds (0-4)")
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
    
    # Fully application-computed tiers, never trusting model
    if rubric_spec.axis_count == 4:
        if tot >= 10: tier = "Pivotal"
        elif tot >= 7: tier = "Core"
        else: tier = "Minor"
    elif rubric_spec.axis_count == 5:
        if tot >= 13: tier = "Pivotal"
        elif tot >= 9: tier = "Core"
        else: tier = "Minor"
    else:
        if tot >= 8: tier = "Pivotal"
        elif tot >= 6: tier = "Core"
        else: tier = "Minor"
        
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
        "rubric_version": rubric_spec.version
    }
