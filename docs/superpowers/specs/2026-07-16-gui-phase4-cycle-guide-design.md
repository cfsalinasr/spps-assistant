# Phase 4: Coupling Cycle Guide View — Design Spec

**Status:** Approved (brainstorming complete, pending final spec review)
**Date:** 2026-07-16
**Scope:** Phase 4 of the SPPS GUI migration (see `/Users/cristiansalinas/Desktop/spps/SPPS_GUI_MIGRATION_PLAN.md` §7)

## 1. Purpose

Build the Coupling Cycle Guide view: a read-only, print-matched, on-screen
preview of the coupling-cycle GMP record that `POST /synthesis/generate`
(Phase 3) already writes to PDF/DOCX. The chemist uses this view to see
what to do for the current cycle without opening the exported file, then
prints/exports the real document for hand-signing.

## 2. Scope decisions

- **Last synthesis only.** No history browsing, no "Recent syntheses"
  table. Matches Phase 3's existing single-marker (`last_synthesis.json`)
  scope exactly. Browsing past syntheses is out of scope for this phase.
- **Read-only, not a data-entry form.** Per `DESIGN_CONTEXT.md` §6.6: "These
  are printed form elements — squares for hand-ticking, not interactive
  HTML checkboxes." The GMP checkboxes, date/operator fields, and
  done-by/reviewed-by fields render as static blank lines matching the
  print output. No checkbox state is captured or persisted.
- **One trackable signal: current cycle position.** Since checkbox
  completion isn't captured, "progress" is limited to which cycle the user
  is currently looking at — a single persisted integer, advanced via
  Prev/Next. This drives the Dashboard's "Cycle N of M" display. It is not
  a claim that cycle N was actually completed in the lab, only that it's
  the last one viewed.
