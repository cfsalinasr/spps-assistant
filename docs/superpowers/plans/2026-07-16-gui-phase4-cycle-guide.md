# GUI Migration Phase 4: Coupling Cycle Guide View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the read-only Coupling Cycle Guide view: a print-matched, on-screen preview of the GMP cycle record that `/synthesis/generate` (Phase 3) already writes to PDF/DOCX, with Prev/Next navigation and export buttons that open the real generated files.

**Architecture:** A pre-existing duplication between `pdf_generator.py` and `docx_generator.py` (each independently computes per-cycle dispatch/deprotection/coupling/vessel-assignment data) is resolved by extracting a single shared application-layer function, `build_cycle_guide_view_data()`, that both exporters and the new API route consume. The result is persisted into the existing `last_synthesis.json` marker at generation time (computed once, from real domain objects, so the on-screen preview can never drift from the exported documents). The frontend adds one new read-only view plus two small IPC extensions (`setCyclePosition`, `openFile`).

**Tech Stack:** Flask, pytest (backend — unchanged from Phases 1–3). Electron, React, TypeScript, Vitest, React Testing Library (frontend — unchanged from Phases 2–3).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-16-gui-phase4-cycle-guide-design.md` — read it in full before starting; every task below implements a specific section of it.
- Parent plan: `/Users/cristiansalinas/Desktop/spps/SPPS_GUI_MIGRATION_PLAN.md` §7.
- Python 3.11 (`python3.11`), run tests with `pytest` directly (on PATH at `/opt/homebrew/bin/pytest`).
- Node `v25.9.0` / npm `11.12.1`, run frontend tests with `npx vitest run` from `desktop/`.
- The API layer contains **no business logic** — only request/response marshalling and calls into `application`/`domain`/`infrastructure`.
- Response envelope convention (unchanged): `{"ok": true, "data": ...}` / `{"ok": false, "error": {"code": "...", "message": "..."}}`.
- The renderer process must **never** receive the sidecar's port or auth token. All sidecar HTTP calls happen in the main process; the renderer only calls `window.spps.*` methods.
- Do not mutate the real, persistent `~/.spps_assistant/spps_database.db` or `~/.spps_assistant/last_synthesis.json` from any automated test. Python-side tests use the `tmp_path`-isolated `app_with_redirected_marker` fixture from `tests/api/conftest.py`. TypeScript-side tests that spawn a real sidecar (`api-bridge.test.ts`) are restricted to read-only routes for exactly this reason — do **not** add a real-sidecar test for `setCyclePosition` (it mutates state and depends on a prior synthesis existing, which isn't deterministic across machines/CI).
- `build_cycle_guide_view_data()` is the **single source of truth** for per-cycle GMP record content. `pdf_generator.py` and `docx_generator.py` must render from it, not recompute it. Existing PDF/DOCX generator tests are the regression net — their assertions (`path.exists()`, etc.) must keep passing unchanged after the refactor; if a cell's formatted string content would differ from before the refactor, that's a bug in the refactor, not an acceptable behavior change.
- The GMP checkboxes, date/operator fields, and done-by/reviewed-by fields in the Cycle Guide view are **read-only, print-matched presentational elements** — never real form inputs, never persisted. See `DESIGN_CONTEXT.md` §6.6.
- TDD: for every task, write the failing test first, confirm it fails for the expected reason, then write the minimal code to pass it.
- Commit after each task with a focused message; do not squash multiple tasks into one commit.
- If a step's exact assertion/selector doesn't match what the actual rendered output looks like once real code is running, investigate and adapt precisely — don't force a mismatched test to pass by weakening it.

---

### Task 1: Move `build_coupling_label` to the domain layer

**Files:**
- Modify: `spps_assistant/domain/sequence.py` (add `build_coupling_label`)
- Modify: `spps_assistant/infrastructure/pdf_generator.py` (remove `_build_coupling_label`, use the domain one)
- Modify: `spps_assistant/infrastructure/docx_generator.py` (same)
- Modify: `tests/infrastructure/test_generators.py` (`TestBuildCouplingLabel` now tests the single shared function)

**Interfaces:**
- Consumes: `token_to_3letter` (existing, same file), `SynthesisConfig` (existing, `domain/models.py`).
- Produces: `build_coupling_label(config: SynthesisConfig, token: str) -> str`, importable from `spps_assistant.domain.sequence`. Task 2's `build_cycle_guide_view_data()` calls this directly.

This is a pure relocation — behavior is identical before and after. It's a separate task because Task 2's shared function needs a single home for this logic to call, and leaving two duplicate private copies in the generators would just add a third copy once the API/GUI needs it too.

- [ ] **Step 1: Update the test file to import from the new location**

In `tests/infrastructure/test_generators.py`, replace lines 14–15:

```python
from spps_assistant.domain.sequence import token_to_3letter as _pdf_token_3letter
from spps_assistant.domain.sequence import token_to_3letter as _docx_token_3letter
```

with:

```python
from spps_assistant.domain.sequence import token_to_3letter as _pdf_token_3letter
from spps_assistant.domain.sequence import token_to_3letter as _docx_token_3letter
from spps_assistant.domain.sequence import build_coupling_label
```

Remove `_build_coupling_label as _pdf_coupling_label` from the `pdf_generator` import block (lines 16–21) and `_build_coupling_label as _docx_coupling_label` from the `docx_generator` import block (lines 22–26), so those two import blocks become:

```python
from spps_assistant.infrastructure.pdf_generator import (
    generate_cycle_guide_pdf,
    generate_peptide_info_pdf,
    generate_materials_pdf,
)
from spps_assistant.infrastructure.docx_generator import (
    generate_cycle_guide_docx,
    generate_peptide_info_docx,
)
```

Then replace the entire `TestBuildCouplingLabel` class (currently 10 tests, lines 116–181) with 5 tests against the single shared function:

```python
class TestBuildCouplingLabel:
    def test_hbtu_with_oxyma_and_base(self):
        """Coupling label includes HBTU, Oxyma, and DIEA."""
        config = _make_config(activator='HBTU', use_oxyma=True, base='DIEA')
        label = build_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' in label
        assert 'DIEA' in label

    def test_hbtu_with_oxyma_no_base(self):
        """Coupling label omits 'None' when base is 'None'."""
        config = _make_config(activator='HBTU', use_oxyma=True, base='None')
        label = build_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' in label
        assert 'None' not in label

    def test_hbtu_no_oxyma(self):
        """Coupling label omits Oxyma when use_oxyma is False."""
        config = _make_config(activator='HBTU', use_oxyma=False, base='DIEA')
        label = build_coupling_label(config, 'A')
        assert 'HBTU' in label
        assert 'Oxyma' not in label

    def test_dic_with_oxyma(self):
        """Label includes DIC and Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=True)
        label = build_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' in label

    def test_dic_without_oxyma(self):
        """Label includes DIC but not Oxyma."""
        config = _make_config(activator='DIC', use_oxyma=False)
        label = build_coupling_label(config, 'A')
        assert 'DIC' in label
        assert 'Oxyma' not in label
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/infrastructure/test_generators.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_coupling_label' from 'spps_assistant.domain.sequence'`

- [ ] **Step 3: Add the function to the domain layer**

In `spps_assistant/domain/sequence.py`, add near the top (after the existing imports):

```python
from spps_assistant.domain.models import SynthesisConfig
```

Then add, right after the existing `token_to_3letter` function:

```python
def build_coupling_label(config: SynthesisConfig, token: str) -> str:
    """Build the coupling reagent label shown in the GMP coupling record.

    E.g. "Ala + HBTU + Oxyma + DIEA" or "Ala + DIC + Oxyma".
    """
    three = token_to_3letter(token)
    act = config.activator
    base = config.base

    if act in ('DIC', 'DCC'):
        if config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        return f"{three} + {act}"
    else:
        if config.use_oxyma and base not in ('None', 'none', ''):
            return f"{three} + {act} + Oxyma + {base}"
        elif config.use_oxyma:
            return f"{three} + {act} + Oxyma"
        return f"{three} + {act} + {base}"
```

- [ ] **Step 4: Remove the duplicate from `pdf_generator.py`**

In `spps_assistant/infrastructure/pdf_generator.py`, change the import block (currently lines 16–17):

```python
from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.sequence import token_to_3letter
```

to:

```python
from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.sequence import build_coupling_label, token_to_3letter
```

Delete the entire `_build_coupling_label` function (currently lines 109–127, right before `_header_paragraph`).

In `_build_coupling_table` (currently line ~312), change:

```python
    coupling_label = _build_coupling_label(config, first_token)
```

to:

```python
    coupling_label = build_coupling_label(config, first_token)
```

- [ ] **Step 5: Remove the duplicate from `docx_generator.py`**

In `spps_assistant/infrastructure/docx_generator.py`, change the import block (currently lines 13–14):

```python
from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.sequence import token_to_3letter
```

to:

```python
from spps_assistant.domain.constants import THREE_LETTER_CODE
from spps_assistant.domain.sequence import build_coupling_label, token_to_3letter
```

Delete the entire `_build_coupling_label` function (currently lines 138–152, right before the cover-page section comment).

In `_add_cycle_page` (currently line ~334), change:

```python
    coupling_label = _build_coupling_label(config, first_token)
```

to:

```python
    coupling_label = build_coupling_label(config, first_token)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/infrastructure/test_generators.py -v`
Expected: all pass (5 in `TestBuildCouplingLabel`, plus all the pre-existing generator tests still passing unchanged)

Run the full suite to confirm nothing else broke: `pytest -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add spps_assistant/domain/sequence.py spps_assistant/infrastructure/pdf_generator.py spps_assistant/infrastructure/docx_generator.py tests/infrastructure/test_generators.py
git commit -m "refactor: move build_coupling_label to domain/sequence.py, dedupe from pdf/docx generators"
```

---

### Task 2: `CycleGuideViewData` dataclasses + `build_cycle_guide_view_data()`

**Files:**
- Modify: `spps_assistant/domain/models.py` (add `DispatchRow`, `GmpStep`, `VesselAssignment`, `SecondaryCouplingRow`, `CyclePageData`, `CycleGuideViewData`)
- Modify: `spps_assistant/application/synthesis_guide.py` (add `build_cycle_guide_view_data` and its private helpers)
- Test: `tests/application/test_cycle_guide_view_data.py` (new file)

**Interfaces:**
- Consumes: `CouplingCycle`, `SynthesisConfig`, `Vessel`, `ResidueInfo` (existing, `domain/models.py`); `token_to_3letter`, `build_coupling_label`, `parse_token` (existing/Task 1, `domain/sequence.py`); `FMOC_MW_DEFAULTS` (existing, `domain/constants.py`); `calc_volume_stoichiometry`, `calc_volume_legacy`, `format_volume_formula` (existing, `domain/stoichiometry.py`); `build_coupling_cycles` (existing, same file).
- Produces: `build_cycle_guide_view_data(vessels: List[Vessel], coupling_cycles: List[CouplingCycle], config: SynthesisConfig, residue_info_map: Dict, date_str: str) -> CycleGuideViewData`, importable from `spps_assistant.application.synthesis_guide`. Task 3 and Task 4 (PDF/DOCX refactor) and Task 5 (marker persistence) all call this exact signature. `CycleGuideViewData.cycles: List[CyclePageData]`; each `CyclePageData` has `dispatch_rows: List[DispatchRow]`, `deprotection_steps: List[GmpStep]`, `coupling_steps: List[GmpStep]`, `vessel_assignments: List[VesselAssignment]`, `secondary_coupling_rows: Optional[List[SecondaryCouplingRow]]` — these exact field names are relied on by Tasks 3–5.

- [ ] **Step 1: Write the failing tests**

Create `tests/application/test_cycle_guide_view_data.py`:

```python
"""Tests for build_cycle_guide_view_data (application/synthesis_guide.py)."""

import pytest

from spps_assistant.domain.models import (
    CycleGuideViewData, CyclePageData, DispatchRow, GmpStep,
    ResidueInfo, SecondaryCouplingRow, SynthesisConfig, Vessel, VesselAssignment,
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.synthesis_guide import (
    build_coupling_cycles, build_cycle_guide_view_data,
)


def _vessel(number, name, seq, resin_mass_g=0.1, sub=0.3):
    tokens = tokenize(seq)
    return Vessel(
        number=number, name=name,
        original_tokens=tokens, reversed_tokens=list(reversed(tokens)),
        resin_mass_g=resin_mass_g, substitution_mmol_g=sub,
    )


def _info(token, base, prot='', fmoc_mw=311.3, free_mw=71.08, stock_conc=0.5):
    return ResidueInfo(
        token=token, base_code=base, protection=prot,
        fmoc_mw=fmoc_mw, free_mw=free_mw, stock_conc=stock_conc,
    )


def _config(**kwargs):
    defaults = dict(
        name='Test', vessel_label='Vessel', vessel_method='Teabag',
        volume_mode='stoichiometry', activator='HBTU', use_oxyma=True,
        base='DIEA', deprotection_reagent='Piperidine 20%',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
        include_bb_test=True, include_kaiser_test=False,
        starting_vessel_number=1, output_directory='out',
        resin_mass_strategy='fixed', fixed_resin_mass_g=0.1, target_yield_mg=None,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


class TestBuildCycleGuideViewData:
    def test_returns_cycle_guide_view_data(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert isinstance(result, CycleGuideViewData)
        assert result.synthesis_name == 'Test'
        assert result.date_str == '2026-01-01'

    def test_one_cycle_page_per_coupling_cycle(self):
        v = _vessel(1, 'P1', 'AGW')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {}, '2026-01-01')
        assert len(result.cycles) == 3
        assert all(isinstance(c, CyclePageData) for c in result.cycles)

    def test_cycle_page_numbers_match_coupling_cycles(self):
        v = _vessel(1, 'P1', 'AG')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {}, '2026-01-01')
        assert [c.cycle_number for c in result.cycles] == [1, 2]
        assert all(c.total_cycles == 2 for c in result.cycles)

    def test_dispatch_row_uses_residue_info_map_values(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        info = {'A': _info('A', 'A', fmoc_mw=311.3)}
        result = build_cycle_guide_view_data([v], cycles, config, info, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert isinstance(row, DispatchRow)
        assert row.residue_3letter == 'Ala'
        assert row.fmoc_mw == pytest.approx(311.3)
        assert row.vessel_numbers == [1]

    def test_dispatch_row_falls_back_to_fmoc_mw_defaults_when_token_missing(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {}, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert row.fmoc_mw == pytest.approx(311.3)  # FMOC_MW_DEFAULTS['A']

    def test_dispatch_row_legacy_volume_mode(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(volume_mode='legacy')
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        row = result.cycles[0].dispatch_rows[0]
        assert row.formula_shown == 'V = 1 × 2 mL'

    def test_deprotection_steps_include_bb_test_when_enabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_bb_test=True)
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert any('Bromophenol' in s.detail for s in steps)
        assert all(isinstance(s, GmpStep) for s in steps)

    def test_deprotection_steps_omit_bb_test_when_disabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_bb_test=False)
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert not any('Bromophenol' in s.detail for s in steps)

    def test_deprotection_steps_include_kaiser_test_when_enabled(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(include_kaiser_test=True)
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].deprotection_steps
        assert any('Kaiser' in s.label for s in steps)

    def test_deprotection_reagent_step_checkbox_count(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert result.cycles[0].deprotection_steps[0].n_checkboxes == 2
        assert result.cycles[0].deprotection_steps[1].n_checkboxes == 3

    def test_coupling_steps_has_four_repeats_plus_wash(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        steps = result.cycles[0].coupling_steps
        assert len(steps) == 5
        assert steps[0].label == '1st coupling'
        assert steps[-1].label == 'Post-coupling wash'
        assert steps[-1].n_checkboxes == 0

    def test_coupling_step_label_reflects_activator(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(activator='DIC', use_oxyma=True)
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert 'DIC' in result.cycles[0].coupling_steps[0].detail

    def test_vessel_assignment_shows_residue_for_active_vessel(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config()
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        va = result.cycles[0].vessel_assignments[0]
        assert isinstance(va, VesselAssignment)
        assert va.vessel_number == 1
        assert va.residue_3letter == 'Ala'

    def test_vessel_assignment_shows_none_for_out_vessel(self):
        v1 = _vessel(1, 'P1', 'A')       # 1 residue
        v2 = _vessel(2, 'P2', 'AG')      # 2 residues
        cycles = build_coupling_cycles([v1, v2])
        config = _config()
        info = {'A': _info('A', 'A'), 'G': _info('G', 'G', fmoc_mw=297.3, free_mw=57.05)}
        result = build_cycle_guide_view_data([v1, v2], cycles, config, info, '2026-01-01')
        cycle_2 = result.cycles[1]
        va1 = next(va for va in cycle_2.vessel_assignments if va.vessel_number == 1)
        assert va1.residue_3letter is None

    def test_secondary_coupling_rows_present_for_teabag(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(vessel_method='Teabag')
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        rows = result.cycles[0].secondary_coupling_rows
        assert rows is not None
        assert isinstance(rows[0], SecondaryCouplingRow)
        assert rows[0].residue_3letter == 'Ala'

    def test_secondary_coupling_rows_none_for_non_teabag(self):
        v = _vessel(1, 'P1', 'A')
        cycles = build_coupling_cycles([v])
        config = _config(vessel_method='Column')
        result = build_cycle_guide_view_data([v], cycles, config, {'A': _info('A', 'A')}, '2026-01-01')
        assert result.cycles[0].secondary_coupling_rows is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_cycle_guide_view_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'CycleGuideViewData' from 'spps_assistant.domain.models'`

- [ ] **Step 3: Add the dataclasses**

In `spps_assistant/domain/models.py`, append at the end of the file (after `MaterialsRow`):

```python
@dataclass
class DispatchRow:
    residue_3letter: str
    fmoc_mw: float
    mmol: float
    volume_ml: float
    formula_shown: str
    vessel_numbers: List[int]


@dataclass
class GmpStep:
    label: str
    detail: str
    n_checkboxes: int
    duration: str


@dataclass
class VesselAssignment:
    vessel_number: int
    vessel_name: str
    residue_3letter: Optional[str]   # None means this vessel is OUT at this cycle


@dataclass
class SecondaryCouplingRow:
    vessel_number: int
    vessel_name: str
    residue_3letter: str


@dataclass
class CyclePageData:
    cycle_number: int
    total_cycles: int
    dispatch_rows: List[DispatchRow]
    deprotection_steps: List[GmpStep]
    coupling_steps: List[GmpStep]
    vessel_assignments: List[VesselAssignment]
    secondary_coupling_rows: Optional[List[SecondaryCouplingRow]]   # None unless Teabag method


@dataclass
class CycleGuideViewData:
    synthesis_name: str
    date_str: str
    cycles: List[CyclePageData]
```

- [ ] **Step 4: Run tests again to confirm the next failure**

Run: `pytest tests/application/test_cycle_guide_view_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_cycle_guide_view_data' from 'spps_assistant.application.synthesis_guide'`

- [ ] **Step 5: Implement `build_cycle_guide_view_data`**

In `spps_assistant/application/synthesis_guide.py`, change the model import (currently line 8–10):

```python
from spps_assistant.domain.models import (
    CouplingCycle, SynthesisConfig, Vessel, YieldResult
)
```

to:

```python
from spps_assistant.domain.models import (
    CouplingCycle, CycleGuideViewData, CyclePageData, DispatchRow, GmpStep,
    SecondaryCouplingRow, SynthesisConfig, Vessel, VesselAssignment, YieldResult
)
```

Add these constants right after the existing imports (before `build_coupling_cycles`):

```python
WASH_DURATION = '2 × 1 min'
COUPLING_DURATION = '30 min'
```

Then add the following functions, right after `build_coupling_cycles` and before `determine_resin_mass`:

```python
def _build_dispatch_rows(
    cycle: CouplingCycle, config: SynthesisConfig, residue_info_map: Dict
) -> List[DispatchRow]:
    """Build dispatch rows (one per residue token active in this cycle)."""
    from spps_assistant.domain.sequence import token_to_3letter
    from spps_assistant.domain.constants import FMOC_MW_DEFAULTS
    # parse_token is already imported at module level in this file.
    from spps_assistant.domain.stoichiometry import (
        calc_volume_stoichiometry, calc_volume_legacy, format_volume_formula
    )

    n_vessels = len(cycle.all_vessels)
    total_resin_mmol = sum(v.resin_mass_g * v.substitution_mmol_g for v in cycle.all_vessels)
    avg_resin_mmol = total_resin_mmol / n_vessels if n_vessels else 0.03

    rows = []
    for token, vessel_nums in cycle.residues_at_position.items():
        three = token_to_3letter(token)
        n_v = len(vessel_nums)

        if token in residue_info_map:
            res = residue_info_map[token]
            fmoc_mw = res.fmoc_mw
            stock_conc = res.stock_conc
        else:
            try:
                base, _ = parse_token(token)
            except ValueError:
                base = 'X'
            fmoc_mw = FMOC_MW_DEFAULTS.get(token, FMOC_MW_DEFAULTS.get(base, 353.4))
            stock_conc = 0.5

        if config.volume_mode == 'legacy':
            volume_ml = calc_volume_legacy(n_v)
            formula_str = f"V = {n_v} × 2 mL"
        else:
            volume_ml = calc_volume_stoichiometry(n_v, config.aa_equivalents, avg_resin_mmol, stock_conc)
            formula_str = format_volume_formula(
                n_v, config.aa_equivalents, avg_resin_mmol, stock_conc, volume_ml
            )

        mmol = n_v * config.aa_equivalents * avg_resin_mmol

        rows.append(DispatchRow(
            residue_3letter=three,
            fmoc_mw=fmoc_mw,
            mmol=mmol,
            volume_ml=volume_ml,
            formula_shown=formula_str,
            vessel_numbers=sorted(vessel_nums),
        ))
    return rows


def _build_deprotection_steps(config: SynthesisConfig) -> List[GmpStep]:
    """Build the deprotection GMP steps for a cycle, matching the configured protocol."""
    dep_name = config.deprotection_reagent
    steps = [
        GmpStep(label='1. Deprotection', detail=f'{dep_name} in DMF', n_checkboxes=2, duration='2 × 10 min'),
        GmpStep(label='2. DMF wash', detail='DMF (3×)', n_checkboxes=3, duration='3 × 1 min'),
    ]
    if config.include_bb_test:
        steps.append(GmpStep(
            label='3. Bromophenol Blue test', detail='Bromophenol Blue in DMF (1×)',
            n_checkboxes=1, duration='1 × 2 min',
        ))
        steps.append(GmpStep(label='4. DMF wash', detail='DMF (2×)', n_checkboxes=2, duration=WASH_DURATION))
        steps.append(GmpStep(label='5. DCM wash', detail='DCM (2×)', n_checkboxes=2, duration=WASH_DURATION))
    else:
        steps.append(GmpStep(label='3. DMF wash', detail='DMF (2×)', n_checkboxes=2, duration=WASH_DURATION))
        steps.append(GmpStep(label='4. DCM wash', detail='DCM (2×)', n_checkboxes=2, duration=WASH_DURATION))
    if config.include_kaiser_test:
        steps.append(GmpStep(
            label='Kaiser test', detail='Coupling completeness check',
            n_checkboxes=1, duration='As needed',
        ))
    return steps


def _build_coupling_steps(config: SynthesisConfig, cycle: CouplingCycle) -> List[GmpStep]:
    """Build the coupling GMP steps for a cycle (4 repeats + post-coupling wash)."""
    from spps_assistant.domain.sequence import build_coupling_label

    first_token = next(iter(cycle.residues_at_position), 'AA')
    coupling_label = build_coupling_label(config, first_token)

    return [
        GmpStep(label='1st coupling', detail=coupling_label, n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='2nd coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='3rd coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='4th coupling', detail=f'Repeat: {coupling_label}', n_checkboxes=1, duration=COUPLING_DURATION),
        GmpStep(label='Post-coupling wash', detail='DMF (2×1 min), DCM (3×1 min)', n_checkboxes=0, duration='5 min'),
    ]


def _build_vessel_assignments(cycle: CouplingCycle) -> List[VesselAssignment]:
    """Build the per-vessel residue-or-OUT assignment list for a cycle."""
    from spps_assistant.domain.sequence import token_to_3letter

    idx = cycle.cycle_number - 1
    assignments = []
    for vessel in cycle.all_vessels:
        if idx < len(vessel.reversed_tokens):
            three = token_to_3letter(vessel.reversed_tokens[idx])
        else:
            three = None
        assignments.append(VesselAssignment(
            vessel_number=vessel.number, vessel_name=vessel.name, residue_3letter=three,
        ))
    return assignments


def _build_secondary_coupling_rows(
    cycle: CouplingCycle, config: SynthesisConfig
) -> Optional[List[SecondaryCouplingRow]]:
    """Build the Teabag-only secondary coupling verification rows, or None."""
    from spps_assistant.domain.sequence import token_to_3letter

    if config.vessel_method != 'Teabag':
        return None

    idx = cycle.cycle_number - 1
    rows = []
    for vessel in cycle.all_vessels:
        if idx < len(vessel.reversed_tokens):
            three = token_to_3letter(vessel.reversed_tokens[idx])
        else:
            three = 'OUT'
        rows.append(SecondaryCouplingRow(
            vessel_number=vessel.number, vessel_name=vessel.name, residue_3letter=three,
        ))
    return rows


def build_cycle_guide_view_data(
    vessels: List[Vessel],
    coupling_cycles: List[CouplingCycle],
    config: SynthesisConfig,
    residue_info_map: Dict,
    date_str: str,
) -> CycleGuideViewData:
    """Build the structured, display-ready data for every coupling cycle.

    This is the single source of truth for per-cycle GMP record content —
    both the PDF/DOCX generators and the GUI's Cycle Guide view render
    from this, so the on-screen preview and the exported documents can
    never drift apart.
    """
    cycles = [
        CyclePageData(
            cycle_number=cycle.cycle_number,
            total_cycles=cycle.total_cycles,
            dispatch_rows=_build_dispatch_rows(cycle, config, residue_info_map),
            deprotection_steps=_build_deprotection_steps(config),
            coupling_steps=_build_coupling_steps(config, cycle),
            vessel_assignments=_build_vessel_assignments(cycle),
            secondary_coupling_rows=_build_secondary_coupling_rows(cycle, config),
        )
        for cycle in coupling_cycles
    ]

    return CycleGuideViewData(synthesis_name=config.name, date_str=date_str, cycles=cycles)
```

Note: `List`, `Dict`, `Optional` are already imported at the top of this file (`from typing import Dict, List, Optional, Tuple`) — no new typing import needed.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/application/test_cycle_guide_view_data.py -v`
Expected: 17 passed

Run the full suite: `pytest -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add spps_assistant/domain/models.py spps_assistant/application/synthesis_guide.py tests/application/test_cycle_guide_view_data.py
git commit -m "feat(application): add build_cycle_guide_view_data — shared cycle GMP record data"
```

---

### Task 3: Refactor `pdf_generator.py` to consume `CyclePageData`

**Files:**
- Modify: `spps_assistant/infrastructure/pdf_generator.py`

**Interfaces:**
- Consumes: `build_cycle_guide_view_data` (Task 2, `application/synthesis_guide.py`); `CyclePageData`, `DispatchRow`, `GmpStep`, `VesselAssignment`, `SecondaryCouplingRow` (Task 2, `domain/models.py`).
- Produces: `generate_cycle_guide_pdf(...)` — **public signature unchanged** (still takes `vessels`, `coupling_cycles`, `config`, `residue_info_map`, `date_str` as before). No caller outside this file needs to change.

This task has no new tests of its own — the existing `TestGenerateCycleGuidePDF` tests (and every other test in `test_generators.py` that touches PDF generation) are the regression net. The goal is: same public behavior, computation moved out.

- [ ] **Step 1: Confirm the regression baseline passes before touching anything**

Run: `pytest tests/infrastructure/test_generators.py -k "PDF or CouplingLabel" -v`
Expected: all pass (this is the baseline you must not break)

- [ ] **Step 2: Replace the cycle-page builder functions**

In `spps_assistant/infrastructure/pdf_generator.py`, replace the entire block from `_build_aa_dispatch_table` through the end of `_build_cycle_page_elements` — this is the whole "Cycle page helpers" section, right after the module-level `TABLE_HEADER_STYLE`/`DEPROTECTION_STYLE`/`COUPLING_STYLE` constants and before the "Public API" section comment (line numbers shifted after Task 1's edit to this file — locate by function name, not line number) — with:

```python
def _build_aa_dispatch_table(dispatch_rows: List[DispatchRow]) -> Table:
    """Build the AA dispatch table for a coupling cycle page."""
    data = [['Residue (3-letter)', 'Fmoc-MW (g/mol)', 'mmol', 'Volume (mL)', 'Formula', 'Status', 'Vessels']]

    for row in dispatch_rows:
        vessels_str = ', '.join(str(vn) for vn in row.vessel_numbers)
        data.append([
            row.residue_3letter,
            f"{row.fmoc_mw:.1f}",
            f"{row.mmol:.4f}",
            f"{row.volume_ml:.3f}",
            row.formula_shown,
            '[ ]',
            vessels_str,
        ])

    col_widths = [2.5 * cm, 2.5 * cm, 1.8 * cm, 2.2 * cm, 7.0 * cm, 1.2 * cm, 2.5 * cm]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TABLE_HEADER_STYLE)
    return table


def _build_deprotection_table(deprotection_steps: List[GmpStep]) -> Table:
    """Build the GMP deprotection steps table."""
    rows = [['[ ]', 'Step', 'Details', 'Time']]
    for step in deprotection_steps:
        rows.append(['[ ]', step.label, step.detail, step.duration])

    col_widths = [1.0 * cm, 4.0 * cm, 8.0 * cm, 3.0 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(DEPROTECTION_STYLE)
    return table


def _build_coupling_table(coupling_steps: List[GmpStep]) -> Table:
    """Build the GMP coupling steps table."""
    rows = [['[ ]', 'Step', 'Details', 'Time']]
    for step in coupling_steps:
        checkbox = '[ ]' if step.n_checkboxes > 0 else ''
        rows.append([checkbox, step.label, step.detail, step.duration])

    col_widths = [1.0 * cm, 3.0 * cm, 10.0 * cm, 2.5 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(COUPLING_STYLE)
    return table


def _build_vessel_assignment_line(vessel_assignments: List[VesselAssignment], vessel_label: str) -> List:
    """Build vessel assignment text lines for the bottom of a cycle page."""
    elems = [Paragraph("Vessel Assignment:", SECTION_STYLE)]
    for va in vessel_assignments:
        residue = va.residue_3letter if va.residue_3letter is not None else 'OUT'
        line = f"{vessel_label} <b>{va.vessel_number}</b> [{va.vessel_name}]: {residue}"
        elems.append(Paragraph(line, SMALL_STYLE))
    return elems


def _build_secondary_coupling_table(
    secondary_coupling_rows: Optional[List[SecondaryCouplingRow]],
) -> Optional[Table]:
    """Build the secondary coupling verification table (Teabag method only)."""
    if secondary_coupling_rows is None:
        return None

    rows = [['Vessel #', 'Name', 'Residue', '1st [ ]', '2nd [ ]', '3rd [ ]', '4th [ ]']]
    for row in secondary_coupling_rows:
        rows.append([str(row.vessel_number), row.vessel_name, row.residue_3letter, '[ ]', '[ ]', '[ ]', '[ ]'])

    col_widths = [1.5 * cm, 4.0 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TABLE_HEADER_STYLE)
    return table


def _build_cycle_page_elements(cycle_page: CyclePageData, vessel_label: str) -> List:
    """Build all flowables for a single coupling cycle page."""
    elems = []

    elems.extend(_header_paragraph('', cycle_page.cycle_number, cycle_page.total_cycles))

    elems.append(Paragraph(
        f"Cycle {cycle_page.cycle_number} of {cycle_page.total_cycles} — AA Dispatch",
        SECTION_STYLE
    ))
    elems.append(_build_aa_dispatch_table(cycle_page.dispatch_rows))
    elems.append(Spacer(1, 3 * mm))

    elems.append(Paragraph("Deprotection", SECTION_STYLE))
    elems.append(_build_deprotection_table(cycle_page.deprotection_steps))
    elems.append(Spacer(1, 3 * mm))

    elems.append(Paragraph("Coupling", SECTION_STYLE))
    elems.append(_build_coupling_table(cycle_page.coupling_steps))
    elems.append(Spacer(1, 3 * mm))

    elems.extend(_build_vessel_assignment_line(cycle_page.vessel_assignments, vessel_label))
    elems.append(Spacer(1, 3 * mm))

    sec_table = _build_secondary_coupling_table(cycle_page.secondary_coupling_rows)
    if sec_table is not None:
        elems.append(Paragraph("Secondary Coupling Verification", SECTION_STYLE))
        elems.append(sec_table)

    return elems
```

- [ ] **Step 3: Update `generate_cycle_guide_pdf` to call the shared builder**

In the same file, in `generate_cycle_guide_pdf` (in the "Public API" section — line numbers shifted after Task 1's edit, locate by function name), replace the loop:

```python
    # One page per coupling cycle
    for cycle in coupling_cycles:
        cycle_elems = _build_cycle_page_elements(cycle, config, residue_info_map)
```

with:

```python
    from spps_assistant.application.synthesis_guide import build_cycle_guide_view_data

    view_data = build_cycle_guide_view_data(vessels, coupling_cycles, config, residue_info_map, date_str)

    # One page per coupling cycle
    for cycle_page in view_data.cycles:
        cycle_elems = _build_cycle_page_elements(cycle_page, config.vessel_label)
```

and update the two references to `cycle.cycle_number`/`cycle.total_cycles` a few lines below (in the per-page header `Paragraph`) to `cycle_page.cycle_number`/`cycle_page.total_cycles`:

```python
        header = Paragraph(
            f"<b>{synthesis_name}</b>  |  Cycle {cycle_page.cycle_number}/{cycle_page.total_cycles}  "
            f"|  Date: ________________  |  Operator: ________________",
            BODY_STYLE,
        )
```

- [ ] **Step 4: Remove now-unused imports and constants**

At the top of the file, the import block:

```python
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, calc_mass_mg, format_volume_formula
)
```

is no longer used anywhere in this file (the volume/formula computation moved to `application/synthesis_guide.py` in Task 2). Delete this import line entirely.

The module-level constants `WASH_DURATION = '2 × 1 min'` and `COUPLING_DURATION = '30 min'` (in the "Constants" section near the top of the file) are also no longer referenced anywhere in this file — their values now arrive pre-formatted in each `GmpStep.duration`, built once by `application/synthesis_guide.py`'s `build_cycle_guide_view_data()`. Delete both constant lines.

- [ ] **Step 5: Run tests to verify nothing broke**

Run: `pytest tests/infrastructure/test_generators.py -v`
Expected: all pass, identical pass count to Step 1's baseline

Run the full suite: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/infrastructure/pdf_generator.py
git commit -m "refactor(pdf): render cycle pages from shared CyclePageData instead of recomputing"
```

---

### Task 4: Refactor `docx_generator.py` to consume `CyclePageData`

**Files:**
- Modify: `spps_assistant/infrastructure/docx_generator.py`

**Interfaces:**
- Consumes: same as Task 3.
- Produces: `generate_cycle_guide_docx(...)` — **public signature unchanged**.

Same approach and same regression net as Task 3, applied to the DOCX generator.

- [ ] **Step 1: Confirm the regression baseline passes before touching anything**

Run: `pytest tests/infrastructure/test_generators.py -k "DOCX or CouplingLabel" -v`
Expected: all pass

- [ ] **Step 2: Replace the cycle-page builder functions**

In `spps_assistant/infrastructure/docx_generator.py`, replace the entire block from `_build_aa_dispatch_data` through the end of `_add_cycle_page` — this is the whole "Cycle pages" section, right after the "Cover page" section's `_build_cover` function and before the "Public API" section comment (line numbers shifted after Task 1's edit to this file — locate by function name, not line number) — with:

```python
def _add_aa_dispatch_table(doc: Document, dispatch_rows: List[DispatchRow]) -> None:
    """Add the AA dispatch table for a cycle page to *doc*."""
    aa_data = [['Residue', 'Fmoc-MW', 'mmol', 'Volume (mL)', 'Formula', 'Status', 'Vessels']]
    for row in dispatch_rows:
        aa_data.append([
            row.residue_3letter, f"{row.fmoc_mw:.1f}", f"{row.mmol:.4f}", f"{row.volume_ml:.3f}",
            row.formula_shown, '[ ]',
            ', '.join(str(vn) for vn in row.vessel_numbers),
        ])
    _add_table_with_header(doc, aa_data)


def _add_deprotection_table(doc: Document, deprotection_steps: List[GmpStep]) -> None:
    """Add the deprotection steps table for a cycle page to *doc*."""
    dep_data = [['[ ]', 'Step', 'Details', 'Time']]
    for step in deprotection_steps:
        dep_data.append(['[ ]', step.label, step.detail, step.duration])
    _add_table_with_header(doc, dep_data, header_bg='1A5276')


def _add_coupling_table(doc: Document, coupling_steps: List[GmpStep]) -> None:
    """Add the coupling steps table for a cycle page to *doc*."""
    coup_data = [['[ ]', 'Step', 'Details', 'Time']]
    for step in coupling_steps:
        checkbox = '[ ]' if step.n_checkboxes > 0 else ''
        coup_data.append([checkbox, step.label, step.detail, step.duration])
    _add_table_with_header(doc, coup_data, header_bg='1E8449')


def _add_vessel_assignment(doc: Document, vessel_assignments: List[VesselAssignment], vessel_label: str) -> None:
    """Add vessel assignment bullet lines to doc."""
    p = doc.add_paragraph()
    p.add_run('Vessel Assignment:').bold = True
    for va in vessel_assignments:
        residue = va.residue_3letter if va.residue_3letter is not None else 'OUT'
        text = f"  {vessel_label} {va.vessel_number} [{va.vessel_name}]: {residue}"
        doc.add_paragraph(text, style='List Bullet')


def _add_secondary_coupling_table(
    doc: Document, secondary_coupling_rows: Optional[List[SecondaryCouplingRow]]
) -> None:
    """Add secondary coupling verification table (Teabag method only)."""
    if secondary_coupling_rows is None:
        return
    doc.add_heading('Secondary Coupling Verification', 3)
    sec_data = [['Vessel #', 'Name', 'Residue', '1st [ ]', '2nd [ ]', '3rd [ ]', '4th [ ]']]
    for row in secondary_coupling_rows:
        sec_data.append([str(row.vessel_number), row.vessel_name, row.residue_3letter, '[ ]', '[ ]', '[ ]', '[ ]'])
    _add_table_with_header(doc, sec_data)


def _add_cycle_page(doc: Document, cycle_page: CyclePageData, vessel_label: str) -> None:
    """Add a single coupling cycle page to the DOCX document."""
    p = doc.add_paragraph()
    run = p.add_run(
        f"Cycle {cycle_page.cycle_number} of {cycle_page.total_cycles}  |  "
        f"Date: ________________  |  Operator: ________________"
    )
    run.bold = True
    run.font.size = Pt(10)

    doc.add_heading(f'Cycle {cycle_page.cycle_number} — AA Dispatch', 3)
    _add_aa_dispatch_table(doc, cycle_page.dispatch_rows)
    doc.add_paragraph()

    doc.add_heading('Deprotection', 3)
    _add_deprotection_table(doc, cycle_page.deprotection_steps)
    doc.add_paragraph()

    doc.add_heading('Coupling', 3)
    _add_coupling_table(doc, cycle_page.coupling_steps)
    doc.add_paragraph()

    _add_vessel_assignment(doc, cycle_page.vessel_assignments, vessel_label)
    _add_secondary_coupling_table(doc, cycle_page.secondary_coupling_rows)
```

- [ ] **Step 3: Update the model import block and `generate_cycle_guide_docx`**

At the top of the file, change:

```python
from spps_assistant.domain.models import (
    CouplingCycle, SynthesisConfig, Vessel, YieldResult, SolubilityResult
)
```

to:

```python
from spps_assistant.domain.models import (
    CouplingCycle, CyclePageData, DispatchRow, GmpStep, SecondaryCouplingRow,
    SynthesisConfig, Vessel, VesselAssignment, YieldResult, SolubilityResult
)
```

In `generate_cycle_guide_docx` (in the "Public API" section — line numbers shifted after Task 1's edit, locate by function name), replace:

```python
    # Coupling cycle pages
    for i, cycle in enumerate(coupling_cycles):
        _add_cycle_page(doc, cycle, config, residue_info_map)
        if i < len(coupling_cycles) - 1:
            doc.add_page_break()
```

with:

```python
    from spps_assistant.application.synthesis_guide import build_cycle_guide_view_data

    view_data = build_cycle_guide_view_data(vessels, coupling_cycles, config, residue_info_map, date_str)

    # Coupling cycle pages
    for i, cycle_page in enumerate(view_data.cycles):
        _add_cycle_page(doc, cycle_page, config.vessel_label)
        if i < len(view_data.cycles) - 1:
            doc.add_page_break()
```

- [ ] **Step 4: Remove now-unused imports and constants**

At the top of the file, the import block:

```python
from spps_assistant.domain.stoichiometry import (
    calc_volume_stoichiometry, calc_volume_legacy, format_volume_formula
)
```

is no longer used anywhere in this file. Delete this import line entirely.

The module-level constants `WASH_DURATION = '2 × 1 min'` and `COUPLING_DURATION = '30 min'` (in the "Constants" section near the top of the file) are also no longer referenced anywhere in this file, for the same reason as in Task 3. Delete both constant lines.

- [ ] **Step 5: Run tests to verify nothing broke**

Run: `pytest tests/infrastructure/test_generators.py -v`
Expected: all pass, identical pass count to Task 3's Step 1 baseline plus this task's DOCX baseline

Run the full suite: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/infrastructure/docx_generator.py
git commit -m "refactor(docx): render cycle pages from shared CyclePageData instead of recomputing"
```

---

### Task 5: Persist cycle guide data into the `last_synthesis.json` marker

**Files:**
- Modify: `spps_assistant/application/synthesis_guide.py` (`SynthesisGuideUseCase.run()`)
- Modify: `spps_assistant/api/routes/synthesis.py` (`generate_synthesis()`)
- Modify: `tests/api/test_synthesis_routes.py`

**Interfaces:**
- Consumes: `build_cycle_guide_view_data` (Task 2).
- Produces: `SynthesisGuideUseCase.run()` now returns `Tuple[Dict[str, str], CycleGuideViewData]` (was `Dict[str, str]`) — the only caller is `generate_synthesis()` in this same task. The `last_synthesis.json` marker gains `output_paths`, `current_cycle`, and `cycle_guide` fields; Task 6 (`POST /synthesis/cycle-position`) reads `current_cycle` and `cycle_guide.cycles` from it, and Task 9 (`CycleGuide.tsx`) reads all three.

- [ ] **Step 1: Write the failing test**

In `tests/api/test_synthesis_routes.py`, replace the existing `test_generate_writes_last_synthesis_marker` test with:

```python
def test_generate_writes_last_synthesis_marker(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.get('/synthesis/last')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['name'] == 'TestRun'
    assert body['data']['vessel_count'] == 1
    assert body['data']['current_cycle'] == 1
    assert 'cycle_guide_pdf' in body['data']['output_paths']
    assert 'cycle_guide_docx' in body['data']['output_paths']
    assert len(body['data']['cycle_guide']['cycles']) == 1
    assert body['data']['cycle_guide']['synthesis_name'] == 'TestRun'
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/api/test_synthesis_routes.py::test_generate_writes_last_synthesis_marker -v`
Expected: FAIL — `KeyError: 'current_cycle'` (or similar, since the marker doesn't have these fields yet)

- [ ] **Step 3: Update `SynthesisGuideUseCase.run()` to build and return cycle guide data**

In `spps_assistant/application/synthesis_guide.py`, change the `run()` method's return type annotation (currently):

```python
    def run(
        self,
        output_dir: str,
        config: SynthesisConfig,
        residue_info_map: Dict,
        vessels: List[Vessel],
        yield_results: Optional[List[YieldResult]] = None,
        solubility_results: Optional[Dict] = None,
    ) -> Dict[str, str]:
```

to:

```python
    def run(
        self,
        output_dir: str,
        config: SynthesisConfig,
        residue_info_map: Dict,
        vessels: List[Vessel],
        yield_results: Optional[List[YieldResult]] = None,
        solubility_results: Optional[Dict] = None,
    ) -> Tuple[Dict[str, str], CycleGuideViewData]:
```

Update its docstring's `Returns:` section to:

```python
        Returns:
            Tuple of (output_paths, cycle_guide_data). output_paths maps
            output file types to their paths. cycle_guide_data is the
            structured per-cycle GMP record data for the GUI's Cycle Guide
            view — the same data the PDF/DOCX generators render from
            internally, so the two can never drift apart.
```

Inside the method body, right after the `# 2 & 3. Calculate yields and solubility` block and before `# 4 & 5. Generate cycle guide (PDF + DOCX)`, add:

```python
        # Build the shared cycle-guide view data once, from real domain
        # objects. Both the PDF/DOCX generators below and this method's
        # return value use this same data — the on-screen preview and the
        # exported documents can never drift apart.
        cycle_guide_data = build_cycle_guide_view_data(
            vessels, coupling_cycles, config, residue_info_map, today
        )
```

Change the method's final `return` statement (currently):

```python
        return {
            'cycle_guide_pdf': str(cycle_guide_pdf),
            'cycle_guide_docx': str(cycle_guide_docx),
            'peptide_info_pdf': str(peptide_info_pdf),
            'peptide_info_docx': str(peptide_info_docx),
        }
```

to:

```python
        return {
            'cycle_guide_pdf': str(cycle_guide_pdf),
            'cycle_guide_docx': str(cycle_guide_docx),
            'peptide_info_pdf': str(peptide_info_pdf),
            'peptide_info_docx': str(peptide_info_docx),
        }, cycle_guide_data
```

- [ ] **Step 4: Update the route to persist the extended marker**

In `spps_assistant/api/routes/synthesis.py`, add to the imports at the top:

```python
from dataclasses import asdict
```

In `generate_synthesis()`, change:

```python
    use_case = SynthesisGuideUseCase(db=db, config_repo=config_repo)
    try:
        output_paths = use_case.run(
            output_dir=config.output_directory,
            config=config,
            residue_info_map=residue_info_map,
            vessels=vessels,
            yield_results=yield_results,
            solubility_results=solubility_results,
        )
    except Exception as exc:  # noqa: BLE001 - surface any generation failure to the caller
        logger.exception('Synthesis generation failed')
        return err('generate_failed', 'Synthesis generation failed. Check server logs for details.'), 500

    _MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        'name': config.name,
        'output_directory': config.output_directory,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'vessel_count': len(vessels),
    }
```

to:

```python
    use_case = SynthesisGuideUseCase(db=db, config_repo=config_repo)
    try:
        output_paths, cycle_guide_data = use_case.run(
            output_dir=config.output_directory,
            config=config,
            residue_info_map=residue_info_map,
            vessels=vessels,
            yield_results=yield_results,
            solubility_results=solubility_results,
        )
    except Exception as exc:  # noqa: BLE001 - surface any generation failure to the caller
        logger.exception('Synthesis generation failed')
        return err('generate_failed', 'Synthesis generation failed. Check server logs for details.'), 500

    _MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        'name': config.name,
        'output_directory': config.output_directory,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'vessel_count': len(vessels),
        'output_paths': output_paths,
        'current_cycle': 1,
        'cycle_guide': asdict(cycle_guide_data),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_synthesis_routes.py -v`
Expected: all pass (including the updated `test_generate_writes_last_synthesis_marker` and the existing `test_generate_marker_write_failure_returns_200`, which doesn't inspect marker contents so it's unaffected)

Run the full suite: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/application/synthesis_guide.py spps_assistant/api/routes/synthesis.py tests/api/test_synthesis_routes.py
git commit -m "feat(api): persist cycle guide data + output paths in the last_synthesis marker"
```

---

### Task 6: `POST /synthesis/cycle-position` route

**Files:**
- Modify: `spps_assistant/api/routes/synthesis.py`
- Modify: `tests/api/test_synthesis_routes.py`

**Interfaces:**
- Consumes: `_MARKER_PATH` (existing, same file).
- Produces: `POST /synthesis/cycle-position` — body `{"cycle_number": int}`, response `{"ok": true, "data": {"current_cycle": <int>}}`. Task 7's `spps.setCyclePosition()` IPC handler calls this exact route.

- [ ] **Step 1: Write the failing tests**

Append to `tests/api/test_synthesis_routes.py`:

```python
def test_set_cycle_position_updates_marker(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 2})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['current_cycle'] == 2

    last = client.get('/synthesis/last').get_json()
    assert last['data']['current_cycle'] == 2


def test_set_cycle_position_out_of_range_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 99})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_set_cycle_position_zero_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 0})

    assert resp.status_code == 400


def test_set_cycle_position_no_synthesis_returns_400(app):
    client = app.test_client()

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 1})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'no_active_synthesis'


def test_set_cycle_position_non_integer_returns_400(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'
    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': 'two'})

    assert resp.status_code == 400


def test_set_cycle_position_boolean_returns_400(app, tmp_path):
    """bool is a subclass of int in Python — {"cycle_number": true} must not silently pass."""
    client = app.test_client()
    out_dir = tmp_path / 'output'
    client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {'name': 'TestRun', 'output_directory': str(out_dir)},
    })

    resp = client.post('/synthesis/cycle-position', json={'cycle_number': True})

    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_synthesis_routes.py -k set_cycle_position -v`
Expected: FAIL with 404 (route doesn't exist yet)

- [ ] **Step 3: Implement the route**

In `spps_assistant/api/routes/synthesis.py`, add after `generate_synthesis()` and before `last_synthesis()`:

```python
@synthesis_bp.post('/synthesis/cycle-position')
def set_cycle_position():
    """Update the persisted current-cycle pointer for the last synthesis.

    This is a convenience position marker only — not part of the GMP
    audit trail, which lives in the signed, printed PDF/DOCX.
    """
    body = request.get_json(silent=True)
    cycle_number = body.get('cycle_number') if isinstance(body, dict) else None
    if not isinstance(cycle_number, int) or isinstance(cycle_number, bool):
        return err('invalid_body', 'Request body must include integer "cycle_number"'), 400

    if not _MARKER_PATH.exists():
        return err('no_active_synthesis', 'No synthesis has been generated yet.'), 400

    try:
        marker_data = json.loads(_MARKER_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        logger.exception('Failed to read synthesis marker for cycle-position update')
        return err('marker_read_failed', 'Could not read the synthesis marker.'), 500

    cycle_guide = marker_data.get('cycle_guide') or {}
    total_cycles = len(cycle_guide.get('cycles', []))
    if total_cycles == 0 or not (1 <= cycle_number <= total_cycles):
        return err('invalid_body', f'cycle_number must be between 1 and {total_cycles}'), 400

    marker_data['current_cycle'] = cycle_number

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', dir=_MARKER_PATH.parent, delete=False,
            encoding='utf-8', suffix='.tmp',
        ) as tmp_file:
            tmp_path = tmp_file.name
            json.dump(marker_data, tmp_file)
        os.replace(tmp_path, _MARKER_PATH)
        tmp_path = None
    except OSError:
        logger.exception('Failed to write synthesis marker file')
        return err('marker_write_failed', 'Could not save the cycle position.'), 500
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning('Failed to remove temporary synthesis marker file', exc_info=True)

    return ok({'current_cycle': cycle_number})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_synthesis_routes.py -v`
Expected: all pass

Run the full suite: `pytest -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add spps_assistant/api/routes/synthesis.py tests/api/test_synthesis_routes.py
git commit -m "feat(api): add POST /synthesis/cycle-position route"
```

---

### Task 7: Preload/IPC extensions — `setCyclePosition` + extended `LastSynthesisEnvelope`

**Files:**
- Modify: `desktop/src/preload/index.d.ts`
- Modify: `desktop/src/main/api-bridge.ts`
- Modify: `desktop/src/preload/index.ts`

**Interfaces:**
- Consumes: `fetchFromSidecar` (existing, `api-bridge.ts`).
- Produces: `window.spps.setCyclePosition(cycleNumber: number): Promise<CyclePositionEnvelope>`; `LastSynthesisEnvelope.data` gains `output_paths`, `current_cycle`, `cycle_guide` (all optional). Task 9 (`CycleGuide.tsx`) and Task 10 (nav wiring) both depend on these exact type/method names.

This task is pure type/wiring — no new automated test is added here (matching Phase 3's precedent: `api-bridge.ts`'s real-sidecar tests are restricted to read-only routes, and `setCyclePosition` mutates state depending on a prior synthesis existing, per this plan's Global Constraints). Task 6's Python tests already cover the route's behavior; Task 9's component tests cover the renderer calling `window.spps.setCyclePosition`.

- [ ] **Step 1: Add the new types to `preload/index.d.ts`**

In `desktop/src/preload/index.d.ts`, add these new interfaces right before `export interface LastSynthesisEnvelope`:

```typescript
export interface DispatchRow {
  residue_3letter: string
  fmoc_mw: number
  mmol: number
  volume_ml: number
  formula_shown: string
  vessel_numbers: number[]
}

export interface GmpStep {
  label: string
  detail: string
  n_checkboxes: number
  duration: string
}

export interface VesselAssignment {
  vessel_number: number
  vessel_name: string
  residue_3letter: string | null
}

export interface SecondaryCouplingRow {
  vessel_number: number
  vessel_name: string
  residue_3letter: string
}

export interface CyclePageData {
  cycle_number: number
  total_cycles: number
  dispatch_rows: DispatchRow[]
  deprotection_steps: GmpStep[]
  coupling_steps: GmpStep[]
  vessel_assignments: VesselAssignment[]
  secondary_coupling_rows: SecondaryCouplingRow[] | null
}

export interface CycleGuideData {
  synthesis_name: string
  date_str: string
  cycles: CyclePageData[]
}

export interface CyclePositionEnvelope {
  ok: boolean
  data?: { current_cycle: number }
  error?: { code: string; message: string }
}
```

Then change `LastSynthesisEnvelope` from:

```typescript
export interface LastSynthesisEnvelope {
  ok: boolean
  data?: {
    name: string
    output_directory: string
    generated_at: string
    vessel_count: number
  } | null
  error?: { code: string; message: string }
}
```

to:

```typescript
export interface LastSynthesisEnvelope {
  ok: boolean
  data?: {
    name: string
    output_directory: string
    generated_at: string
    vessel_count: number
    output_paths?: Record<string, string>
    current_cycle?: number
    cycle_guide?: CycleGuideData
  } | null
  error?: { code: string; message: string }
}
```

Add to the `SppsApi` interface, right after `getLastSynthesis: () => Promise<LastSynthesisEnvelope>`:

```typescript
  setCyclePosition: (cycleNumber: number) => Promise<CyclePositionEnvelope>
```

- [ ] **Step 2: Register the IPC handler in `api-bridge.ts`**

In `desktop/src/main/api-bridge.ts`, in `registerSynthesisHandlers`, add right after the `spps:getLastSynthesis` handler:

```typescript
  ipcMain.handle('spps:setCyclePosition', (_event, cycleNumber: number) =>
    fetchFromSidecar(getSidecarInfo(), '/synthesis/cycle-position', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_number: cycleNumber })
    })
  )
```

Update the doc comment above `registerSynthesisHandlers` to mention it:

```typescript
/**
 * Registers the IPC handlers for the synthesis wizard and Cycle Guide
 * routes: window.spps.parseSequences(), .getResidues(), .saveResidue(),
 * .generateSynthesis(), .getLastSynthesis(), .setCyclePosition(). Each
 * delegates to fetchFromSidecar to reach the corresponding backend route.
 */
```

- [ ] **Step 3: Expose it in `preload/index.ts`**

In `desktop/src/preload/index.ts`, add to the `spps` object, right after `getLastSynthesis`:

```typescript
  setCyclePosition: (cycleNumber: number) => ipcRenderer.invoke('spps:setCyclePosition', cycleNumber),
```

- [ ] **Step 4: Verify the typecheck passes**

Run: `cd desktop && npm run typecheck`
Expected: no errors

- [ ] **Step 5: Run the existing suite to confirm nothing broke**

Run: `cd desktop && npx vitest run`
Expected: all pass (unchanged count — this task is pure typing/wiring)

- [ ] **Step 6: Commit**

```bash
git add desktop/src/preload/index.d.ts desktop/src/main/api-bridge.ts desktop/src/preload/index.ts
git commit -m "feat(desktop): add setCyclePosition IPC + extend LastSynthesisEnvelope with cycle guide data"
```

---

### Task 8: `spps:openFile` main-process handler

**Files:**
- Modify: `desktop/src/main/dialogs.ts`
- Modify: `desktop/src/main/dialogs.test.ts`
- Modify: `desktop/src/preload/index.d.ts`
- Modify: `desktop/src/preload/index.ts`

**Interfaces:**
- Consumes: `shell.openPath` (Electron built-in).
- Produces: `window.spps.openFile(path: string): Promise<void>` — opens the file in its default OS viewer. Task 9 (`CycleGuide.tsx`) calls this for its Export PDF/DOCX buttons.

- [ ] **Step 1: Write the failing tests**

In `desktop/src/main/dialogs.test.ts`, add `openPath` to the mocked `shell`:

```typescript
const showOpenDialogMock = vi.fn()
const showItemInFolderMock = vi.fn()
const openPathMock = vi.fn()
const ipcMainHandlers: Record<string, (...args: unknown[]) => unknown> = {}

vi.mock('electron', () => ({
  dialog: { showOpenDialog: (...args: unknown[]) => showOpenDialogMock(...args) },
  shell: {
    showItemInFolder: (...args: unknown[]) => showItemInFolderMock(...args),
    openPath: (...args: unknown[]) => openPathMock(...args)
  },
  ipcMain: {
    handle: (channel: string, handler: (...args: unknown[]) => unknown) => {
      ipcMainHandlers[channel] = handler
    }
  }
}))
```

Update the `beforeEach` to reset the new mock:

```typescript
  beforeEach(() => {
    showOpenDialogMock.mockReset()
    showItemInFolderMock.mockReset()
    openPathMock.mockReset()
    for (const key of Object.keys(ipcMainHandlers)) delete ipcMainHandlers[key]
    registerDialogHandlers(ipcMain)
  })
```

Add new test cases at the end of the `describe('registerDialogHandlers', ...)` block, right after the existing `spps:openFolder` tests:

```typescript
  it('spps:openFile calls shell.openPath with the given path', async () => {
    openPathMock.mockResolvedValue('')
    await ipcMainHandlers['spps:openFile'](null, '/tmp/out/guide.pdf')
    expect(openPathMock).toHaveBeenCalledWith('/tmp/out/guide.pdf')
  })

  it('spps:openFile does not call shell.openPath with a non-string argument', async () => {
    await ipcMainHandlers['spps:openFile'](null, 123)
    expect(openPathMock).not.toHaveBeenCalled()
  })

  it('spps:openFile does not call shell.openPath with an empty string', async () => {
    await ipcMainHandlers['spps:openFile'](null, '')
    expect(openPathMock).not.toHaveBeenCalled()
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd desktop && npx vitest run src/main/dialogs.test.ts`
Expected: FAIL — `ipcMainHandlers['spps:openFile']` is `undefined`

- [ ] **Step 3: Implement the handler**

In `desktop/src/main/dialogs.ts`, add after the existing `spps:openFolder` handler, inside `registerDialogHandlers`:

```typescript
  ipcMain.handle('spps:openFile', (_event, filePath: string) => {
    if (typeof filePath !== 'string' || filePath.length === 0) {
      console.warn('spps:openFile received invalid path:', filePath)
      return
    }
    return shell.openPath(filePath)
  })
```

- [ ] **Step 4: Add the preload wiring**

In `desktop/src/preload/index.d.ts`, add to `SppsApi`, right after `openFolder: (path: string) => Promise<void>`:

```typescript
  openFile: (path: string) => Promise<void>
```

In `desktop/src/preload/index.ts`, add to the `spps` object, right after `openFolder`:

```typescript
  openFile: (path: string) => ipcRenderer.invoke('spps:openFile', path),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd desktop && npx vitest run src/main/dialogs.test.ts`
Expected: all pass (9 tests: 6 existing + 3 new)

Run the full suite: `cd desktop && npm run typecheck && npx vitest run`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add desktop/src/main/dialogs.ts desktop/src/main/dialogs.test.ts desktop/src/preload/index.d.ts desktop/src/preload/index.ts
git commit -m "feat(desktop): add spps:openFile handler (shell.openPath) for Cycle Guide export buttons"
```

---

### Task 9: `CycleGuide.tsx` view

**Files:**
- Create: `desktop/src/renderer/src/views/CycleGuide.tsx`
- Test: `desktop/src/renderer/src/views/CycleGuide.test.tsx`

**Interfaces:**
- Consumes: `window.spps.getLastSynthesis()`, `window.spps.setCyclePosition()` (Task 7), `window.spps.openFile()` (Task 8); `CycleGuideData`, `CyclePageData` types (Task 7, `preload/index.d.ts`).
- Produces: `CycleGuide` component, default export, props `{ onNewSynthesis: () => void }`. Task 10 imports and renders this from `App.tsx`.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/CycleGuide.test.tsx`:

```typescript
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CycleGuide from './CycleGuide'
import type { CycleGuideData } from '../../../preload/index.d'

function makeGuide(): CycleGuideData {
  return {
    synthesis_name: 'TestRun',
    date_str: '2026-01-01',
    cycles: [
      {
        cycle_number: 1,
        total_cycles: 2,
        dispatch_rows: [
          {
            residue_3letter: 'Ala',
            fmoc_mw: 311.3,
            mmol: 0.09,
            volume_ml: 0.6,
            formula_shown: 'V = ...',
            vessel_numbers: [1]
          }
        ],
        deprotection_steps: [
          { label: '1. Deprotection', detail: 'Piperidine 20% in DMF', n_checkboxes: 2, duration: '2 × 10 min' }
        ],
        coupling_steps: [
          { label: '1st coupling', detail: 'Ala + HBTU + Oxyma + DIEA', n_checkboxes: 1, duration: '30 min' },
          { label: 'Post-coupling wash', detail: 'DMF, DCM', n_checkboxes: 0, duration: '5 min' }
        ],
        vessel_assignments: [{ vessel_number: 1, vessel_name: 'Pep1', residue_3letter: 'Ala' }],
        secondary_coupling_rows: null
      },
      {
        cycle_number: 2,
        total_cycles: 2,
        dispatch_rows: [],
        deprotection_steps: [],
        coupling_steps: [],
        vessel_assignments: [{ vessel_number: 1, vessel_name: 'Pep1', residue_3letter: null }],
        secondary_coupling_rows: null
      }
    ]
  }
}

function stubSpps(overrides: Record<string, unknown> = {}): void {
  vi.stubGlobal('spps', {
    getLastSynthesis: () =>
      Promise.resolve({
        ok: true,
        data: {
          name: 'TestRun',
          output_directory: '/tmp/out',
          generated_at: '2026-01-01T00:00:00+00:00',
          vessel_count: 1,
          output_paths: { cycle_guide_pdf: '/tmp/out/guide.pdf', cycle_guide_docx: '/tmp/out/guide.docx' },
          current_cycle: 1,
          cycle_guide: makeGuide()
        }
      }),
    setCyclePosition: vi.fn().mockResolvedValue({ ok: true, data: { current_cycle: 1 } }),
    openFile: vi.fn().mockResolvedValue(undefined),
    ...overrides
  })
}

describe('CycleGuide', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the seeded current cycle', async () => {
    stubSpps()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('of 2 total cycles')).toBeInTheDocument()
    expect(screen.getByText('Ala')).toBeInTheDocument()
  })

  it('Prev is disabled on the first cycle, Next is enabled', async () => {
    stubSpps()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /prev/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
  })

  it('clicking Next advances the cycle and saves the position', async () => {
    stubSpps()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => expect(screen.getByText('of 2 total cycles')).toBeInTheDocument())
    expect(window.spps.setCyclePosition).toHaveBeenCalledWith(2)
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('clicking Export PDF opens the real generated file', async () => {
    stubSpps()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export pdf/i }))

    expect(window.spps.openFile).toHaveBeenCalledWith('/tmp/out/guide.pdf')
  })

  it('shows an empty state and a New synthesis button when no synthesis exists', async () => {
    stubSpps({ getLastSynthesis: () => Promise.resolve({ ok: true, data: null }) })
    const onNewSynthesis = vi.fn()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={onNewSynthesis} />)

    await waitFor(() => expect(screen.getByText(/no active synthesis/i)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /new synthesis/i }))
    expect(onNewSynthesis).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd desktop && npx vitest run src/renderer/src/views/CycleGuide.test.tsx`
Expected: FAIL — `Failed to resolve import "./CycleGuide"`

- [ ] **Step 3: Implement the component**

Create `desktop/src/renderer/src/views/CycleGuide.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import type { CycleGuideData, CyclePageData } from '../../../preload/index.d'

type CycleGuideState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'error' }
  | { status: 'loaded'; guide: CycleGuideData; outputPaths: Record<string, string> }

interface CycleGuideProps {
  onNewSynthesis: () => void
}

export default function CycleGuide({ onNewSynthesis }: Readonly<CycleGuideProps>): React.JSX.Element {
  const [state, setState] = useState<CycleGuideState>({ status: 'loading' })
  const [cycleIndex, setCycleIndex] = useState(0)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.cycle_guide) {
          const guide = envelope.data.cycle_guide
          setState({ status: 'loaded', guide, outputPaths: envelope.data.output_paths ?? {} })
          const seeded = (envelope.data.current_cycle ?? 1) - 1
          setCycleIndex(Math.min(Math.max(seeded, 0), guide.cycles.length - 1))
        } else {
          setState({ status: 'none' })
        }
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  function goTo(index: number, guide: CycleGuideData): void {
    const clamped = Math.min(Math.max(index, 0), guide.cycles.length - 1)
    setCycleIndex(clamped)
    window.spps.setCyclePosition(clamped + 1).catch(() => {
      // Non-fatal: this is a convenience position marker, not part of the
      // GMP audit trail. Keep the locally-navigated cycle either way.
    })
  }

  if (state.status === 'loading') {
    return <p className="text-text3 font-sans text-sm p-5">Loading…</p>
  }

  if (state.status === 'error' || state.status === 'none') {
    return (
      <div className="bg-bg p-5">
        <Card className="bg-bg2">
          <CardContent className="flex flex-col items-center justify-center py-10 text-center">
            <p className="text-text2 font-sans text-sm mb-4">
              {state.status === 'error'
                ? "Couldn't load the cycle guide. Is the sidecar running?"
                : 'No active synthesis yet.'}
            </p>
            <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
              + New synthesis
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const cycle: CyclePageData = state.guide.cycles[cycleIndex]
  const pdfPath = state.outputPaths.cycle_guide_pdf
  const docxPath = state.outputPaths.cycle_guide_docx

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-text font-sans text-base font-medium">Coupling cycle guide</h1>
          <p className="text-text3 font-mono text-xs">{state.guide.synthesis_name}</p>
        </div>
        <div className="flex gap-2">
          {pdfPath && (
            <Button onClick={() => window.spps.openFile(pdfPath)} className="bg-bg3">
              ⬇ Export PDF
            </Button>
          )}
          {docxPath && (
            <Button onClick={() => window.spps.openFile(docxPath)} className="bg-bg3">
              ⬇ Export DOCX
            </Button>
          )}
        </div>
      </div>

      <Card className="bg-bg2 mb-4">
        <CardContent className="flex items-center justify-between py-4">
          <div>
            <div className="text-teal font-mono text-2xl font-light">{cycle.cycle_number}</div>
            <div className="text-text3 font-mono text-xs">of {cycle.total_cycles} total cycles</div>
          </div>
          <div className="flex gap-2">
            <Button disabled={cycleIndex === 0} onClick={() => goTo(cycleIndex - 1, state.guide)} className="bg-bg3">
              ◀ Prev
            </Button>
            <Button
              disabled={cycleIndex === state.guide.cycles.length - 1}
              onClick={() => goTo(cycleIndex + 1, state.guide)}
              className="bg-bg3"
            >
              Next ▶
            </Button>
          </div>
          <div className="text-right">
            <div className="text-text3 font-sans text-xs">Date</div>
            <div className="text-text2 font-sans text-sm border-b border-[color:var(--border)] min-w-[120px]">
              ________________
            </div>
          </div>
          <div className="text-right">
            <div className="text-text3 font-sans text-xs">Operator</div>
            <div className="text-text2 font-sans text-sm border-b border-[color:var(--border)] min-w-[120px]">
              ________________
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Amino acid dispatch</h2>
          <Card className="bg-bg2 mb-4">
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text3 font-sans text-xs uppercase">
                    <th className="text-left p-2">Residue</th>
                    <th className="text-left p-2">Volume</th>
                    <th className="text-left p-2">Vessels</th>
                  </tr>
                </thead>
                <tbody>
                  {cycle.dispatch_rows.map((row) => (
                    <tr key={row.residue_3letter} className="border-t border-[color:var(--border)]">
                      <td className="p-2 text-text font-mono">{row.residue_3letter}</td>
                      <td className="p-2 text-teal font-mono">{row.volume_ml.toFixed(2)} mL</td>
                      <td className="p-2">
                        {row.vessel_numbers.map((vn) => (
                          <span key={vn} className="text-text2 font-mono text-xs mr-1">
                            V{vn}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Vessel assignment</h2>
          <Card className="bg-bg2">
            <CardContent className="py-3">
              {cycle.vessel_assignments.map((va) => (
                <div key={va.vessel_number} className="text-text2 font-mono text-xs mb-1">
                  V{va.vessel_number} <span className="text-text3">[{va.vessel_name}]</span> →{' '}
                  {va.residue_3letter ? (
                    <span className="text-teal">{va.residue_3letter}</span>
                  ) : (
                    <span className="text-text3">OUT</span>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div>
          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Deprotection record</h2>
          <Card className="bg-bg2 mb-4">
            <CardContent className="p-0">
              {cycle.deprotection_steps.map((step) => (
                <div
                  key={step.label}
                  className="flex items-center gap-3 p-2 border-b border-[color:var(--border)] last:border-b-0"
                >
                  <div className="flex gap-1">
                    {Array.from({ length: step.n_checkboxes }).map((_, i) => (
                      <div key={i} className="w-3 h-3 border border-[color:var(--border2)]" />
                    ))}
                  </div>
                  <div className="flex-1 text-text font-sans text-xs">{step.label}</div>
                  <div className="text-text3 font-sans text-xs">{step.duration}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Coupling record</h2>
          <Card className="bg-bg2">
            <CardContent className="p-0">
              {cycle.coupling_steps.map((step) => (
                <div
                  key={step.label}
                  className="flex items-center gap-3 p-2 border-b border-[color:var(--border)] last:border-b-0"
                >
                  {step.n_checkboxes > 0 && <div className="w-3 h-3 border border-[color:var(--border2)]" />}
                  <div className="flex-1">
                    <div className="text-text font-sans text-xs">{step.label}</div>
                    <div className="text-text3 font-sans text-xs">{step.detail}</div>
                  </div>
                  <div className="text-text3 font-sans text-xs">{step.duration}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd desktop && npx vitest run src/renderer/src/views/CycleGuide.test.tsx`
Expected: 5 passed

- [ ] **Step 5: Verify typecheck and full suite**

Run: `cd desktop && npm run typecheck && npx vitest run`
Expected: no errors, all tests pass

- [ ] **Step 6: Commit**

```bash
git add desktop/src/renderer/src/views/CycleGuide.tsx desktop/src/renderer/src/views/CycleGuide.test.tsx
git commit -m "feat(desktop): add CycleGuide view — read-only cycle navigation with export buttons"
```

---

### Task 10: Navigation wiring — App, NewSynthesis, Step5Confirm, Dashboard

**Files:**
- Modify: `desktop/src/renderer/src/App.tsx`
- Modify: `desktop/src/renderer/src/App.test.tsx`
- Modify: `desktop/src/renderer/src/views/NewSynthesis.tsx`
- Modify: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`
- Modify: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `CycleGuide` (Task 9); `window.spps.getLastSynthesis()` (Task 7).
- Produces: the "Cycle guide" tab becomes clickable once a synthesis exists; Dashboard's last-synthesis card and the post-generate success screen both gain a "View cycle guide" link that switches to it.

- [ ] **Step 1: Write the failing test for App.tsx's tab-enabling**

In `desktop/src/renderer/src/App.test.tsx`, add a new test at the end of the `describe('App', ...)` block:

```typescript
  it('enables the Cycle guide tab once a synthesis exists', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} }),
      getLastSynthesis: () =>
        Promise.resolve({
          ok: true,
          data: {
            name: 'TestRun',
            output_directory: '/tmp/out',
            generated_at: '2026-01-01T00:00:00+00:00',
            vessel_count: 1,
            cycle_guide: { synthesis_name: 'TestRun', date_str: '2026-01-01', cycles: [] },
            current_cycle: 1
          }
        }),
      pickFastaFile: vi.fn().mockResolvedValue(null)
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    await waitFor(() => {
      const tab = nav.getByText('Cycle guide')
      expect(tab.className).not.toContain('cursor-not-allowed')
    })
  })
```

- [ ] **Step 2: Run tests to verify the new test fails**

Run: `cd desktop && npx vitest run src/renderer/src/App.test.tsx`
Expected: FAIL — the new test's assertion fails (`Cycle guide` still has `cursor-not-allowed`, since `App.tsx` doesn't check `getLastSynthesis` yet)

- [ ] **Step 3: Update `App.tsx`**

Replace the full contents of `desktop/src/renderer/src/App.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import Dashboard from './views/Dashboard'
import NewSynthesis from './views/NewSynthesis'
import CycleGuide from './views/CycleGuide'

const TABS = ['Dashboard', 'New synthesis', 'Cycle guide', 'Materials', 'Peptide info'] as const
type Tab = (typeof TABS)[number]

function getTabClassName(active: boolean, enabled: boolean): string {
  if (active) {
    return 'text-teal border-b-2 border-teal px-4 py-3 text-xs font-medium cursor-pointer'
  }
  if (enabled) {
    return 'text-text2 px-4 py-3 text-xs font-medium cursor-pointer'
  }
  return 'text-text3 px-4 py-3 text-xs font-medium cursor-not-allowed'
}

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>('Dashboard')
  const [cycleGuideEnabled, setCycleGuideEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (!cancelled && envelope.ok && envelope.data?.cycle_guide) {
          setCycleGuideEnabled(true)
        }
      })
      .catch(() => {
        // Leave the tab disabled — matches the "no active synthesis" state.
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab) => {
          const enabled =
            tab === 'Dashboard' ||
            tab === 'New synthesis' ||
            (tab === 'Cycle guide' && cycleGuideEnabled)
          const active = tab === activeTab
          return (
            <button
              key={tab}
              type="button"
              disabled={!enabled}
              onClick={() => setActiveTab(tab)}
              className={getTabClassName(active, enabled)}
            >
              {tab}
            </button>
          )
        })}
      </nav>
      {activeTab === 'Dashboard' && (
        <Dashboard
          onNewSynthesis={() => setActiveTab('New synthesis')}
          onViewCycleGuide={() => setActiveTab('Cycle guide')}
        />
      )}
      {activeTab === 'New synthesis' && (
        <NewSynthesis
          onDone={() => setActiveTab('Dashboard')}
          onViewCycleGuide={() => setActiveTab('Cycle guide')}
        />
      )}
      {activeTab === 'Cycle guide' && (
        <CycleGuide onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
    </div>
  )
}

export default App
```

- [ ] **Step 4: Thread `onViewCycleGuide` through `NewSynthesis.tsx`**

In `desktop/src/renderer/src/views/NewSynthesis.tsx`, change the props interface and function signature:

```typescript
interface NewSynthesisProps {
  onDone: () => void
  onViewCycleGuide: () => void
}

export default function NewSynthesis({
  onDone,
  onViewCycleGuide
}: Readonly<NewSynthesisProps>): React.JSX.Element {
```

Change the Step 5 render line:

```typescript
      {state.step === 5 && (
        <Step5Confirm state={state} dispatch={dispatch} onDone={onDone} onViewCycleGuide={onViewCycleGuide} />
      )}
```

- [ ] **Step 5: Add the "View cycle guide" link to `Step5Confirm.tsx`**

In `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`, change the props interface and function signature:

```typescript
interface Step5Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
  onDone: () => void
  onViewCycleGuide: () => void
}

export default function Step5Confirm({
  state,
  dispatch,
  onDone,
  onViewCycleGuide
}: Readonly<Step5Props>): React.JSX.Element {
```

In the success-screen return block, change the button row from:

```tsx
          <div className="flex justify-center gap-3">
            {firstPath && (
              <Button onClick={() => window.spps.openFolder(firstPath)} className="bg-bg3">
                Open folder
              </Button>
            )}
            <Button onClick={onDone} className="bg-teal text-bg hover:bg-teal/90">
              Done
            </Button>
          </div>
```

to:

```tsx
          <div className="flex justify-center gap-3">
            {firstPath && (
              <Button onClick={() => window.spps.openFolder(firstPath)} className="bg-bg3">
                Open folder
              </Button>
            )}
            <Button onClick={onViewCycleGuide} className="bg-bg3">
              View cycle guide
            </Button>
            <Button onClick={onDone} className="bg-teal text-bg hover:bg-teal/90">
              Done
            </Button>
          </div>
```

- [ ] **Step 6: Update `Step5Confirm.test.tsx` and `NewSynthesis.test.tsx` for the new required prop**

In `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`, the shared `renderStep5` helper (used by every test in the file) currently is:

```typescript
function renderStep5(
  state: WizardState,
  onDone = vi.fn()
): Omit<RenderResult, 'rerender'> & {
  dispatch: ReturnType<typeof vi.fn>
  onDone: ReturnType<typeof vi.fn>
  rerender: (ui: React.ReactElement) => void
  getState: () => WizardState
} {
  let currentState = state
  const dispatch = vi.fn()
  const { rerender, ...utils } = render(
    <Step5Confirm state={currentState} dispatch={dispatch} onDone={onDone} />
  )

  dispatch.mockImplementation((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
    rerender(<Step5Confirm state={currentState} dispatch={dispatch} onDone={onDone} />)
  })

  return { ...utils, dispatch, onDone, rerender, getState: () => currentState }
}
```

Replace it with a version that also creates and passes `onViewCycleGuide`, and returns it so tests can assert on it:

```typescript
function renderStep5(
  state: WizardState,
  onDone = vi.fn(),
  onViewCycleGuide = vi.fn()
): Omit<RenderResult, 'rerender'> & {
  dispatch: ReturnType<typeof vi.fn>
  onDone: ReturnType<typeof vi.fn>
  onViewCycleGuide: ReturnType<typeof vi.fn>
  rerender: (ui: React.ReactElement) => void
  getState: () => WizardState
} {
  let currentState = state
  const dispatch = vi.fn()
  const { rerender, ...utils } = render(
    <Step5Confirm
      state={currentState}
      dispatch={dispatch}
      onDone={onDone}
      onViewCycleGuide={onViewCycleGuide}
    />
  )

  dispatch.mockImplementation((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
    rerender(
      <Step5Confirm
        state={currentState}
        dispatch={dispatch}
        onDone={onDone}
        onViewCycleGuide={onViewCycleGuide}
      />
    )
  })

  return { ...utils, dispatch, onDone, onViewCycleGuide, rerender, getState: () => currentState }
}
```

This is the only edit needed for the file's 6 existing tests (they all go through this helper). Then add one new test at the end of the `describe('Step5Confirm', ...)` block:

```typescript
  it('clicking "View cycle guide" calls onViewCycleGuide', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onViewCycleGuide } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view cycle guide/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view cycle guide/i }))

    expect(onViewCycleGuide).toHaveBeenCalledTimes(1)
  })
```

In `desktop/src/renderer/src/views/NewSynthesis.test.tsx`, the file has a single `render(<NewSynthesis onDone={onDone} />)` call (line 55). Change it to:

```typescript
    render(<NewSynthesis onDone={onDone} onViewCycleGuide={vi.fn()} />)
```

- [ ] **Step 7: Add "View cycle guide" to `Dashboard.tsx`**

In `desktop/src/renderer/src/views/Dashboard.tsx`, change the props interface and function signature:

```typescript
interface DashboardProps {
  onNewSynthesis: () => void
  onViewCycleGuide: () => void
}

export default function Dashboard({
  onNewSynthesis,
  onViewCycleGuide
}: Readonly<DashboardProps>): React.JSX.Element {
```

In the `'active'` branch of the last-synthesis card, change:

```tsx
          {lastSynthesis.status === 'active' && (
            <>
              <p className="text-text font-sans text-sm mb-1">{lastSynthesis.name}</p>
              <p className="text-text3 font-mono text-xs">
                {lastSynthesis.vesselCount} vessel(s) — generated {lastSynthesis.generatedAt}
              </p>
            </>
          )}
```

to:

```tsx
          {lastSynthesis.status === 'active' && (
            <>
              <p className="text-text font-sans text-sm mb-1">{lastSynthesis.name}</p>
              <p className="text-text3 font-mono text-xs mb-4">
                {lastSynthesis.vesselCount} vessel(s) — generated {lastSynthesis.generatedAt}
              </p>
              <Button onClick={onViewCycleGuide} className="bg-teal text-bg hover:bg-teal/90">
                View cycle guide
              </Button>
            </>
          )}
```

- [ ] **Step 8: Update `Dashboard.test.tsx` for the new required prop**

In `desktop/src/renderer/src/views/Dashboard.test.tsx`, every one of the file's 5 existing `render(<Dashboard onNewSynthesis={() => {}} />)` calls (lines 39, 57, 70, 99, 115) must gain the new required prop. Change each to:

```typescript
    render(<Dashboard onNewSynthesis={() => {}} onViewCycleGuide={() => {}} />)
```

Also add `userEvent` to the top-level imports (not currently imported in this file):

```typescript
import userEvent from '@testing-library/user-event'
```

Then add one new test, in the same `describe('Dashboard', ...)` block, right after the existing `'shows the last generated synthesis instead of the empty state when one exists'` test — it reuses that same test's `getLastSynthesis` stub shape:

```typescript
  it('clicking "View cycle guide" on an active synthesis calls onViewCycleGuide', async () => {
    const onViewCycleGuide = vi.fn()
    vi.stubGlobal(
      'spps',
      baseStub({
        getConfig: () => Promise.resolve({ ok: true, data: {} }),
        getLastSynthesis: () =>
          Promise.resolve({
            ok: true,
            data: {
              name: 'BatchA',
              output_directory: '/tmp/out',
              generated_at: '2026-07-13T00:00:00',
              vessel_count: 2
            }
          })
      })
    )
    const user = userEvent.setup()

    render(<Dashboard onNewSynthesis={() => {}} onViewCycleGuide={onViewCycleGuide} />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view cycle guide/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view cycle guide/i }))

    expect(onViewCycleGuide).toHaveBeenCalledTimes(1)
  })
```

- [ ] **Step 9: Run all tests to verify they pass**

Run: `cd desktop && npx vitest run`
Expected: all pass, including the new App.tsx, Step5Confirm.tsx, and Dashboard.tsx tests

Run: `cd desktop && npm run typecheck`
Expected: no errors

- [ ] **Step 10: Commit**

```bash
git add desktop/src/renderer/src/App.tsx desktop/src/renderer/src/App.test.tsx desktop/src/renderer/src/views/NewSynthesis.tsx desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx desktop/src/renderer/src/views/NewSynthesis.test.tsx desktop/src/renderer/src/views/Dashboard.tsx desktop/src/renderer/src/views/Dashboard.test.tsx
git commit -m "feat(desktop): wire Cycle guide navigation from tab bar, Dashboard, and post-generate screen"
```

---

## After all tasks: whole-branch review and manual smoke test

Once all 10 tasks are complete:

1. Run the full backend suite (`pytest -v`) and full frontend suite (`cd desktop && npm run typecheck && npx vitest run`) one final time from a clean checkout of the branch.
2. Dispatch a final whole-branch code review on the most capable available model, covering the full diff against `main` — pay particular attention to: (a) whether `pdf_generator.py`/`docx_generator.py`'s refactored output is genuinely byte-for-byte equivalent to pre-refactor behavior (Tasks 3–4), (b) whether the marker's atomic-write/cleanup pattern was correctly replicated in the new `POST /synthesis/cycle-position` route (Task 6), (c) whether `CycleGuide.tsx`'s state machine correctly handles the loading/error/none/loaded cases without gaps.
3. Manually smoke-test the real Electron app end to end (extend Phase 3's ad-hoc Playwright `_electron` driver): generate a synthesis, confirm the app lands on/can navigate to Cycle Guide, click Prev/Next through a few cycles, click Export PDF and Export DOCX and confirm the real files open, navigate to Dashboard and confirm "View cycle guide" appears and the position persisted.
4. Follow `superpowers:finishing-a-development-branch` to open the PR and iterate through CI/CodeRabbit to a clean merge, per this project's established pattern from Phases 1–3.
