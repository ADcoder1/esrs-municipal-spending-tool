# Data Policy

This repository is designed to publish the tool and methodology, not municipal
source data.

## Public by Default

The following can be public:

- Source code
- Synthetic sample CSV files
- Blank mapping templates
- Documentation of the methodology
- Screenshots based on synthetic data
- Aggregated examples that cannot identify suppliers, people, invoices, or
  internal municipal decisions

## Private by Default

The following must stay outside the repository unless explicitly cleared for
publication:

- Invoice-level data
- General ledger extracts
- Supplier names or supplier identifiers
- Employee, HR, payroll, or workforce data
- Meeting notes and workshop notes
- Draft city feedback
- Local OneDrive, SharePoint, network, or desktop paths
- Any file that can identify people, suppliers, projects, or internal
  decision-making

## Working With Private Data

Use one of these private configuration mechanisms:

- `config.local.json`, which is ignored by Git
- environment variables such as `ESRS_INVOICE_PATH` and `ESRS_MAPPING_PATH`

Do not copy private data into `samples/`.

## Before Publishing Outputs

Review generated CSV exports before sharing. The row-level export may include
supplier names, invoice text, project codes, and department names if those
fields exist in the input data.

The safer public-facing export is usually the category validation export,
provided categories and amounts are sufficiently aggregated and reviewed.

