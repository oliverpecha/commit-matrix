from utils.csv_writer import write_csv_row


def init_flush_state(commits_with_ids):
    return {
        "expected_write_order": [c[0] for c in commits_with_ids],
        "write_index": 0,
        "pending_results": {},
        "error_count": 0,
        "success_count": 0,
    }


def stash_result(flush_state, result_id, result):
    flush_state["pending_results"][result_id] = result


def flush_ready_results(flush_state, csv_path, file_exists, existing_hashes):
    outputs = []

    while (
        flush_state["write_index"] < len(flush_state["expected_write_order"])
        and flush_state["expected_write_order"][flush_state["write_index"]] in flush_state["pending_results"]
    ):
        res_id = flush_state["expected_write_order"][flush_state["write_index"]]
        res = flush_state["pending_results"].pop(res_id)

        if res:
            if isinstance(res, str):
                flush_state["error_count"] += 1
                outputs.append(res)
            else:
                headers, row, hash_short, ui_block = res
                flush_state["success_count"] += 1
                is_first = (flush_state["write_index"] == 0 and not file_exists)
                write_csv_row(csv_path, headers, row, is_first_write=is_first)
                if is_first:
                    file_exists = True
                existing_hashes.add(hash_short)
                outputs.append(ui_block)

        flush_state["write_index"] += 1

    return file_exists, outputs
