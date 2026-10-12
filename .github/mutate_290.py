"""Throwaway (#290 AC6, never merged): apply one mutation from mutations_290.py and require its
property, at its full count in the properties suite, to go red. Exit 0 when it is caught."""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mutations_290 import MUTATIONS  # noqa: E402

wid = sys.argv[1]
path, old, new, unit_file, name = MUTATIONS[wid]
target = Path(path)
text = target.read_text()
assert text.count(old) == 1, f"{wid}: anchor matches {text.count(old)} times"
target.write_text(text.replace(old, new, 1))
folder, stem = unit_file.split("/")[1], Path(unit_file).name.removeprefix("test_")
driver = f"tests/properties/test_{folder}_{stem}"
assert Path(driver).is_file(), driver
command = ["uv", "run", "--locked", "pytest", "-W", "error", "-p", "no:cacheprovider", "--suite", "properties", driver, "-k", name]
print("$", " ".join(command), flush=True)
done = subprocess.run(command, capture_output=True, text=True, check=False)
out = done.stdout + done.stderr
print(out[-6000:])
failed = re.findall(r"(?m)^FAILED (\S+)", out)
caught = done.returncode == 1 and any(f"::{name}" in f for f in failed)
print(f"{wid}: {'CAUGHT' if caught else 'MISSED'} by {name} (exit {done.returncode}, failed {failed})")
sys.exit(0 if caught else 1)
