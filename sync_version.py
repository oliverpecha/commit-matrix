import os
import re
from pathlib import Path

def get_version():
    with open("VERSION", "r", encoding="utf-8") as f:
        return f.read().strip()

def sync_all_frontend_assets(version):
    # Regex to match any ?v=0.1.x or similar version strings
    pattern = re.compile(r'\?v=\d+\.\d+\.\d+')
    replacement = f'?v={version}'
    
    frontend_dir = Path("frontend")
    updated_count = 0
    
    for ext in ("*.js", "*.html"):
        for file_path in frontend_dir.rglob(ext):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            if pattern.search(content):
                new_content = pattern.sub(replacement, content)
                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    updated_count += 1
                    
    print(f"✅ Synchronized {updated_count} files to v{version}")

if __name__ == "__main__":
    v = get_version()
    sync_all_frontend_assets(v)
