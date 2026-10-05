#!/bin/bash
cd "$(dirname "$0")"
python3 tiktok_printer.py
echo
read -p "Stopped. Press Enter to close..."
