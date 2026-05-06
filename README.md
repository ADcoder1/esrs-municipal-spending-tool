# ESRS Municipal Spending Tool

Local, dependency-free tool for classifying municipal procurement or invoice
data against ESRS environmental themes.

The project publishes the tool and method. Real municipal data should stay
private.

## Main Tool

The main product in this repository is the local analysis app. It can run in
two forms:

- directly from source as a local browser app
- as a packaged desktop app for macOS or Windows

When the desktop app is built, the user double-clicks an app bundle or `.exe`
instead of running Python manually.

The source-run local app is:

```text
http://127.0.0.1:8765
```

It uses a browser interface, but runs classification through the local Python
backend so it can handle large municipal XLSX workbooks, private files, and
configured reference materials.

## Desktop App Builds

To build a standalone desktop launcher locally:

```bash
python3 -m pip install pyinstaller
python3 scripts/build_desktop_app.py
```

That produces a packaged desktop app in:

```text
dist/desktop/
```

Notes:

- macOS builds must be created on macOS
- Windows builds must be created on Windows
- the repository includes a GitHub Actions workflow at
  `.github/workflows/build-desktop.yml` that builds both automatically on tag
  pushes such as `v0.2.0`

The desktop app still opens the main analysis interface in the user's browser,
but the server, launcher, and configuration live inside a native app bundle.

## Public Demo

Once GitHub Pages is enabled, the public browser-only demo is available at:

```text
https://adcoder1.github.io/esrs-municipal-spending-tool/
```

The public demo uses synthetic sample data and supports CSV and XLSX files
directly in the browser. No data is uploaded to a server. If no separate
mapping file is uploaded, the demo uses its built-in sample mapping. For
private municipal datasets, large Excel workbooks, and the fuller review
workflow, use the main local app.

## Why This Exists

Municipal finance and sustainability teams often need to answer a practical
question: what did we spend on climate and sustainability?

This tool helps structure that question by using ESRS environmental themes as
analytical lenses:

- `E1` Climate change
- `E2` Pollution
- `E3` Water and marine resources
- `E4` Biodiversity and ecosystems
- `E5` Resource use and circular economy
- `None` Not environmentally relevant by default
- `Unmatched` No mapping found

It does not claim that spending is sustainable, calculate environmental impact,
or produce formal ESRS disclosures.

## Features

- Loads invoice/procurement data from CSV or XLSX
- Loads an ESRS category mapping file from CSV or XLSX
- Classifies rows into `E1-E5`, `None`, or `Unmatched`
- Summarizes spending by ESRS theme, confidence, category, and missing fields
- Surfaces uncertainty through `High`, `Medium`, and `Needs review`
- Flags review concerns from municipal co-design work:
  - green space is not automatically biodiversity-positive
  - circular economy spend may need funding-source review
  - construction spend may need net-impact review
- Exports classified rows to CSV
- Exports a category validation CSV for city feedback

## Run The Main Tool

```bash
python3 app.py
```

Open the URL shown in the terminal, usually:

```text
http://127.0.0.1:8765
```

By default, the app uses synthetic sample files from `samples/`, but the local
UI is designed to be the primary analysis workspace.

## Use Private Local Data

Do not edit tracked source files with private paths.

Instead, create a local config file:

```bash
cp config.local.example.json config.local.json
```

Edit `config.local.json` with absolute paths to your private files. The file is
ignored by Git.

You can also use environment variables:

```bash
ESRS_INVOICE_PATH="/absolute/path/to/invoices.xlsx" \
ESRS_MAPPING_PATH="/absolute/path/to/mapping.xlsx" \
python3 app.py
```

Supported settings:

- `ESRS_INVOICE_PATH`
- `ESRS_MAPPING_PATH`
- `ESRS_DATA_DIR`
- `ESRS_MEETING_NOTES_PATH`
- `ESRS_GAP_REPORT_PATH`
- `ESRS_CODE_PLAN_PATH`

## Share With A Collaborator

To create a local-share package for a collaborator:

```bash
python3 scripts/build_collaborator_bundle.py
```

That creates:

- `dist/esrs-municipal-spending-tool-local/`
- `dist/esrs-municipal-spending-tool-local.zip`

The bundle includes:

- `Configure-ESRS-Tool.command` and `Configure-ESRS-Tool.bat`
- `Run-ESRS-Tool.command` and `Run-ESRS-Tool.bat`
- `LOCAL_COLLABORATOR_SETUP.md`

Typical collaborator flow:

1. Extract the zip
2. Install Python `3.9+` if needed
3. Run the `Configure` launcher once to choose local files
4. Run the `Run` launcher to open the tool in a browser

The collaborator's data stays on their own machine.

## Repository Contents

- `app.py`: local app entry point
- `desktop_launcher.py`: native desktop launcher for packaged app builds
- `launch_local_tool.py`: opens the main local app in a browser
- `setup_local_tool.py`: writes a local config through a setup flow
- `esrs_tool/`: Python backend and XLSX/CSV parser
- `static/`: main local browser UI
- `samples/`: synthetic public sample data
- `docs/`: methodology, templates, and data policy
- `docs/index.html`: browser-only public demo for GitHub Pages
- `config.example.json`: public sample configuration
- `config.local.example.json`: private configuration template

## Data Safety

Real invoice, procurement, ledger, supplier, HR, and meeting-note data should
not be committed. See [docs/data-policy.md](docs/data-policy.md).

Before publishing the repository, follow
[docs/open-source-checklist.md](docs/open-source-checklist.md).

## Development

Run tests:

```bash
python3 -m unittest
```

Run a quick syntax check:

```bash
PYTHONPYCACHEPREFIX=/tmp/esrs-pycache python3 -m py_compile app.py esrs_tool/*.py
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
