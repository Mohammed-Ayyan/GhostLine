import glob, re

for f in sorted(glob.glob('website/*.html')):
    content = open(f, encoding='utf-8', errors='ignore').read()
    matches = sorted(set(re.findall(r'media/[a-zA-Z0-9_\-\.]+', content)))
    if matches:
        print(f"=== {f} ===")
        for m in matches:
            print("  ", m)

