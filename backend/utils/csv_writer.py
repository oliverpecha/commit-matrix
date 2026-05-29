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
