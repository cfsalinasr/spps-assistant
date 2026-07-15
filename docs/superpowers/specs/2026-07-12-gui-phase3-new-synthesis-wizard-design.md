# Design: Phase 3 — New Synthesis Setup Wizard

**Status:** Approved (brainstorming session, 2026-07-12)
**Supersedes:** N/A — first design doc for this phase
**Parent plan:** `/Users/cristiansalinas/Desktop/spps/SPPS_GUI_MIGRATION_PLAN.md` §7, Phase 3

## Purpose

Build the 5-step "New Synthesis" wizard (`DESIGN_CONTEXT.md` §7, View 2) end to
end: three new Flask sidecar routes plus the React wizard that drives them,
reaching a real `/synthesis/generate` call that writes real PDF/DOCX files —
the same output the v1.0 CLI's `generate` command produces, driven through the
GUI instead of interactive terminal prompts.

Both the backend routes and the frontend wizard are built together in this one
phase (not split into a backend-only followed by a frontend-only phase), since
the wizard has no meaningful demo state without real endpoints to call, and
each route is a thin, fast-to-review wrapper around already-existing,
already-tested `application`/`domain`/`infrastructure` logic — there's no
backend-only research risk that would justify shipping it standalone first.

## Non-negotiable priority (carried forward from the parent plan)

Test coverage, clean-architecture layering, code quality, and security take
priority over staying strictly within this phase's original scope. See
`feedback_quality_over_scope` in project memory.

## 1. Backend API additions

Three new route files under `spps_assistant/api/routes/`, following the exact
convention `routes/config.py` and `routes/health.py` already established in
Phase 1: each route file only marshals HTTP request/response — all real logic
stays in `application`/`domain`/`infrastructure`, which this phase does not
modify (only adds thin call-sites into existing, already-tested functions).

Every route requires the `X-SPPS-Sidecar-Token` header (enforced by the
existing `before_request` hook — no new auth code needed) and returns the
existing `{"ok": bool, "data"/"error": ...}` envelope.

### `routes/sequences.py`

**`POST /sequences/parse`**

Request body:
```json
{ "fasta_path": "/absolute/path/to/file.fasta", "materials_path": "/absolute/path/to/materials.csv" }
```
`materials_path` is optional (`null` or omitted if not provided).

Wraps, in order:
1. `application.sequence_loader.parse_and_validate_sequences(Path(fasta_path))`
2. `application.sequence_loader.build_vessels(parsed_sequences, starting_num, substitution_mmol_g=...)` —
   `starting_num` and `substitution_mmol_g` come from the current config
   (`ConfigRepository.load()`), matching the CLI's exact defaulting.
3. If `materials_path` given: `application.sequence_loader.load_materials_map(Path(materials_path))`.

Response `data`:
```json
{
  "vessels": [
    {
      "number": 1, "name": "PvAMP66",
      "original_tokens": ["W","K","K", ...], "reversed_tokens": ["F","F","K", ...]
    }
  ],
  "materials_residue_map": { "W": { "token": "W", "fmoc_mw": 585.7, "free_mw": 204.2, ... } }
}
```
`materials_residue_map` is omitted from the response if no `materials_path` was given.

Errors (FASTA parse failure, invalid residue token, materials file parse
failure) surface as the existing `{"ok": false, "error": {...}}` shape — these
are `ValueError`s already raised by the wrapped functions, caught and
converted to a 400 response with the exception message.

### `routes/residues.py`

**`GET /residues`** — wraps `SQLiteRepository.list_residues()` directly, no
transformation needed (already returns a list of dicts).

**Precedence when both a materials file and the DB have a value for the same
token** (matches the CLI's `prompt_residue_mws` exactly, which checks
`residue_info_map` — pre-seeded from the materials file — before falling back
to the DB): materials-file values win; DB values (`GET /residues`) only fill
in tokens the materials file didn't cover. Step 2's frontend table merges
`materials_residue_map` (from `/sequences/parse`, if a materials file was
given) over the `GET /residues` result — materials file entries take
priority — before rendering the initial editable rows.

**`POST /residues`** — body is a single residue record
(`{"token", "base_code", "protection", "fmoc_mw", "free_mw", ...}`), wraps
`SQLiteRepository.save_residue(...)`.

