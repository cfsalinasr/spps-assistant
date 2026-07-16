# GUI Migration Phase 5: Materials Explosion View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the read-only Materials Explosion view: a summary of the reagent quantities needed for the last-generated synthesis (residue types, total mass, total volume, a per-residue requirements table, and a calculation-basis card), with export buttons that open the real generated XLSX/PDF files — the fourth of the five views in the original mockup.

**Architecture:** The v1.0 CLI's materials-explosion domain/application logic (`spps_assistant/application/materials.py`: `build_materials_rows`, `MaterialsRow`) is 100% reused, unchanged, exactly as the master migration plan promises. A new pure function, `build_materials_view_data()`, wraps `build_materials_rows()` with the summary statistics the view needs (total residue types, total mass, total volume, a stringified config summary) and returns a single `MaterialsViewData` object. `SynthesisGuideUseCase.run()` (already the single place that generates the Cycle Guide PDF/DOCX at `/synthesis/generate` time) is extended to also generate the Materials XLSX/PDF at the same time, using this same object — so the on-screen preview and the two exported files can never drift apart, mirroring exactly how Phase 4 solved this problem for the Cycle Guide. The result is persisted into the existing `last_synthesis.json` marker (`materials` field, alongside the existing `cycle_guide` field) and exposed via the existing `/synthesis/last` route — no new HTTP route is needed, `/materials/build` becomes an unnecessary indirection now that materials data is a byproduct of the single `/synthesis/generate` call, computed once from the same real domain objects.

**Design deviation from the static mockup, and why:** the mockup's third stat card ("DMF volume needed — Couplings + washes") has no corresponding real domain calculation anywhere in the v1.0 codebase (verified: no `DMF` volume math exists outside GMP step *labels* in `synthesis_guide.py`). Fabricating one would violate this project's "quality over scope" standard (real computed data only, never invented numbers in a GMP-adjacent scientific tool). The third stat card instead shows **"Total reagent volume"** — the sum of `MaterialsRow.volume_ml` across all rows, which *is* a real, already-computed domain value (the stock-solution volume to prepare per reagent).

**Tech Stack:** Flask, pytest (backend — unchanged from Phases 1–4). Electron, React, TypeScript, Vitest, React Testing Library (frontend — unchanged from Phases 2–4).

## Global Constraints

