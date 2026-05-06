# ESRS Municipal Spending Tool: Local Collaborator Setup

This package is designed so a collaborator can run the full ESRS Municipal
Spending Tool on their own machine without pushing private data to GitHub or a
shared server.

## What This Package Needs

- Python `3.9` or newer installed locally
- A local copy of the invoice or procurement file (`.xlsx` or `.csv`)
- A local copy of the reviewed ESRS mapping file (`.xlsx` or `.csv`)

## Recommended First Run

### macOS

1. Double-click `Configure-ESRS-Tool.command`
2. Choose the local invoice/procurement file
3. Choose the local mapping file
4. Optionally choose meeting notes or other local reference files
5. The tool will save those paths in `config.local.json`
6. Choose `yes` when asked whether to open the tool now

### Windows

1. Double-click `Configure-ESRS-Tool.bat`
2. Choose the local invoice/procurement file
3. Choose the local mapping file
4. Optionally choose meeting notes or other local reference files
5. The tool will save those paths in `config.local.json`
6. Choose `yes` when asked whether to open the tool now

## Later Runs

After setup, use:

- `Run-ESRS-Tool.command` on macOS
- `Run-ESRS-Tool.bat` on Windows

The tool opens in the browser and runs locally, usually at a URL like:

```text
http://127.0.0.1:8765
```

If port `8765` is already busy, the launcher will choose the next available
local port automatically.

## Data Handling

- Files are read locally from the collaborator's machine
- The browser UI is local
- The analysis backend is local
- Private municipal files are not uploaded to GitHub Pages

## If Python Is Missing

If double-clicking the launcher does not work, install Python `3.9+` and try
again. On Windows, installing Python from the official installer and enabling
the "Add Python to PATH" option is usually enough.
