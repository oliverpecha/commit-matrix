"""CSV ledger writing utilities."""
import csv
import os

def ensure_csv_exists(csv_path):
    """Check if CSV exists and return boolean."""
    return os.path.exists(csv_path)

def write_csv_row(csv_path, headers, row, is_first_write=False):
    """Append a row to the CSV ledger."""
    with open(csv_path, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if is_first_write:
            writer.writerow(headers)
        writer.writerow(row)

def load_existing_hashes(csv_path):
    import os, csv
    if not os.path.exists(csv_path): return set()
    hashes = set()
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            for row in csv.DictReader(file):
                h = row.get('Hash') or row.get('hash_short')
                if h: hashes.add(h.strip())
    except Exception as e: print(f'Duplicate check error: {e}')
    return hashes
