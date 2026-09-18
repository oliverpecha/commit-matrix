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
    """Pure LLM network execution pipe."""
    MAX_RETRIES = 6
    retries = MAX_RETRIES
    hash_short = work_item.arch_meta["commit_sha"][:7]

    while retries > 0:
        try:
            aimd.acquire()
            rate_limits.wait_if_needed()

            with open(work_item.rubric_path, "r", encoding="utf-8") as f:
                sys_prompt = f.read()

            trail_section = f"\n\n# {work_item.arch_gen_trail}" if getattr(work_item, "arch_gen_trail", None) else ""
            user_prompt = (
                f"# Repository Architecture Context\n{work_item.arch_context}{trail_section}\n\n"
                f"# Commit to Score\n"
                f"Hash: {hash_short}\n"
                f"Date: {work_item.commit_parts[1]}\n"
                f"Subject: {work_item.commit_parts[3]}\n\n"
                f"Diff:\n{work_item.commit_parts[4][:8000] if len(work_item.commit_parts) > 4 else ''}\n"
            )

            from backend.services.inference.scoring_call import run_inference
            result = run_inference(sys_prompt, user_prompt, work_item.model_name, rate_limits, aimd)
            
            logging.debug(f"Worker scored {hash_short} -> {result['axes']} (total: {result['tot']})")
            
            return work_item.topo_id, {
                "axes": result["axes"],
                "tot": result["tot"],
                "score_pct": result["score_pct"],
                "tier": result["tier"],
                "danger_flag": result["danger_flag"],
                "debt_direction": result["debt_direction"],
                "touches": result["touches"],
                "rubric_version": result["rubric_version"],
                "success": True
            }

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            err_str = str(e)
            aimd.release(success=False)

            is_transient = any(
                token in err_str.lower()
                for token in ("503", "429", "unavailable", "quota", "spending cap", "high demand", "rate limit")
            )

            if is_transient and retries > 0:
                backoff = 15 * (7 - retries)
                import time
                time.sleep(backoff)
                retries -= 1
                continue

            print(f"\n🔴 FATAL EXCEPTION in worker processing {hash_short}:", flush=True)
            traceback.print_exc()
            return work_item.topo_id, {"success": False, "error": err_str}

    return work_item.topo_id, {"success": False, "error": "Max retries exceeded"}
