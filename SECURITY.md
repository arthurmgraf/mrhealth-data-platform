# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email: arthurmgraf@hotmail.com
3. Include a detailed description of the vulnerability
4. Allow reasonable time for a fix before public disclosure

## Security Practices

- GCP Workload Identity Federation (zero service account keys)
- All secrets managed via environment variables
- PostgreSQL connections via SSH tunnel
- Terraform state in remote backend with encryption
- No PII in logs or error messages
