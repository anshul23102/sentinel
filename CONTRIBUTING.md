# Contributing to Sentinel

Thank you for your interest in contributing to Sentinel. This project is part of the **Elite Coders Summer of Code (ECSoC) 2026** program.

## Getting Started

1. **Find an issue** - Browse [open issues](https://github.com/anshul23102/sentinel/issues) and pick one labeled `good first issue` if you are new
2. **Comment on the issue** - Say you want to work on it so it gets assigned to you
3. **Fork the repo** - Do not push directly to this repo
4. **Create a branch** - Name it something like `feat/your-feature` or `fix/your-fix`
5. **Make your changes** - Follow the code style already in the project
6. **Open a pull request** - Fill out the PR template completely

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Free Groq API key at [console.groq.com](https://console.groq.com)

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY to .env
python3 -m uvicorn main:app --port 8000 --host 0.0.0.0
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

## Pull Request Rules

- All PRs must target the `main` branch
- One feature or fix per PR - keep it focused
- Write a clear description of what you changed and why
- If your PR closes an issue, write `Closes #<issue-number>` in the description
- Do not include unrelated changes

## Code Style

- **Python:** Follow PEP 8, keep functions small and focused
- **JavaScript/React:** Use functional components and hooks
- No commented-out code, no debug print statements in final PRs

## ECSoC Scoring

This repository participates in ECSoC 2026. Merged PRs with the `ECSoC26` label are automatically scored:

| Level | Points |
|---|---|
| L1 - Easy | 5 XP |
| L2 - Medium | 10 XP |
| L3 - Difficult | 15 XP |

The project admin assigns the label before merging. You do not need to add it yourself.

## Questions

Open a [GitHub Discussion](https://github.com/anshul23102/sentinel/discussions) or comment on the relevant issue.
