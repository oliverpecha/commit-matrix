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

            response = completion(
                model=work_item.model_name,
                api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            aimd.release(success=True)

            usage = response.get("usage", {})
            rate_limits.record_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            
            raw_content = response.choices[0].message.content
            try:
                result = json.loads(raw_content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                result = json.loads(json_match.group(0)) if json_match else {"C": 1, "I": 1, "R": 1, "S": 1, "D": 1}

            # Normalize JSON keys
            c = int(result.get("criticality") or result.get("Criticality") or result.get("C") or 1)
            i = int(result.get("infrastructure") or result.get("Infrastructure") or result.get("I") or 1)
            r = int(result.get("ripple") or result.get("Ripple") or result.get("R") or 1)
            s = int(result.get("scope") or result.get("Scope") or result.get("S") or 1)
            d = int(result.get("documentation") or result.get("Documentation") or result.get("D") or 1)
            total = c + i + r + s + d

            tier_label = (
                "🔴 CRITICAL" if total >= 12
                else "🟡 SIGNIFICANT" if total >= 8
                else "🟢 ROUTINE"
            )

            logging.debug(f"Worker scored {hash_short}")
            
            return work_item.topo_id, {
                "C": c, "I": i, "R": r, "S": s, "D": d,
                "tier": tier_label,
                "success": True
            }

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
