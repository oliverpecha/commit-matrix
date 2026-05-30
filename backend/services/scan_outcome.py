def success_eof():
    return "\n\n[__MATRIX_EOF_SUCCESS__]"

def cleanup_race_success_eof():
    return (
        "\n\n⚠️ Engine cleanup race detected while resolving final container state. "
        "Stream output above is authoritative.\n[__MATRIX_EOF_SUCCESS__]"
    )

def failure_eof(exit_code):
    return f"\n\n❌ FATAL ENGINE CRASH (Exit Code {exit_code}). See traceback above.\n[__MATRIX_EOF_FAIL_CODE_{exit_code}__]"

def docker_invocation_failed(stdout_text, stderr_text):
    details = stderr_text.strip() or stdout_text.strip() or "No docker error output captured."
    return f"❌ DOCKER INVOCATION FAILED: {details}\n"

def stream_exception_message(ex):
    return f"\n⚠️ INTERNAL STREAM STREAM EXCEPTION ERROR: {str(ex)}\n"
