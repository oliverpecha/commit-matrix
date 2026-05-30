def resolve_future_result(future, commit_i, timeout=120):
    """
    Resolve a future result with a timeout, normalizing errors to (id, None)
    and returning both the id and result plus a log message (or None).
    """
    try:
        result_i, result = future.result(timeout=timeout)
        log_msg = None
    except Exception as e:
        log_msg = f"⚠️ Worker failed on commit {commit_i}: {e}"
        result_i, result = commit_i, None

    return result_i, result, log_msg
