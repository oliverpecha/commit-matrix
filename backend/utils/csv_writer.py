import os
import csv

def load_existing_hashes(csv_path):
    hashes = set()
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if headers:
                try:
                    hash_idx = headers.index("Hash")
                    for row in reader:
                        if len(row) > hash_idx:
                            hashes.add(row[hash_idx][:7])
                except ValueError:
                    pass
    return hashes

def ensure_csv_exists(csv_path):
    file_exists = os.path.exists(csv_path)
    if not file_exists:
        # Create nested directories if they do not exist
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    return file_exists

def write_csv_row(csv_path, headers, row, is_first_write=False):
    # Ensure directory exists immediately before write just in case
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if is_first_write:
            writer.writerow(headers)
        writer.writerow(row)

def compact_csv_merge(csv_path, headers, chunk_size=50000):
    import os, csv, heapq, tempfile

    def sort_key(row):
        try:
            return -int(row[0])
        except (ValueError, IndexError):
            return 0

    tmp_files = []
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            while True:
                chunk = [row for _, row in zip(range(chunk_size), reader)]
                if not chunk:
                    break
                chunk.sort(key=sort_key)
                tf = tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8", delete=False, dir=os.path.dirname(csv_path))
                csv.writer(tf).writerows(chunk)
                tf.close()
                tmp_files.append(tf.name)

        def read_rows(path):
            with open(path, newline="", encoding="utf-8") as f:
                yield from csv.reader(f)

        out_tmp = f"{csv_path}.tmp"
        with open(out_tmp, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerow(headers)
            writer.writerows(heapq.merge(*(read_rows(p) for p in tmp_files), key=sort_key))

        os.replace(out_tmp, csv_path)
    finally:
        for p in tmp_files:
            try:
                os.remove(p)
            except OSError:
                pass
