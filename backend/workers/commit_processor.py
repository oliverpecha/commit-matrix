"""Commit processing worker function."""
import json
import os
import sys

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from litellm import completion


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
            rate_limits.record_usage(
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )

            response_headers = getattr(response, "_hidden_params", {}).get("response_headers", {})
            if response_headers:
                rate_limits.update_from_headers(response_headers)

            result = json.loads(response.choices[0].message.content)

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
                f"🧬 Matrix #{topo_id} • {hash_short}\n"
                "─────────────────────────────────────────────────────────────────────────\n"
                f"Date      │ {date_str}\n"
                f"Subject   │ {subject[:60]}...\n"
                f"Tier      │ {tier_label} (Score: {total_score})\n"
                f"Scope     │ {scope_str}\n"
                f"Impact    │ C:{criticality} I:{infrastructure} R:{ripple} S:{scope} D:{documentation}\n"
                "─────────────────────────────────────────────────────────────────────────\n"
                f"🚀 [{bar}] {progress_pct}% • {remaining} commits remaining\n"
            )

            print(f"⚙️  [Worker] Scored {hash_short} -> Queued for ledger flush...\n", flush=True)
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
