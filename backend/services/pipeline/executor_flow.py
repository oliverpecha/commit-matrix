from backend.workers.commit_processor import process_commit


def submit_work_item(executor, work_item, rate_limits, aimd):
    future = executor.submit(
        process_commit,
        work_item.topo_id,
        work_item.commit_parts,
        work_item.total_unscanned,
        work_item.processed_count,
        work_item.arch_context,
        work_item.model_name,
        work_item.rubric_path,
        rate_limits,
        aimd,
        work_item.arch_tree_signature,
        work_item.arch_gen,
        None,
    )
    return future


def seed_initial_batch(
    executor,
    work_item_iterator,
    max_workers,
    total_unscanned,
    processed_count,
    arch_context,
    model_name,
    rubric_path,
    rate_limits,
    aimd,
    arch_tree_signature=None,
    arch_gen=None,
):
    active_futures = {}

    processed_count = int(processed_count)

    for _ in range(max_workers):
        try:
            work_item = next(work_item_iterator)
            future = submit_work_item(executor, work_item, rate_limits, aimd)
            active_futures[future] = work_item.topo_id
            processed_count += 1
        except StopIteration:
            break

    return active_futures, processed_count


def replenish_one(executor, work_item_iterator, active_futures, rate_limits, aimd):
    try:
        work_item = next(work_item_iterator)
        future = submit_work_item(executor, work_item, rate_limits, aimd)
        active_futures[future] = work_item.topo_id
    except StopIteration:
        pass
