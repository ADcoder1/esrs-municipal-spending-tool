# Contributing

Thanks for helping improve the ESRS Municipal Spending Tool.

## Before Opening a Pull Request

- Do not commit real municipal, supplier, invoice, employee, meeting-note, or
  personally identifiable data.
- Use `samples/` or synthetic fixtures for tests and examples.
- Keep the app dependency-free unless a new dependency materially improves the
  public tool.
- Prefer transparent rules and review flags over opaque classifications.
- Preserve `None` as a valid outcome for spending that is not environmentally
  relevant by default.

## Development

Run the app:

```bash
python3 app.py
```

Run the tests:

```bash
python3 -m unittest
```

Use a private local configuration when working with non-public data:

```bash
cp config.local.example.json config.local.json
```

Then edit `config.local.json` with absolute paths to your private files. This
file is ignored by Git.

## Pull Request Checklist

- The code runs against `samples/sample_invoices.csv`.
- New behavior is documented in `README.md` or `docs/`.
- No private paths or sensitive data are included.
- Exports remain usable as CSV.

