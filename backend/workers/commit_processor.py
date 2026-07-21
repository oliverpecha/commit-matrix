"""Commit processing worker function."""
import json
import os
import sys
import sqlite3
import glob
import logging
import threading

# Thread-local storage to cache database connections per worker thread
_thread_locals = threading.local()
logger = logging.getLogger(__name__)

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from litellm import completion


def _resolve_db_path() -> str | None:
    """
    Robust path resolution supporting local testing, target repositories, 
    and remote MochiClaw mount targets.
    """
    target_repo = os.environ.get("TARGET_REPO")
    if target_repo:
        possible_path = os.path.join(target_repo, "data/commit_matrix.db")
        if os.path.exists(possible_path):
            return possible_path

    db_paths = glob.glob('data/**/commit_matrix.db', recursive=True)
    if db_paths:
        return db_paths[0]
        
    fallback = 'data/commit_matrix.db'
    if os.path.exists(fallback):
        return fallback
        
    return None


def _resolve_shape(sig: str, current_shape: str | None) -> str:
    if current_shape and current_shape != 'unknown':
        return current_shape
    if not sig:
        return 'unknown'

    db_path = _resolve_db_path()
    if not db_path:
        return 'unknown'

    try:
        if not hasattr(_thread_locals, "conn"):
            _thread_locals.conn = sqlite3.connect(
                db_path, 
                timeout=5.0, 
                check_same_thread=False
            )
            _thread_locals.conn.execute('PRAGMA journal_mode=WAL;')

        cursor = _thread_locals.conn.cursor()
        cursor.execute(
            'SELECT shape_label, shape FROM architecture_snapshots WHERE snapshot_sig LIKE ? OR snapshot_sig = ? LIMIT 1', 
            (f'{sig[:12]}%', sig)
        )
        res = cursor.fetchone()
        
        if res:
            shape_label = res[0] or res[1] or 'unknown'
            try:
                from backend.services.architecture.taxonomy import get_shape_metadata
                meta = get_shape_metadata(res[1] or res[0] or "")
                if meta and meta.get("icon") and meta.get("icon") != "•":
                    return f"{meta.get('icon')} {meta.get('label', shape_label)}"
            except Exception:
                pass
            return shape_label
            
    except sqlite3.OperationalError as e:
        logger.warning(f"[Telemetry Congestion Warning] Shape lookup dropped due to lock: {e}")
    except Exception as e:
        logger.error(f"[Telemetry Exception] Unexpected error resolving shape: {e}")
        
    return 'unknown'

import json
import os
import sys

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from litellm import completion


