import os
import re
import sys

def main():
    # 1. Read the central truth
    try:
        with open('VERSION', 'r') as f:
            version = f.read().strip()
    except FileNotFoundError:
        print("❌ [Guardrail] Fatal: VERSION file not found in root.")
        sys.exit(1)

    # 2. Regex Patterns
    # Matches ES6 imports: import { xyz } from "./file.js" OR import "./file.js"
    # Preserves whatever quotes you used (' or ")
    js_import_pattern = re.compile(r'(import\s+.*?(?:from\s+)?["\']\..*?\.js)(?:\?v=[^"\']+)?(["\'])')

    # Matches HTML script/link tags: src="/static/js/app.js" or Jinja: src="{{ url_for(...) }}"
    html_asset_pattern = re.compile(r'((?:src|href)=["\'].*?(?:\.js|\.css).*?)(?:\?v=[^"\']+)?(["\'])')

    changes_made = False

    def process_file(filepath, pattern):
        with open(filepath, 'r') as f:
            content = f.read()

        # \g<1> is the import path, \g<2> is the closing quote
        new_content = pattern.sub(rf'\g<1>?v={version}\g<2>', content)

        if content != new_content:
            with open(filepath, 'w') as f:
                f.write(new_content)
            print(f"  ↳ Synced cache tags: {filepath}")
            return True
        return False

    print(f"🔄 [Guardrail] Syncing assets to VERSION {version}...")

    # 3. Sweep /static/js/
    for root, _, files in os.walk('static/js'):
        for file in files:
            if file.endswith('.js'):
                if process_file(os.path.join(root, file), js_import_pattern):
                    changes_made = True

    # 4. Sweep /templates/
    for root, _, files in os.walk('templates'):
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
