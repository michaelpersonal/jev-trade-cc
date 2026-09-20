#!/bin/zsh
set -e
cd /Users/michaelguo/projects/jev-trade-cc
# wait for the wikipedia fetcher to exit on its own (success or failure)
while pgrep -f "src/universe.py" > /dev/null; do sleep 5; done
echo "=== universe fetch finished; snapshots on disk: $(ls data/raw/snapshots | wc -l) ==="
.venv/bin/python src/build_universe_from_cache.py
echo "=== downloading prices ==="
cd src && ../.venv/bin/python data.py
echo "=== backtest ==="
../.venv/bin/python backtest.py
