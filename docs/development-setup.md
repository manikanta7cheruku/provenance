# Development Setup (Windows, macOS, Linux)

Phase 0 needs only Git. Docker is needed from Phase 1.

## 1. Install tools

| Tool | Windows | Check |
|---|---|---|
| Git | Installed | `git --version` |
| Python 3.11+ | Installed (3.11.4) | `python --version` |
| Node.js 20+ | Installed (24.x works) | `node --version` |
| WSL2 | Open PowerShell as Administrator, run `wsl --install`, restart | `wsl --status` |
| Docker Desktop | https://www.docker.com/products/docker-desktop/ . Enable "Use WSL 2 based engine" | `docker --version` |
| uv (Python package manager) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` | `uv --version` |

macOS and Linux: install Docker Desktop or Docker Engine, then `curl -LsSf https://astral.sh/uv/install.sh | sh`.

Virtualization must be enabled in BIOS for Docker Desktop on Windows. If Docker Desktop reports that virtualization is disabled, enable it in BIOS first.

## 2. Where to work

Do not work inside `C:\Windows\System32`. Use a normal folder such as `C:\dev`.

```
mkdir C:\dev
cd C:\dev
```

Place the extracted `provenance` folder at `C:\dev\provenance`.

## 3. Virtual environment

You do not create one by hand. From Phase 1 onward, `uv sync` creates `.venv` automatically and installs pinned dependencies. Activate only if you want to run tools directly:

```
.venv\Scripts\Activate.ps1      # Windows PowerShell
source .venv/bin/activate       # macOS and Linux
```

Everyday commands will go through `uv run ...` or `docker compose ...`, so activation is optional.

## 4. Accounts and keys needed later

None are needed for Phase 0. Needed from Phase 1:

| Item | Where to get it | Goes in | Needed at |
|---|---|---|---|
| Gemini API key | Google AI Studio | `.env` as `GEMINI_API_KEY` | Checkpoint 1.4 |
| Groq API key (backup) | Groq console | `.env` as `GROQ_API_KEY` | Optional |
| Adzuna app id and key | Adzuna developer portal | `.env` | Checkpoint 2.1 |
| GitHub OAuth app | GitHub, Settings, Developer settings | `.env` | Checkpoint 3.1 |
| Resend or Brevo SMTP | Provider dashboard (needs your own domain) | `.env` | Production only |

Dev email uses Mailpit in Docker. No account needed.

Never commit `.env`. It is already in `.gitignore`.

## 5. First push to GitHub

1. On GitHub, create a new empty repository named `provenance` under `manikanta7cheruku`. Do not add a README, license, or .gitignore there.
2. In PowerShell:

```
cd C:\dev\provenance
git init -b main
git add .
git commit -m "docs(phase-0): add planning pack"
git remote add origin https://github.com/manikanta7cheruku/provenance.git
git push -u origin main
git tag v0.0.1
git push origin v0.0.1
```

If Git says it does not know who you are:

```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```