**Which rows get persisted back to the DB:** matches the CLI's
`prompt_residue_mws` exactly, which only calls `save_residue` for tokens it
had to resolve via DB-lookup-or-prompt — never for tokens already supplied by
a materials file. So Step 2 calls `POST /residues` only for rows whose value
came from the DB or was manually entered/edited by the user; rows populated
from an uploaded materials file are *not* written back to the DB (the
materials file stays the source of truth for those tokens, matching the
CLI's behavior — silently promoting a one-off materials-file value into the
permanent residue library would be a surprising side effect). The frontend
tracks each row's origin (`'db' | 'materials' | 'manual'`) to know which to
save on Continue.

### `routes/synthesis.py`

**`POST /synthesis/generate`**

Request body carries everything accumulated across Steps 1-4:
```json
{
  "vessels": [ /* from /sequences/parse, resin_mass_g/substitution_mmol_g filled in per Step 4 */ ],
  "residue_info_map": { "W": {...}, ... },
  "config_overrides": {
    "deprotection_reagent", "activator", "use_oxyma", "base", "volume_mode",
    "include_bb_test", "include_kaiser_test", "vessel_method",
    "resin_mass_strategy", "fixed_resin_mass_g", "target_yield_mg",
    "output_directory"
  }
}
```

Server-side, in order:
1. `build_config_from_defaults({**config_repo.load(), **config_overrides})` to
   get a `SynthesisConfig` — `build_config_from_defaults` only accepts 3
   explicit override kwargs (`volume_mode`, `output_dir`, `starting_num`);
   every other field (`activator`, `base`, `resin_mass_strategy`, etc.) is
   read via `.get()` straight from its single dict argument, so merging
   `config_overrides` over the loaded defaults *before* the call — not
   passing them as `**kwargs` — is what actually threads every overridden
   field through correctly.
2. If `resin_mass_strategy == 'target'`: `apply_target_resin_mass(vessels, config, residue_info_map)`
   to back-calculate each vessel's `resin_mass_g` (mirrors the CLI's target-yield path exactly).
3. `calc_yields_and_solubility(vessels, residue_info_map)`.
4. `SynthesisGuideUseCase(db, config_repo).run(output_dir=..., config=..., residue_info_map=..., vessels=..., yield_results=..., solubility_results=...)`.
5. On success, write `~/.spps_assistant/last_synthesis.json`:
   ```json
   { "name": "...", "output_directory": "...", "generated_at": "2026-07-12T...", "vessel_count": 2 }
   ```
   (see §3 below for why this exists and how the Dashboard consumes it.)

Response `data`: the `output_paths` dict `SynthesisGuideUseCase.run` already
returns (`{"cycle_guide_pdf": "...", "cycle_guide_docx": "...", "peptide_info_pdf": "...", "peptide_info_docx": "..."}`).

Errors from any step (invalid config, back-calculation failure, generation
failure) surface as `{"ok": false, "error": {...}}` — no partial files are
left in an inconsistent state beyond what `SynthesisGuideUseCase.run` already
guarantees today.

## 2. Frontend structure

```
desktop/src/renderer/src/views/
  NewSynthesis.tsx                     — shell: useReducer, step-indicator, Back/Continue nav
  new-synthesis/
    wizardReducer.ts                   — state shape + actions (pure, unit-testable alone)
    Step1Sequences.tsx                 — file picker (native dialog only), parse preview, reversed-sequence display
    Step2ResidueMW.tsx                 — table of unique tokens, DB-prefilled + optional materials-file override, editable
    Step3Reagents.tsx                  — matches the existing mockup exactly (pill selectors); activator DIC/DCC -> base "None (recommended)" coupling is local UI logic here
    Step4Resin.tsx                     — strategy pill (fixed/target), substitution + mass/yield inputs
    Step5Confirm.tsx                   — read-only summary of Steps 1-4 (no calculated preview), Generate button, success/error state
```

Reducer state shape (one object threaded through all 5 steps, lives only for
the lifetime of the wizard being mounted — no persistence if the user
navigates back to the Dashboard mid-wizard):

