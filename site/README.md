# DeliveryTwin AI: public site

Interactive research preview: home (`/en`, `/pt`), interactive lab (`/en/lab`), research results (`/en/research`), privacy (`/en/privacy`), and the early-access endpoint (`POST /api/interest`). Decisions: [`DECISIONS.md`](DECISIONS.md).

## Run locally

```bash
# 1. data (from the repository root; needs the Python env and the recorded runs under runs/g3)
uv run python scripts/site_export.py      # scenarios + hidden-truth files (~3 min, 8 cores)
uv run python scripts/site_research.py    # research.json

# 2. site
cd site
npm install
npm run dev            # http://localhost:3000
npm test               # what-if parser tests
npm run typecheck
npm run build && npm start
```

The data files under `public/data` are committed, so the site builds without Python.

## Deploy (Vercel)

Production: https://deliverytwin-puce.vercel.app

```bash
cd site
vercel link                      # once: create or link the project
vercel blob create-store deliverytwin-interest   # once: Blob store for the contact form (entries are written with private access)
# connect the store to the project in the Vercel dashboard (Storage → Connect), which sets BLOB_READ_WRITE_TOKEN
vercel deploy --prod
```

**Commit author on the Hobby plan.** When `site/` is deployed from inside the git repository, Vercel reads the last commit's author and blocks the deployment if that email is not a member of the Vercel account ("commit author doesn't have permission"). Either commit with an email that belongs to the Vercel account, or deploy from a copy outside git:

```bash
D=$(mktemp -d) && tar --exclude=node_modules --exclude=.next --exclude='.env*' -cf - -C site . | tar -xf - -C "$D"
python3 scripts/check_secrets.py --dir "$D" --public && (cd "$D" && vercel deploy --prod --yes)
```

Environment variables:

| Name | Required | Purpose |
|---|---|---|
| `BLOB_READ_WRITE_TOKEN` | for the contact form | Set by Vercel when a Blob store is connected. Without it the form returns 503 and shows an error; the rest of the site works. |
| `SITE_URL` | optional | Absolute base URL for metadata (Open Graph). |

Read submissions with `vercel blob list` and `vercel blob get <pathname>` (entries live under `interest/<date>/`). Delete on request with `vercel blob delete <pathname>`.

## Before publishing

Run the confidentiality guard from the repository root. It blocks secrets and any text from internal commercial documents:

```bash
python3 scripts/check_secrets.py --dir site --public
```
