# Organizer dataset clarification

Status recorded: 2026-07-18.

The project owner reported the following clarification from the challenge
discussion:

- Kai stated that teams may use any dataset that fits the problem, may work
  with one or more bacterial species, and may build and debug their own
  dataset.
- Sanika confirmed that the dataset used in the tutorial was an example rather
  than a mandatory challenge dataset.
- A challenge-provided FASTA cohort or hidden split should therefore not be
  treated as an external dependency.

## ResistSense decision

ResistSense uses a self-curated *Escherichia coli* cohort from BV-BRC. Only
`Laboratory Method` resistant/susceptible observations are eligible. Concordant
duplicates collapse to one label; contradictory genome-antibiotic pairs are
excluded. Assembly metadata QC and cgMLST HC50 grouping are required.

The candidate cohort contains 2,909 genomes with clear labels for all five
declared antibiotics and 1,306 genetic groups. Groups are assigned intact to
training, probability calibration, conformal calibration, or held-out test.

## Submission provenance action

Archive the original challenge-platform message, screenshot, or URL from Kai
and Sanika alongside this note before submission. This file records the project
decision but is not a substitute for the primary organizer communication.
