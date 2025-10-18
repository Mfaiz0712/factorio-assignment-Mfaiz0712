#!/usr/bin/env python3
"""Random instance generator for stress–testing."""
import json, random, sys

def main(n_recipes=20, n_items=15):
    recipes = {}
    items = [f"i{i}" for i in range(n_items)]
    for r in range(n_recipes):
        out_item = random.choice(items)
        recipes[f"r{r}"] = {
            "machine": "assembler_1",
            "time_s": random.uniform(0.3, 3.0),
            "in": {random.choice(items): random.randint(1, 3)},
            "out": {out_item: random.randint(1, 3)}
        }
    data = {
        "machines": {"assembler_1": {"crafts_per_min": 30}},
        "recipes": recipes,
        "modules": {},
        "limits": {"raw_supply_per_min": {}, "max_machines": {"assembler_1": 100}},
        "target": {"item": out_item, "rate_per_min": 100}
    }
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