- Parent plan: `/Users/cristiansalinas/Desktop/spps/SPPS_GUI_MIGRATION_PLAN.md` §7, Phase 5 bullet.
- Python 3.11 (`python3.11`), run tests with `pytest` directly (on PATH at `/opt/homebrew/bin/pytest`).
- Node `v25.9.0` / npm `11.12.1`, run frontend tests with `npm test -- --run` from `desktop/`.
- The API layer contains **no business logic** — only request/response marshalling and calls into `application`/`domain`/`infrastructure`. All materials-explosion math lives in `application/materials.py`.
- Response envelope convention (unchanged): `{"ok": true, "data": ...}` / `{"ok": false, "error": {"code": "...", "message": "..."}}`.
- The renderer process must **never** receive the sidecar's port or auth token. All sidecar HTTP calls happen in the main process; the renderer only calls `window.spps.*` methods.
- `MaterialsUseCase` (the v1.0 CLI's weekly-materials command class, `spps_assistant/application/materials.py`) must **not** be modified — the CLI's `spps-assistant materials` command behavior stays 100% unchanged, per the master plan's "domain/application/infrastructure/cli layers stay 100% unchanged" decision. `build_materials_view_data()` is a **new**, separate function that reuses `build_materials_rows()` (already shared, already unchanged) but is only ever called from the GUI's `/synthesis/generate` flow.
- Do not mutate the real, persistent `~/.spps_assistant/spps_database.db` or `~/.spps_assistant/last_synthesis.json` from any automated test. Python-side API tests use the `tmp_path`-isolated `app_with_redirected_marker` fixture from `tests/api/conftest.py`.
- `build_materials_view_data()` is the **single source of truth** for the materials summary. `generate_materials_xlsx`/`generate_materials_pdf` render from its `.rows`/`.config_summary`, not a second independent computation.
- Python dataclass field names and TypeScript interface field names must match **field-for-field** across the whole JSON boundary (`MaterialsRow`, `MaterialsViewData`) — this was a recurring whole-branch-review check in Phase 4 and must hold here too.
- TDD: for every task, write the failing test first, confirm it fails for the expected reason, then write the minimal code to pass it.
- Commit after each task with a focused message; do not squash multiple tasks into one commit.
- If a step's exact assertion/selector doesn't match what the actual rendered output looks like once real code is running, investigate and adapt precisely — don't force a mismatched test to pass by weakening it.

---

### Task 1: `MaterialsViewData` domain model + `build_materials_view_data()`

**Files:**
- Modify: `spps_assistant/domain/models.py` (add `MaterialsViewData` dataclass)
- Modify: `spps_assistant/application/materials.py` (add `build_materials_view_data()`)
- Test: `tests/application/test_materials_view_data.py` (new file)

**Interfaces:**
- Consumes: `MaterialsRow`, `SynthesisConfig`, `Vessel` (existing, `domain/models.py`); `build_materials_rows(vessels, residue_info_map, config) -> List[MaterialsRow]` (existing, unchanged, `application/materials.py`).
- Produces: `MaterialsViewData` dataclass, importable from `spps_assistant.domain.models`. `build_materials_view_data(vessels: List[Vessel], residue_info_map: Dict, config: SynthesisConfig) -> MaterialsViewData`, importable from `spps_assistant.application.materials`. Task 2's `SynthesisGuideUseCase.run()` calls this directly.

- [ ] **Step 1: Write the failing test**

Create `tests/application/test_materials_view_data.py`:

```python
"""Tests for build_materials_view_data (application/materials.py)."""

import pytest

from spps_assistant.domain.models import (
    MaterialsViewData, MaterialsRow, ResidueInfo, SynthesisConfig, Vessel,
)
from spps_assistant.domain.sequence import tokenize
from spps_assistant.application.materials import build_materials_view_data


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
        name='TestRun', vessel_label='Vessel', vessel_method='Teabag',
        volume_mode='stoichiometry', activator='HBTU', use_oxyma=True,
        base='DIEA', deprotection_reagent='Piperidine 20%',
        aa_equivalents=3.0, activator_equivalents=3.0, base_equivalents=6.0,
        include_bb_test=True, include_kaiser_test=False,
        starting_vessel_number=1, output_directory='out',
        resin_mass_strategy='fixed', fixed_resin_mass_g=0.1, target_yield_mg=None,
    )
    defaults.update(kwargs)
    return SynthesisConfig(**defaults)


class TestBuildMaterialsViewData:
    def test_returns_materials_view_data(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        result = build_materials_view_data(
            [v], {'A': _info('A', 'A'), 'G': _info('G', 'G')}, config
        )
        assert isinstance(result, MaterialsViewData)
        assert result.synthesis_name == 'TestRun'

    def test_rows_match_build_materials_rows(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        assert len(result.rows) == 2
        assert all(isinstance(r, MaterialsRow) for r in result.rows)

    def test_total_residue_types_matches_row_count(self):
        v = _vessel(1, 'P1', 'AGW')
        config = _config()
        residue_info_map = {
            'A': _info('A', 'A'), 'G': _info('G', 'G'), 'W': _info('W', 'W'),
        }
        result = build_materials_view_data([v], residue_info_map, config)
        assert result.total_residue_types == len(result.rows) == 3

    def test_total_mass_mg_is_sum_of_row_masses(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        expected = round(sum(r.mass_mg for r in result.rows), 2)
        assert result.total_mass_mg == expected

    def test_total_volume_ml_is_sum_of_row_volumes(self):
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        residue_info_map = {'A': _info('A', 'A'), 'G': _info('G', 'G')}
        result = build_materials_view_data([v], residue_info_map, config)
        expected = round(sum(r.volume_ml for r in result.rows), 3)
        assert result.total_volume_ml == expected

    def test_config_summary_has_string_values(self):
        v = _vessel(1, 'P1', 'A')
        config = _config(activator='DIC', aa_equivalents=5.0)
        result = build_materials_view_data([v], {'A': _info('A', 'A')}, config)
        assert result.config_summary['Activator'] == 'DIC'
        assert result.config_summary['AA Equivalents'] == '5.0'
        assert all(isinstance(v, str) for v in result.config_summary.values())

    def test_empty_vessels_returns_empty_view(self):
        config = _config()
        result = build_materials_view_data([], {}, config)
        assert result.rows == []
        assert result.total_residue_types == 0
        assert result.total_mass_mg == 0
        assert result.total_volume_ml == 0

    def test_unresolved_residue_is_skipped_not_crashed(self):
        """A token missing from residue_info_map is silently skipped by
        build_materials_rows (existing behavior) — the view data must not
        crash, and total_residue_types must reflect only resolved rows."""
        v = _vessel(1, 'P1', 'AG')
        config = _config()
        result = build_materials_view_data([v], {'A': _info('A', 'A')}, config)
        assert result.total_residue_types == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/application/test_materials_view_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'MaterialsViewData' from 'spps_assistant.domain.models'`

- [ ] **Step 3: Add `MaterialsViewData` to the domain layer**

In `spps_assistant/domain/models.py`, add right after the existing `MaterialsRow` dataclass (after line 101):

```python
@dataclass
class MaterialsViewData:
    synthesis_name: str
    rows: List[MaterialsRow]
    total_residue_types: int
    total_mass_mg: float
    total_volume_ml: float
    config_summary: Dict[str, str]
```

Confirm `Dict` is already imported in this file's `typing` import (it is, alongside `List`/`Optional` — used by `CyclePageData` and others already in this file).

- [ ] **Step 4: Add `build_materials_view_data()` to the application layer**

In `spps_assistant/application/materials.py`, add the import and function at the end of the file (after the existing `build_materials_rows` function, before the `MaterialsUseCase` class):

```python
from spps_assistant.domain.models import MaterialsRow, MaterialsViewData, SynthesisConfig, Vessel
```

(Replace the existing `from spps_assistant.domain.models import MaterialsRow, SynthesisConfig, Vessel` import line with the line above — same line, just adding `MaterialsViewData`.)

```python
def build_materials_view_data(
    vessels: List[Vessel],
    residue_info_map: Dict,
    config: SynthesisConfig,
) -> MaterialsViewData:
    """Build the full materials-explosion view data for the GUI's Materials
    view: the per-residue rows plus summary statistics, all derived from
    real domain objects so the on-screen preview and the exported XLSX/PDF
    (which render from the same .rows/.config_summary) can never drift.

    Args:
        vessels: List of Vessel objects
        residue_info_map: Token -> ResidueInfo map
        config: SynthesisConfig with equivalents settings

    Returns:
        MaterialsViewData with rows and summary stats
    """
    rows = build_materials_rows(vessels, residue_info_map, config)

    config_summary = {
        'Activator': str(config.activator),
        'AA Equivalents': str(config.aa_equivalents),
        'Volume Mode': str(config.volume_mode),
        'Base': str(config.base),
    }

    return MaterialsViewData(
        synthesis_name=config.name,
        rows=rows,
        total_residue_types=len(rows),
        total_mass_mg=round(sum(r.mass_mg for r in rows), 2),
        total_volume_ml=round(sum(r.volume_ml for r in rows), 3),
        config_summary=config_summary,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/application/test_materials_view_data.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass (390 + 8 new = 398)

- [ ] **Step 7: Commit**

```bash
git add spps_assistant/domain/models.py spps_assistant/application/materials.py tests/application/test_materials_view_data.py
git commit -m "feat(application): add build_materials_view_data for the GUI Materials view"
```

---

### Task 2: Generate Materials XLSX/PDF at `/synthesis/generate` time

**Files:**
- Modify: `spps_assistant/application/synthesis_guide.py` (`SynthesisGuideUseCase.run()`)
- Modify: `spps_assistant/api/routes/synthesis.py` (unpack the new 3-tuple)
- Modify: `spps_assistant/cli/generate_cmd.py` (unpack the new 3-tuple)
- Test: `tests/api/test_synthesis_routes.py`

**Interfaces:**
- Consumes: `build_materials_view_data(vessels, residue_info_map, config) -> MaterialsViewData` (Task 1); `generate_materials_xlsx(path, synthesis_name, materials_rows) -> None` and `generate_materials_pdf(path, synthesis_name, materials_rows, config_summary) -> None` (existing, unchanged, `infrastructure/xlsx_generator.py` / `infrastructure/pdf_generator.py`).
- Produces: `SynthesisGuideUseCase.run(...) -> Tuple[Dict[str, str], CycleGuideViewData, MaterialsViewData]` — output_paths now also contains `materials_xlsx`/`materials_pdf` keys. Task 3's marker persistence consumes the third tuple element.

Note: `SynthesisGuideUseCase.run()` has no dedicated unit test file — it's only exercised indirectly through `POST /synthesis/generate` in `tests/api/test_synthesis_routes.py` (confirmed: `tests/application/test_synthesis_guide_use_case.py` only tests `build_coupling_cycles`/`determine_resin_mass`/`build_config_from_defaults`/`calc_yields_and_solubility`/`apply_target_resin_mass`, not `run()` itself). This task's test therefore extends the existing `test_generate_writes_real_output_files` in `tests/api/test_synthesis_routes.py`.

- [ ] **Step 1: Write the failing test**

In `tests/api/test_synthesis_routes.py`, find the existing `test_generate_writes_real_output_files` test:

```python
def test_generate_writes_real_output_files(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {
            'name': 'TestRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'fixed',
            'fixed_resin_mass_g': 0.1,
        },
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert out_dir.exists()
    assert len(list(out_dir.glob('*.pdf'))) >= 1
```

Add these two assertions at the end of it (materials XLSX/PDF must exist on disk alongside the cycle-guide/peptide-info PDFs already asserted):

```python
    assert len(list(out_dir.glob('*.xlsx'))) >= 1
    assert 'materials_xlsx' in body['data']
    assert 'materials_pdf' in body['data']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_synthesis_routes.py::test_generate_writes_real_output_files -v`
Expected: FAIL with `AssertionError` (no `.xlsx` file exists yet, `output_paths` has no `materials_xlsx` key).

- [ ] **Step 3: Extend `SynthesisGuideUseCase.run()`**

In `spps_assistant/application/synthesis_guide.py`, update the import block near the top (line 8-11) to add `MaterialsViewData`:

```python
from spps_assistant.domain.models import (
    CouplingCycle, CycleGuideViewData, CyclePageData, DispatchRow, GmpStep,
    MaterialsViewData, SecondaryCouplingRow, SynthesisConfig, Vessel, VesselAssignment, YieldResult
)
```

Update the `run()` method's return type annotation (currently at the line matching `) -> Tuple[Dict[str, str], CycleGuideViewData]:`) to:

```python
    ) -> Tuple[Dict[str, str], CycleGuideViewData, MaterialsViewData]:
