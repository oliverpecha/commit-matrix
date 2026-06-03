import os

_ARCH_TEST_ONLY = os.environ.get("MATRIX_ARCH_TEST_ONLY", "").strip().lower() in ("1", "true", "yes", "on")

if _ARCH_TEST_ONLY:
    def process_commit(*args, **kwargs):
        raise SystemExit("MATRIX_ARCH_TEST_ONLY is set; process_commit should not be called in this mode.")
else:
    from workers.commit_processor import process_commit


def submit_commit(executor, commit_i, commit_parts, total_unscanned, processed_count,
                  arch_context, model_name, rubric_path, rate_limits, aimd,
                  arch_tree_signature=None, arch_gen=None, arch_gen_trail=None):
    future = executor.submit(
        process_commit,
        commit_i, commit_parts, total_unscanned, processed_count,
        arch_context, model_name, rubric_path, rate_limits, aimd,
        arch_tree_signature, arch_gen, arch_gen_trail
    )
    return future


def seed_initial_batch(executor, commit_iterator, max_workers, total_unscanned, processed_count,
                       arch_context, model_name, rubric_path, rate_limits, aimd,
                       arch_tree_signature=None, arch_gen=None, arch_gen_trail=None):
    active_futures = {}

    for _ in range(max_workers):
        try:
            next_i, next_parts = next(commit_iterator)
            future = submit_commit(
                executor, next_i, next_parts, total_unscanned, processed_count,
                arch_context, model_name, rubric_path, rate_limits, aimd,
                arch_tree_signature=arch_tree_signature,
                arch_gen=arch_gen,
                arch_gen_trail=arch_gen_trail,
            )
            processed_count += 1
            active_futures[future] = next_i
        except StopIteration:
            break

    return active_futures, processed_count


def replenish_one(executor, commit_iterator, active_futures, total_unscanned, processed_count,
                  arch_context, model_name, rubric_path, rate_limits, aimd,
                  arch_tree_signature=None, arch_gen=None, arch_gen_trail=None):
    try:
        next_i, next_parts = next(commit_iterator)
        future = submit_commit(
            executor, next_i, next_parts, total_unscanned, processed_count,
            arch_context, model_name, rubric_path, rate_limits, aimd,
            arch_tree_signature=arch_tree_signature,
            arch_gen=arch_gen,
            arch_gen_trail=arch_gen_trail,
        )
        processed_count += 1
        active_futures[future] = next_i
    except StopIteration:
        pass

    return processed_count
