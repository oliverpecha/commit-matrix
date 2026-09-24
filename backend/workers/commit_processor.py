"""Commit processing worker function."""
import os
import sys
import logging

logger = logging.getLogger(__name__)

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

def process_commit(
    topo_id,
    parts,
    total_unscanned,
    processed_count,
    arch_context,
    model_name,
    rubric_path,
    rate_limits,
    aimd,
    arch_tree_signature=None,
    arch_meta=None,
    arch_change_shape=None,
    arch_gen=None,
    arch_gen_trail=None,
):
    hash_full, date_str, author, subject = parts[:4]
    diff = parts[4] if len(parts) > 4 else ""
    hash_short = hash_full[:7]

    try:
        from backend.services.inference.schema_enforcer import parse_and_validate, RubricSpec
        from backend.services.inference.prompt_assembly import build_prompt
        import json
        
        # 1. PROMPT ASSEMBLY (Arch context is safely preserved here)
        with open(rubric_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()

        user_prompt = build_prompt(arch_context, arch_gen_trail, hash_short, date_str, author, subject, diff)
        rubric_spec = RubricSpec(sys_prompt)

        # 2. INFERENCE CALL
        if str(os.environ.get("MOCK_SCORE", "false")).strip().lower() in ("1", "true", "yes", "on"):
            from backend.utils.mock_generator import generate_dynamic_mock_touches, generate_mock_axes
            axes = generate_mock_axes(rubric_spec.axes_keys)
            touches = generate_dynamic_mock_touches(sys_prompt)
            raw_mock_result = {
                "axes": axes,
                "touches": touches,
                "debt_direction": "neutral"
            }
            result = parse_and_validate(json.dumps(raw_mock_result), rubric_spec)
            aimd.release(success=True)
        else:
            from backend.services.inference.scoring_call import run_inference
            result = run_inference(sys_prompt, user_prompt, model_name, rate_limits, aimd)

        # 3. DATA EXTRACTION & ROW GENERATION (Via unified inference_pipe)
        from backend.services.inference.scoring_call import format_commit_row
        headers, row = format_commit_row(topo_id, parts, result, rubric_spec, model_name, arch_tree_signature, arch_gen)
        axes = result["axes"]
        touches = result["touches"]
        total_score = result["tot"]
        tier_label = result["tier"]

        # 5. UI GENERATION (Delegated safely)
        safe_total = max(1, total_unscanned)
        safe_done = min(max(0, processed_count), safe_total)
        progress_pct = int((safe_done / safe_total) * 100)
        
        from types import SimpleNamespace
        from backend.services.pipeline.pipeline_presentation import render_commit_score_card
        
        # Safely map arch_change_shape into arch_meta so the presentation module doesn't lose the label
        safe_arch_meta = arch_meta.copy() if arch_meta else {}
        if "cause_tag" not in safe_arch_meta and arch_change_shape:
            safe_arch_meta["cause_tag"] = arch_change_shape

        work_item = SimpleNamespace(
            topo_id=topo_id,
            arch_meta=safe_arch_meta,
            commit_parts=parts,
            arch_tree_signature=arch_tree_signature
        )
        scores = axes.copy()
        scores['tier'] = tier_label
        scores['touches'] = touches
        scores['tot'] = total_score
        
        progress_data = {
            'filled': min(16, int((progress_pct / 100) * 16)),
            'pct': progress_pct,
            'remaining': max(0, safe_total - safe_done)
        }
        
        ui_block = render_commit_score_card(work_item, scores, progress_data)

        return topo_id, (headers, row, hash_short, ui_block)

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        err_str = str(e)
        if "Max retries exceeded" in err_str or "API Error" in err_str:
            return topo_id, f"❌ API hard-fail on {hash_short}. Aborting this commit. Error: {err_str}"
        import traceback
        print(f"\n🔴 FATAL EXCEPTION in worker processing {hash_short}:", flush=True)
        traceback.print_exc()
        return topo_id, f"❌ Error scoring commit {hash_short}: {err_str}"