- **Export buttons open existing files, they don't regenerate.** The PDF
  and DOCX were already written by `/synthesis/generate`. "Export PDF" /
  "Export DOCX" in the Cycle Guide view open those real files directly
  (via the OS's default viewer), matching the "the guide reflects what was
  actually generated" principle — not a live re-render of current on-screen
  state.

## 3. Backend architecture

### 3.1 Existing duplication this phase must resolve

`infrastructure/pdf_generator.py` and `infrastructure/docx_generator.py`
each independently compute the same per-cycle numbers from
`CouplingCycle` + `SynthesisConfig` + `residue_info_map`:

- AA dispatch table rows (3-letter residue, Fmoc-MW, mmol, volume,
  formula string, vessel numbers) — `_build_aa_dispatch_table` (PDF) /
  `_build_aa_dispatch_data` (DOCX)
- Deprotection GMP steps (varies on `deprotection_reagent`,
  `include_bb_test`, `include_kaiser_test`) — `_build_deprotection_table` /
  `_build_deprotection_data`
- Coupling GMP steps (varies on `activator`, `use_oxyma`, `base`) —
  `_build_coupling_table` / (inlined in `_add_cycle_page`)
- Vessel assignment (residue or "OUT" per vessel) —
  `_build_vessel_assignment_line` / `_add_vessel_assignment`
- Secondary coupling verification (Teabag method only) —
  `_build_secondary_coupling_table` / `_add_secondary_coupling_table`
- Even the literal constants are duplicated: `WASH_DURATION = '2 × 1 min'`
  and `COUPLING_DURATION = '30 min'` are defined separately in both files
  with identical values.

The GUI needs these exact same numbers as structured JSON. Computing them
a third time in the API layer would add a third copy instead of fixing
the duplication, so this phase extracts the shared computation instead.

### 3.2 New shared application-layer function

Add to `application/synthesis_guide.py`:

```python
def build_cycle_guide_view_data(
    vessels: List[Vessel],
    coupling_cycles: List[CouplingCycle],
    config: SynthesisConfig,
    residue_info_map: Dict,
) -> CycleGuideViewData:
    """Build the structured, display-ready data for every coupling cycle.

    This is the single source of truth for per-cycle GMP record content —
    both the PDF/DOCX generators and the GUI's Cycle Guide view render
    from this, so the on-screen preview and the exported documents can
    never drift apart.
    """
```

New dataclasses in `domain/models.py` (plain data, JSON-serializable):

- `DispatchRow`: `residue_3letter`, `fmoc_mw`, `mmol`, `volume_ml`,
  `formula_shown`, `vessel_numbers: List[int]`
- `GmpStep`: `label`, `detail`, `n_checkboxes`, `duration` (covers both
  deprotection and coupling rows — same shape, both are "label + detail +
  checkbox count + duration")
- `VesselAssignment`: `vessel_number`, `vessel_name`, `residue_3letter:
  Optional[str]` (`None` means OUT)
- `SecondaryCouplingRow`: `vessel_number`, `vessel_name`, `residue_3letter`
  (only populated when `config.vessel_method == 'Teabag'`)
- `CyclePageData`: `cycle_number`, `total_cycles`, `dispatch_rows:
  List[DispatchRow]`, `deprotection_steps: List[GmpStep]`,
  `coupling_steps: List[GmpStep]`, `vessel_assignments:
  List[VesselAssignment]`, `secondary_coupling_rows:
  Optional[List[SecondaryCouplingRow]]`
- `CycleGuideViewData`: `synthesis_name`, `date_str`, `cycles:
  List[CyclePageData]`

Both `pdf_generator.py`'s and `docx_generator.py`'s per-cycle builder
functions are refactored to accept a `CyclePageData` and render it
(ReportLab `Table` / `python-docx` table respectively) instead of
recomputing values from `CouplingCycle` directly. The public
`generate_cycle_guide_pdf`/`generate_cycle_guide_docx` signatures are
unchanged (still take `vessels`, `coupling_cycles`, `config`,
`residue_info_map`) — they call `build_cycle_guide_view_data()` internally
as their first step, so no caller outside these two files needs to change.

### 3.3 Persistence: extend the existing marker

`SynthesisGuideUseCase.run()` already builds `coupling_cycles` before
generating PDF/DOCX. Add one call to `build_cycle_guide_view_data()` at
that point, and have `POST /synthesis/generate` (in
`api/routes/synthesis.py`) persist the result into the existing
`last_synthesis.json` marker (same atomic temp-file + `os.replace()`
pattern already in place), extending the marker's fields:

```json
{
  "name": "...",
  "output_directory": "...",
  "generated_at": "...",
  "vessel_count": 3,
  "output_paths": {
    "cycle_guide_pdf": "...", "cycle_guide_docx": "...",
    "peptide_info_pdf": "...", "peptide_info_docx": "..."
  },
  "current_cycle": 1,
  "cycle_guide": { "synthesis_name": "...", "date_str": "...", "cycles": [ ... ] }
}
```

`output_paths` is new too — it's already computed by
`SynthesisGuideUseCase.run()`'s return value today but never persisted
(only returned once, in the `/synthesis/generate` response). The Cycle
Guide view's export buttons need it after that response is long gone.

### 3.4 Route changes

- **Extend `GET /synthesis/last`**: no new endpoint. Its response's `data`
  already returns the whole marker dict; it just carries more fields now
  (`output_paths`, `current_cycle`, `cycle_guide`). Existing consumers
  (Dashboard) that only read `name`/`generated_at`/`vessel_count` are
  unaffected.
- **New `POST /synthesis/cycle-position`**: body `{"cycle_number": int}`.
  Validates `1 <= cycle_number <= cycle_guide.cycles.length` (400
  `invalid_body` otherwise) and the marker must already exist (400
  `no_active_synthesis` otherwise), then rewrites only the
  `current_cycle` field via the same atomic write pattern. Called on every
  Prev/Next click — cheap, no recomputation.

## 4. Frontend architecture

### 4.1 New view

`desktop/src/renderer/src/views/CycleGuide.tsx` — styled per
`DESIGN_CONTEXT.md` §7 View 3 and the mockup's `.cycle-header`, `.gmp-row`,
`.gmp-step`, `.gmp-field`, `.vessel-chip`, `.dispatch-table` classes
(reusing shadcn `Table`/`Card` primitives the way Phase 3's wizard steps
already compose custom classes on top of shadcn). Local state is just the
displayed cycle index, seeded from `current_cycle` on load; all cycle
content comes from the `cycle_guide.cycles` array already returned by
`getLastSynthesis()` — no per-navigation fetch needed beyond the initial
load and the (fire-and-forget, non-blocking) position-save call.

Empty state (no synthesis generated yet) mirrors Dashboard's existing
`'none'`-status pattern: a message directing the user to New Synthesis,
not a broken/blank table.

### 4.2 Preload/IPC extensions

- `LastSynthesisEnvelope`'s `data` shape gains `output_paths`,
  `current_cycle`, and `cycle_guide` (all optional/nullable, matching the
  existing envelope's `| null` pattern for the no-synthesis-yet case).
- New `spps.setCyclePosition(cycleNumber: number): Promise<SppsEnvelope>`
  → `POST /synthesis/cycle-position`. Note: `SppsEnvelope.data` is typed
  for `/config` responses (`SppsConfig`); this call's response doesn't
  carry a meaningful `data` payload, so the plan should either introduce a
  generic `SppsEnvelope<T = void>` or a dedicated minimal envelope type —
  not silently reuse the config-shaped one (this exact imprecision was a
  CodeRabbit finding on Phase 3's `saveResidue`; don't repeat it here).
  Failure is non-fatal: if the save fails (network/IPC error), the
  renderer keeps the locally-navigated cycle index and does not block or
  show an error — this is a convenience position marker, not part of the
  GMP audit trail (that lives in the signed, printed PDF).
- New `spps.openFile(path: string): Promise<void>` → new
  `ipcMain.handle('spps:openFile', ...)` in `dialogs.ts`, using
  `shell.openPath` (opens the file in its default OS viewer — distinct
  from the existing `spps:openFolder`, which reveals a file *in* Finder
  via `shell.showItemInFolder`). Same invalid-path guard pattern as the
  existing `openFolder` handler.

### 4.3 Navigation wiring

- `App.tsx`'s "Cycle guide" tab (present in `TABS`, currently always
  disabled) becomes enabled once `getLastSynthesis()` resolves with real
  data. There is no shared/global state store in this codebase (each view
  fetches its own data independently — confirmed from Phases 2/3); `App.tsx`
  makes its own lightweight `getLastSynthesis()` call on mount purely to
  decide tab-enablement, separate from Dashboard's own call for its
  last-synthesis card. This is a small duplicated fetch, consistent with
  the existing per-component-fetch pattern rather than introducing a new
  state-sharing mechanism for one boolean.
- Dashboard's last-synthesis card gets a "View cycle guide" button that
  switches the active tab — the simplified equivalent of the mockup's
  "clicking a row in the active-synthesis table" behavior, since this
  scope has no per-vessel active-synthesis table.
- Phase 3's post-generate success screen (`Step5Confirm.tsx`) gets a
  direct "View cycle guide" link alongside its existing "Done" button,
  since the marker (and thus the cycle guide data) already exists at that
  point.

## 5. Testing strategy

- **`build_cycle_guide_view_data()`**: new unit tests in
  `tests/application/test_synthesis_guide_use_case.py` (or a new sibling
  file if it grows large) covering dispatch-row computation, the
  `include_bb_test`/`include_kaiser_test`/`vessel_method` conditionals on
  step generation, and OUT-row vessel assignment.
- **PDF/DOCX regression**: existing 61 tests in `test_generators.py` (plus
  `TestGenerateCycleGuidePDF` and friends) are the regression net for the
  refactor — output structure must stay identical. A few new tests assert
  the generators now consume `CyclePageData` rather than recomputing raw
  values.
- **New route tests**: `GET /synthesis/last` returning the extended
  payload; `POST /synthesis/cycle-position` (valid cycle number,
  out-of-range rejection, missing marker) — following Phase 3's
  `tests/api/conftest.py` shared-fixture convention.
- **New desktop component tests**: `CycleGuide.tsx` (renders the seeded
  cycle, Prev/Next boundary disabling, empty state) and the `spps:openFile`
  IPC handler (`dialogs.test.ts`), following Phase 3's `*.test.tsx`
  conventions.
- **Manual smoke test**: extend the ad-hoc Playwright `_electron` driver
  built during Phase 3's smoke test to also walk: generate a synthesis →
  land on/navigate to Cycle Guide → Prev/Next through a few cycles →
  Export PDF/DOCX opens the real file → Dashboard reflects the current
  cycle position.

## 6. Out of scope for this phase

- Multi-synthesis history / browsing past syntheses.
- Interactive checkbox / signature persistence (explicitly ruled out by
  `DESIGN_CONTEXT.md` §6.6).
- Any change to what the exported PDF/DOCX *contain* — this phase adds a
  read path to already-generated content, not new document features.
- Materials Explosion view (Phase 5) and Peptide Info stub (Phase 6).
