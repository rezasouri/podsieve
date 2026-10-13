# Security policy

## Reporting a vulnerability

Please avoid publicly disclosing exploitable security issues or sensitive files in GitHub issues. Use GitHub's **Report a vulnerability** private reporting workflow if enabled for this repository. If private reporting is unavailable, contact the maintainer through a private channel before sharing exploit details.

In your report, include the affected PodSieve version or commit, operating system, reproducible impact, and a minimal proof of concept with private data removed.

## Protecting audio and credentials

- Never commit `.env`, Hugging Face tokens, browser cookies, personal recordings, or generated datasets.
- Review downloaded URL content and third-party model assets before processing.
- Be cautious with imported paths and deletion actions; back up important source audio.
- Do not include sensitive audio or personally identifying content in public bug reports.

No vulnerability-response SLA or supported-version guarantee is published yet.
