"""Commit processing worker function."""
import os
import json
import sys

if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from litellm import completion

def process_commit(i, parts, total_unscanned, processed_count, arch_context, model_name, rubric_path, rate_limits, aimd):
    MAX_RETRIES = 6
    retries = MAX_RETRIES
    
    hash_full, date_str, author, subject = parts[:4]
    diff = parts[4] if len(parts) > 4 else ""
    hash_short = hash_full[:7]
    
    while retries > 0:
        try:
            aimd.acquire()
            
            if os.environ.get("MATRIX_STRESS_TEST") == "1":
                import random
                if random.random() < float(os.environ.get("MATRIX_CRASH_RATE", "0.3")):
                    raise Exception('litellm.ServiceUnavailableError: 503 STRESS TEST simulated')
            
            rate_limits.wait_if_needed()
            
            with open(rubric_path, 'r') as f:
                sys_prompt = f.read()
            
            user_prompt = f"# Repository Architecture Context\n{arch_context}\n\n# Commit to Score\nHash: {hash_short}\nDate: {date_str}\nAuthor: {author}\nSubject: {subject}\n\nDiff:\n{diff[:8000]}\n"
            
            response = completion(
                model=model_name,
                api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            aimd.release(success=True)
            
            usage = response.get('usage', {})
            rate_limits.record_usage(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0))
            
            headers = getattr(response, '_hidden_params', {}).get('response_headers', {})
            if headers:
                rate_limits.update_from_headers(headers)
            
            result = json.loads(response.choices[0].message.content)
            
            criticality = int(result.get("criticality") or result.get("Criticality") or result.get("C") or 1)
            infrastructure = int(result.get("infrastructure") or result.get("Infrastructure") or result.get("I") or 1)
            ripple = int(result.get("ripple") or result.get("Ripple") or result.get("R") or 1)
            scope = int(result.get("scope") or result.get("Scope") or result.get("S") or 1)
            documentation = int(result.get("documentation") or result.get("Documentation") or result.get("D") or 1)
            total_score = criticality + infrastructure + ripple + scope + documentation
            
            tier_label = "🔴 CRITICAL" if total_score >= 12 else "🟡 SIGNIFICANT" if total_score >= 8 else "🟢 ROUTINE"
            
            scope_tags = []
            if any(x in diff.lower() for x in ['backend/parser.py', 'backend/main.py', 'dockerfile']): scope_tags.append('scripts')
            if '.json' in diff.lower() or 'config' in diff.lower(): scope_tags.append('config')
            if 'dashboard' in diff.lower() or 'index.html' in diff.lower(): scope_tags.append('dashboard')
            if 'readme' in diff.lower() or '.md' in diff.lower(): scope_tags.append('docs')
            if 'metrics' in diff.lower(): scope_tags.append('metrics')
            if total_score >= 12: scope_tags.append('critical')
            scope_str = ', '.join(scope_tags) if scope_tags else 'None'
            
            commit_type = 'commit'
            commit_scope = ''
            if subject.startswith('feat'):
                commit_type = 'feat'
                commit_scope = subject.split('(')[1].split(')')[0] if '(' in subject else 'core'
            elif subject.startswith('fix'):
                commit_type = 'fix'
                commit_scope = subject.split('(')[1].split(')')[0] if '(' in subject else 'core'
            elif subject.startswith('chore'):
                commit_type = 'chore'
                commit_scope = subject.split('(')[1].split(')')[0] if '(' in subject else ''
            
            additions = diff.count('\n+') - diff.count('\n+++')
            deletions = diff.count('\n-') - diff.count('\n---')
            
            headers = ['#', 'Date', 'Type', 'Scope', 'Subject', 'Tier', 'C', 'I', 'R', 'S', 'D', 'Total', 'Additions', 'Deletions', 'Hash']
            row = [i, date_str, commit_type, commit_scope, subject, tier_label.split()[1], criticality, infrastructure, ripple, scope, documentation, total_score, f'+{additions}', f'-{deletions}', hash_short]
            
            # --- FIXED PROGRESS MATH ---
            # progress_pct is now based on processed_count / total_unscanned
            progress_pct = int((processed_count / total_unscanned) * 100)
            remaining = total_unscanned - processed_count
            bar = '█' * int((progress_pct / 100) * 16) + '░' * (16 - int((progress_pct / 100) * 16))
            
            ui_block = f"─────────────────────────────────────────────────────────────────────────\n🧬 Matrix #{i} • {hash_short}\n─────────────────────────────────────────────────────────────────────────\nDate      │ {date_str}\nSubject   │ {subject[:60]}...\nTier      │ {tier_label} (Score: {total_score})\nScope     │ {scope_str}\nImpact    │ C:{criticality} I:{infrastructure} R:{ripple} S:{scope} D:{documentation}\n─────────────────────────────────────────────────────────────────────────\n🚀 [{bar}] {progress_pct}% • {remaining} commits remaining\n"
            
            print(f"⚙️  [Worker] Scored {hash_short} -> Queued for ledger flush...\n", flush=True)
            return i, (headers, row, hash_short, ui_block)
            
        except Exception as e:
            err_str = str(e)
            aimd.release(success=False)
            
            is_transient = any(k in err_str.lower() for k in ["503", "429", "unavailable", "quota", "spending cap", "high demand", "rate limit"])
            
            if is_transient:
                if retries > 0:
                    backoff = 15 * (7 - retries)
                    print(f"⚠️  [Worker] API congestion on {hash_short} (attempt {7-retries}/6). Pausing {backoff}s... Resuming shortly.\n", flush=True)
                    import time
                    time.sleep(backoff)
                    retries -= 1
                    continue
                else:
                    print(f"❌ CRITICAL: API error hard-failed {MAX_RETRIES} times on {hash_short}. Aborting.", flush=True)
                    os._exit(1)
            else:
                import traceback
                print(f"\n🔴 FATAL EXCEPTION in worker processing {hash_short}:", flush=True)
                traceback.print_exc()
                return i, f"❌ Error scoring commit {hash_short}: {err_str}"
                
    return i, f"❌ Error scoring commit {hash_short}: Max retries exceeded"