```ts
interface WizardState {
  step: 1 | 2 | 3 | 4 | 5
  fastaPath: string | null
  materialsPath: string | null
  vessels: ParsedVessel[]                    // from /sequences/parse
  residueMap: Record<string, ResidueInfo & { origin: 'db' | 'materials' | 'manual' }>
                                              // origin drives which rows POST /residues persists on Continue (see §1)
  reagents: {
    deprotectionReagent: string
    activator: string
    useOxyma: boolean
    base: string
    volumeMode: 'stoichiometry' | 'legacy'
    completenessTest: 'bromophenol' | 'kaiser' | 'none'
  }
  resin: {
    strategy: 'fixed' | 'target'
    substitutionMmolG: number
    fixedResinMassG: number
    targetYieldMg: number | null
  }
  outputDirectory: string
  generateResult: { status: 'idle' | 'generating' | 'success' | 'error'; paths?: Record<string,string>; error?: string }
}
```

Navigation: `App.tsx`'s "New synthesis" tab (currently greyed out /
`cursor-not-allowed`) becomes a real, active tab routing to `<NewSynthesis />`.
Dashboard's two existing "+ New synthesis" buttons (header CTA and empty-state
CTA) navigate there too. Each step's "Continue →" is disabled until that
step's required fields are filled (matches `DESIGN_CONTEXT.md`'s stated rule);
"Back" decrements `step` without clearing any previously-entered data.

## 3. Active-synthesis marker and Dashboard integration

The CLI has no concept of a persisted "active synthesis" — every `generate`
invocation is a stateless one-shot. For the Dashboard to show something other
than its current always-empty state after a real generate, `/synthesis/generate`
writes a minimal local marker file, `~/.spps_assistant/last_synthesis.json`
(schema in §1 above).

The Dashboard's existing config-loading `useEffect` (in `Dashboard.tsx`) gains
a second fetch — a new `GET /synthesis/last` route (thin wrapper reading this
marker file, `{"ok": true, "data": null}` if it doesn't exist yet) — and
renders its existing empty-state card only when no marker is present;
otherwise renders a minimal "active synthesis" summary (name, vessel count,
generated-at) in its place. This is intentionally minimal: richer per-cycle
progress tracking is Phase 4's problem once the Cycle Guide view's real data
model exists — this phase does not try to anticipate that shape.

## 4. Post-generate flow

On a successful `/synthesis/generate` call, Step 5 shows a success state
(generated file paths + an "Open folder" button using the OS file manager via
a new, narrow main-process IPC handler — `shell.showItemInFolder`, no new
Node-integration surface in the renderer) and a "Done" action that navigates
back to the Dashboard, which now shows the active-synthesis summary from §3.
No placeholder/disabled "View cycle guide" button — that arrives for real in
Phase 4.

## 5. Error handling

Every sidecar call failure (bad FASTA, invalid token, save-residue failure,
generate failure) renders an inline error banner within the current step —
same visual pattern as `Dashboard.tsx`'s existing "Couldn't load
configuration" state — and never blocks navigation to already-completed
steps, per `DESIGN_CONTEXT.md` §10's rule that a single field/step error must
not block the whole UI.

## 6. Testing strategy

- **Backend:** Flask test-client tests per new route file (same pattern as
  existing `tests/api/`), covering success + validation-error paths. No new
  domain/application unit tests needed — this phase adds no new domain logic,
  only new call-sites into already-tested functions.
- **Frontend:**
  - `wizardReducer.ts`: pure unit tests for every action/transition, no
    rendering needed.
  - Each `StepN*.tsx`: RTL tests for its own rendering/validation logic in
    isolation, stubbing `window.spps.*` (same pattern as `Dashboard.test.tsx`).
  - `NewSynthesis.tsx`: one integration-style test driving all 5 steps
    end-to-end against a stubbed sidecar, verifying the full happy path
    reaches a successful generate and the success state renders.
- **Manual verification:** a real `npm run dev` smoke test through the whole
  wizard against the actual local sidecar, generating real files and
  confirming they match v1.0 CLI output for the same inputs (regression
  check, same discipline as Phase 2's Dashboard verification and the plan's
  own Phase 7 packaging smoke-test note).

## Explicitly out of scope for this phase

- Drag-and-drop file input (native "Browse" dialog only).
- A calculated yield/solubility preview on Step 5 (raw-selection summary only
  — yields/solubility become visible once Phase 4's Cycle Guide view exists).
- Any richer "active synthesis" / per-cycle progress model beyond the minimal
  marker file in §3 — that's Phase 4's responsibility once its real data
  shape is known.
- Windows-specific packaging/interpreter concerns (already tracked
  separately, project is macOS-first per the parent plan).
