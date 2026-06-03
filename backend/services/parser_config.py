import os

MODEL_NAME = os.environ.get('MATRIX_MODEL', 'gemini/gemini-2.5-flash-lite')
TARGET_RPM = float(os.environ.get('MATRIX_RPM_LIMIT', os.environ.get('TARGET_RPM', '15.0')))
MAX_WORKERS = int(os.environ.get('MATRIX_MAX_WORKERS', os.environ.get('MAX_WORKERS', '6')))
HOST_REPO_NAME = os.environ.get('HOST_REPO_NAME', 'commit-matrix')
RUBRIC_NAME = os.environ.get('RUBRIC_NAME', 'cirsd')
CSV_PATH = f'/app/data/{HOST_REPO_NAME}/{HOST_REPO_NAME}_ledger_{RUBRIC_NAME}.csv'
RUBRIC_PATH = f'/app/rubrics/{RUBRIC_NAME}.md'

# Architecture generator configuration (Milestone 1)
MATRIX_ARCH_ENABLED = os.environ.get('MATRIX_ARCH_ENABLED', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
MATRIX_ARCH_MODEL = os.environ.get('MATRIX_ARCH_MODEL', MODEL_NAME)
MATRIX_ARCH_MAX_RETRIES = int(os.environ.get('MATRIX_ARCH_MAX_RETRIES', '3'))
MATRIX_ARCH_RETRY_BACKOFF_SEC = float(os.environ.get('MATRIX_ARCH_RETRY_BACKOFF_SEC', '20'))
MATRIX_ARCH_MAX_FILES = int(os.environ.get('MATRIX_ARCH_MAX_FILES', '8'))
MATRIX_ARCH_MAX_CHARS_PER_FILE = int(os.environ.get('MATRIX_ARCH_MAX_CHARS_PER_FILE', '4000'))
MATRIX_ARCH_USE_PREVIOUS = os.environ.get('MATRIX_ARCH_USE_PREVIOUS', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
MATRIX_ARCH_ALLOW_STALE_CONTINUE = os.environ.get('MATRIX_ARCH_ALLOW_STALE_CONTINUE', 'ask').strip().lower()
MATRIX_ARCH_HEURISTIC_MODE = os.environ.get('MATRIX_ARCH_HEURISTIC_MODE', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
MATRIX_ARCH_MODEL_DIRECTED_MODE = os.environ.get('MATRIX_ARCH_MODEL_DIRECTED_MODE', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
MATRIX_ARCH_GENERATOR_VERSION = os.environ.get('MATRIX_ARCH_GENERATOR_VERSION', 'archgen-v1')
MATRIX_ARCH_SIGNIFICANCE_MODE = os.environ.get('MATRIX_ARCH_SIGNIFICANCE_MODE', 'heuristic')
MATRIX_ARCH_VERBOSE = os.environ.get('MATRIX_ARCH_VERBOSE', 'true').strip().lower() in ('1', 'true', 'yes', 'on')

# High-level architecture generation mode:
# - programmatic       → only programmatic blueprint (no LLM)
# - llm-single-pass    → single-pass LLM generation
# - llm-two-pass       → 2-pass model-directed retrieval
# - llm-tool-agentic   → agentic tool-calling retrieval
MATRIX_ARCH_MODE = os.environ.get('MATRIX_ARCH_MODE', 'programmatic').strip().lower()
