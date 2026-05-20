#!/usr/bin/env python3
"""
CommitMatrix Calibration Harness v2
=====================================
Tests each rubric against its validation fixtures by sending real payloads
to your LiteLLM proxy and comparing actual vs expected JSON output.
"""

import argparse
import json
import os
import sys
import time
import datetime
import threading
import concurrent.futures
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_API_KEY  = os.getenv("LITELLM_API_KEY",  "sk-1234")
RUBRICS_DIR      = Path(os.getenv("RUBRICS_DIR",  "./backend/rubrics"))
FIXTURES_DIR     = Path(os.getenv("FIXTURES_DIR", "./calibration/fixtures"))
REPORTS_DIR      = Path(os.getenv("REPORTS_DIR",  "./calibration/reports"))

PASS_THRESHOLD   = 0.80
HARD_FIELDS      = ["danger_flag"]
SOFT_TOT_DELTA   = 1

ALL_RUBRICS = ["grid", "plan", "wave", "form", "cord", "lock", "flux", "ship"]

RUBRIC_PROFILES = {
    "grid": "Infrastructure / DevOps",
    "plan": "Backend / API",
    "wave": "Frontend / UI",
    "form": "Library / SDK / CLI",
    "cord": "Full-Stack / Monorepo",
    "lock": "Security / Auth / Crypto",
    "flux": "Data / ML / Pipeline",
    "ship": "Mobile / Native App",
}

FIXTURE_EMOJI = {
    "floor":       "🪨",
    "typical":     "📦",
    "adversarial": "🎭",
}

# ── Spinner ───────────────────────────────────────────────────────────────────
class Spinner:
    def __init__(self, label):
        self.label = label
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        dots = ""
        while not self._stop.is_set():
            print(f"\r     {self.label}{dots}   ", end="", flush=True)
            dots = dots + "." if len(dots) < 5 else ""
            time.sleep(0.35)

    def start(self):
        self._thread.start()

    def stop(self, suffix=""):
        self._stop.set()
        self._thread.join()
        print(f"\r     {self.label}{suffix}" + " " * 10)


# ── JSON contract validator ───────────────────────────────────────────────────
REQUIRED_FIELDS = {"tot", "score_pct", "tier", "danger_flag", "debt_direction"}
VALID_TIERS     = {"Critical", "Significant", "Routine", "Trivial"}
VALID_DEBT_DIRS = {"increases", "neutral", "reduces"}

DEBT_AXIS_CONSISTENCY = {
    "grid": ("D", {1: "increases", 2: "neutral", 3: "reduces"}),
    "wave": ("E", {1: "increases", 2: "neutral", 3: "reduces"}),
}

def validate_contract(payload: dict, rubric_name: str = "") -> list:
    violations = []
    for f in REQUIRED_FIELDS:
        if f not in payload:
            violations.append(f"missing field: {f}")

    if "tier" in payload and payload["tier"] not in VALID_TIERS:
        violations.append(f"invalid tier: {payload['tier']!r}")

    if "debt_direction" in payload and payload["debt_direction"] not in VALID_DEBT_DIRS:
        violations.append(f"invalid debt_direction: {payload['debt_direction']!r}")

    touches = [k for k in payload if k.startswith("touches_")]
    if not touches:
        violations.append("missing at least one touches_* boolean")

    axis_keys = sorted([k for k in payload if k.isupper() and len(k) == 1])
    for k in axis_keys:
        v = payload[k]
        if not isinstance(v, int) or v not in (1, 2, 3):
            violations.append(f"invalid axis score {k}={v!r}")

    if axis_keys and "tot" in payload:
        expected_tot = sum(payload[k] for k in axis_keys)
        if payload["tot"] != expected_tot:
            violations.append(f"tot={payload['tot']} but sum of axes = {expected_tot}")

    if "tot" in payload and "score_pct" in payload and axis_keys:
        max_score = len(axis_keys) * 3
        expected_pct = round(payload["tot"] / max_score * 100, 1)
        if abs(payload["score_pct"] - expected_pct) > 0.2:
            violations.append(f"score_pct={payload['score_pct']} but expected {expected_pct}")

    if rubric_name in DEBT_AXIS_CONSISTENCY and "debt_direction" in payload:
        debt_axis, mapping = DEBT_AXIS_CONSISTENCY[rubric_name]
        axis_val = payload.get(debt_axis)
        if isinstance(axis_val, int) and axis_val in mapping:
            expected_debt = mapping[axis_val]
            actual_debt   = payload["debt_direction"]
            if actual_debt != expected_debt:
                violations.append(f"debt inconsistency: {debt_axis}={axis_val} implies {expected_debt!r}")

    return violations


