# ResistSense deployment

The production-shaped local deployment is two services: a FastAPI scientific
backend and a React/vinext frontend. The API image is based on Python 3.11 and
copies AMRFinderPlus 4.2.7, its database, BLAST, and helper binaries from the
official NCBI image pinned by digest. It does not require a Docker socket at
runtime.

The NumPy, SciPy, joblib, pandas, and scikit-learn versions are pinned in
`pyproject.toml` because persisted model artifacts are not portable across
arbitrary scikit-learn versions.

ResistSense remains a research prototype. Deployment does not establish
clinical validity, and every result still requires standard laboratory testing.

## Local container verification

```powershell
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/v1/readiness
```

Open `http://localhost:3000`. Stop the services with:

```powershell
docker compose down
```

## External configuration

- Build the frontend with `NEXT_PUBLIC_API_URL` set to the public HTTPS API.
- Set `RESISTSENSE_CORS_ORIGINS` on the API to the public frontend origin.
- Allocate at least 2 GB memory and enough image storage for the roughly
  2.2 GB uncompressed API image containing AMRFinderPlus and its database.
- Keep the five release-gated model artifacts under
  `artifacts/runtime/models` in the API image.
- Do not expose uploaded FASTA files through logs or persistent public storage.

The repository does not select or mutate a cloud provider. Publishing requires
the owner's deployment account, public URLs, and secret configuration.

## Release assets

Generated datasets and model binaries are intentionally excluded from Git.
Create the checksum-verified release bundle with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package_release.ps1
```

Upload the resulting ignored ZIP as a GitHub Release asset. A clean clone must
extract the verified models to `artifacts/runtime/models` before building the
API image. The tracked `release/manifest.json` records every expected checksum
and the exact model-runtime versions.
