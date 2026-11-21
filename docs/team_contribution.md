# Team contribution statement and declaration of original work

> Fill in before the code freeze. Hiring decisions are individual, so be specific about who owns what.
> All members should also commit to the repository during the day (Section 5: "All members should commit").

## Ownership

Suggested split. Each owner must be able to explain their part and the system as a whole.

| Area | Main files | Owner | Also reviewed by |
|---|---|---|---|
| Rule engine, tools, SQLite schema, loader | `app/rules/engine.py`, `app/tools.py`, `app/db.py`, `app/loader.py` | | |
| Orchestration, classifier, LLM client | `app/graph.py`, `app/agents/classifier.py`, `app/llm.py`, `app/nlp/*` | | |
| Retrieval, ingestion, critic, referral | `app/kb/*`, `app/agents/critic.py`, `app/agents/evidence.py`, `app/agents/referral.py` | | |
| Actions, API, UI, Docker | `app/agents/actions.py`, `app/main.py`, `frontend/`, `docker-compose.yml` | | |
| Data and knowledge base, evaluation | `data/`, `scripts/generate_citizens.py`, `scripts/validate_data.py`, `eval/` | | |

## Declaration of original work

We declare that this submission is our team's own work for the HCLTech Future Ready AI Engineer Hackathon.
- We did not share code with other teams.
- We used AI coding assistants as described in `docs/ai_usage.md`.
- We used open-source libraries under their licences.
- We used no real personal data.
- We can explain every part of the code we submit.

| Name | Signature | Date |
|---|---|---|
| | | |
| | | |
| | | |
| | | |