# ── LiteLLM Call ──────────────────────────────────────────────────────────────
from litellm import completion
import warnings, logging
warnings.filterwarnings('ignore', module='litellm')
logging.getLogger('LiteLLM').setLevel(logging.ERROR)

def call_llm(system_prompt: str, user_content: str, model: str) -> tuple:
    max_retries = 3
    base_delay = 5.0
    
    for attempt in range(max_retries + 1):
        t0 = time.time()
        
        def _do_call():
            return completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_content}
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                num_retries=0
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_call)
                response = future.result(timeout=45)
            
            latency = round(time.time() - t0, 2)
            return response.choices[0].message.content.strip(), latency, attempt, None

        except concurrent.futures.TimeoutError:
            err_msg = "Socket Hang Prevented (45s timeout)"
            error_type = "transient"
        except Exception as e:
            err_msg = str(e)
            if any(code in err_msg for code in ["429", "503", "502", "timeout"]):
                error_type = "transient"
            else:
                error_type = "permanent"
                return None, 0.0, attempt, error_type
        
        if attempt < max_retries and error_type == "transient":
            delay = base_delay * (2 ** attempt)
            print(f"\n      [⚠] Transient API Error. Retrying in {delay}s (Attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
        else:
            return None, round(time.time() - t0, 2), attempt, error_type


# ── Fixture runner ────────────────────────────────────────────────────────────
def run_fixture(fixture_dir: Path, rubric_text: str, model: str, verbose: bool) -> dict:
    arch_path     = fixture_dir / "architecture.md"
    diff_path     = fixture_dir / "commit.diff"
    expected_path = fixture_dir / "expected.json"
    meta_path     = fixture_dir / "meta.json"

    for p in (arch_path, diff_path, expected_path):
        if not p.exists():
            return {"fixture": fixture_dir.name, "error": f"missing file: {p.name}"}

    arch_text = arch_path.read_text()
    diff_text = diff_path.read_text()
    expected  = json.loads(expected_path.read_text())
    meta      = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    ftype     = meta.get("type", fixture_dir.name)
    emoji     = FIXTURE_EMOJI.get(ftype, "📄")

    user_content = (
        f"## ARCHITECTURE CONTEXT\n{arch_text}\n\n"
        f"## GIT DIFF\n```diff\n{diff_text}\n```"
    )

    spinner = Spinner(f"{emoji}  {ftype:<12} calling model")
    spinner.start()

    raw, latency, retries, error_type = call_llm(rubric_text, user_content, model)
    
    if raw is None:
        spinner.stop("✗ call failed")
        print(f" ✗ API {error_type.capitalize()} Error")
        return {
            "fixture": fixture_dir.name,
            "fixture_type": ftype,
            "model": model,
            "contract_ok": False,
            "hard_pass": False,
            "soft_pass": False,
            "retries": retries,
            "error_type": error_type,
            "latency": latency
        }
    else:
        spinner.stop(f"done ({latency}s)")

    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:]).rstrip("`").strip()
        actual = json.loads(clean)
    except json.JSONDecodeError as e:
        return {
            "fixture": fixture_dir.name, "fixture_type": ftype,
            "error": f"JSON parse failed: {e}", "raw_response": raw, "latency": latency,
            "retries": retries, "error_type": "permanent"
        }

    violations = validate_contract(actual)
    contract_ok = len(violations) == 0

    field_results = {}
    for field, exp_val in expected.items():
        act_val = actual.get(field, "__MISSING__")
        field_results[field] = {"expected": exp_val, "actual": act_val, "match": act_val == exp_val}

    hard_pass = all(
        field_results.get(f, {}).get("match", False)
        for f in HARD_FIELDS if f in expected
    )

    expected_tot = expected.get("tot")
    actual_tot   = actual.get("tot")
    tot_delta    = abs(actual_tot - expected_tot) if (expected_tot is not None and actual_tot is not None) else None
    soft_pass    = (tot_delta <= SOFT_TOT_DELTA) if tot_delta is not None else True

    full_pass = contract_ok and hard_pass and soft_pass

    if full_pass:
        status_line = f"     ✅  {ftype:<12} pass  (tot={actual.get('tot')}, tier={actual.get('tier')}, danger={actual.get('danger_flag')}, {latency}s)"
    else:
        status_line = f"     ❌  {ftype:<12} FAIL  (tot={actual.get('tot')}, tier={actual.get('tier')}, danger={actual.get('danger_flag')}, {latency}s)"
    print(status_line)

    if verbose or not full_pass:
        if violations:
            for v in violations:
                print(f"          ⚠  contract: {v}")
        if not hard_pass:
            for f in HARD_FIELDS:
                fr = field_results.get(f, {})
                if not fr.get("match"):
                    print(f"          ✗  {f}: expected={fr.get('expected')!r}  got={fr.get('actual')!r}")
        if tot_delta is not None and tot_delta > SOFT_TOT_DELTA:
            print(f"          ✗  tot: expected={expected_tot}  got={actual_tot}  delta={tot_delta}")

    return {
        "fixture": fixture_dir.name, "fixture_type": ftype, "key_check": meta.get("key_check", ""),
        "model": model, "contract_ok": contract_ok, "violations": violations,
        "hard_pass": hard_pass, "soft_pass": soft_pass, "tot_delta": tot_delta,
        "field_results": field_results, "latency": latency,
        "retries": retries, "error_type": None, "raw_response": raw,
    }


