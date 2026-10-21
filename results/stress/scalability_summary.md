# SMT Routing Scalability Stress Results

| Case | Pins | Nets | Grid | Variables | Assertions | Strict status/time (s) | Fallback status/time (s) | Peak memory (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| scale_S_balanced | 10 | 3 | 4×8 | 2326 | 3755 | sat / 1.175 | — | 111.016 |
| scale_S_asymmetric | 10 | 3 | 4×8 | 2326 | 3755 | unsat / 0.995 | sat / 0.868 | 113.484 |
| scale_M_balanced | 20 | 6 | 8×12 | 14652 | 23146 | sat / 16.085 | — | 276.484 |
| scale_M_asymmetric | 20 | 6 | 8×12 | 14652 | 23146 | unsat / 10.130 | timeout / 300.000† | 249.641 |
| scale_L_balanced | 30 | 9 | 12×16 | 44754 | 61737 | timeout / 300.000† | timeout / 300.000† | 513.828 |
| scale_L_asymmetric | 30 | 9 | 12×16 | 44754 | 61737 | timeout / 300.000† | timeout / 300.000† | 514.078 |
| scale_XL_balanced | 42 | 12 | 16×24 | 125226 | 171911 | timeout / 300.000† | timeout / 300.000† | 1423.641 |
| scale_XL_asymmetric | 42 | 12 | 16×24 | 125226 | 171911 | timeout / 300.000† | timeout / 300.000† | 1401.141 |

† Timeout results are right-censored and plotted at 300 s. UNSAT is a proved result and is reported at its observed solve time.

These are deterministic synthetic/composed stress cases, not additional industrial circuit benchmarks. Model size is the maximum across the strict and fallback passes; the CSV preserves each pass separately.
