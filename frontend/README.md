# ResistSense frontend

React/vinext user interface for the ResistSense Genome Firewall. This client
does not run bioinformatics or create predictions: it uploads a reconstructed
FASTA to the Python API and renders its structured, audited response.
It also renders aggregate frozen-test evidence and deterministic Prediction
Autopsy cases supplied by the API; it never calculates those results locally.

## Prerequisites

- Node.js `>=22.13.0`

## Local start

```bash
npm install
npm run dev
npm run build
```

Set `NEXT_PUBLIC_API_URL` to the FastAPI origin (default
`http://127.0.0.1:8000`). The API must be deployed with the frontend; a static
frontend alone is intentionally shown as offline.

## Useful Commands

- `npm run dev`: start local development
- `npm run build`: verify the vinext build output
- `npm test`: build and verify the rendered ResistSense product shell
