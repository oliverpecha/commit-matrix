import json
import re

def enforce_v2_contract(raw_content):
    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if not json_match:
            raise ValueError("No valid JSON found in LLM response.")
        result = json.loads(json_match.group(0))

    axes = {k: int(v) for k, v in result.items() if len(k) == 1 and k.isupper()}
    if not axes:
        raise ValueError("Missing V2 axes in response.")
        
    return {
        "axes": axes,
        "tot": int(result.get("tot", sum(axes.values()))),
        "score_pct": float(result.get("score_pct", 0.0)),
        "tier": str(result.get("tier", "Minor")),
        "danger_flag": str(result.get("danger_flag", "false")).lower() == "true",
        "debt_direction": str(result.get("debt_direction", "neutral")),
        "touches": {k: int(v) if str(v).isdigit() else (1 if str(v).lower() == "true" else 0) 
                    for k, v in result.items() if k.startswith("touches_")}
    }
