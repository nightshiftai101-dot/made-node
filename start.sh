#!/bin/bash
echo "============================================================"
echo "  M.A.D.E. Coin Node  v0.9.1-testnet"
echo "  Making A Daily Earning"
echo "============================================================"
echo

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed."
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip"
    echo "  macOS:          brew install python3"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt --quiet

echo
echo "Starting M.A.D.E. Coin Node..."
echo
python3 node.py "$@"
