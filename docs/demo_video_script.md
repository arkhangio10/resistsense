# ResistSense demo video script

Target duration: 2 minutes 40 seconds. Record in English at 1080p with clear
voice audio and no background music. Keep the application full-screen and the
browser zoom at 100%.

## Shot list and narration

### 0:00–0:18 — Problem and thesis

**Screen:** Landing view, title, and `Predict · Challenge · Abstain`.

**Narration:**

“Antimicrobial-resistance models can produce confident answers even when the
genome, biological evidence, or statistical support is incomplete.
ResistSense is a Genome Firewall for *E. coli*. It predicts resistance,
challenges each prediction through independent safety barriers, and abstains
when the evidence is not sufficient.”

### 0:18–0:48 — Verified judge path

**Screen:** Start Judge Mode and load the verified frozen-test example.

**Narration:**

“For a reproducible demonstration, I load a real held-out sample from the
frozen genetic-group test split. The application never invents frontend
probabilities: every result comes from the FastAPI scientific pipeline. The
five supported antibiotics receive either a resistance-associated signal, a
susceptibility-compatible signal, or a machine-readable no-call.”

### 0:48–1:12 — Mechanism-informed result

**Screen:** Select gentamicin and show the ribosome, membrane-stress sequence,
and illustrated endpoint. Then select a resistant result.

**Narration:**

“The visualization changes with the antibiotic mechanism and result. For
gentamicin it illustrates ribosomal disruption and membrane failure. A
resistance signal preserves cellular structure. This is an accelerated
educational illustration, not microscopy, a viability measurement, or a
clinical recommendation.”

### 1:12–1:38 — Firewall Replay

**Screen:** Open Firewall Replay and point to statistical association, known
biological evidence, target gate, OOD/conformal checks, and immutable outcome.

**Narration:**

“Firewall Replay separates statistical association from known biological
markers and independent molecular-target evidence. Missing annotation,
calibration, target evidence, genome quality, or out-of-distribution support
forces a no-call. Absence of a resistance marker is never treated as proof of
susceptibility.”

### 1:38–1:58 — Prediction Autopsy

**Screen:** Show prevented and residual held-out errors.

**Narration:**

“Prediction Autopsy makes failures visible. On the frozen grouped test, the
firewall prevented 55 of 68 base-model errors and openly exposes the 13 errors
that remained. Class-aware coverage, uncertainty intervals, and residual harm
are reported rather than hidden behind one accuracy number.”

### 1:58–2:22 — GPT-5.6 auditor

**Screen:** Run or reveal the Evidence Conflict Auditor; show `source: openai`,
validation passed, privacy boundary, and immutable result.

**Narration:**

“GPT-5.6 Sol performs a constrained second-pass evidence audit. It receives
only allowlisted structured evidence—never raw FASTA, filenames, checksums, or
personal data. A deterministic validator rejects any changed status,
probability, evidence identifier, count, or unsafe clinical language. The
scientific result is locked before the model runs.”

### 2:22–2:40 — Build Week work and close

**Screen:** Evidence Passport, safety-eval score, repository link, and final
tagline.

**Narration:**

“I built ResistSense as a solo participant. Codex accelerated implementation,
testing, review, deployment automation, and documentation; I made the product,
scientific, safety, and design decisions. The research demo passes 47 release
checks and 58 backend tests, while external clinical validation remains
explicit future work. ResistSense: Predict. Challenge. Abstain.”

## Recording checklist

- Keep the final exported video below 2:50.
- Show the permanent Cloud Run URL in the address bar.
- Ensure the GPT card shows a successful OpenAI audit at least once.
- Do not show `.env`, API keys, cloud-console secrets, local paths, or logs.
- Upload to YouTube as `Public`, not `Unlisted` or `Private`.
- Verify playback, audio, captions, and the public URL in an incognito window.