def _axis_bar(value: int, max_val: int = 3, width: int = 5) -> str:
    value = max(0, int(value or 0))
    filled = min(int(width * value / max_val), width)
    return chr(9608) * filled + chr(9617) * (width - filled)


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
    MAX_RETRIES = 6
    retries = MAX_RETRIES

    hash_full, date_str, author, subject = parts[:4]
    diff = parts[4] if len(parts) > 4 else ""
    hash_short = hash_full[:7]

    while retries > 0:
        try:
            aimd.acquire()

            if str(os.environ.get("MATRIX_STRESS_TEST", "false")).strip().lower() in ("1", "true", "yes", "on"):
                import random
                if random.random() < float(os.environ.get("MATRIX_CRASH_RATE", "0.3")):
                    raise Exception("litellm.ServiceUnavailableError: 503 STRESS TEST simulated")

            rate_limits.wait_if_needed()

            with open(rubric_path, "r", encoding="utf-8") as f:
                sys_prompt = f.read()

            trail_section = f"\n\n# {arch_gen_trail}" if arch_gen_trail else ""
            user_prompt = (
                f"# Repository Architecture Context\n{arch_context}{trail_section}\n\n"
                f"# Commit to Score\n"
                f"Hash: {hash_short}\n"
                f"Date: {date_str}\n"
                f"Author: {author}\n"
                f"Subject: {subject}\n\n"
                f"Diff:\n{diff[:8000]}\n"
            )

            if str(os.environ.get("RANDOM_SCORE", "false")).strip().lower() in ("1", "true", "yes", "on"):
                import random
                result = {
                    "criticality": random.randint(1, 3),
                    "infrastructure": random.randint(1, 3),
                    "ripple": random.randint(1, 3),
                    "scope": random.randint(1, 3),
                    "documentation": random.randint(1, 3)
                }
                aimd.release(success=True)
            else:
                response = completion(
                    model=model_name,
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
                response_headers = getattr(response, "_hidden_params", {}).get("response_headers", {})
                if response_headers:
                    rate_limits.update_from_headers(response_headers)
                raw_content = response.choices[0].message.content
                try:
                    result = json.loads(raw_content)
                except json.JSONDecodeError:
                    import re
                    json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                    result = json.loads(json_match.group(0)) if json_match else {"criticality": 1, "infrastructure": 1, "ripple": 1, "scope": 1, "documentation": 1}

            criticality = int(result.get("criticality") or result.get("Criticality") or result.get("C") or 1)
            infrastructure = int(result.get("infrastructure") or result.get("Infrastructure") or result.get("I") or 1)
            ripple = int(result.get("ripple") or result.get("Ripple") or result.get("R") or 1)
            scope = int(result.get("scope") or result.get("Scope") or result.get("S") or 1)
            documentation = int(result.get("documentation") or result.get("Documentation") or result.get("D") or 1)
            total_score = criticality + infrastructure + ripple + scope + documentation

            tier_label = (
                "🔴 CRITICAL" if total_score >= 12
                else "🟡 SIGNIFICANT" if total_score >= 8
                else "🟢 ROUTINE"
            )

            diff_lower = diff.lower()
            scope_tags = []
            if any(x in diff_lower for x in ("backend/parser.py", "backend/main.py", "dockerfile")):
                scope_tags.append("scripts")
            if ".json" in diff_lower or "config" in diff_lower:
                scope_tags.append("config")
            if "dashboard" in diff_lower or "index.html" in diff_lower:
                scope_tags.append("dashboard")
            if "readme" in diff_lower or ".md" in diff_lower:
                scope_tags.append("docs")
            if "metrics" in diff_lower:
                scope_tags.append("metrics")
            if total_score >= 12:
                scope_tags.append("critical")
            scope_str = ", ".join(scope_tags) if scope_tags else "None"

            commit_type = "commit"
            commit_scope = ""
            if subject.startswith("feat"):
                commit_type = "feat"
                commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
            elif subject.startswith("fix"):
                commit_type = "fix"
                commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else "core"
            elif subject.startswith("chore"):
                commit_type = "chore"
                commit_scope = subject.split("(")[1].split(")")[0] if "(" in subject else ""

            additions = diff.count("\n+") - diff.count("\n+++")
            deletions = diff.count("\n-") - diff.count("\n---")

            headers = [
                "#",
                "Date",
                "Type",
                "Scope",
                "Subject",
                "Tier",
                "C",
                "I",
                "R",
                "S",
                "D",
                "Total",
                "Additions",
                "Deletions",
                "Hash",
                "TreeSig",
                "ArchGen",
            ]
            row = [
                topo_id,
                date_str,
                commit_type,
                commit_scope,
                subject,
                tier_label.split()[1],
                criticality,
                infrastructure,
                ripple,
                scope,
                documentation,
                total_score,
                f"+{additions}",
                f"-{deletions}",
                hash_short,
                arch_tree_signature or "",
                arch_gen if arch_gen is not None else "",
            ]

            safe_total = max(1, total_unscanned)
            safe_done = min(max(0, processed_count), safe_total)
            progress_pct = int((safe_done / safe_total) * 100)
            remaining = max(0, safe_total - safe_done)
            filled = min(16, int((progress_pct / 100) * 16))
            bar = "█" * filled + "░" * (16 - filled)

            ui_block = (
                "─────────────────────────────────────────────────────────────────────────\n"
                f"🧬 Commit #{topo_id} • {hash_short} __TOPO:{topo_id}__\n"
                "─────────────────────────────────────────────────────────────────────────\n"
                f"Date      │ {date_str}\n"
                f"Subject   │ {subject[:60]}...\n"
                f"Tier      │ {tier_label} (Score: {total_score})\n"
                f"Scope     │ {scope_str}\n"
                f"Impact    │ C {_axis_bar(criticality)}  I {_axis_bar(infrastructure)}  R {_axis_bar(ripple)}  S {_axis_bar(scope)}  D {_axis_bar(documentation)}\n"
                f"Snapshot  │ {(arch_tree_signature or 'N/A')[:24]} ({_resolve_shape(arch_tree_signature, arch_change_shape)})\n"
                "─────────────────────────────────────────────────────────────────────────\n"
                f"🚀 [{bar}] {progress_pct}% • {remaining} commits remaining\n"
            )
            return topo_id, (headers, row, hash_short, ui_block)

        except Exception as e:
            err_str = str(e)
            aimd.release(success=False)

            is_transient = any(
                token in err_str.lower()
                for token in ("503", "429", "unavailable", "quota", "spending cap", "high demand", "rate limit")
            )

            if is_transient:
                if retries > 0:
                    backoff = 15 * (7 - retries)
                    print(
                        f"⚠️  [Worker] API congestion on {hash_short} (attempt {7 - retries}/6). "
                        f"Pausing {backoff}s... Resuming shortly.\n",
                        flush=True,
                    )
                    import time
                    time.sleep(backoff)
                    retries -= 1
                    continue

                print(f"❌ CRITICAL: API error hard-failed {MAX_RETRIES} times on {hash_short}. Aborting.", flush=True)
                return topo_id, f"❌ API hard-fail on {hash_short}. Aborting this commit."

            import traceback
            print(f"\n🔴 FATAL EXCEPTION in worker processing {hash_short}:", flush=True)
            traceback.print_exc()
            return topo_id, f"❌ Error scoring commit {hash_short}: {err_str}"

    return topo_id, f"❌ Error scoring commit {hash_short}: Max retries exceeded"
