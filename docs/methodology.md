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

## Contextual Review Prompts

The category mapping provides a first ESRS lens. The tool then adds a contextual
prompt where a broad category cannot, on its own, establish environmental
relevance or performance. These prompts are based on municipal co-design
feedback and are not impact scores or automated claims that a purchase is
positive or negative.

- **Construction and land:** check materials, reuse, energy performance, land
  use and biodiversity effects.
- **Transport and freight:** check purpose, mode, fuel or technology,
  alternatives, vehicle/load and route efficiency.
- **Energy and heating:** check the energy source and distinguish supply,
  efficiency measures and fossil combustion.
- **Climate adaptation:** record the resilience function, for example flood,
  stormwater, heat or climate-proof building measures.
- **Food and catering:** distinguish product groups and sourcing; meat and dairy
  may have higher climate relevance.
- **Chemicals and cleaning:** check the substance, hazard profile, release
  pathway and disposal. Cleaning alone is not necessarily a pollution issue.
- **Water, marine resources and green space:** distinguish water quantity,
  quality and system function; check direct marine effects and ecological
  outcomes, rather than assuming maintenance provides a biodiversity benefit.
- **Circularity, durable goods and ICT:** look for evidence of waste prevention,
  reuse, lifespan, warranty, repairability, spare parts and take-back.
- **Plastics:** review both material use and pollution pathways because the topic
  can cut across E2 and E5.

The tool reports strict **manual-review rows** separately from **rows with
context prompts**. A prompt is an invitation to interpret the available data
carefully; it does not automatically mean that the classification is wrong.

## Current MVP Workflow

1. Load invoice or procurement data.
2. Load a category mapping table.
3. Classify each row by procurement category.
4. Surface categories marked as `Needs review`.
5. Flag meeting-derived concerns:
   - broad categories have a documented contextual review prompt
   - green space is not automatically biodiversity-positive
   - construction, transport, food, chemicals and circularity are interpreted
     using the available purpose and specification evidence
6. Export classified rows for internal analysis.
7. Export category-level validation CSV for city feedback.

## Known Limits

The current prototype does not calculate environmental performance, emissions,
or formal ESRS disclosures.

It does not yet reconcile invoice classifications against General Ledger totals.

It does not yet integrate external systems such as energy, water, HR, policy
registers, target databases, or governance records.

