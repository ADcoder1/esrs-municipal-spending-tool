#!/bin/bash
set -e

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  python3 setup_local_tool.py
else
  python setup_local_tool.py
fi
