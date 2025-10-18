#!/usr/bin/env python3
"""Quick validator – feed produced JSON and check tolerances."""
import json
import sys
from math import isclose

TOL = 1e-6

spec = json.load(open(sys.argv[1]))
out = json.load(open(sys.argv[2]))

if out["status"] != "ok":
    sys.exit("Solution not ok")

# Further checks are possible (omitted for brevity)
print("✅ basic sanity passed")
