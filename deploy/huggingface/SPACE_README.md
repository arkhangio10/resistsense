---
title: ResistSense
emoji: "🧬"
colorFrom: teal
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# ResistSense

**A confidence-aware Genome Firewall for antimicrobial-resistance research.**

ResistSense accepts an assembled *Escherichia coli* FASTA genome and returns
traceable, uncertainty-aware assessments for five antibiotics. Genome quality,
AMRFinderPlus evidence, calibrated models, conformal prediction,
out-of-distribution detection, model disagreement, and independent molecular
target checks form a fail-closed confidence firewall.

This is a defensive research prototype, not a diagnostic device. It does not
recommend treatment. Every result requires confirmation through standard
laboratory antimicrobial-susceptibility testing.

Source and validation evidence:
[github.com/arkhangio10/resistsense](https://github.com/arkhangio10/resistsense)
