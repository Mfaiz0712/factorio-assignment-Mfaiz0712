import json
import subprocess
from pathlib import Path

SAMPLE = """
{
"edges":[
{"from":"s1","to":"a","lo":900,"hi":900},
{"from":"a","to":"b","lo":0,"hi":900},
{"from":"b","to":"sink","lo":0,"hi":900},
{"from":"s2","to":"a","lo":600,"hi":600},
{"from":"a","to":"c","lo":0,"hi":600},
{"from":"c","to":"sink","lo":0,"hi":600}
],
"sources":{"s1":900,"s2":600},
"sink":"sink",
"caps":{"a":1600}
}
"""

def test_flow():
    exe = ["python", str(Path(__file__).parent.parent / "belts" / "main.py")]
    proc = subprocess.run(exe, input=SAMPLE.encode(), capture_output=True, timeout=5)
    assert proc.returncode == 0, proc.stderr.decode()
    data = json.loads(proc.stdout)
    assert data["status"] == "ok"
    assert abs(data["max_flow_per_min"] - 1500) < 1e-5