# ── Rubric runner ─────────────────────────────────────────────────────────────
def run_rubric(rubric_name: str, model: str, verbose: bool, rubric_idx: int, total_rubrics: int) -> dict:
    rubric_path   = RUBRICS_DIR / f"{rubric_name}.md"
    fixtures_root = FIXTURES_DIR / rubric_name
    profile       = RUBRIC_PROFILES.get(rubric_name, "")

    print(f"\n{'─'*60}")
    print(f"  📋  [{rubric_idx}/{total_rubrics}]  {rubric_name.upper()}  —  {profile}")
    print(f"{'─'*60}\n")

    if not rubric_path.exists():
        print(f"  ❌  rubric file not found: {rubric_path}")
        return {}
    if not fixtures_root.exists():
        print(f"  ❌  fixtures directory not found: {fixtures_root}")
        return {}

    rubric_text  = rubric_path.read_text()
    fixture_dirs = sorted([d for d in fixtures_root.iterdir() if d.is_dir()])
    fixture_order = ["floor", "typical", "adversarial"]
    fixture_dirs  = sorted(fixture_dirs, key=lambda d: fixture_order.index(d.name) if d.name in fixture_order else 99)

    results = []
    for fd in fixture_dirs:
        result = run_fixture(fd, rubric_text, model, verbose)
        results.append(result)

    valid_fixtures = [r for r in results if "error" not in r and r.get("error_type") != "transient"]
    denominator = len(valid_fixtures)

    if not denominator:
        print(f"\n  ⛔  all fixtures errored — cannot evaluate this rubric")
        return {"rubric": rubric_name, "model": model, "results": results, "summary": {}}

    contract_pass = sum(1 for r in valid_fixtures if r.get("contract_ok"))
    hard_pass_ct  = sum(1 for r in valid_fixtures if r.get("hard_pass"))
    soft_pass_ct  = sum(1 for r in valid_fixtures if r.get("soft_pass"))
    full_pass_ct  = sum(1 for r in valid_fixtures if r.get("hard_pass") and r.get("soft_pass"))
    
    pass_rate = round(full_pass_ct / denominator, 3)
    avg_latency = round(sum(r.get("latency", 0) for r in valid_fixtures) / denominator, 2)

    adv = next((r for r in valid_fixtures if r.get("fixture_type") == "adversarial"), None)
    adv_danger_ok = adv["field_results"].get("danger_flag", {}).get("match") if adv and "field_results" in adv else None

    promoted = pass_rate >= PASS_THRESHOLD and (adv_danger_ok is not False)

    summary = {
        "rubric": rubric_name, "model": model,
        "total_fixtures": denominator, "errors": len([r for r in results if "error" in r]),
        "contract_pass": contract_pass, "hard_pass": hard_pass_ct,
        "soft_pass": soft_pass_ct, "full_pass": full_pass_ct,
        "pass_rate": pass_rate, "avg_latency_s": avg_latency,
        "adversarial_ok": adv_danger_ok, "promoted": promoted,
        "threshold": PASS_THRESHOLD,
    }

    print()
    bar_filled = int(pass_rate * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    print(f"  {'✅ PROMOTED' if promoted else '❌ NOT PROMOTED'}")
    print(f"  [{bar}] {pass_rate:.0%}  (threshold {PASS_THRESHOLD:.0%})")
    print(f"  contract {contract_pass}/{denominator}  ·  hard {hard_pass_ct}/{denominator}  ·  soft {soft_pass_ct}/{denominator}  ·  avg {avg_latency}s")
    if adv_danger_ok is False:
        print(f"  ⚠  adversarial fixture did NOT trigger danger_flag — automatic disqualification")

    return {"rubric": rubric_name, "model": model, "summary": summary, "results": results}


# ── Report writer ─────────────────────────────────────────────────────────────
def write_report(all_results: list, model: str, rubrics_to_run: list):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "-").replace(":", "-")
    rubric_tag = "all" if len(rubrics_to_run) == len(ALL_RUBRICS) else "-".join(rubrics_to_run)
    
    json_path = REPORTS_DIR / f"report_{rubric_tag}_{safe_model}_{timestamp}.json"
    txt_path  = REPORTS_DIR / f"report_{rubric_tag}_{safe_model}_{timestamp}.txt"

    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)

    lines = [
        "CommitMatrix Calibration Report",
        "=" * 60,
        f"  Model     : {model}",
        f"  Timestamp : {timestamp}",
        f"  Threshold : {PASS_THRESHOLD:.0%}",
        "",
    ]

    promoted_list, failed_list = [], []
    for r in all_results:
        s = r.get("summary", {})
        if not s:
            continue
        tag = "PROMOTED" if s.get("promoted") else "FAILED  "
        bar_f = int(s["pass_rate"] * 10)
        bar = "█" * bar_f + "░" * (10 - bar_f)
        lines.append(
            f"  {tag}  {s['rubric'].upper():<6}  [{bar}] {s['pass_rate']:.0%}  "
            f"hard={s['hard_pass']}/{s['total_fixtures']}  "
            f"adv_danger={s['adversarial_ok']}  "
            f"avg={s['avg_latency_s']}s"
        )
        (promoted_list if s.get("promoted") else failed_list).append(s["rubric"].upper())

    lines += [
        "",
        f"  Promoted : {', '.join(promoted_list) or 'none'}",
        f"  Failed   : {', '.join(failed_list) or 'none'}",
        "",
        "Failure detail:",
    ]

    for r in all_results:
        for fx in r.get("results", []):
            if "error" in fx:
                lines.append(f"  ERROR  {r.get('rubric','?').upper()}/{fx.get('fixture', '?')}: {fx['error']}")
                continue
            if fx.get("contract_ok") and fx.get("hard_pass") and fx.get("soft_pass"):
                continue
            lines.append(f"  {r.get('rubric','?').upper()}/{fx.get('fixture', '?')}:")
            for v in fx.get("violations", []):
                lines.append(f"    contract: {v}")
            for field, fr in fx.get("field_results", {}).items():
                if not fr["match"]:
                    lines.append(f"    {field}: expected={fr['expected']!r}  got={fr['actual']!r}")

    txt_path.write_text("\n".join(lines))
    return json_path, txt_path


