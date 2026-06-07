import os

MODEL_NAME = os.environ.get('MATRIX_MODEL', 'gemini/gemini-2.5-flash-lite')
TARGET_RPM = float(os.environ.get('MATRIX_RPM_LIMIT', os.environ.get('TARGET_RPM', '15.0')))
MAX_WORKERS = int(os.environ.get('MATRIX_MAX_WORKERS', os.environ.get('MAX_WORKERS', '6')))
HOST_REPO_NAME = os.environ.get('HOST_REPO_NAME', 'commit-matrix')
RUBRIC_NAME = os.environ.get('RUBRIC_NAME', 'cirsd')
CSV_PATH = f'/app/data/{HOST_REPO_NAME}/{HOST_REPO_NAME}_ledger_{RUBRIC_NAME}.csv'
RUBRIC_PATH = f'/app/rubrics/{RUBRIC_NAME}.md'
