# ResistSense class-aware safety report

> Internal research validation only. This is not a clinical release and does not recommend treatment. Standard laboratory antimicrobial-susceptibility testing is required.

- Research demo status: `pass`
- Clinical release status: `fail_not_externally_validated`
- Frozen prediction SHA-256: `0c5c0fa157d89eefb08a9861eb36c057eb122775ef35b140b56a6f729a04f28f`
- Test-set retuning allowed: `false`

## Class-specific coverage and residual errors

| Antibiotic | R coverage | S coverage | Incorrect emitted R-class signals | Incorrect emitted S-class signals |
| --- | ---: | ---: | ---: | ---: |
| ampicillin | 55.2% (101/183) | 1.6% (4/254) | 0/183 | 4/254 |
| cefotaxime | 12.5% (4/32) | 74.1% (300/405) | 1/32 | 0/405 |
| ciprofloxacin | 1.8% (1/56) | 81.4% (310/381) | 1/56 | 0/381 |
| gentamicin | 0.0% (0/27) | 84.4% (346/410) | 0/27 | 0/410 |
| trimethoprim/sulfamethoxazole | 32.2% (38/118) | 80.3% (256/319) | 2/118 | 5/319 |

The JSON artifact also contains genetic-group bootstrap intervals, exact numerators and denominators, no-call reasons, harm-specific residual rates, and class-aware base-model risk/coverage curves.

## Interpretation boundary

High selective accuracy does not imply uniform usefulness. Endpoints with low resistant-class coverage are abstention-dominant for that class. The frozen test set has already been inspected and will not be used for further threshold or model tuning. Independent, overlap-free external validation remains future work.