```

Update the docstring's `Returns:` section (the block starting `Returns:\n            Tuple of (output_paths, cycle_guide_data)...`) to:

```python
        Returns:
            Tuple of (output_paths, cycle_guide_data, materials_data).
            output_paths maps output file types to their paths.
            cycle_guide_data is the structured per-cycle GMP record data for
            the GUI's Cycle Guide view. materials_data is the structured
            materials-explosion data for the GUI's Materials view. Both are
            the same data the PDF/DOCX/XLSX generators render from
            internally, so the GUI previews and the exported documents can
            never drift apart.
        """
```

Add the import for `build_materials_view_data` alongside the existing local imports at the top of the method body (the block that currently reads):

```python
        from spps_assistant.infrastructure.pdf_generator import (
            generate_cycle_guide_pdf, generate_peptide_info_pdf
        )
        from spps_assistant.infrastructure.docx_generator import (
            generate_cycle_guide_docx, generate_peptide_info_docx
        )
```

replace with:

```python
        from spps_assistant.application.materials import build_materials_view_data
        from spps_assistant.infrastructure.pdf_generator import (
            generate_cycle_guide_pdf, generate_peptide_info_pdf, generate_materials_pdf
        )
        from spps_assistant.infrastructure.docx_generator import (
            generate_cycle_guide_docx, generate_peptide_info_docx
        )
        from spps_assistant.infrastructure.xlsx_generator import generate_materials_xlsx
```

Right after the existing cycle-guide file-path block (the lines defining `cycle_guide_pdf`, `cycle_guide_docx`, `peptide_info_pdf`, `peptide_info_docx`) and before the `generate_cycle_guide_pdf(...)` call, add the materials file paths:

```python
        materials_xlsx = out_path / f"{safe_name}_materials.xlsx"
        materials_pdf = out_path / f"{safe_name}_materials.pdf"
```

After the two `generate_peptide_info_pdf(...)` / `generate_peptide_info_docx(...)` calls (i.e. right after step "6. Peptide info documents", before "7. Log to DB"), add:

```python
        # 6.5 Materials explosion (XLSX + PDF), computed once and shared
        # with this method's return value so the GUI preview and the
        # exported files can never drift apart.
        materials_data = build_materials_view_data(vessels, residue_info_map, config)

        generate_materials_xlsx(
            path=materials_xlsx,
            synthesis_name=config.name,
            materials_rows=materials_data.rows,
        )

        generate_materials_pdf(
            path=materials_pdf,
            synthesis_name=config.name,
            materials_rows=materials_data.rows,
            config_summary=materials_data.config_summary,
        )
```

Finally, update the method's final `return` statement:

```python
        return {
            'cycle_guide_pdf': str(cycle_guide_pdf),
            'cycle_guide_docx': str(cycle_guide_docx),
            'peptide_info_pdf': str(peptide_info_pdf),
            'peptide_info_docx': str(peptide_info_docx),
            'materials_xlsx': str(materials_xlsx),
            'materials_pdf': str(materials_pdf),
        }, cycle_guide_data, materials_data
```

- [ ] **Step 4: Update the two real callers**

In `spps_assistant/api/routes/synthesis.py`, find (in `generate_synthesis()`):

```python
        output_paths, cycle_guide_data = use_case.run(
```

Change to:

```python
        output_paths, cycle_guide_data, materials_data = use_case.run(
```

(Leave the rest of that call's arguments unchanged — same call, just a 3-value unpack. `materials_data` isn't used yet in this file; Task 3 uses it.)

In `spps_assistant/cli/generate_cmd.py`, find (around line 196):

```python
        output_paths, _cycle_guide_data = use_case.run(
```

Change to:

```python
        output_paths, _cycle_guide_data, _materials_data = use_case.run(
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_synthesis_routes.py tests/cli/ -v`
Expected: PASS.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add spps_assistant/application/synthesis_guide.py spps_assistant/api/routes/synthesis.py spps_assistant/cli/generate_cmd.py tests/api/test_synthesis_routes.py
git commit -m "feat: generate materials XLSX/PDF at synthesis-generate time"
```

---

### Task 3: Persist materials data in the `last_synthesis.json` marker

**Files:**
- Modify: `spps_assistant/api/routes/synthesis.py` (`generate_synthesis()`)
- Test: `tests/api/test_synthesis_routes.py`

**Interfaces:**
- Consumes: `materials_data: MaterialsViewData` (Task 2's third return value, already unpacked in this file).
- Produces: the JSON marker's `data.materials` field (an object matching `MaterialsViewData`'s field names exactly — `synthesis_name`, `rows`, `total_residue_types`, `total_mass_mg`, `total_volume_ml`, `config_summary`), returned by `GET /synthesis/last`. Task 4's TypeScript type mirrors this shape field-for-field.

- [ ] **Step 1: Write the failing test**

In `tests/api/test_synthesis_routes.py`, find the existing test that asserts on `body['data']['cycle_guide']` after a `POST /synthesis/generate` call (search for `cycle_guide` — likely near the top of the file, testing the generate response). Add a new test right after it:

```python
def test_generate_persists_materials_data_in_marker(app, tmp_path):
    """POST /synthesis/generate must persist a real materials view (rows +
    summary stats) in the marker, retrievable via GET /synthesis/last."""
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A', 'G'])],
        'residue_info_map': {
            'A': _residue_payload(311.3, 71.08),
            'G': _residue_payload(297.3, 57.05),
        },
        'config_overrides': {'name': 'MaterialsTest', 'output_directory': str(out_dir)},
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert 'materials_xlsx' in body['data']
    assert 'materials_pdf' in body['data']

    last_resp = client.get('/synthesis/last')
    last_body = last_resp.get_json()
    materials = last_body['data']['materials']
    assert materials['synthesis_name'] == 'MaterialsTest'
    assert materials['total_residue_types'] == 2
    assert len(materials['rows']) == 2
    assert materials['rows'][0]['token'] in ('A', 'G')
    assert isinstance(materials['config_summary'], dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_synthesis_routes.py::test_generate_persists_materials_data_in_marker -v`
Expected: FAIL with `KeyError: 'materials'`

- [ ] **Step 3: Persist `materials` in the marker**

In `spps_assistant/api/routes/synthesis.py`, find the `marker_data` dict construction in `generate_synthesis()`:

```python
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

Add the `materials` key:

```python
    marker_data = {
        'name': config.name,
        'output_directory': config.output_directory,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'vessel_count': len(vessels),
        'output_paths': output_paths,
        'current_cycle': 1,
        'cycle_guide': asdict(cycle_guide_data),
        'materials': asdict(materials_data),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_synthesis_routes.py::test_generate_persists_materials_data_in_marker -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/api/routes/synthesis.py tests/api/test_synthesis_routes.py
git commit -m "feat(api): persist materials view data in the last_synthesis marker"
```

---

### Task 4: Frontend types — `MaterialsRow`, `MaterialsViewData`, extend `LastSynthesisEnvelope`

**Files:**
- Modify: `desktop/src/preload/index.d.ts`

**Interfaces:**
- Consumes: nothing (pure type additions).
- Produces: `MaterialsRow`, `MaterialsViewData` TypeScript interfaces, and `LastSynthesisEnvelope.data.materials?: MaterialsViewData`, importable from `../../../preload/index.d` in the renderer. Task 5's `Materials.tsx` and Task 6's wiring both import these.

This task has no automated test of its own (it's a type-only change with no runtime behavior) — its correctness is verified by `npm run typecheck` passing after Task 5 uses these types, and this task's own step below.

- [ ] **Step 1: Add the type definitions**

In `desktop/src/preload/index.d.ts`, add right after the existing `CycleGuideData` interface (after line 90):

```typescript
export interface MaterialsRow {
  token: string
  protection: string
  fmoc_mw: number
  mmol_needed: number
  mass_mg: number
  stock_conc: number
  volume_ml: number
  notes: string
  formula: string
  volume_ul: number | null
}

export interface MaterialsViewData {
  synthesis_name: string
  rows: MaterialsRow[]
  total_residue_types: number
  total_mass_mg: number
  total_volume_ml: number
  config_summary: Record<string, string>
}
```

- [ ] **Step 2: Extend `LastSynthesisEnvelope`**

Find the `LastSynthesisEnvelope` interface:

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

Add `materials?: MaterialsViewData` to the `data` object:

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
    materials?: MaterialsViewData
  } | null
  error?: { code: string; message: string }
}
```

- [ ] **Step 3: Verify typecheck passes**

Run (from `desktop/`): `npm run typecheck`
Expected: PASS (no consumers of these new types yet, so nothing can fail — this just confirms the new interfaces themselves are syntactically valid TypeScript).

- [ ] **Step 4: Commit**

```bash
git add desktop/src/preload/index.d.ts
git commit -m "feat(desktop): add MaterialsRow/MaterialsViewData types"
```

---

### Task 5: `Materials.tsx` view component

**Files:**
- Create: `desktop/src/renderer/src/views/Materials.tsx`
- Test: `desktop/src/renderer/src/views/Materials.test.tsx`

**Interfaces:**
- Consumes: `window.spps.getLastSynthesis()` (existing), `window.spps.openFile(path)` (existing); `MaterialsRow`, `MaterialsViewData` (Task 4).
- Produces: `Materials` React component with props `{ onNewSynthesis: () => void }` (mirrors `CycleGuide`'s prop shape exactly). Task 6 wires this into `App.tsx`.

This view intentionally has **no navigation state** (unlike `CycleGuide`'s Prev/Next) — it's a single static summary of the last synthesis, matching the mockup's single-page layout.

- [ ] **Step 1: Write the failing test**

Create `desktop/src/renderer/src/views/Materials.test.tsx`:

```typescript
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Materials from './Materials'
import type { MaterialsViewData } from '../../../preload/index.d'

function makeMaterials(): MaterialsViewData {
  return {
    synthesis_name: 'TestRun',
    rows: [
      {
        token: 'A',
        protection: '',
        fmoc_mw: 311.3,
        mmol_needed: 0.18,
        mass_mg: 105.4,
        stock_conc: 0.5,
        volume_ml: 0.36,
        notes: 'Fmoc-Ala-OH',
        formula: 'V = ...',
        volume_ul: null
      },
      {
        token: 'G',
        protection: '',
        fmoc_mw: 297.3,
        mmol_needed: 0.24,
        mass_mg: 71.4,
        stock_conc: 0.5,
        volume_ml: 0.48,
        notes: 'Fmoc-Gly-OH',
        formula: 'V = ...',
        volume_ul: null
      }
    ],
    total_residue_types: 2,
    total_mass_mg: 176.8,
    total_volume_ml: 0.84,
    config_summary: { Activator: 'HBTU', 'AA Equivalents': '3.0', 'Volume Mode': 'stoichiometry', Base: 'DIEA' }
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
          output_paths: { materials_xlsx: '/tmp/out/mats.xlsx', materials_pdf: '/tmp/out/mats.pdf' },
          materials: makeMaterials()
        }
      }),
    openFile: vi.fn().mockResolvedValue(''),
    ...overrides
  })
}

describe('Materials', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the synthesis name and stat cards', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('2')).toBeInTheDocument() // total_residue_types
    expect(screen.getByText(/176.8/)).toBeInTheDocument() // total_mass_mg
    expect(screen.getByText(/0.84/)).toBeInTheDocument() // total_volume_ml
  })

  it('renders one requirements row per residue', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('G')).toBeInTheDocument()
  })

  it('renders the calculation-basis config summary', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('HBTU')).toBeInTheDocument()
    expect(screen.getByText('DIEA')).toBeInTheDocument()
  })

  it('clicking Export XLSX opens the real generated file', async () => {
    const openFile = vi.fn().mockResolvedValue('')
    stubSpps({ openFile })
    const user = userEvent.setup()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export xlsx/i }))
    expect(openFile).toHaveBeenCalledWith('/tmp/out/mats.xlsx')
  })

  it('shows an error message when opening the exported file fails', async () => {
    const openFile = vi.fn().mockResolvedValue('File not found.')
    stubSpps({ openFile })
    const user = userEvent.setup()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export pdf/i }))
    await waitFor(() => expect(screen.getByText('File not found.')).toBeInTheDocument())
  })

  it('shows an empty state and a New synthesis button when no synthesis exists', async () => {
    stubSpps()
    vi.stubGlobal('spps', {
      getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
      openFile: vi.fn()
    })
    const onNewSynthesis = vi.fn()
    render(<Materials onNewSynthesis={onNewSynthesis} />)

    await waitFor(() => expect(screen.getByText(/no active synthesis/i)).toBeInTheDocument())
    await userEvent.setup().click(screen.getByRole('button', { name: /new synthesis/i }))
    expect(onNewSynthesis).toHaveBeenCalled()
  })

  it('shows an error state instead of crashing when getLastSynthesis rejects', async () => {
    vi.stubGlobal('spps', {
      getLastSynthesis: () => Promise.reject(new Error('sidecar down')),
      openFile: vi.fn()
    })
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText(/sidecar running/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `desktop/`): `npx vitest run src/renderer/src/views/Materials.test.tsx`
Expected: FAIL with a module-not-found error for `./Materials`.

- [ ] **Step 3: Implement `Materials.tsx`**

Create `desktop/src/renderer/src/views/Materials.tsx`:

```typescript
import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import type { MaterialsViewData } from '../../../preload/index.d'

type MaterialsState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'error' }
  | { status: 'loaded'; materials: MaterialsViewData; outputPaths: Record<string, string> }

interface MaterialsProps {
  onNewSynthesis: () => void
}

export default function Materials({ onNewSynthesis }: Readonly<MaterialsProps>): React.JSX.Element {
  const [state, setState] = useState<MaterialsState>({ status: 'loading' })
  const [exportError, setExportError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.materials) {
          setState({
            status: 'loaded',
            materials: envelope.data.materials,
            outputPaths: envelope.data.output_paths ?? {}
          })
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

  async function handleExport(path: string): Promise<void> {
    setExportError(null)
    const result = await window.spps.openFile(path)
    if (result) {
      setExportError(result)
    }
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
                ? "Couldn't load materials. Is the sidecar running?"
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

  const { materials } = state
  const xlsxPath = state.outputPaths.materials_xlsx
  const pdfPath = state.outputPaths.materials_pdf

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-text font-sans text-base font-medium">Materials explosion</h1>
          <p className="text-text3 font-mono text-xs">{materials.synthesis_name}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            {xlsxPath && (
              <Button onClick={() => handleExport(xlsxPath)} className="bg-bg3">
                ⬇ Export XLSX
              </Button>
            )}
            {pdfPath && (
              <Button onClick={() => handleExport(pdfPath)} className="bg-bg3">
                ⬇ Export PDF
              </Button>
            )}
          </div>
          {exportError && <p className="text-red-500 font-sans text-xs">{exportError}</p>}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total residue types
            </div>
            <div className="text-teal font-mono text-2xl font-light">{materials.total_residue_types}</div>
          </CardContent>
        </Card>
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total Fmoc-AA mass
            </div>
            <div className="text-teal font-mono text-2xl font-light">
              {materials.total_mass_mg.toFixed(1)} <span className="text-sm text-text3">mg</span>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total reagent volume
            </div>
            <div className="text-teal font-mono text-2xl font-light">
              {materials.total_volume_ml.toFixed(2)} <span className="text-sm text-text3">mL</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Amino acid requirements</h2>
      <Card className="bg-bg2 mb-4">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text3 font-sans text-xs uppercase">
                <th className="text-left p-2">Residue</th>
                <th className="text-left p-2">Fmoc-MW</th>
                <th className="text-left p-2">mmol</th>
                <th className="text-left p-2">Mass to weigh</th>
                <th className="text-left p-2">Volume</th>
              </tr>
            </thead>
            <tbody>
              {materials.rows.map((row) => (
                <tr key={row.token} className="border-t border-[color:var(--border)]">
                  <td className="p-2 text-text font-mono">
                    {row.token}
                    {row.protection && <span className="text-text3">({row.protection})</span>}
                  </td>
                  <td className="p-2 text-text2 font-mono">{row.fmoc_mw.toFixed(1)}</td>
                  <td className="p-2 text-text2 font-mono">{row.mmol_needed.toFixed(2)}</td>
                  <td className="p-2 text-teal font-mono">
                    {row.volume_ul !== null ? `${row.volume_ul.toFixed(1)} µL` : `${row.mass_mg.toFixed(1)} mg`}
                  </td>
                  <td className="p-2 text-text2 font-mono">{row.volume_ml.toFixed(2)} mL</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Calculation basis</h2>
      <Card className="bg-bg2">
        <CardContent className="py-3">
          {Object.entries(materials.config_summary).map(([key, value]) => (
            <div key={key} className="flex justify-between text-xs font-sans py-1">
              <span className="text-text3">{key}</span>
              <span className="text-text2 font-mono">{value}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `desktop/`): `npx vitest run src/renderer/src/views/Materials.test.tsx`
Expected: PASS (7 tests)

- [ ] **Step 5: Run typecheck and the full desktop test suite**

Run (from `desktop/`): `npm run typecheck && npm test -- --run`
Expected: typecheck clean, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add desktop/src/renderer/src/views/Materials.tsx desktop/src/renderer/src/views/Materials.test.tsx
git commit -m "feat(desktop): add Materials view — read-only reagent explosion summary"
```

---

### Task 6: Wire the Materials tab and "View materials" buttons

**Files:**
- Modify: `desktop/src/renderer/src/App.tsx`
- Modify: `desktop/src/renderer/src/App.test.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.test.tsx`
- Modify: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`
- Modify: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`
- Modify: `desktop/src/renderer/src/views/NewSynthesis.tsx`

**Interfaces:**
- Consumes: `Materials` component (Task 5), `envelope.data?.materials` (Task 3's marker field, surfaced via the existing `LastSynthesisEnvelope` type from Task 4).
- Produces: the "Materials" tab in `App.tsx`'s nav becomes clickable once a synthesis with materials data exists; "View materials" buttons on the Dashboard and the post-generate Step 5 screen navigate straight to it — mirroring the existing "Cycle guide"/`onViewCycleGuide` wiring exactly.

- [ ] **Step 1: Write the failing test for App.tsx's tab-enable logic**

In `desktop/src/renderer/src/App.test.tsx`, find the existing `'enables the Cycle guide tab once a synthesis exists'` test (it stubs `spps` directly via `vi.stubGlobal`, then checks `nav.getByText('Cycle guide').className` no longer contains `'cursor-not-allowed'`). Add an analogous test right after it, matching that exact pattern (not `getByRole`/`toBeDisabled`, which this file doesn't use elsewhere):

```typescript
  it('enables the Materials tab once a synthesis with materials data exists', async () => {
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
            materials: { synthesis_name: 'TestRun', rows: [], total_residue_types: 0, total_mass_mg: 0, total_volume_ml: 0, config_summary: {} }
          }
        }),
      pickFastaFile: vi.fn().mockResolvedValue(null)
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    await waitFor(() => {
      const tab = nav.getByText('Materials')
      expect(tab.className).not.toContain('cursor-not-allowed')
    })
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `desktop/`): `npx vitest run src/renderer/src/App.test.tsx`
Expected: FAIL — the "Materials" tab's className still contains `'cursor-not-allowed'` (`enabled` in `getTabClassName`'s condition doesn't yet check `materialsEnabled`).

- [ ] **Step 3: Wire `App.tsx`**

In `desktop/src/renderer/src/App.tsx`, add the import:

```typescript
import Materials from './views/Materials'
```

Add a second piece of state alongside `cycleGuideEnabled`:

```typescript
  const [cycleGuideEnabled, setCycleGuideEnabled] = useState(false)
  const [materialsEnabled, setMaterialsEnabled] = useState(false)
```

Update the existing `getLastSynthesis` effect to also check for `materials`:

```typescript
  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.cycle_guide) {
          setCycleGuideEnabled(true)
        }
        if (envelope.ok && envelope.data?.materials) {
          setMaterialsEnabled(true)
        }
      })
      .catch(() => {
        // Leave the tabs disabled — matches the "no active synthesis" state.
      })
    return () => {
      cancelled = true
    }
  }, [])
```

Add a handler mirroring `handleViewCycleGuide`:

```typescript
  function handleViewMaterials(): void {
    setMaterialsEnabled(true)
    setActiveTab('Materials')
  }
```

Update the tab-enable check inside the `TABS.map(...)` block:

```typescript
          const enabled =
            tab === 'Dashboard' ||
            tab === 'New synthesis' ||
            (tab === 'Cycle guide' && cycleGuideEnabled) ||
            (tab === 'Materials' && materialsEnabled)
```

Thread `onViewMaterials` into `Dashboard` and `NewSynthesis`, and add the `Materials` tab's render branch:

```typescript
      {activeTab === 'Dashboard' && (
        <Dashboard
          onNewSynthesis={() => setActiveTab('New synthesis')}
          onViewCycleGuide={handleViewCycleGuide}
          onViewMaterials={handleViewMaterials}
        />
      )}
      {activeTab === 'New synthesis' && (
        <NewSynthesis
          onDone={() => setActiveTab('Dashboard')}
          onViewCycleGuide={handleViewCycleGuide}
          onViewMaterials={handleViewMaterials}
        />
      )}
      {activeTab === 'Cycle guide' && (
        <CycleGuide onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
      {activeTab === 'Materials' && (
        <Materials onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
```

- [ ] **Step 4: Wire `Dashboard.tsx`**

In `desktop/src/renderer/src/views/Dashboard.tsx`, add `onViewMaterials: () => void` to `DashboardProps` and the destructured props:

```typescript
interface DashboardProps {
  onNewSynthesis: () => void
  onViewCycleGuide: () => void
  onViewMaterials: () => void
}

export default function Dashboard({
  onNewSynthesis,
  onViewCycleGuide,
  onViewMaterials
}: Readonly<DashboardProps>): React.JSX.Element {
```

Add a second button next to the existing "View cycle guide" button (inside the `lastSynthesis.status === 'active'` block):

```typescript
          {lastSynthesis.status === 'active' && (
            <>
              <p className="text-text font-sans text-sm mb-1">{lastSynthesis.name}</p>
              <p className="text-text3 font-mono text-xs mb-4">
                {lastSynthesis.vesselCount} vessel(s) — generated {lastSynthesis.generatedAt}
              </p>
              <div className="flex gap-2">
                <Button onClick={onViewCycleGuide} className="bg-teal text-bg hover:bg-teal/90">
                  View cycle guide
                </Button>
                <Button onClick={onViewMaterials} className="bg-teal text-bg hover:bg-teal/90">
                  View materials
                </Button>
              </div>
            </>
          )}
```

In `desktop/src/renderer/src/views/Dashboard.test.tsx`, every existing `render(<Dashboard .../>)` call must now also pass `onViewMaterials={() => {}}` (or a `vi.fn()` if the test asserts on it) — grep for `render(<Dashboard` in that file and add the prop to each call site, matching how `onViewCycleGuide` is already passed. This file's existing mock helper is `baseStub(overrides)` (not `stubSpps`), used via `vi.stubGlobal('spps', baseStub({...}))`. Add one new test, mirroring the existing "clicking View cycle guide" test's `getLastSynthesis` override shape:

```typescript
  it('clicking View materials calls onViewMaterials', async () => {
    const onViewMaterials = vi.fn()
    vi.stubGlobal(
      'spps',
      baseStub({
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

    render(
      <Dashboard onNewSynthesis={() => {}} onViewCycleGuide={() => {}} onViewMaterials={onViewMaterials} />
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view materials/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view materials/i }))

    expect(onViewMaterials).toHaveBeenCalledTimes(1)
  })
```

- [ ] **Step 5: Wire `Step5Confirm.tsx` and `NewSynthesis.tsx`**

In `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`, add `onViewMaterials: () => void` to `Step5Props` and the destructured props:

```typescript
interface Step5Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
  onDone: () => void
  onViewCycleGuide: () => void
  onViewMaterials: () => void
}

export default function Step5Confirm({
  state,
  dispatch,
  onDone,
  onViewCycleGuide,
  onViewMaterials
}: Readonly<Step5Props>): React.JSX.Element {
```

Add a button next to the existing "View cycle guide" button:

```typescript
            <Button onClick={onViewCycleGuide} className="bg-bg3">
              View cycle guide
            </Button>
            <Button onClick={onViewMaterials} className="bg-bg3">
              View materials
            </Button>
```

In `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`, this file renders `Step5Confirm` through a shared `renderStep5(state, onDone, onViewCycleGuide)` helper (not repeated raw `render(...)` calls). Add an `onViewMaterials` parameter and thread it through both `<Step5Confirm .../>` JSX blocks inside that helper (the initial `render(...)` call and the `rerender(...)` call inside `dispatch.mockImplementation`), and through the helper's return object, mirroring `onViewCycleGuide` exactly:

```typescript
function renderStep5(
  state: WizardState,
  onDone = vi.fn(),
  onViewCycleGuide = vi.fn(),
  onViewMaterials = vi.fn()
): Omit<RenderResult, 'rerender'> & {
  dispatch: ReturnType<typeof vi.fn>
  onDone: ReturnType<typeof vi.fn>
  onViewCycleGuide: ReturnType<typeof vi.fn>
  onViewMaterials: ReturnType<typeof vi.fn>
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
      onViewMaterials={onViewMaterials}
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
        onViewMaterials={onViewMaterials}
      />
    )
  })

  return { ...utils, dispatch, onDone, onViewCycleGuide, onViewMaterials, rerender, getState: () => currentState }
}
```

Then add a test mirroring the existing `'clicking "View cycle guide" calls onViewCycleGuide'` test exactly (that test first stubs `generateSynthesis` and clicks "Generate" — the "View cycle guide"/"View materials" buttons only render once `state.generateResult.status === 'success'`):

```typescript
  it('clicking "View materials" calls onViewMaterials', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { materials_xlsx: '/tmp/output/Test_materials.xlsx' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onViewMaterials } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view materials/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view materials/i }))

    expect(onViewMaterials).toHaveBeenCalledTimes(1)
  })
```

In `desktop/src/renderer/src/views/NewSynthesis.tsx`, add `onViewMaterials: () => void` to its own props interface and thread it through to `Step5Confirm`:

```typescript
  onViewCycleGuide,
  onViewMaterials
```

```typescript
        <Step5Confirm
          state={state}
          dispatch={dispatch}
          onDone={onDone}
          onViewCycleGuide={onViewCycleGuide}
          onViewMaterials={onViewMaterials}
        />
```

(Read the file first — `NewSynthesis.tsx`'s props interface and the exact `<Step5Confirm .../>` call site are both single, small, contiguous blocks; match the existing formatting.)

- [ ] **Step 6: Run tests to verify they pass**

Run (from `desktop/`): `npm test -- --run`
Expected: PASS, all files.

- [ ] **Step 7: Run typecheck and lint**

Run (from `desktop/`): `npm run typecheck && npm run lint`
Expected: typecheck clean; lint 0 errors (pre-existing prettier warnings in unrelated files are fine, don't fix files this task didn't touch).

- [ ] **Step 8: Run the full backend test suite too (nothing should have broken)**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add desktop/src/renderer/src/App.tsx desktop/src/renderer/src/App.test.tsx desktop/src/renderer/src/views/Dashboard.tsx desktop/src/renderer/src/views/Dashboard.test.tsx desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx desktop/src/renderer/src/views/NewSynthesis.tsx
git commit -m "feat(desktop): wire Materials tab navigation from tab bar, Dashboard, and post-generate screen"
```

---

## After all tasks: whole-branch review and manual smoke test

Per this project's established pattern (Phases 1–4), after Task 6 is complete and committed:

1. Run a final whole-branch review (fresh subagent or `opus`-level review) against the full diff from the branch's base commit — independently re-verify the Python↔TypeScript field-for-field contract (`MaterialsRow`/`MaterialsViewData` in both languages), that `MaterialsUseCase`/`materials_cmd.py` (the v1.0 CLI path) are byte-identical to before this phase, and that no `output_paths`/marker consumer was missed.
2. Run a manual Electron smoke test (Playwright `_electron` driver, extending Phase 3/4's script): New Synthesis → Generate → "View materials" from the success screen → confirm stat cards show real numbers → Export XLSX and Export PDF both call `shell.openPath` with the correct real filenames → Dashboard's "View materials" button reopens the same data → verify the real XLSX/PDF files on disk contain the expected residue rows (a lightweight `openpyxl`/`pypdf` check, temporarily installed, same as prior phases).
3. Push, open the PR, and follow the same CodeRabbit/SonarCloud iteration loop documented in `SPPS_GUI_MIGRATION_PLAN.md`'s Phase 4 section — verify every finding against current code, fix what's real, defer what's genuinely out of scope with logged reasoning, and don't merge past a stale review without checking the exact HEAD commit's actual review/status.
