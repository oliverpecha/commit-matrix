"""Commit scoring worker function. Stripped of all UI and DB logic for thread safety."""
import json
import os
import sys
import logging
import traceback

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from litellm import completion
logger = logging.getLogger(__name__)

def process_commit_scoring(work_item, rate_limits, aimd):
    """Pure LLM network execution pipe routed via canonical inference_pipe."""
    hash_short = work_item.arch_meta["commit_sha"][:7]

    try:
        from backend.services.inference.scoring_call import run_inference
        from backend.services.inference.prompt_assembly import build_prompt
        from backend.services.inference.schema_enforcer import RubricSpec, parse_and_validate

        with open(work_item.rubric_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()

        parts = work_item.commit_parts
        date_str = parts[1] if len(parts) > 1 else ""
        author = parts[2] if len(parts) > 2 else ""
        subject = parts[3] if len(parts) > 3 else ""
        diff = parts[4] if len(parts) > 4 else ""

        user_prompt = build_prompt(
            work_item.arch_context,
            getattr(work_item, "arch_gen_trail", None),
            hash_short,
            date_str,
            author,
            subject,
            diff,
        )

        rubric_spec = RubricSpec(sys_prompt)

        if str(os.environ.get("MOCK_SCORE", "false")).strip().lower() in ("1", "true", "yes", "on"):
            from backend.utils.mock_generator import generate_dynamic_mock_touches, generate_mock_axes
            axes = generate_mock_axes(rubric_spec.axes_keys)
            touches = generate_dynamic_mock_touches(sys_prompt)
            raw_mock_result = {
                "axes": axes,
                "touches": touches,
                "debt_direction": "neutral",
            }
            result = parse_and_validate(json.dumps(raw_mock_result), rubric_spec)
        else:
            result = run_inference(sys_prompt, user_prompt, work_item.model_name, rate_limits, aimd, rubric_spec=rubric_spec)

        logging.debug(f"Worker scored {hash_short} -> {result['axes']} (total: {result['tot']})")

        from backend.services.inference.scoring_call import format_commit_row
        headers, row = format_commit_row(
            work_item.topo_id,
            work_item.commit_parts,
            result,
            rubric_spec,
            work_item.model_name,
            getattr(work_item, "arch_tree_signature", None),
            getattr(work_item, "arch_gen", None)
        )

        return work_item.topo_id, {
            "axes": result["axes"],
            "tot": result["tot"],
            "score_pct": result["score_pct"],
            "tier": result["tier"],
            "danger_flag": result["danger_flag"],
            "debt_direction": result["debt_direction"],
            "touches": result["touches"],
            "rubric_version": result["rubric_version"],
            "headers": headers,
            "row": row,
            "csv_headers": headers,
            "csv_row": row,
            "success": True,
        }

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        err_str = str(e)
        print(f"\n🔴 FATAL EXCEPTION in worker processing {hash_short}:", flush=True)
        traceback.print_exc()
        return work_item.topo_id, {"success": False, "error": err_str}
