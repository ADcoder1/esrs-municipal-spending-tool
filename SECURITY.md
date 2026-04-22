# Security and Data Handling

Please do not open public issues or pull requests containing private municipal
data, supplier identifiers, invoice text, employee data, unpublished meeting
notes, credentials, or local network paths.

If you discover a security or privacy issue, report it privately to the project
maintainers before public disclosure.

## Sensitive Data Rules

- Keep real procurement, ledger, supplier, HR, and meeting-note data outside the
  repository.
- Use `config.local.json` or environment variables for private file paths.
- Share only synthetic or explicitly cleared sample data.
- Review generated CSV exports before sharing them outside the project team.

