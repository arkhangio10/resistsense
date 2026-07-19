# Permanent Hugging Face deployment

The public ResistSense deployment uses one Hugging Face Docker Space. Nginx
exposes a single public port and routes the application internally:

```text
/        -> React / vinext on port 3000
/api/*   -> FastAPI on port 8000
/health  -> FastAPI health check
```

The Space image contains the pinned AMRFinderPlus tool and database. The five
checksum-frozen runtime models, phase-2 audit, and Prediction Autopsy are
downloaded from a versioned GitHub Release during the image build. Generated
models are therefore not committed to the source repository.

## Publish from Windows PowerShell

1. Create a free Hugging Face account and a user access token with write
   permission.
2. Install the official `hf` CLI and authenticate locally.
3. Run `deploy/huggingface/Publish-ResistSenseSpace.ps1` with the Hugging Face
   namespace that owns the Space.

The publishing script performs the following operations:

- creates a deterministic ZIP containing only required runtime artifacts;
- creates or verifies its checksum-frozen GitHub Release;
- stages only tracked application source files;
- creates or reuses a public Docker Space;
- uploads the complete deployment in one commit.

The public URL has the form
`https://<namespace>-resistsense.hf.space`. Free CPU hardware can sleep after
inactivity, but the URL remains stable and a visitor wakes the Space.

## Runtime policy

- CPU: two AMRFinderPlus threads.
- Input: one reconstructed *E. coli* FASTA, maximum 15 MB.
- Missing models, annotation, calibration, targets, or genome quality still
  produce a machine-readable `no-call`.
- Every result remains provisional and requires standard laboratory
  susceptibility testing.
