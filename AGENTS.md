# Independent church member project

- This repository is independent of COMMON. Never access or modify another project's data, authentication or configuration.
- Never commit real roster files, names, phone numbers, case documents, credentials, runtime databases or backups. Tests use clearly synthetic data only.
- No registration, nickname/anonymous author, opinion tracking, AI judgments, comments, votes, signatures or member directory.
- Every protected API and document path must enforce server-side active identity. Never trust supplied author names or IDs.
- Keep role-separated administrator access, CSRF/Origin protection, TOTP, and independent publication review.
- Preserve member IDs on roster changes. Ambiguous matches require explicit human confirmation. Do not automatically remove missing members.
- Do not describe SMS, hosting, visual QA or legal/editorial review as complete without evidence.
- Run `python -m pytest -q` and `node --check app/static/app.js` for auth, data and UI changes. Document verification limits in docs/VALIDATION.md.
