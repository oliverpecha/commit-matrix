import asyncio
import os


CONTAINER_NAME = "matrix-analyzer-singleton"


def remove_container(container_name=CONTAINER_NAME):
    debug_mode = str(os.environ.get("MATRIX_DEBUG", "false")).strip().lower() in ("1", "true", "yes", "on")
    if debug_mode:
        return
    os.system(f"docker rm -f {container_name} > /dev/null 2>&1")


def force_remove_container(container_name=CONTAINER_NAME):
    os.system(f"docker rm -f {container_name} > /dev/null 2>&1")


def pause_container(container_name=CONTAINER_NAME):
    os.system(f"docker pause {container_name} > /dev/null 2>&1")
    return {"status": "paused", "action": "pause"}


def unpause_container(container_name=CONTAINER_NAME):
    os.system(f"docker unpause {container_name} > /dev/null 2>&1")
    return {"status": "running", "action": "play"}


def build_scan_docker_cmd(repo: str, rubric: str, container_name=CONTAINER_NAME):
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    max_w = os.environ.get("MATRIX_MAX_WORKERS", "32")
    max_commits = os.environ.get("MATRIX_MAX_COMMITS", "0")
    rpm_limit = os.environ.get("MATRIX_RPM_LIMIT", "15")
    model_name = os.environ.get("MATRIX_MODEL", "gemini/gemini-2.5-flash-lite")
    stress_test = os.environ.get("MATRIX_STRESS_TEST", "0")
    crash_rate = os.environ.get("MATRIX_CRASH_RATE", "0.4")

    target_volume = f"/root/commit-matrix" if repo == "commit-matrix" else f"/root/commit-matrix/data/{repo}/src"
    data_volume = "/root/commit-matrix/data"

    return [
        "docker", "run", "-d", "--name", container_name,
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
        "-e", f"MATRIX_STRESS_TEST={stress_test}",
        "-e", f"MATRIX_CRASH_RATE={crash_rate}",
        "-e", "PYTHONPATH=/app",
        "-e", "LITELLM_LOG=ERROR",
        "-e", "SUPPRESS_LITELLM_LOGS=True",
        "-e", f"HOST_REPO_NAME={repo}",
        "-e", f"RUBRIC_NAME={rubric}",
        "commit-matrix-core:latest",
        "python", "-u", "/app/backend/parser.py", "--repo", "/target_repo"
    ]


async def run_docker_detached(docker_cmd):
    process = await asyncio.create_subprocess_exec(
        *docker_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout, stderr


async def follow_container_logs(container_name=CONTAINER_NAME):
    return await asyncio.create_subprocess_exec(
        "docker", "logs", "-f", container_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )


async def inspect_container_exit_code(container_name=CONTAINER_NAME):
    inspect = await asyncio.create_subprocess_exec(
        "docker", "inspect", "-f", "{{.State.ExitCode}}", container_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    i_out, _ = await inspect.communicate()
    exit_code = i_out.decode(errors="ignore").strip()
    return inspect.returncode, exit_code
