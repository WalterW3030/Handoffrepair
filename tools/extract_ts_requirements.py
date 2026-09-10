"""Extract ToolSandbox's Python requirements from its own packaging files.
Run on the machine: python3 tools/extract_ts_requirements.py /ephemeral/hr/ToolSandbox
Writes: tools/ts_requirements.txt (installable: pip install -r tools/ts_requirements.txt)
Rules: drop pins that fail on py3.12 (ccy==1.3.1 class) -> keep package, loosen version.
"""
import re, sys, os

repo = sys.argv[1] if len(sys.argv) > 1 else "/ephemeral/hr/ToolSandbox"
deps = []

# pyproject.toml [project.dependencies] / setup.py install_requires / requirements.txt
pyproject = os.path.join(repo, "pyproject.toml")
req_txt = os.path.join(repo, "requirements.txt")

if os.path.exists(pyproject):
    text = open(pyproject).read()
    m = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip().strip(',').strip('"').strip("'")
            if line and not line.startswith("#"):
                deps.append(line)
elif os.path.exists(req_txt):
    for line in open(req_txt):
        line = line.strip()
        if line and not line.startswith("#"):
            deps.append(line)

# py3.12 compatibility: ccy<1.4 has no py3.12 wheels; 2.0.0+ does
fixed = []
for d in deps:
    if d.startswith("ccy"):
        fixed.append("ccy>=2.0.0")
    else:
        fixed.append(d)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ts_requirements.txt")
open(out, "w").write("\n".join(fixed) + "\n")
print(f"wrote {out} with {len(fixed)} requirements")
