# Provider Registry

Official documentation is an engineering dependency. Every external platform, API, library service, auth provider, storage provider and infrastructure component used by Provenance has a file here. Do not rely on blog posts when an official page exists.

## Template

Copy [_template.md](_template.md) to `<provider>.md`.

## Index

| Provider | Role | File | Status |
|---|---|---|---|
| Google Gemini API | LLM and embeddings (dev) | gemini.md | To create at 1.4 |
| Groq | LLM backup | groq.md | To create if used |
| PostgreSQL and pgvector | Database | postgres.md | To create at 1.1 |
| Cloudflare R2 | Production object storage | r2.md | To create at 3.7 |
| Mailpit | Dev mail catcher | mailpit.md | To create at 1.3 |
| Resend or Brevo | Production email | email.md | To create at 3.7 |
| Greenhouse | ATS source | [greenhouse.md](greenhouse.md) | Recorded 2.5, unverified |
| Lever | ATS source | [lever.md](lever.md) | Recorded 2.5, verified (owner confirmation pending) |
| Ashby | ATS source | [ashby.md](ashby.md) | Recorded 2.5, unverified |
| Remotive | Job API | [remotive.md](remotive.md) | Recorded 2.5, restricted |
| Adzuna | Job API | [adzuna.md](adzuna.md) | Recorded 2.5, restricted |
| GitHub | Candidate evidence | github.md | To create at 3.1 |
| LinkedIn, Indeed, Wellfound, Naukri | User import only | [import-only-platforms.md](import-only-platforms.md) | Recorded 2.5 |
| LeetCode, CodeChef, GeeksforGeeks | Candidate evidence, restricted | one file each | To create at 3.1 |