def print_final_summary(all_results: list, model: str, json_path, txt_path, elapsed: float):
    promoted = [r["summary"]["rubric"].upper() for r in all_results if r.get("summary", {}).get("promoted")]
    failed   = [r["summary"]["rubric"].upper() for r in all_results if r.get("summary") and not r["summary"].get("promoted")]
    total    = len(promoted) + len(failed)

    print(f"\n{'═'*60}")
    print(f"  🏁  CALIBRATION COMPLETE")
    print(f"{'═'*60}")
    print(f"  Model    : {model}")
    print(f"  Duration : {elapsed:.1f}s")
    print(f"  Rubrics  : {total} tested\n")

    if promoted:
        print(f"  ✅  Promoted  ({len(promoted)}/{total}) : {', '.join(promoted)}")
    if failed:
        print(f"  ❌  Failed    ({len(failed)}/{total}) : {', '.join(failed)}")

    print()
    if json_path:
        print(f"  📄  JSON report : {json_path}")
        print(f"  📄  Text report : {txt_path}")

    overall_ok = len(failed) == 0 and total > 0
    print()
    if overall_ok:
        print("  🟢  All rubrics promoted — model is calibrated for this rubric set.")
    else:
        print("  🔴  One or more rubrics failed — review failure detail in the text report.")
    print()
    return overall_ok


