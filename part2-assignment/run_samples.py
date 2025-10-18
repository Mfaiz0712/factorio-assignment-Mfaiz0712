#!/usr/bin/env python3
"""
Helper – run both tools on the bundled sample and show side-by-side.
Usage:
    python run_samples.py "python factory/main.py" "python belts/main.py"
"""
import json, subprocess, sys, textwrap, pathlib

FACT_SAMPLE = pathlib.Path(__file__).with_name("tests").joinpath("test_factory.py").read_text().split('SAMPLE_IN = """')[1].split('"""')[0]
BELT_SAMPLE = pathlib.Path(__file__).with_name("tests").joinpath("test_belts.py").read_text().split('SAMPLE = """')[1].split('"""')[0]

factory_cmd, belts_cmd = sys.argv[1:3]

def run(cmd, inp):
    proc = subprocess.run(cmd.split(), input=inp.encode(), capture_output=True, timeout=5)
    if proc.returncode:
        print(proc.stderr.decode())
        sys.exit(proc.returncode)
    return json.loads(proc.stdout)

print("Factory sample →", json.dumps(run(factory_cmd, FACT_SAMPLE), indent=2))
print("Belts   sample →", json.dumps(run(belts_cmd, BELT_SAMPLE), indent=2))
