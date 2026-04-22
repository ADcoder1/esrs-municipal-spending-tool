# Open Source Release Checklist

Use this checklist before publishing the repository.

- `git status --short` shows no private data files.
- `config.local.json` is ignored and not staged.
- The app runs with `samples/sample_invoices.csv`.
- No source file contains private OneDrive, SharePoint, desktop, or network
  paths.
- `README.md` explains how to configure private local files.
- `LICENSE` and `NOTICE` are present.
- `SECURITY.md` explains how to handle sensitive data.
- `docs/data-policy.md` is linked from the README.
- Sample data is synthetic.
- Screenshots, if added, use synthetic data.
- `CITATION.cff` has the correct public repository URL before release.

