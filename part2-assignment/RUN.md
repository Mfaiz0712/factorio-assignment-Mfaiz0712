
```bash
# one-liner sample check
python run_samples.py "python factory/main.py" "python belts/main.py"

# full test-suite
FACTORY_CMD="python factory/main.py" \
BELTS_CMD="python belts/main.py" \
pytest -q
```
