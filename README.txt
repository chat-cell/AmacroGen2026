AmacroGen
=========

This package contains the SMT-based routing component of AmacroGen. It uses
Z3 to route multi-pin nets on an abstract two-layer grid, with symmetry
constraints and an optional fallback pass that relaxes symmetry. It also
provides solution validation, routing plots, and benchmark scripts.

Project repository: https://github.com/chat-cell/AmacroGen2026

Package contents
----------------
smt/amacro_router/       Input parsing, SMT encoding, routing, and reporting
smt/amacro/              20 circuit benchmark cases
smt/amacro/scalability/  8 synthetic stress cases and their input manifest
smt/tests/              Regression tests
results/                Reference routing images and stress summary tables
requirements.txt        Direct Python dependencies
requirements-lock.txt   Dependency snapshot from Python 3.9 on macOS arm64

Installation
------------
Use Python 3.9 or newer. Linux or macOS with the Unix ps command is required
for the stress runner's process-memory measurement. For Windows, run stress
benchmarks under WSL with Python and dependencies installed inside WSL.

From the package root, create and activate a virtual environment:

    python -m venv .venv

Linux/macOS:
    source .venv/bin/activate

Windows PowerShell:
    .venv\Scripts\Activate.ps1

Then install the dependencies:

    python -m pip install -r requirements.txt

The lock file records a specific environment; it is not a universal lock
for every Python version and operating system.

Quick start
-----------
Run the following commands from the smt directory:

    cd smt
    python runsmt_new.py --case amacro/amacro_cp_M5 --output ../results/new_runs

Each run creates a new case/timestamp directory containing routing.png.
Batch runs also write CSV and Markdown summaries. No per-run JSON files
or batch manifests are written. Existing run directories are preserved.
The default solver timeout is 300 seconds per pass. If the strict pass
does not find a solution, the router can try again without symmetry.
Use --disable-fallback when strict symmetry is required.

Run the 8 synthetic stress cases (Linux/macOS or WSL):

    python run_scalability.py --cases-root amacro/scalability --output ../results/new_stress_runs --timeout 300

Export a strict SMT-LIB model:

    python export_smt.py --case amacro/amacro_cp_M5 --phase strict --output ../results/cp_M5.smt2

Run the regression tests:

    python -m unittest discover -s tests -v

Each entry script accepts --help. See smt/README.md for the code layout.
combine_scalability_results.py can merge a newly generated circuit summary
CSV (--table-ii-csv) with a stress summary CSV (--stress-csv). Use --output
to specify the combined CSV file.

Input format
------------
Each case directory contains:

  grid_config.txt        One line: rows cols
  net_config.txt         One net per line: name x1 y1 x2 y2 ...
  constraint_config.txt  Optional symmetry, length, and conflict constraints

Pin coordinates are 1-based, and each net needs at least two distinct pins.
Blank lines and full-line comments beginning with # are supported.
Use the included cases as input examples. Constraint parsing is implemented
in smt/amacro_router/data/inputs.py.

Reference results and scope
---------------------------
The supplied results directory contains 28 routing images and the stress
summary CSV/Markdown. The result_dir entries in the reference
CSV describe historical locations and do not resolve within this package.
Run the scripts above to generate new images and summaries. Timings
and timeout outcomes depend on hardware and the software environment.

The stress cases are synthetic/composed examples. The router validates
its abstract grid model; it does not perform foundry sign-off DRC or LVS.
This package does not include a complete layout-generation flow or PDK.

License
-------
This project is licensed under the MIT License. See LICENSE for details.
