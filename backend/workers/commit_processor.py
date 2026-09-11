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
        from backend.services.inference_pipe.llm_gateway import execute_inference
        from backend.services.inference_pipe.prompt_assembly import build_prompt
        from backend.services.inference_pipe.schema_enforcer import enforce_v2_contract
        
        # 1. PROMPT ASSEMBLY (Arch context is safely preserved here)
        with open(rubric_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()

        user_prompt = build_prompt(arch_context, arch_gen_trail, hash_short, date_str, author, subject, diff)

        # 2. INFERENCE CALL
        if str(os.environ.get("MOCK_SCORE", "false")).strip().lower() in ("1", "true", "yes", "on"):
            import random
            from backend.utils.mock_generator import generate_dynamic_mock_touches
            import re
            
            axes_keys = re.findall(r'"([A-Z])":', sys_prompt)
            if not axes_keys:
                axes_keys = ["C", "O", "R", "D"]
            from backend.utils.mock_generator import generate_mock_axes
            axes = generate_mock_axes(axes_keys)
            touches = generate_dynamic_mock_touches(sys_prompt)
            tot_score = sum(axes.values())
            
            result = {
                "axes": axes,
                "tot": tot_score,
                "tier": "Pivotal" if tot_score >= 13 else "Core" if tot_score >= 8 else "Minor",
                "touches": touches
            }
            aimd.release(success=True)
        else:
            raw_content = execute_inference(model_name, sys_prompt, user_prompt, rate_limits, aimd)
            result = enforce_v2_contract(raw_content)

        # 3. DATA EXTRACTION
        axes = result.get("axes", {})
        touches = result.get("touches", {})
        total_score = result.get("tot", sum(axes.values()))
        tier_label_raw = result.get("tier", "Minor")

        if not axes:
            import re
            rubric_keys = re.findall(r'"([A-Z])":', sys_prompt) if 'sys_prompt' in locals() else []
            axes = {k: 1 for k in rubric_keys} if rubric_keys else {"C": 1, "O": 1, "R": 1, "D": 1}

        tier_label = (
            "🔺 PIVOTAL" if "critical" in tier_label_raw.lower() or "pivotal" in tier_label_raw.lower() else
            "🟦 CORE" if "significant" in tier_label_raw.lower() or "core" in tier_label_raw.lower() else
            "➖ MINOR"
        )

        import re
        m_type = re.match(r"^([a-zA-Z_-]+)(?:\(([^)]+)\))?:", subject)
        if m_type:
            commit_type = m_type.group(1).lower()
            commit_scope = m_type.group(2) or ""
        else:
            commit_type = "chore"
            commit_scope = ""

        additions = diff.count("\n+") - diff.count("\n+++")
        deletions = diff.count("\n-") - diff.count("\n---")

        # 4. ROW GENERATION (Arch sig and gen safely preserved here for the DB/CSV)
        headers = ["#", "Date", "Type", "Scope", "Subject", "Tier", "Total", "Additions", "Deletions", "Hash", "TreeSig", "ArchGen"]
        clean_tier = tier_label.split()[1] if tier_label else tier_label_raw
        row = [topo_id, date_str, commit_type, commit_scope, subject, clean_tier, total_score, f"+{additions}", f"-{deletions}", hash_short, arch_tree_signature or "", arch_gen if arch_gen is not None else ""]

        import re
        axes_ordered = re.findall(r'"([A-Z])":', sys_prompt) if 'sys_prompt' in locals() else ["C", "O", "R", "D"]
        for k in axes_ordered:
            if k in axes:
                headers.append(k)
                row.append(axes[k])
            
        for k in sorted(touches.keys()):
            headers.append(k)
            row.append(touches[k])

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