# ── CLI ───────────────────────────────────────────────────────────────────────
def build_parser():
    class FriendlyParser(argparse.ArgumentParser):
        def error(self, message):
            print(f"\n❌ Oops! Invalid parameter: {message}")
            print("💡 Try: calibrate-matrix --rubric all --model gemini/gemini-3.1-pro-preview")
            import sys; sys.exit(2)
    
    parser = FriendlyParser(
        prog="calibrate.py",
        description="CommitMatrix Calibration Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rubric", default="all", metavar="NAME")
    parser.add_argument("--model", default="gemini/gemini-3.1-pro-preview", metavar="PROVIDER/MODEL")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--threshold", type=float, default=PASS_THRESHOLD, metavar="FLOAT")
    return parser

def main():
    global PASS_THRESHOLD
    parser = build_parser()
    args   = parser.parse_args()

    if "/" not in args.model and args.model != "all":
        print(f"\n❌ Error: Model '{args.model}' is missing its provider prefix.")
        print("💡 Example: 'gemini/gemini-3.1-pro-preview'")
        sys.exit(2)

    PASS_THRESHOLD = args.threshold
    rubrics_to_run = ALL_RUBRICS if args.rubric == "all" else [args.rubric.lower()]

    unknown = [r for r in rubrics_to_run if r not in ALL_RUBRICS]
    if unknown:
        print(f"❌  Unknown rubric(s): {', '.join(unknown)}")
        sys.exit(2)

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          CommitMatrix Calibration Harness v2             ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
    print(f"  🤖  Model     : {args.model}")
    print(f"  📂  Rubrics   : {', '.join(r.upper() for r in rubrics_to_run)}")
    print(f"  🎯  Threshold : {PASS_THRESHOLD:.0%} pass rate required")
    print(f"  🔗  LiteLLM   : {LITELLM_BASE_URL}")
    print(f"  🔬  Fixtures  : floor · typical · adversarial  (3 per rubric)")
    print(f"  📊  Total     : {len(rubrics_to_run) * 3} fixture runs\n")
    print("  ℹ   Verbose mode is " + ("ON" if args.verbose else "OFF"))
    print()
    
    t_start = time.time()
    all_results = []

    for i, rubric in enumerate(rubrics_to_run, 1):
        result = run_rubric(rubric, args.model, args.verbose, i, len(rubrics_to_run))
        if result:
            all_results.append(result)

    elapsed = round(time.time() - t_start, 1)

    json_path, txt_path = None, None
    if all_results and not args.no_report:
        json_path, txt_path = write_report(all_results, args.model, rubrics_to_run)

    overall_ok = print_final_summary(all_results, args.model, json_path, txt_path, elapsed)
    sys.exit(0 if overall_ok else 1)

if __name__ == "__main__":
    main()
