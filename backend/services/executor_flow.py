from workers.commit_processor import process_commit


def submit_commit(executor, commit_i, commit_parts, total_unscanned, processed_count,
                  arch_context, model_name, rubric_path, rate_limits, aimd):
    future = executor.submit(
        process_commit,
        commit_i, commit_parts, total_unscanned, processed_count,
        arch_context, model_name, rubric_path, rate_limits, aimd
    )
    return future


def seed_initial_batch(executor, commit_iterator, max_workers, total_unscanned, processed_count,
                       arch_context, model_name, rubric_path, rate_limits, aimd):
    active_futures = {}

    for _ in range(max_workers):
        try:
            next_i, next_parts = next(commit_iterator)
            future = submit_commit(
                executor, next_i, next_parts, total_unscanned, processed_count,
                arch_context, model_name, rubric_path, rate_limits, aimd
            )
            processed_count += 1
            active_futures[future] = next_i
        except StopIteration:
            break

    return active_futures, processed_count


def replenish_one(executor, commit_iterator, active_futures, total_unscanned, processed_count,
                  arch_context, model_name, rubric_path, rate_limits, aimd):
    try:
        next_i, next_parts = next(commit_iterator)
        future = submit_commit(
            executor, next_i, next_parts, total_unscanned, processed_count,
            arch_context, model_name, rubric_path, rate_limits, aimd
        )
        processed_count += 1
        active_futures[future] = next_i
    except StopIteration:
        pass

    return processed_count
