import glob
__version__ = "0.1.3"
import asyncio
import os
import subprocess


def get_container_name(repo: str = "commit-matrix", rubric: str = None, owner: str = "local") -> str:
    return f"matrix-analyzer-{owner}-{repo}-{rubric}"


def remove_container(repo_or_container: str = "commit-matrix", rubric: str = None):
    debug_mode = str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on")
    if debug_mode:
        return
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    subprocess.run(["docker", "rm", "-f", c_name], capture_output=True)


def force_remove_container(repo_or_container: str = "commit-matrix", rubric: str = None):
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    subprocess.run(["docker", "rm", "-f", c_name], capture_output=True)


def pause_container(repo_or_container: str = "commit-matrix", rubric: str = None):
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    subprocess.run(["docker", "pause", c_name], capture_output=True)
    return {"status": "paused", "action": "pause", "target": c_name}


def unpause_container(repo_or_container: str = "commit-matrix", rubric: str = None):
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    subprocess.run(["docker", "unpause", c_name], capture_output=True)
    return {"status": "running", "action": "play", "target": c_name}


def build_scan_docker_cmd(repo: str, rubric: str, container_name: str | None = None):
    c_name = container_name or get_container_name(repo, rubric)
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    max_w = os.environ.get("MATRIX_MAX_WORKERS", "32")
    max_commits = os.environ.get("MATRIX_MAX_COMMITS", "0")
    rpm_limit = os.environ.get("MATRIX_RPM_LIMIT", "15")
    model_name = os.environ.get("MATRIX_MODEL", "gemini/gemini-2.5-flash-lite")
    trigger_source = os.environ.get("MATRIX_TRIGGER_SOURCE", "browser")
    stress_test = os.environ.get("MATRIX_STRESS_TEST", "false")
    crash_rate = os.environ.get("MATRIX_CRASH_RATE", "0.4")
    random_score = os.environ.get("RANDOM_SCORE", "false")
    matrix_debug = os.environ.get("MATRIX_DEBUG", "false")

    target_volume = f"/root/commit-matrix/data/{repo}/src"
    if repo == "commit-matrix":
        target_volume = "/root/commit-matrix"
    else:
        import sqlite3
        db_path = (glob.glob(f"data/*/{repo}/db/{repo}.db") + [f"data/local/{repo}/db/{repo}.db"])[0]
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    row = conn.execute("SELECT value FROM repo_metadata WHERE key='repo_path'").fetchone()
                    if row and row[0]:
                        target_volume = row[0]
            except Exception:
                pass
    data_volume = "/root/commit-matrix/data"

    return [
        "docker", "run", "-d", "--name", c_name,
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{target_volume}:/target_repo",
        "-v", f"{data_volume}:/app/data",
        "-v", "/root/commit-matrix/rubrics:/app/rubrics",
        "-v", "/root/commit-matrix/backend:/app/backend",
        "-e", f"GEMINI_API_KEY={gemini_key}",
        "-e", f"MATRIX_MAX_WORKERS={max_w}",
        "-e", f"MATRIX_MAX_COMMITS={max_commits}",
        "-e", f"MATRIX_RPM_LIMIT={rpm_limit}",
        "-e", f"MATRIX_MODEL={model_name}",
        "-e", f"MATRIX_TRIGGER_SOURCE={trigger_source}",
        "-e", f"MATRIX_STRESS_TEST={stress_test}",
        "-e", f"MATRIX_CRASH_RATE={crash_rate}",
        "-e", f"RANDOM_SCORE={random_score}",
        "-e", f"MATRIX_DEBUG={matrix_debug}",
        "-e", "PYTHONPATH=/app",
        "-e", "LITELLM_LOG=ERROR",
        "-e", "SUPPRESS_LITELLM_LOGS=True",
        "-e", f"HOST_REPO_NAME={repo}",
        "-e", f"RUBRIC_NAME={rubric}",
        "-e", f"HOST_REPO_PATH={target_volume}",
        "commit-matrix-core:latest",
        "python", "-u", "/app/backend/commit_pipeline.py", "--repo", "/target_repo"
    ]


async def run_docker_detached(docker_cmd):
    process = await asyncio.create_subprocess_exec(
        *docker_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout, stderr


async def follow_container_logs(repo_or_container: str = "commit-matrix", rubric: str = None):
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    return await asyncio.create_subprocess_exec(
        "docker", "logs", "-f", c_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )


async def inspect_container_exit_code(repo_or_container: str = "commit-matrix", rubric: str = None):
    c_name = repo_or_container if repo_or_container.startswith("matrix-analyzer-") else get_container_name(repo_or_container, rubric)
    inspect = await asyncio.create_subprocess_exec(
        "docker", "inspect", "-f", "{{.State.ExitCode}}", c_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    i_out, _ = await inspect.communicate()
    exit_code = i_out.decode(errors="ignore").strip()
    return inspect.returncode, exit_code
