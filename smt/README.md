# SMT code layout

The top-level Python scripts remain compatible command-line entry points.
Implementation code is organized by responsibility inside `amacro_router/`.

```text
smt/
  runsmt_new.py                  Single-case routing entry point
  export_smt.py                  SMT-LIB export entry point
  run_all_cases.py               Circuit batch entry point
  run_scalability.py             Stress benchmark entry point
  combine_scalability_results.py Combined summary entry point
  amacro_router/
    data/
      types.py                  Shared dataclasses and type aliases
      inputs.py                 Grid/net/constraint file parsing
      graph.py                  Routing graph and mirror transformations
      symmetry.py               Symmetry inference
    encoding/
      helpers.py                SMT expressions and length bounds
      model.py                  Variable and constraint construction
    routing/
      solver.py                 Solver passes, extraction and fallback
      validation.py             Abstract-model solution validation
    results/
      plotting.py               Routing visualization
      writer.py                 Result directories and routing images
    benchmarks/
      circuit_schema.py         Circuit ordering and CSV fields
      circuit_reports.py        Circuit summary formatting
      circuits.py               Circuit batch execution
      stress_reports.py         Stress summary formatting
      stress_process.py         Subprocess execution and memory sampling
      stress.py                 Stress batch orchestration
      combine.py                Combined summaries
    cli/
      route.py                  Single-case CLI arguments and execution
      export.py                 SMT-LIB export CLI
  amacro/                       Benchmark inputs
  tests/                        Regression tests
```

Run these examples from `smt/`, with the dependencies in the parent directory's
`requirements.txt` installed:

```sh
python runsmt_new.py --case amacro/amacro_cp_M5 --output ../results/new_runs
python export_smt.py --case amacro/amacro_cp_M5 --phase strict --output ../results/cp_M5.smt2
python run_all_cases.py --cases-root amacro --output ../results/new_circuit_runs
python run_scalability.py --help
python combine_scalability_results.py --help
python -m unittest discover -s tests -v
```

Existing imports such as `from runsmt_new import build_model, load_case` continue
to work. New implementation code can import directly from the relevant module,
for example `from amacro_router.encoding.model import build_model`.

Routing runs write `routing.png`; batch runs also write CSV and Markdown
summaries. Per-run JSON files and batch manifests are not generated. The
stress runner receives metrics through subprocess stdout and retains the
input `amacro/scalability/case_manifest.json` for case ordering and metadata.
The combined-summary script takes `--table-ii-csv`, `--stress-csv`, and
`--output`. The stress runner's memory sampler uses the Unix `ps` command.
