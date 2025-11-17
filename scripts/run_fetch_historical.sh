#!/bin/bash
# Wrapper script to run fetch_historical_data.py with conda environment

# Activate conda environment
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate banknifty_trading

# Change to project directory
cd "$(dirname "$0")/.."

# Run the script
python3 scripts/fetch_historical_data.py "$@"

