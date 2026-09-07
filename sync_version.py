import os, re, sys, subprocess

def main():
    try:
        with open('VERSION', 'r') as f:
            version = f.read().strip()
    except FileNotFoundError:
        print("❌ Fatal: VERSION file not found.")
        sys.exit(1)

    # Safely captures static imports, dynamic import(), and src/href assets
    pattern = re.compile(r'((?:import\s+.*?from\s+|import\s*\(\s*|(?:src|href)=)["\'][^"\']+\.(?:js|css))(?:\?v=[^"\']+)?(["\'])')
    changes = False

    def process_file(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        new_content = pattern.sub(rf'\g<1>?v={version}\g<2>', content)
        
        if content != new_content:
            with open(filepath, 'w') as f:
                f.write(new_content)
            subprocess.run(['git', 'add', filepath], check=False)
            return True
        return False

    for root, _, files in os.walk('frontend/static'):
        for file in files:
            if file.endswith('.js') and process_file(os.path.join(root, file)):
                changes = True

    for root, _, files in os.walk('frontend/templates'):
        for file in files:
            if file.endswith('.html') and process_file(os.path.join(root, file)):
                changes = True

    print(f"✅ Sync complete for {version}")

if __name__ == "__main__":
    main()