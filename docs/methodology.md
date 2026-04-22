# Methodology

The tool classifies municipal procurement or invoice rows against ESRS
environmental themes:

- `E1` Climate change
- `E2` Pollution
- `E3` Water and marine resources
- `E4` Biodiversity and ecosystems
- `E5` Resource use and circular economy
- `None` Not environmentally relevant by default
- `Unmatched` No mapping found

## Principles

Invoice data is the first interpretation layer. It can show where money flows,
but it cannot prove environmental impact on its own.

General Ledger data is the validation layer. It should be used to check totals,
aggregation, and consistency with financial reporting.

ESRS E1-E5 are analytical lenses. They are not treated as formal reporting
categories or claims that spending is sustainable.

Uncertainty is intentional. The tool tracks confidence and review flags instead
of forcing precise classifications when source data is ambiguous.

`None` is valid. Many invoices are not environmentally relevant by default and
should remain outside E1-E5.

## Current MVP Workflow

1. Load invoice or procurement data.
2. Load a category mapping table.
3. Classify each row by procurement category.
4. Surface categories marked as `Needs review`.
5. Flag meeting-derived concerns:
   - green space is not automatically biodiversity-positive
   - circular economy spend may need funding-source review
   - construction spend may need net-impact review
6. Export classified rows for internal analysis.
7. Export category-level validation CSV for city feedback.

## Known Limits

The current prototype does not calculate environmental performance, emissions,
or formal ESRS disclosures.

It does not yet reconcile invoice classifications against General Ledger totals.

It does not yet integrate external systems such as energy, water, HR, policy
registers, target databases, or governance records.

