import os
import re
import sys
import subprocess

def main():
    try:
        with open('VERSION', 'r') as f:
            version = f.read().strip()
    except FileNotFoundError:
        print("❌ [Guardrail] Fatal: VERSION file not found in root.")
        sys.exit(1)

    # Regex patterns with safely preserved backslashes
    js_import_pattern = re.compile(r'(import\s+.*?(?:from\s+)?["\']\..*?\.js)(?:\?v=[^"\']+)?(["\'])')
    html_asset_pattern = re.compile(r'((?:src|href)=["\'].*?(?:\.js|\.css).*?)(?:\?v=[^"\']+)?(["\'])')

    changes_made = False

    def process_file(filepath, pattern):
        with open(filepath, 'r') as f:
            content = f.read()

        new_content = pattern.sub(rf'\g<1>?v={version}\g<2>', content)

        if content != new_content:
            with open(filepath, 'w') as f:
                f.write(new_content)
            
            # Surgically stage ONLY the specific file that was modified
            subprocess.run(['git', 'add', filepath], check=False)
            print(f"  ↳ Synced and staged cache tags: {filepath}")
            return True
        return False

    print(f"🔄 [Guardrail] Syncing assets to VERSION {version}...")

    for root, _, files in os.walk('frontend/static'):
        for file in files:
            if file.endswith('.js'):
                if process_file(os.path.join(root, file), js_import_pattern):
                    changes_made = True

    for root, _, files in os.walk('frontend/templates'):
        for file in files:
            if file.endswith('.html'):
                if process_file(os.path.join(root, file), html_asset_pattern):
                    changes_made = True

    if not changes_made:
        print("✅ [Guardrail] All assets already in sync.")
    else:
        print("✅ [Guardrail] Sync complete.")

if __name__ == "__main__":
    main()
