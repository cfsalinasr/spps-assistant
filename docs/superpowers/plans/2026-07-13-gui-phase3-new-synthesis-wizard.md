# GUI Migration Phase 3: New Synthesis Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 5-step "New Synthesis" wizard end to end: three new Flask sidecar routes (`/sequences/parse`, `/residues`, `/synthesis/generate` + `/synthesis/last`) plus the React wizard that drives them, reaching a real `/synthesis/generate` call that writes real PDF/DOCX files — the same output the v1.0 CLI's `generate` command produces.

**Architecture:** Backend routes are thin wrappers around already-existing, already-tested `application`/`domain`/`infrastructure` logic (no new domain logic). The wizard holds all 5 steps' in-progress state in a single `useReducer` in `NewSynthesis.tsx`; each step is its own component reading/dispatching against that shared state via props. The main process gains new file/folder dialog handlers and new sidecar-proxying IPC handlers, both exposed to the renderer only through the existing typed `window.spps.*` preload bridge — the renderer never learns the sidecar's port/token, matching Phase 2's established security boundary.

**Tech Stack:** Flask, pytest (backend — unchanged from Phase 1). Electron, React, TypeScript, Vitest, React Testing Library, `@testing-library/user-event` (frontend — unchanged from Phase 2).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-12-gui-phase3-new-synthesis-wizard-design.md` — read it in full before starting; every task below implements a specific section of it.
- Parent plan: `/Users/cristiansalinas/Desktop/spps/SPPS_GUI_MIGRATION_PLAN.md` §5–§7.
- Python 3.11 (`python3.11`), run tests with `pytest` directly (on PATH at `/opt/homebrew/bin/pytest`).
- Node `v25.9.0` / npm `11.12.1`, run frontend tests with `npx vitest run` from `desktop/`.
- The API layer contains **no business logic** — only request/response marshalling and calls into `application`/`domain`/`infrastructure`, exactly like Phase 1's `/config` route.
- Response envelope convention (unchanged from Phase 1): `{"ok": true, "data": ...}` / `{"ok": false, "error": {"code": "...", "message": "..."}}`.
- The renderer process must **never** receive the sidecar's port or auth token. All sidecar HTTP calls happen in the main process; the renderer only calls `window.spps.*` methods.
- Do not mutate the real, persistent `~/.spps_assistant/spps_database.db` or `~/.spps_assistant/last_synthesis.json` from any automated test — Python-side tests use `tmp_path`-isolated repositories (matching Phase 1's `test_config_routes.py` fixture pattern); TypeScript-side tests that need a real running sidecar are restricted to read-only routes for exactly this reason (see Task 6).
- `build_config_from_defaults(config_defaults, volume_mode=None, output_dir=None, starting_num=None)` only accepts those 3 fields as explicit kwargs — every other `SynthesisConfig` field is read via `.get()` from its single dict argument. To apply arbitrary overrides, merge them into the dict *before* calling it (`{**config_repo.load(), **overrides}`), never pass them as `**kwargs`.
- TDD: for every task, write the failing test first, confirm it fails for the expected reason, then write the minimal code to pass it.
- Commit after each task with a focused message; do not squash multiple tasks into one commit.
- If a step's exact assertion/selector doesn't match what the actual rendered output looks like once real code is running, investigate and adapt precisely (matching Phase 2's established practice) — don't force a mismatched test to pass by weakening it.

---

### Task 1: `/sequences/parse` route

**Files:**
- Create: `spps_assistant/api/routes/sequences.py`
- Modify: `spps_assistant/api/app.py` (register the new blueprint)
- Test: `tests/api/test_sequences_routes.py`

**Interfaces:**
- Consumes: `parse_and_validate_sequences`, `build_vessels`, `load_materials_map` from `spps_assistant.application.sequence_loader` (existing, unmodified); `ok`/`err` from `spps_assistant.api.responses` (existing).
- Produces: `sequences_bp` Blueprint registering `POST /sequences/parse`, importable from `spps_assistant.api.routes.sequences`. Response `data.vessels` is a list of `{number, name, original_tokens, reversed_tokens, resin_mass_g, substitution_mmol_g}` dicts — Task 3 and every frontend step task after Task 4 rely on this exact shape (`ParsedVessel` in `wizardReducer.ts` mirrors it field-for-field).

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_sequences_routes.py`:

```python
"""Tests for the /sequences/parse route."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository

SIMPLE_FASTA = ">Peptide1\nAGLK\n>Peptide2\nFW\n"
SIMPLE_CSV = (
    "ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n"
    "A,,311.3,71.08,,Fmoc-Ala-OH\n"
    "G,,297.3,57.05,,Fmoc-Gly-OH\n"
)


@pytest.fixture
def app(tmp_path):
    """Flask app wired to a throwaway YAML config file, not the real user config."""
    config_path = tmp_path / 'spps_config.yaml'
    repo = YAMLConfigRepository(config_path)
    return create_app(config_repo=repo)


@pytest.fixture
def fasta_file(tmp_path):
    p = tmp_path / 'seqs.fasta'
    p.write_text(SIMPLE_FASTA, encoding='utf-8')
    return p


@pytest.fixture
def materials_file(tmp_path):
    p = tmp_path / 'mats.csv'
    p.write_text(SIMPLE_CSV, encoding='utf-8')
    return p


def test_parse_returns_vessels(app, fasta_file):
    client = app.test_client()

    resp = client.post('/sequences/parse', json={'fasta_path': str(fasta_file)})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    vessels = body['data']['vessels']
    assert len(vessels) == 2
    assert vessels[0]['name'] == 'Peptide1'
    assert vessels[0]['original_tokens'] == ['A', 'G', 'L', 'K']
    assert vessels[0]['reversed_tokens'] == ['K', 'L', 'G', 'A']
    assert 'materials_residue_map' not in body['data']


def test_parse_with_materials_file_includes_residue_map(app, fasta_file, materials_file):
    client = app.test_client()

    resp = client.post('/sequences/parse', json={
        'fasta_path': str(fasta_file),
        'materials_path': str(materials_file),
    })

    assert resp.status_code == 200
    body = resp.get_json()
    residue_map = body['data']['materials_residue_map']
    assert residue_map['A']['fmoc_mw'] == pytest.approx(311.3)
    assert residue_map['G']['free_mw'] == pytest.approx(57.05)


def test_parse_missing_fasta_path_returns_400(app):
    client = app.test_client()

    resp = client.post('/sequences/parse', json={})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_parse_invalid_fasta_file_returns_400(app, tmp_path):
    client = app.test_client()
    missing = tmp_path / 'nonexistent.fasta'

    resp = client.post('/sequences/parse', json={'fasta_path': str(missing)})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'parse_failed'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_sequences_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spps_assistant.api.routes.sequences'`

- [ ] **Step 3: Write the minimal implementation**

Create `spps_assistant/api/routes/sequences.py`:

```python
"""Sequence parsing route — Step 1 of the New Synthesis wizard."""

from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok

sequences_bp = Blueprint('sequences', __name__)


@sequences_bp.post('/sequences/parse')
def parse_sequences():
    """Parse a FASTA file (and optional materials file) into vessels."""
    from spps_assistant.application.sequence_loader import (
        build_vessels, load_materials_map, parse_and_validate_sequences,
    )

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('fasta_path'):
        return err('invalid_body', 'Request body must include "fasta_path"'), 400

    fasta_path = body['fasta_path']
    materials_path = body.get('materials_path')

    config_repo = current_app.config['CONFIG_REPO']
    config_defaults = config_repo.load()
    starting_num = int(config_defaults.get('starting_vessel_number', 1))
    substitution_mmol_g = float(config_defaults.get('substitution_mmol_g', 0.3))

    try:
        parsed_sequences = parse_and_validate_sequences(Path(fasta_path))
    except ValueError as exc:
        return err('parse_failed', str(exc)), 400

    vessels = build_vessels(
        parsed_sequences, starting_num, substitution_mmol_g=substitution_mmol_g,
    )

    data = {
        'vessels': [
            {
                'number': v.number,
                'name': v.name,
                'original_tokens': v.original_tokens,
                'reversed_tokens': v.reversed_tokens,
                'resin_mass_g': v.resin_mass_g,
                'substitution_mmol_g': v.substitution_mmol_g,
            }
            for v in vessels
        ]
    }

    if materials_path:
        try:
            materials_map = load_materials_map(Path(materials_path))
        except ValueError as exc:
            return err('materials_parse_failed', str(exc)), 400
        data['materials_residue_map'] = {
            token: asdict(info) for token, info in materials_map.items()
        }

    return ok(data)
```

Modify `spps_assistant/api/app.py` — add the import:

```python
from spps_assistant.api.routes.sequences import sequences_bp
```

and register the blueprint (after `app.register_blueprint(config_bp)`):

```python
    app.register_blueprint(sequences_bp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_sequences_routes.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add spps_assistant/api/routes/sequences.py spps_assistant/api/app.py tests/api/test_sequences_routes.py
git commit -m "feat(api): add POST /sequences/parse route"
```

---

### Task 2: `create_app` DB injection + `/residues` routes

**Files:**
- Modify: `spps_assistant/api/app.py` (add `db` param, register the new blueprint)
- Create: `spps_assistant/api/routes/residues.py`
- Test: `tests/api/test_residues_routes.py`

**Interfaces:**
- Consumes: `SQLiteRepository` from `spps_assistant.infrastructure.sqlite_repository` (existing — `save_residue(token, base_code, protection, fmoc_mw, free_mw, ...)`, `get_residue(token) -> Optional[ResidueInfo]`, `list_residues() -> List[Dict]`); `DatabaseRepository` port from `spps_assistant.application.ports` (existing).
- Produces: `create_app(..., db: Optional[DatabaseRepository] = None)` — every later task that needs a DB-backed test app passes `db=SQLiteRepository(tmp_path / 'test.db')` the same way Task 1 passes `config_repo=`. `residues_bp` Blueprint registering `GET /residues` and `POST /residues`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_residues_routes.py`:

```python
"""Tests for the /residues routes."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository


@pytest.fixture
def app(tmp_path):
    """Flask app wired to a throwaway SQLite DB, not the real user database."""
    db_path = tmp_path / 'spps_database.db'
    db = SQLiteRepository(db_path)
    return create_app(db=db)


def test_get_residues_returns_empty_list_initially(app):
    client = app.test_client()

    resp = client.get('/residues')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data'] == []


def test_post_residue_saves_and_returns_it(app):
    client = app.test_client()

    resp = client.post('/residues', json={
        'token': 'A', 'base_code': 'A', 'protection': '',
        'fmoc_mw': 311.3, 'free_mw': 71.08,
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data']['token'] == 'A'
    assert body['data']['fmoc_mw'] == pytest.approx(311.3)


def test_post_residue_then_get_residues_includes_it(app):
    client = app.test_client()
    client.post('/residues', json={
        'token': 'A', 'base_code': 'A', 'protection': '',
        'fmoc_mw': 311.3, 'free_mw': 71.08,
    })

    resp = client.get('/residues')

    tokens = [r['token'] for r in resp.get_json()['data']]
    assert 'A' in tokens


def test_post_residue_missing_token_returns_400(app):
    client = app.test_client()

    resp = client.post('/residues', json={'fmoc_mw': 1.0, 'free_mw': 1.0})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_post_residue_invalid_mw_returns_400(app):
    client = app.test_client()

    resp = client.post('/residues', json={'token': 'A', 'fmoc_mw': 'not-a-number', 'free_mw': 1.0})

    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_residues_routes.py -v`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'db'`

- [ ] **Step 3: Write the minimal implementation**

Create `spps_assistant/api/routes/residues.py`:

```python
"""Residue MW library routes — Step 2 of the New Synthesis wizard."""

from dataclasses import asdict

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok

residues_bp = Blueprint('residues', __name__)


@residues_bp.get('/residues')
def list_residues():
    """Return every residue MW record in the library."""
    db = current_app.config['DB_REPO']
    return ok(db.list_residues())


@residues_bp.post('/residues')
def save_residue():
    """Upsert a single residue MW record."""
    db = current_app.config['DB_REPO']
    body = request.get_json(silent=True)

    if not isinstance(body, dict) or not body.get('token'):
        return err('invalid_body', 'Request body must include "token"'), 400

    try:
        db.save_residue(
            token=body['token'],
            base_code=body.get('base_code', body['token']),
            protection=body.get('protection', ''),
            fmoc_mw=float(body['fmoc_mw']),
            free_mw=float(body['free_mw']),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return err('invalid_body', f'Invalid residue record: {exc}'), 400

    saved = db.get_residue(body['token'])
    return ok(asdict(saved))
```

Modify `spps_assistant/api/app.py` to its full new state:

```python
"""Flask app factory for the SPPS Assistant API sidecar."""

import hmac
from typing import Any, Dict, Optional, Tuple

from flask import Flask, request

from spps_assistant.api.responses import err
from spps_assistant.api.routes.config import config_bp
from spps_assistant.api.routes.health import health_bp
from spps_assistant.api.routes.residues import residues_bp
from spps_assistant.api.routes.sequences import sequences_bp
from spps_assistant.application.ports import ConfigRepository, DatabaseRepository

AUTH_HEADER = 'X-SPPS-Sidecar-Token'


def create_app(
    config_repo: Optional[ConfigRepository] = None,
    auth_token: Optional[str] = None,
    db: Optional[DatabaseRepository] = None,
) -> Flask:
    """Build and configure the Flask application.

    Args:
        config_repo: ConfigRepository implementation to use for /config
            routes. Defaults to a real YAMLConfigRepository (constructed
            lazily to avoid importing infrastructure at module load time
            for routes that don't need it).
        auth_token: shared-secret token required on the X-SPPS-Sidecar-Token
            header of every request. When None (the default, used by tests
            and any direct create_app() call), no authentication is
            enforced. The real entrypoint (spps_assistant.api.__main__)
            always passes a randomly generated token, so every real
            deployment is protected — only direct create_app() usage is
            open by default.
        db: DatabaseRepository implementation to use for /residues and
            /synthesis routes. Defaults to a real SQLiteRepository
            (constructed lazily, same reasoning as config_repo).
    """
    app = Flask(__name__)

    if config_repo is None:
        from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository
        config_repo = YAMLConfigRepository()
    app.config['CONFIG_REPO'] = config_repo

    if db is None:
        from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
        db = SQLiteRepository()
    app.config['DB_REPO'] = db

    if auth_token is not None:
        @app.before_request
        def _require_sidecar_token() -> Optional[Tuple[Dict[str, Any], int]]:
            if not hmac.compare_digest(request.headers.get(AUTH_HEADER, ''), auth_token):
                return err('unauthorized', 'Missing or invalid sidecar token'), 401
            return None

    app.register_blueprint(health_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(sequences_bp)
    app.register_blueprint(residues_bp)

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_residues_routes.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full API test suite so far**

Run: `pytest tests/api/ -v`
Expected: all previously-passing tests plus these 5 still pass, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/api/app.py spps_assistant/api/routes/residues.py tests/api/test_residues_routes.py
git commit -m "feat(api): add db injection to create_app, GET/POST /residues routes"
```

---

### Task 3: `/synthesis/generate` + `/synthesis/last` routes

**Files:**
- Create: `spps_assistant/api/routes/synthesis.py`
- Modify: `spps_assistant/api/app.py` (register the new blueprint)
- Test: `tests/api/test_synthesis_routes.py`

**Interfaces:**
- Consumes: `build_config_from_defaults`, `apply_target_resin_mass`, `calc_yields_and_solubility`, `SynthesisGuideUseCase` from `spps_assistant.application.synthesis_guide` (existing, unmodified); `Vessel`, `ResidueInfo` from `spps_assistant.domain.models` (existing).
- Produces: `synthesis_bp` Blueprint registering `POST /synthesis/generate` and `GET /synthesis/last`. `POST /synthesis/generate`'s `data` is the `output_paths` dict `SynthesisGuideUseCase.run` already returns. `GET /synthesis/last`'s `data` is `{"name", "output_directory", "generated_at", "vessel_count"}` or `null` — Task 13's Dashboard integration relies on this exact shape.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_synthesis_routes.py`:

```python
"""Tests for the /synthesis/generate and /synthesis/last routes."""

import pytest

from spps_assistant.api.app import create_app
from spps_assistant.infrastructure.sqlite_repository import SQLiteRepository
from spps_assistant.infrastructure.yaml_config import YAMLConfigRepository


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app wired to throwaway config/DB, with the marker file redirected
    to a tmp path so this test never touches the real
    ~/.spps_assistant/last_synthesis.json."""
    import spps_assistant.api.routes.synthesis as synthesis_module

    config_path = tmp_path / 'spps_config.yaml'
    db_path = tmp_path / 'spps_database.db'
    marker_path = tmp_path / 'last_synthesis.json'
    monkeypatch.setattr(synthesis_module, '_MARKER_PATH', marker_path)

    config_repo = YAMLConfigRepository(config_path)
    db = SQLiteRepository(db_path)
    return create_app(config_repo=config_repo, db=db)


def _vessel_payload(number, name, tokens):
    return {
        'number': number, 'name': name,
        'original_tokens': tokens, 'reversed_tokens': list(reversed(tokens)),
        'resin_mass_g': 0.1, 'substitution_mmol_g': 0.3,
    }


def _residue_payload(fmoc_mw=311.3, free_mw=71.08):
    return {'base_code': 'A', 'protection': '', 'fmoc_mw': fmoc_mw, 'free_mw': free_mw}


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


def test_last_synthesis_returns_null_when_none_generated(app):
    client = app.test_client()

    resp = client.get('/synthesis/last')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['ok'] is True
    assert body['data'] is None


def test_generate_missing_vessels_returns_400(app):
    client = app.test_client()

    resp = client.post('/synthesis/generate', json={})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_generate_target_yield_strategy_backcalculates_resin_mass(app, tmp_path):
    client = app.test_client()
    out_dir = tmp_path / 'output'

    resp = client.post('/synthesis/generate', json={
        'vessels': [_vessel_payload(1, 'Pep1', ['A'])],
        'residue_info_map': {'A': _residue_payload()},
        'config_overrides': {
            'name': 'TargetRun',
            'output_directory': str(out_dir),
            'resin_mass_strategy': 'target',
            'target_yield_mg': 50.0,
        },
    })

    assert resp.status_code == 200
    assert len(list(out_dir.glob('*.pdf'))) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_synthesis_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spps_assistant.api.routes.synthesis'`

- [ ] **Step 3: Write the minimal implementation**

Create `spps_assistant/api/routes/synthesis.py`:

```python
"""Synthesis generation routes — final steps of the New Synthesis wizard."""

import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, request

from spps_assistant.api.responses import err, ok
from spps_assistant.domain.models import ResidueInfo, Vessel

synthesis_bp = Blueprint('synthesis', __name__)

_MARKER_PATH = Path.home() / '.spps_assistant' / 'last_synthesis.json'


def _vessel_from_dict(data: dict) -> Vessel:
    return Vessel(
        number=data['number'],
        name=data['name'],
        original_tokens=data['original_tokens'],
        reversed_tokens=data['reversed_tokens'],
        resin_mass_g=data.get('resin_mass_g', 0.1),
        substitution_mmol_g=data.get('substitution_mmol_g', 0.3),
    )


def _residue_info_from_dict(token: str, data: dict) -> ResidueInfo:
    return ResidueInfo(
        token=token,
        base_code=data.get('base_code', token),
        protection=data.get('protection', ''),
        fmoc_mw=float(data['fmoc_mw']),
        free_mw=float(data['free_mw']),
        stock_conc=float(data.get('stock_conc', 0.5)),
        density_g_ml=data.get('density_g_ml'),
        equivalents_multiplier=float(data.get('equivalents_multiplier', 1.0)),
    )


@synthesis_bp.post('/synthesis/generate')
def generate_synthesis():
    """Run the full synthesis guide generation workflow and write real output files."""
    from spps_assistant.application.synthesis_guide import (
        SynthesisGuideUseCase, apply_target_resin_mass,
        build_config_from_defaults, calc_yields_and_solubility,
    )

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('vessels'):
        return err('invalid_body', 'Request body must include "vessels"'), 400

    try:
        vessels = [_vessel_from_dict(v) for v in body['vessels']]
        residue_info_map = {
            token: _residue_info_from_dict(token, data)
            for token, data in body.get('residue_info_map', {}).items()
        }
    except (KeyError, TypeError, ValueError) as exc:
        return err('invalid_body', f'Invalid vessel or residue data: {exc}'), 400

    config_repo = current_app.config['CONFIG_REPO']
    db = current_app.config['DB_REPO']
    config_overrides = body.get('config_overrides', {})
    merged_defaults = {**config_repo.load(), **config_overrides}

    try:
        config = build_config_from_defaults(merged_defaults)
    except ValueError as exc:
        return err('invalid_config', str(exc)), 400

    if config.resin_mass_strategy == 'target':
        try:
            apply_target_resin_mass(vessels, config, residue_info_map)
        except ValueError as exc:
            return err('resin_mass_failed', str(exc)), 400

    yield_results, solubility_results = calc_yields_and_solubility(vessels, residue_info_map)

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
        return err('generate_failed', str(exc)), 500

    _MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MARKER_PATH.write_text(json.dumps({
        'name': config.name,
        'output_directory': config.output_directory,
        'generated_at': datetime.now().isoformat(),
        'vessel_count': len(vessels),
    }), encoding='utf-8')

    return ok(output_paths)


@synthesis_bp.get('/synthesis/last')
def last_synthesis():
    """Return the most recently generated synthesis's marker data, if any."""
    if not _MARKER_PATH.exists():
        return ok(None)
    return ok(json.loads(_MARKER_PATH.read_text(encoding='utf-8')))
```

Modify `spps_assistant/api/app.py` — add the import:

```python
from spps_assistant.api.routes.synthesis import synthesis_bp
```

and register the blueprint (after `app.register_blueprint(residues_bp)`):

```python
    app.register_blueprint(synthesis_bp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_synthesis_routes.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `pytest -v`
Expected: every previously-passing test (332 from before this phase) plus all `tests/api/` tests from Tasks 1–3 pass, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add spps_assistant/api/routes/synthesis.py spps_assistant/api/app.py tests/api/test_synthesis_routes.py
git commit -m "feat(api): add POST /synthesis/generate and GET /synthesis/last routes"
```

---

## Backend complete after Task 3

Tasks 1–3 are the entire backend surface this phase needs (`/sequences/parse`, `/residues`, `/synthesis/generate`, `/synthesis/last`), all built on top of already-tested `application`/`domain`/`infrastructure` code with no new business logic. Tasks 4 onward build the frontend wizard that drives them.

---

### Task 4: Wizard reducer

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/wizardReducer.ts`
- Test: `desktop/src/renderer/src/views/new-synthesis/wizardReducer.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `WizardState`, `WizardAction`, `ParsedVessel`, `ResidueMwEntry`, `ReagentsState`, `ResinState`, `GenerateResult` types, `initialWizardState`, and `wizardReducer(state, action) -> WizardState`, all importable from `./wizardReducer`. Every step component task (7–11) and the shell (Task 12) import these exact names — this is the single source of truth for the wizard's data shape.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/wizardReducer.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { initialWizardState, wizardReducer, type ResidueMwEntry } from './wizardReducer'

describe('wizardReducer', () => {
  it('SET_STEP updates the current step', () => {
    const next = wizardReducer(initialWizardState, { type: 'SET_STEP', step: 3 })
    expect(next.step).toBe(3)
  })

  it('SET_SEQUENCES stores parsed vessels and the seeded residue map', () => {
    const residueMap: Record<string, ResidueMwEntry> = {
      A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08, origin: 'materials' }
    }
    const next = wizardReducer(initialWizardState, {
      type: 'SET_SEQUENCES',
      fastaPath: '/tmp/seqs.fasta',
      materialsPath: '/tmp/mats.csv',
      vessels: [
        {
          number: 1,
          name: 'Pep1',
          original_tokens: ['A'],
          reversed_tokens: ['A'],
          resin_mass_g: 0.1,
          substitution_mmol_g: 0.3
        }
      ],
      residueMap
    })
    expect(next.fastaPath).toBe('/tmp/seqs.fasta')
    expect(next.materialsPath).toBe('/tmp/mats.csv')
    expect(next.vessels).toHaveLength(1)
    expect(next.residueMap).toEqual(residueMap)
  })

  it('SET_RESIDUE_MAP replaces the whole residue map', () => {
    const residueMap: Record<string, ResidueMwEntry> = {
      A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08, origin: 'db' },
      G: { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05, origin: 'db' }
    }
    const next = wizardReducer(initialWizardState, { type: 'SET_RESIDUE_MAP', residueMap })
    expect(next.residueMap).toEqual(residueMap)
  })

  it('SET_RESIDUE merges a single edited residue into the existing map without dropping others', () => {
    const withOne = wizardReducer(initialWizardState, {
      type: 'SET_RESIDUE_MAP',
      residueMap: {
        A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08, origin: 'db' }
      }
    })
    const next = wizardReducer(withOne, {
      type: 'SET_RESIDUE',
      token: 'G',
      entry: { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05, origin: 'manual' }
    })
    expect(Object.keys(next.residueMap)).toEqual(['A', 'G'])
    expect(next.residueMap.G.origin).toBe('manual')
  })

  it('SET_REAGENTS shallow-merges partial reagent updates', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_REAGENTS',
      reagents: { activator: 'DIC', base: 'None (DIC/DCC)' }
    })
    expect(next.reagents.activator).toBe('DIC')
    expect(next.reagents.base).toBe('None (DIC/DCC)')
    expect(next.reagents.deprotectionReagent).toBe('Piperidine 20%')
  })

  it('SET_RESIN shallow-merges partial resin updates', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_RESIN',
      resin: { strategy: 'target', targetYieldMg: 50 }
    })
    expect(next.resin.strategy).toBe('target')
    expect(next.resin.targetYieldMg).toBe(50)
    expect(next.resin.substitutionMmolG).toBe(0.3)
  })

  it('SET_OUTPUT_DIRECTORY updates the output directory', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_OUTPUT_DIRECTORY',
      outputDirectory: '/Users/me/output'
    })
    expect(next.outputDirectory).toBe('/Users/me/output')
  })

  it('SET_SYNTHESIS_NAME updates the synthesis name', () => {
    const next = wizardReducer(initialWizardState, { type: 'SET_SYNTHESIS_NAME', name: 'BatchA' })
    expect(next.synthesisName).toBe('BatchA')
  })

  it('GENERATE_START sets status to generating', () => {
    const next = wizardReducer(initialWizardState, { type: 'GENERATE_START' })
    expect(next.generateResult).toEqual({ status: 'generating' })
  })

  it('GENERATE_SUCCESS sets status to success with paths', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'GENERATE_SUCCESS',
      paths: { cycle_guide_pdf: '/out/x.pdf' }
    })
    expect(next.generateResult).toEqual({ status: 'success', paths: { cycle_guide_pdf: '/out/x.pdf' } })
  })

  it('GENERATE_ERROR sets status to error with a message', () => {
    const next = wizardReducer(initialWizardState, { type: 'GENERATE_ERROR', error: 'boom' })
    expect(next.generateResult).toEqual({ status: 'error', error: 'boom' })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/renderer/src/views/new-synthesis/wizardReducer.test.ts` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./wizardReducer`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/wizardReducer.ts`:

```typescript
export interface ParsedVessel {
  number: number
  name: string
  original_tokens: string[]
  reversed_tokens: string[]
  resin_mass_g: number
  substitution_mmol_g: number
}

export interface ResidueMwEntry {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
  origin: 'db' | 'materials' | 'manual'
}

export interface ReagentsState {
  deprotectionReagent: string
  activator: string
  useOxyma: boolean
  base: string
  volumeMode: 'stoichiometry' | 'legacy'
  completenessTest: 'bromophenol' | 'kaiser' | 'none'
}

export interface ResinState {
  strategy: 'fixed' | 'target'
  substitutionMmolG: number
  fixedResinMassG: number
  targetYieldMg: number | null
}

export interface GenerateResult {
  status: 'idle' | 'generating' | 'success' | 'error'
  paths?: Record<string, string>
  error?: string
}

export interface WizardState {
  step: 1 | 2 | 3 | 4 | 5
  synthesisName: string
  fastaPath: string | null
  materialsPath: string | null
  vessels: ParsedVessel[]
  residueMap: Record<string, ResidueMwEntry>
  reagents: ReagentsState
  resin: ResinState
  outputDirectory: string
  generateResult: GenerateResult
}

export const initialWizardState: WizardState = {
  step: 1,
  synthesisName: 'MySynthesis',
  fastaPath: null,
  materialsPath: null,
  vessels: [],
  residueMap: {},
  reagents: {
    deprotectionReagent: 'Piperidine 20%',
    activator: 'HBTU',
    useOxyma: true,
    base: 'DIEA',
    volumeMode: 'stoichiometry',
    completenessTest: 'bromophenol'
  },
  resin: {
    strategy: 'fixed',
    substitutionMmolG: 0.3,
    fixedResinMassG: 0.1,
    targetYieldMg: null
  },
  outputDirectory: 'spps_output',
  generateResult: { status: 'idle' }
}

export type WizardAction =
  | { type: 'SET_STEP'; step: WizardState['step'] }
  | {
      type: 'SET_SEQUENCES'
      fastaPath: string
      materialsPath: string | null
      vessels: ParsedVessel[]
      residueMap: Record<string, ResidueMwEntry>
    }
  | { type: 'SET_RESIDUE_MAP'; residueMap: Record<string, ResidueMwEntry> }
  | { type: 'SET_RESIDUE'; token: string; entry: ResidueMwEntry }
  | { type: 'SET_REAGENTS'; reagents: Partial<ReagentsState> }
  | { type: 'SET_RESIN'; resin: Partial<ResinState> }
  | { type: 'SET_OUTPUT_DIRECTORY'; outputDirectory: string }
  | { type: 'SET_SYNTHESIS_NAME'; name: string }
  | { type: 'GENERATE_START' }
  | { type: 'GENERATE_SUCCESS'; paths: Record<string, string> }
  | { type: 'GENERATE_ERROR'; error: string }

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.step }
    case 'SET_SEQUENCES':
      return {
        ...state,
        fastaPath: action.fastaPath,
        materialsPath: action.materialsPath,
        vessels: action.vessels,
        residueMap: action.residueMap
      }
    case 'SET_RESIDUE_MAP':
      return { ...state, residueMap: action.residueMap }
    case 'SET_RESIDUE':
      return {
        ...state,
        residueMap: { ...state.residueMap, [action.token]: action.entry }
      }
    case 'SET_REAGENTS':
      return { ...state, reagents: { ...state.reagents, ...action.reagents } }
    case 'SET_RESIN':
      return { ...state, resin: { ...state.resin, ...action.resin } }
    case 'SET_OUTPUT_DIRECTORY':
      return { ...state, outputDirectory: action.outputDirectory }
    case 'SET_SYNTHESIS_NAME':
      return { ...state, synthesisName: action.name }
    case 'GENERATE_START':
      return { ...state, generateResult: { status: 'generating' } }
    case 'GENERATE_SUCCESS':
      return { ...state, generateResult: { status: 'success', paths: action.paths } }
    case 'GENERATE_ERROR':
      return { ...state, generateResult: { status: 'error', error: action.error } }
    default:
      return state
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/renderer/src/views/new-synthesis/wizardReducer.test.ts`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/wizardReducer.ts desktop/src/renderer/src/views/new-synthesis/wizardReducer.test.ts
git commit -m "feat(desktop): add New Synthesis wizard reducer"
```

---

### Task 5: Main-process file/folder dialogs + preload wiring

**Files:**
- Create: `desktop/src/main/dialogs.ts`
- Test: `desktop/src/main/dialogs.test.ts`
- Modify: `desktop/src/main/index.ts` (register the new handlers)
- Modify: `desktop/src/preload/index.ts` (expose the new methods)
- Modify: `desktop/src/preload/index.d.ts` (add the new type signatures)

**Interfaces:**
- Consumes: `dialog`, `shell` from `electron` (native APIs, unmodified).
- Produces: `registerDialogHandlers(ipcMain: Electron.IpcMain): void`, importable from `./dialogs`, registering `spps:pickFastaFile`, `spps:pickMaterialsFile`, `spps:pickOutputDirectory`, `spps:openFolder`. Produces the renderer-facing `window.spps.pickFastaFile()`, `.pickMaterialsFile()`, `.pickOutputDirectory()` (each `Promise<string | null>`) and `.openFolder(path)` (`Promise<void>`) — Task 7's Step 1, Task 11's Step 5, and Task 13's Dashboard all call these.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/main/dialogs.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest'

const showOpenDialogMock = vi.fn()
const showItemInFolderMock = vi.fn()
const ipcMainHandlers: Record<string, (...args: unknown[]) => unknown> = {}

vi.mock('electron', () => ({
  dialog: { showOpenDialog: (...args: unknown[]) => showOpenDialogMock(...args) },
  shell: { showItemInFolder: (...args: unknown[]) => showItemInFolderMock(...args) },
  ipcMain: {
    handle: (channel: string, handler: (...args: unknown[]) => unknown) => {
      ipcMainHandlers[channel] = handler
    }
  }
}))

import { ipcMain } from 'electron'
import { registerDialogHandlers } from './dialogs'

describe('registerDialogHandlers', () => {
  beforeEach(() => {
    showOpenDialogMock.mockReset()
    showItemInFolderMock.mockReset()
    for (const key of Object.keys(ipcMainHandlers)) delete ipcMainHandlers[key]
    registerDialogHandlers(ipcMain)
  })

  it('spps:pickFastaFile returns the chosen path', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/seqs.fasta'] })
    const result = await ipcMainHandlers['spps:pickFastaFile']()
    expect(result).toBe('/tmp/seqs.fasta')
    expect(showOpenDialogMock).toHaveBeenCalledWith(
      expect.objectContaining({ filters: [{ name: 'FASTA', extensions: ['fasta', 'fa', 'txt'] }] })
    )
  })

  it('spps:pickFastaFile returns null when the user cancels', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: true, filePaths: [] })
    const result = await ipcMainHandlers['spps:pickFastaFile']()
    expect(result).toBeNull()
  })

  it('spps:pickMaterialsFile returns the chosen path', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/mats.csv'] })
    const result = await ipcMainHandlers['spps:pickMaterialsFile']()
    expect(result).toBe('/tmp/mats.csv')
  })

  it('spps:pickOutputDirectory returns the chosen directory', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/out'] })
    const result = await ipcMainHandlers['spps:pickOutputDirectory']()
    expect(result).toBe('/tmp/out')
    expect(showOpenDialogMock).toHaveBeenCalledWith(
      expect.objectContaining({ properties: ['openDirectory', 'createDirectory'] })
    )
  })

  it('spps:openFolder calls shell.showItemInFolder with the given path', () => {
    ipcMainHandlers['spps:openFolder'](null, '/tmp/out/file.pdf')
    expect(showItemInFolderMock).toHaveBeenCalledWith('/tmp/out/file.pdf')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/main/dialogs.test.ts` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./dialogs`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/main/dialogs.ts`:

```typescript
import { dialog, shell, type IpcMain } from 'electron'

/**
 * Registers native file/folder picker IPC handlers used by the New Synthesis
 * wizard. These are the only place in the app that ever calls Electron's
 * dialog/shell APIs — the renderer only ever sees resolved path strings (or
 * null if the user cancels) through the typed window.spps.* preload bridge.
 */
export function registerDialogHandlers(ipcMain: IpcMain): void {
  ipcMain.handle('spps:pickFastaFile', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'FASTA', extensions: ['fasta', 'fa', 'txt'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:pickMaterialsFile', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'Materials', extensions: ['csv', 'xlsx'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:pickOutputDirectory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory', 'createDirectory']
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:openFolder', (_event, folderPath: string) => {
    shell.showItemInFolder(folderPath)
  })
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/main/dialogs.test.ts`
Expected: 5 passed

- [ ] **Step 5: Wire the handlers into the main process**

Modify `desktop/src/main/index.ts` — add the import:

```typescript
import { registerDialogHandlers } from './dialogs'
```

and register the handlers inside `app.whenReady().then(async () => { ... })`, right after the existing `registerConfigHandlers(...)` call:

```typescript
    registerDialogHandlers(ipcMain)
```

- [ ] **Step 6: Expose the new methods in the preload script**

Modify `desktop/src/preload/index.ts` — extend the `spps` object to:

```typescript
const spps = {
  getConfig: () => ipcRenderer.invoke('spps:getConfig'),
  setConfig: (data: Record<string, unknown>) => ipcRenderer.invoke('spps:setConfig', data),
  pickFastaFile: () => ipcRenderer.invoke('spps:pickFastaFile'),
  pickMaterialsFile: () => ipcRenderer.invoke('spps:pickMaterialsFile'),
  pickOutputDirectory: () => ipcRenderer.invoke('spps:pickOutputDirectory'),
  openFolder: (path: string) => ipcRenderer.invoke('spps:openFolder', path)
}
```

- [ ] **Step 7: Add the type signatures**

Modify `desktop/src/preload/index.d.ts` — extend the `SppsApi` interface to:

```typescript
export interface SppsApi {
  getConfig: () => Promise<SppsEnvelope>
  setConfig: (data: Record<string, unknown>) => Promise<SppsEnvelope>
  pickFastaFile: () => Promise<string | null>
  pickMaterialsFile: () => Promise<string | null>
  pickOutputDirectory: () => Promise<string | null>
  openFolder: (path: string) => Promise<void>
}
```

- [ ] **Step 8: Run typecheck**

Run: `npm run typecheck` (from `desktop/`)
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/main/dialogs.ts desktop/src/main/dialogs.test.ts desktop/src/main/index.ts desktop/src/preload/index.ts desktop/src/preload/index.d.ts
git commit -m "feat(desktop): add native file/folder dialog IPC handlers"
```

---

### Task 6: Main-process synthesis IPC bridge + preload wiring

**Files:**
- Modify: `desktop/src/main/api-bridge.ts` (add `registerSynthesisHandlers`)
- Modify: `desktop/src/main/api-bridge.test.ts` (add real-sidecar tests for the new routes)
- Modify: `desktop/src/main/index.ts` (register the new handlers)
- Modify: `desktop/src/preload/index.ts` (expose the new methods)
- Modify: `desktop/src/preload/index.d.ts` (add the new type signatures)

**Interfaces:**
- Consumes: `fetchFromSidecar`, `SidecarInfo` from `./sidecar`/`./api-bridge` (existing, Phase 2); the 4 routes built in Tasks 1–3.
- Produces: `registerSynthesisHandlers(ipcMain, getSidecarInfo): void`, registering `spps:parseSequences`, `spps:getResidues`, `spps:saveResidue`, `spps:generateSynthesis`, `spps:getLastSynthesis`. Produces the renderer-facing `window.spps.parseSequences(fastaPath, materialsPath)`, `.getResidues()`, `.saveResidue(residue)`, `.generateSynthesis(payload)`, `.getLastSynthesis()` — every step component task (7–11) and Task 13's Dashboard call these.

Only `/sequences/parse` (reads a temp file, no persistent side effects) and `GET /synthesis/last`/`GET /residues` (read-only) are exercised against a real running sidecar in this task's test — `POST /residues` and `POST /synthesis/generate` write to the real, persistent `~/.spps_assistant` database/marker file with no way to redirect them from this process (the standalone sidecar entrypoint always uses the real paths), so mutating-route correctness is covered by Task 2/3's isolated Python-side Flask tests instead, and the IPC wiring itself is covered by Task 12's stubbed-sidecar integration test plus the manual smoke test in Task 13.

- [ ] **Step 1: Write the failing tests**

Modify `desktop/src/main/api-bridge.test.ts` — add these imports at the top (alongside the existing ones):

```typescript
import { writeFileSync, unlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
```

and append this new `describe` block at the end of the file:

```typescript
describe('registerSynthesisHandlers routes via fetchFromSidecar', () => {
  it('POST /sequences/parse returns vessels for a real FASTA file', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      const fastaPath = join(tmpdir(), `spps-test-${Date.now()}.fasta`)
      writeFileSync(fastaPath, '>Pep1\nAG\n')
      try {
        const result = (await fetchFromSidecar(handle.info, '/sequences/parse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fasta_path: fastaPath, materials_path: null })
        })) as { ok: boolean; data: { vessels: Array<{ name: string }> } }
        expect(result.ok).toBe(true)
        expect(result.data.vessels[0].name).toBe('Pep1')
      } finally {
        unlinkSync(fastaPath)
      }
    } finally {
      stopSidecar(handle)
    }
  }, 15000)

  it('GET /residues returns a real, structurally-shaped list (read-only — no test mutates the real residue DB)', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      const result = (await fetchFromSidecar(handle.info, '/residues')) as {
        ok: boolean
        data: unknown[]
      }
      expect(result.ok).toBe(true)
      expect(Array.isArray(result.data)).toBe(true)
    } finally {
      stopSidecar(handle)
    }
  }, 15000)

  it('GET /synthesis/last responds with the ok envelope shape (read-only)', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      const result = (await fetchFromSidecar(handle.info, '/synthesis/last')) as {
        ok: boolean
        data: unknown
      }
      expect(result.ok).toBe(true)
    } finally {
      stopSidecar(handle)
    }
  }, 15000)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/main/api-bridge.test.ts` (from `desktop/`)
Expected: FAIL — the sidecar's Python side already has these routes (Tasks 1–3), so these specific tests may actually pass immediately once the sidecar responds; if so, skip straight to Step 4 confirming green, since there's no new *frontend* code to be RED against yet at this exact point (the real RED/GREEN cycle for this task is `registerSynthesisHandlers` itself, exercised via the wiring — proceed to Step 3 regardless, since `registerSynthesisHandlers` doesn't exist yet and Step 5's `index.ts` wiring would fail to typecheck without it).

- [ ] **Step 3: Write the minimal implementation**

Modify `desktop/src/main/api-bridge.ts` — append this function after the existing `registerConfigHandlers`:

```typescript
export function registerSynthesisHandlers(
  ipcMain: Electron.IpcMain,
  getSidecarInfo: () => SidecarInfo
): void {
  ipcMain.handle(
    'spps:parseSequences',
    (_event, fastaPath: string, materialsPath: string | null) =>
      fetchFromSidecar(getSidecarInfo(), '/sequences/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fasta_path: fastaPath, materials_path: materialsPath })
      })
  )

  ipcMain.handle('spps:getResidues', () => fetchFromSidecar(getSidecarInfo(), '/residues'))

  ipcMain.handle('spps:saveResidue', (_event, residue: Record<string, unknown>) =>
    fetchFromSidecar(getSidecarInfo(), '/residues', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(residue)
    })
  )

  ipcMain.handle('spps:generateSynthesis', (_event, payload: Record<string, unknown>) =>
    fetchFromSidecar(getSidecarInfo(), '/synthesis/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  )

  ipcMain.handle('spps:getLastSynthesis', () =>
    fetchFromSidecar(getSidecarInfo(), '/synthesis/last')
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/main/api-bridge.test.ts`
Expected: 5 passed (2 pre-existing + 3 new).

- [ ] **Step 5: Wire the handlers into the main process**

Modify `desktop/src/main/index.ts` — add `registerSynthesisHandlers` to the existing import from `./api-bridge`:

```typescript
import { registerConfigHandlers, registerSynthesisHandlers } from './api-bridge'
```

and register it inside `app.whenReady().then(async () => { ... })`, right after `registerConfigHandlers(...)`:

```typescript
    registerSynthesisHandlers(ipcMain, () => {
      if (!sidecarHandle) throw new Error('Sidecar is not running')
      return sidecarHandle.info
    })
```

- [ ] **Step 6: Expose the new methods in the preload script**

Modify `desktop/src/preload/index.ts` — extend the `spps` object (from Task 5's state) to:

```typescript
const spps = {
  getConfig: () => ipcRenderer.invoke('spps:getConfig'),
  setConfig: (data: Record<string, unknown>) => ipcRenderer.invoke('spps:setConfig', data),
  pickFastaFile: () => ipcRenderer.invoke('spps:pickFastaFile'),
  pickMaterialsFile: () => ipcRenderer.invoke('spps:pickMaterialsFile'),
  pickOutputDirectory: () => ipcRenderer.invoke('spps:pickOutputDirectory'),
  openFolder: (path: string) => ipcRenderer.invoke('spps:openFolder', path),
  parseSequences: (fastaPath: string, materialsPath: string | null) =>
    ipcRenderer.invoke('spps:parseSequences', fastaPath, materialsPath),
  getResidues: () => ipcRenderer.invoke('spps:getResidues'),
  saveResidue: (residue: Record<string, unknown>) => ipcRenderer.invoke('spps:saveResidue', residue),
  generateSynthesis: (payload: Record<string, unknown>) =>
    ipcRenderer.invoke('spps:generateSynthesis', payload),
  getLastSynthesis: () => ipcRenderer.invoke('spps:getLastSynthesis')
}
```

- [ ] **Step 7: Add the type signatures**

Modify `desktop/src/preload/index.d.ts` to its full new state:

```typescript
import { ElectronAPI } from '@electron-toolkit/preload'

export interface SppsConfig {
  [key: string]: unknown
}

export interface SppsEnvelope {
  ok: boolean
  data?: SppsConfig
  error?: { code: string; message: string }
}

export interface ParsedVessel {
  number: number
  name: string
  original_tokens: string[]
  reversed_tokens: string[]
  resin_mass_g: number
  substitution_mmol_g: number
}

export interface ResidueRecord {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
}

export interface ParseSequencesEnvelope {
  ok: boolean
  data?: { vessels: ParsedVessel[]; materials_residue_map?: Record<string, ResidueRecord> }
  error?: { code: string; message: string }
}

export interface ResiduesEnvelope {
  ok: boolean
  data?: ResidueRecord[]
  error?: { code: string; message: string }
}

export interface GenerateEnvelope {
  ok: boolean
  data?: Record<string, string>
  error?: { code: string; message: string }
}

export interface LastSynthesisEnvelope {
  ok: boolean
  data: { name: string; output_directory: string; generated_at: string; vessel_count: number } | null
}

export interface SppsApi {
  getConfig: () => Promise<SppsEnvelope>
  setConfig: (data: Record<string, unknown>) => Promise<SppsEnvelope>
  pickFastaFile: () => Promise<string | null>
  pickMaterialsFile: () => Promise<string | null>
  pickOutputDirectory: () => Promise<string | null>
  openFolder: (path: string) => Promise<void>
  parseSequences: (fastaPath: string, materialsPath: string | null) => Promise<ParseSequencesEnvelope>
  getResidues: () => Promise<ResiduesEnvelope>
  saveResidue: (residue: ResidueRecord) => Promise<SppsEnvelope>
  generateSynthesis: (payload: {
    vessels: ParsedVessel[]
    residue_info_map: Record<string, ResidueRecord>
    config_overrides: Record<string, unknown>
  }) => Promise<GenerateEnvelope>
  getLastSynthesis: () => Promise<LastSynthesisEnvelope>
}

declare global {
  interface Window {
    electron: ElectronAPI
    spps: SppsApi
  }
}
```

- [ ] **Step 8: Run typecheck and the full desktop test suite**

Run: `npm run typecheck && npx vitest run` (from `desktop/`)
Expected: no typecheck errors; all tests pass (including the new ones from Tasks 4–6).

- [ ] **Step 9: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/main/api-bridge.ts desktop/src/main/api-bridge.test.ts desktop/src/main/index.ts desktop/src/preload/index.ts desktop/src/preload/index.d.ts
git commit -m "feat(desktop): add synthesis wizard IPC bridge (parseSequences/getResidues/saveResidue/generateSynthesis/getLastSynthesis)"
```

---

## Main-process + preload wiring complete after Task 6

Every `window.spps.*` method the wizard needs now exists and is typed. Tasks 7–11 build the 5 step components; Task 12 wires them into a shell; Task 13 wires the shell into the app and finishes the Dashboard integration.

---

### Task 7: Step 1 — Sequences

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/Step1Sequences.tsx`
- Test: `desktop/src/renderer/src/views/new-synthesis/Step1Sequences.test.tsx`

**Interfaces:**
- Consumes: `WizardState`, `WizardAction` from `./wizardReducer` (Task 4); `window.spps.pickFastaFile`, `.pickMaterialsFile`, `.parseSequences` (Task 5/6); `Button`, `Card`, `CardContent` from `../../components/ui/button`/`card` (Phase 2).
- Produces: `Step1Sequences` — a default-exported React component taking `{ state: WizardState; dispatch: Dispatch<WizardAction> }`, importable from `./Step1Sequences`. Task 12's shell renders it when `state.step === 1`.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/Step1Sequences.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step1Sequences from './Step1Sequences'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

function renderStep1(state: WizardState = initialWizardState) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step1Sequences state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch, getState: () => currentState }
}

describe('Step1Sequences', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('Continue is disabled until a FASTA file has been parsed', () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn(),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn()
    })

    renderStep1()

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('parses the picked FASTA file and shows the vessel preview with reversed sequences', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          vessels: [
            {
              number: 1,
              name: 'Peptide1',
              original_tokens: ['A', 'G'],
              reversed_tokens: ['G', 'A'],
              resin_mass_g: 0.1,
              substitution_mmol_g: 0.3
            }
          ]
        }
      })
    })
    const user = userEvent.setup()

    renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))

    await waitFor(() => expect(screen.getByText(/1 sequence/i)).toBeInTheDocument())
    expect(screen.getByText('AG')).toBeInTheDocument()
    expect(screen.getByText(/reversed: GA/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('shows an error banner if parsing fails', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/bad.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: false,
        error: { code: 'parse_failed', message: 'Could not parse FASTA file: bad format' }
      })
    })
    const user = userEvent.setup()

    renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))

    await waitFor(() =>
      expect(screen.getByText(/could not parse fasta file/i)).toBeInTheDocument()
    )
  })

  it('clicking Continue dispatches SET_STEP to 2', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          vessels: [
            {
              number: 1,
              name: 'Pep1',
              original_tokens: ['A'],
              reversed_tokens: ['A'],
              resin_mass_g: 0.1,
              substitution_mmol_g: 0.3
            }
          ]
        }
      })
    })
    const user = userEvent.setup()

    const { dispatch } = renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 2 })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step1Sequences.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./Step1Sequences`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/Step1Sequences.tsx`:

```tsx
import { useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { ResidueMwEntry, WizardAction, WizardState } from './wizardReducer'

interface Step1Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

interface MaterialsResidue {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
}

function buildResidueMapFromMaterials(
  materialsResidueMap: Record<string, MaterialsResidue> | undefined
): WizardState['residueMap'] {
  if (!materialsResidueMap) return {}
  const map: WizardState['residueMap'] = {}
  for (const [token, info] of Object.entries(materialsResidueMap)) {
    map[token] = { ...info, origin: 'materials' as const } satisfies ResidueMwEntry
  }
  return map
}

export default function Step1Sequences({ state, dispatch }: Step1Props): React.JSX.Element {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function parseWith(fastaPath: string, materialsPath: string | null): Promise<void> {
    setLoading(true)
    setError(null)
    const envelope = await window.spps.parseSequences(fastaPath, materialsPath)
    setLoading(false)
    if (!envelope.ok || !envelope.data) {
      setError(envelope.error?.message ?? 'Could not parse the FASTA file.')
      return
    }
    dispatch({
      type: 'SET_SEQUENCES',
      fastaPath,
      materialsPath,
      vessels: envelope.data.vessels,
      residueMap: buildResidueMapFromMaterials(envelope.data.materials_residue_map)
    })
  }

  async function pickAndParseFasta(): Promise<void> {
    const fastaPath = await window.spps.pickFastaFile()
    if (!fastaPath) return
    await parseWith(fastaPath, state.materialsPath)
  }

  async function pickMaterialsFile(): Promise<void> {
    const materialsPath = await window.spps.pickMaterialsFile()
    if (!materialsPath || !state.fastaPath) return
    await parseWith(state.fastaPath, materialsPath)
  }

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          <div className="flex gap-3 mb-4">
            <Button onClick={pickAndParseFasta} disabled={loading}>
              {state.fastaPath ? 'Change FASTA file' : 'Browse for FASTA file'}
            </Button>
            {state.fastaPath && (
              <Button onClick={pickMaterialsFile} disabled={loading} className="bg-bg3">
                {state.materialsPath ? 'Change materials file' : '+ Add materials file (optional)'}
              </Button>
            )}
          </div>

          {loading && <p className="text-text3 font-sans text-sm">Parsing…</p>}
          {error && <p className="text-red font-sans text-sm">{error}</p>}

          {state.vessels.length > 0 && (
            <div>
              <p className="text-text3 font-mono text-xs mb-2">
                {state.fastaPath} — {state.vessels.length} sequence(s)
              </p>
              {state.vessels.map((vessel) => (
                <div key={vessel.number} className="mb-2">
                  <p className="text-text3 font-sans text-xs">
                    Vessel {vessel.number} — {vessel.name}
                  </p>
                  <p className="text-text font-mono text-sm">{vessel.original_tokens.join('')}</p>
                  <p className="text-text3 font-mono text-xs">
                    → reversed: {vessel.reversed_tokens.join('')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          disabled={state.vessels.length === 0}
          onClick={() => dispatch({ type: 'SET_STEP', step: 2 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step1Sequences.test.tsx`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/Step1Sequences.tsx desktop/src/renderer/src/views/new-synthesis/Step1Sequences.test.tsx
git commit -m "feat(desktop): add wizard Step 1 (Sequences)"
```

---

### Task 8: Step 2 — Residue MW

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.tsx`
- Test: `desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.test.tsx`

**Interfaces:**
- Consumes: `WizardState`, `WizardAction`, `ResidueMwEntry` from `./wizardReducer` (Task 4); `window.spps.getResidues`, `.saveResidue` (Task 6).
- Produces: `Step2ResidueMW` — default-exported React component, same `{ state, dispatch }` prop shape as Step 1, importable from `./Step2ResidueMW`. Task 12's shell renders it when `state.step === 2`.
- **Precedence rule this task must implement** (per the design spec §1): on mount, fetch `GET /residues` and fill in a `ResidueMwEntry` (`origin: 'db'`) for every unique token from `state.vessels` that is **not already present** in `state.residueMap` (tokens already there came from a materials file in Step 1, `origin: 'materials'`, and must not be overwritten). Any token covered by neither gets a blank, `origin: 'manual'` placeholder row. Saving on Continue only calls `POST /residues` for rows whose `origin !== 'materials'`.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step2ResidueMW from './Step2ResidueMW'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

const TWO_VESSEL_STATE: WizardState = {
  ...initialWizardState,
  fastaPath: '/tmp/seqs.fasta',
  vessels: [
    {
      number: 1,
      name: 'Pep1',
      original_tokens: ['A', 'G'],
      reversed_tokens: ['G', 'A'],
      resin_mass_g: 0.1,
      substitution_mmol_g: 0.3
    }
  ]
}

function renderStep2(state: WizardState) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step2ResidueMW state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch, getState: () => currentState }
}

describe('Step2ResidueMW', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fills in unique tokens from the DB and marks them origin db', async () => {
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
          { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
        ]
      }),
      saveResidue: vi.fn()
    })

    render(<Step2ResidueMW state={TWO_VESSEL_STATE} dispatch={vi.fn()} />)

    await waitFor(() => expect(screen.getByDisplayValue('311.3')).toBeInTheDocument())
    expect(screen.getByDisplayValue('297.3')).toBeInTheDocument()
  })

  it('does not overwrite a token already seeded from a materials file', async () => {
    const stateWithMaterialsToken: WizardState = {
      ...TWO_VESSEL_STATE,
      materialsPath: '/tmp/mats.csv',
      residueMap: {
        A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 999.9, free_mw: 999.9, origin: 'materials' }
      }
    }
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [{ token: 'A', base_code: 'A', protection: '', fmoc_mw: 1.0, free_mw: 1.0 }]
      }),
      saveResidue: vi.fn()
    })

    render(<Step2ResidueMW state={stateWithMaterialsToken} dispatch={vi.fn()} />)

    await waitFor(() => expect(screen.getByDisplayValue('999.9')).toBeInTheDocument())
  })

  it('Continue is disabled until every unique token has a non-zero MW', async () => {
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({ ok: true, data: [] }),
      saveResidue: vi.fn()
    })

    renderStep2(TWO_VESSEL_STATE)

    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled())
  })

  it('Continue saves only non-materials rows to the DB, then advances to step 3', async () => {
    const saveResidue = vi.fn().mockResolvedValue({ ok: true, data: {} })
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
          { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
        ]
      }),
      saveResidue
    })
    const user = userEvent.setup()

    const { dispatch } = renderStep2(TWO_VESSEL_STATE)
    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(saveResidue).toHaveBeenCalledTimes(2)
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 3 })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step2ResidueMW.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./Step2ResidueMW`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.tsx`:

```tsx
import { useEffect, useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { ResidueMwEntry, WizardAction, WizardState } from './wizardReducer'

interface Step2Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

function uniqueTokens(state: WizardState): string[] {
  const tokens = new Set<string>()
  for (const vessel of state.vessels) {
    for (const token of vessel.original_tokens) tokens.add(token)
  }
  return Array.from(tokens)
}

export default function Step2ResidueMW({ state, dispatch }: Step2Props): React.JSX.Element {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getResidues()
      .then((envelope) => {
        if (cancelled) return
        if (!envelope.ok || !envelope.data) {
          setError('Could not load the residue library. Is the sidecar running?')
          setLoading(false)
          return
        }
        const dbMap = new Map(envelope.data.map((r) => [r.token, r]))
        const merged: WizardState['residueMap'] = { ...state.residueMap }
        for (const token of uniqueTokens(state)) {
          if (merged[token]) continue
          const fromDb = dbMap.get(token)
          merged[token] = fromDb
            ? { ...fromDb, origin: 'db' }
            : { token, base_code: token, protection: '', fmoc_mw: 0, free_mw: 0, origin: 'manual' }
        }
        dispatch({ type: 'SET_RESIDUE_MAP', residueMap: merged })
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the residue library. Is the sidecar running?')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updateEntry(token: string, patch: Partial<ResidueMwEntry>): void {
    const current = state.residueMap[token]
    dispatch({
      type: 'SET_RESIDUE',
      token,
      entry: { ...current, ...patch, token, origin: 'manual' }
    })
  }

  async function saveEditedResidues(): Promise<void> {
    const toSave = Object.values(state.residueMap).filter((entry) => entry.origin !== 'materials')
    await Promise.all(
      toSave.map((entry) =>
        window.spps.saveResidue({
          token: entry.token,
          base_code: entry.base_code,
          protection: entry.protection,
          fmoc_mw: entry.fmoc_mw,
          free_mw: entry.free_mw
        })
      )
    )
    dispatch({ type: 'SET_STEP', step: 3 })
  }

  const tokens = uniqueTokens(state)
  const allFilled =
    tokens.length > 0 &&
    tokens.every((token) => {
      const entry = state.residueMap[token]
      return entry && entry.fmoc_mw > 0 && entry.free_mw > 0
    })

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          {loading && <p className="text-text3 font-sans text-sm">Loading residue library…</p>}
          {error && <p className="text-red font-sans text-sm">{error}</p>}
          {!loading &&
            tokens.map((token) => {
              const entry = state.residueMap[token]
              return (
                <div key={token} className="flex items-center gap-3 mb-2">
                  <span className="text-text font-mono text-sm w-16">{token}</span>
                  <input
                    className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-24"
                    type="number"
                    step="0.1"
                    value={entry?.fmoc_mw ?? ''}
                    onChange={(e) => updateEntry(token, { fmoc_mw: Number(e.target.value) })}
                    aria-label={`${token} Fmoc-MW`}
                  />
                  <input
                    className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-24"
                    type="number"
                    step="0.1"
                    value={entry?.free_mw ?? ''}
                    onChange={(e) => updateEntry(token, { free_mw: Number(e.target.value) })}
                    aria-label={`${token} Free-AA-MW`}
                  />
                  <span className="text-text3 font-sans text-xs">{entry?.origin}</span>
                </div>
              )
            })}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 1 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={!allFilled}
          onClick={saveEditedResidues}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step2ResidueMW.test.tsx`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.tsx desktop/src/renderer/src/views/new-synthesis/Step2ResidueMW.test.tsx
git commit -m "feat(desktop): add wizard Step 2 (Residue MW)"
```

---

### Task 9: Step 3 — Reagents

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/Step3Reagents.tsx`
- Test: `desktop/src/renderer/src/views/new-synthesis/Step3Reagents.test.tsx`

**Interfaces:**
- Consumes: `WizardState`, `WizardAction` from `./wizardReducer` (Task 4). No sidecar calls — this step is pure local UI state, matching the mockup at `spps_gui_mockup.html` lines 452–503 (`#view-new-synthesis` step 3 markup) almost exactly.
- Produces: `Step3Reagents` — default-exported React component, `{ state, dispatch }` props, importable from `./Step3Reagents`. Task 12's shell renders it when `state.step === 3`.
- **Key behavior this task must implement** (design spec, matching `DESIGN_CONTEXT.md` §7): selecting `DIC` or `DCC` as the activator forces the base selector to show only `"None (DIC/DCC)"`, active; selecting any other activator restores the normal `DIEA`/`Pyridine` choices (defaulting to `DIEA` if the base was previously forced to `"None (DIC/DCC)"`).

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/Step3Reagents.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Step3Reagents from './Step3Reagents'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

function renderStep3(state: WizardState = initialWizardState) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step3Reagents state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch, getState: () => currentState, rerenderWithLatest: () => currentState }
}

describe('Step3Reagents', () => {
  it('renders the default activator, base, and deprotection reagent as active', () => {
    renderStep3()

    expect(screen.getByText('HBTU').className).toContain('text-teal')
    expect(screen.getByText('DIEA').className).toContain('text-teal')
    expect(screen.getByText('Piperidine 20%').className).toContain('text-teal')
  })

  it('clicking a deprotection reagent pill dispatches SET_REAGENTS', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep3()

    await user.click(screen.getByText('Piperazine 20%'))

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_REAGENTS',
      reagents: { deprotectionReagent: 'Piperazine 20%' }
    })
  })

  it('selecting DIC as activator switches base options to only "None (DIC/DCC)"', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step3Reagents state={state} dispatch={dispatch} />)

    await user.click(screen.getByText('DIC'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)

    expect(screen.queryByText('DIEA')).not.toBeInTheDocument()
    expect(screen.queryByText('Pyridine')).not.toBeInTheDocument()
    expect(screen.getByText('None (DIC/DCC)').className).toContain('text-teal')
  })

  it('switching back to HBTU after DIC restores the standard base options', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step3Reagents state={state} dispatch={dispatch} />)

    await user.click(screen.getByText('DIC'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)
    await user.click(screen.getByText('HBTU'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)

    expect(screen.getByText('DIEA')).toBeInTheDocument()
    expect(screen.getByText('Pyridine')).toBeInTheDocument()
  })

  it('Back dispatches SET_STEP to 2, Continue dispatches SET_STEP to 4', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep3()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 2 })

    await user.click(screen.getByRole('button', { name: /continue/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 4 })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step3Reagents.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./Step3Reagents`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/Step3Reagents.tsx`:

```tsx
import type { Dispatch, ReactNode } from 'react'
import { Button } from '../../components/ui/button'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step3Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

const DEPROTECTION_OPTIONS = ['Piperidine 20%', 'Piperazine 20%']
const ACTIVATOR_OPTIONS = ['HBTU', 'TBTU', 'HCTU', 'DIC', 'DCC']
const BASE_OPTIONS_STANDARD = ['DIEA', 'Pyridine']
const COMPLETENESS_TEST_OPTIONS: Array<{ value: WizardState['reagents']['completenessTest']; label: string }> = [
  { value: 'bromophenol', label: 'Bromophenol Blue' },
  { value: 'kaiser', label: 'Kaiser / Ninhydrin' },
  { value: 'none', label: 'None' }
]

function Pill({
  active,
  onClick,
  children
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'bg-teal-dim text-teal border border-teal px-3 py-1.5 rounded text-xs font-medium mr-2 mb-2'
          : 'bg-bg3 text-text3 border border-transparent px-3 py-1.5 rounded text-xs font-medium mr-2 mb-2'
      }
    >
      {children}
    </button>
  )
}

export default function Step3Reagents({ state, dispatch }: Step3Props): React.JSX.Element {
  const { reagents } = state
  const isDicOrDcc = reagents.activator === 'DIC' || reagents.activator === 'DCC'
  const baseOptions = isDicOrDcc ? ['None (DIC/DCC)'] : BASE_OPTIONS_STANDARD

  function setActivator(activator: string): void {
    const forcesNoBase = activator === 'DIC' || activator === 'DCC'
    const nextBase = forcesNoBase
      ? 'None (DIC/DCC)'
      : reagents.base === 'None (DIC/DCC)'
        ? 'DIEA'
        : reagents.base
    dispatch({ type: 'SET_REAGENTS', reagents: { activator, base: nextBase } })
  }

  return (
    <div>
      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Deprotection reagent</p>
        {DEPROTECTION_OPTIONS.map((option) => (
          <Pill
            key={option}
            active={reagents.deprotectionReagent === option}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { deprotectionReagent: option } })}
          >
            {option}
          </Pill>
        ))}
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Coupling activator</p>
        {ACTIVATOR_OPTIONS.map((option) => (
          <Pill key={option} active={reagents.activator === option} onClick={() => setActivator(option)}>
            {option}
          </Pill>
        ))}
        <div className="mt-2">
          <Pill
            active={reagents.useOxyma}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { useOxyma: true } })}
          >
            + Oxyma
          </Pill>
          <Pill
            active={!reagents.useOxyma}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { useOxyma: false } })}
          >
            No additive
          </Pill>
        </div>
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Base</p>
        {baseOptions.map((option) => (
          <Pill
            key={option}
            active={reagents.base === option}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { base: option } })}
          >
            {option}
          </Pill>
        ))}
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Volume mode</p>
        <Pill
          active={reagents.volumeMode === 'stoichiometry'}
          onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { volumeMode: 'stoichiometry' } })}
        >
          Stoichiometry-based
        </Pill>
        <Pill
          active={reagents.volumeMode === 'legacy'}
          onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { volumeMode: 'legacy' } })}
        >
          Legacy (2 mL/vessel)
        </Pill>
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Coupling completeness test</p>
        {COMPLETENESS_TEST_OPTIONS.map(({ value, label }) => (
          <Pill
            key={value}
            active={reagents.completenessTest === value}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { completenessTest: value } })}
          >
            {label}
          </Pill>
        ))}
      </div>

      <div className="flex justify-between mt-4">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 2 })} className="bg-bg3">
          Back
        </Button>
        <Button
          onClick={() => dispatch({ type: 'SET_STEP', step: 4 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step3Reagents.test.tsx`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/Step3Reagents.tsx desktop/src/renderer/src/views/new-synthesis/Step3Reagents.test.tsx
git commit -m "feat(desktop): add wizard Step 3 (Reagents)"
```

---

### Task 10: Step 4 — Resin

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/Step4Resin.tsx`
- Test: `desktop/src/renderer/src/views/new-synthesis/Step4Resin.test.tsx`

**Interfaces:**
- Consumes: `WizardState`, `WizardAction` from `./wizardReducer` (Task 4). No sidecar calls — pure local UI state.
- Produces: `Step4Resin` — default-exported React component, `{ state, dispatch }` props, importable from `./Step4Resin`. Task 12's shell renders it when `state.step === 4`.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/Step4Resin.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Step4Resin from './Step4Resin'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

function renderStep4(state: WizardState = initialWizardState) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step4Resin state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch }
}

describe('Step4Resin', () => {
  it('shows the fixed-mass input by default and Continue is enabled with valid defaults', () => {
    renderStep4()

    expect(screen.getByLabelText(/resin mass per vessel/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/target yield/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('switching to target yield shows the target yield input instead of resin mass', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step4Resin state={state} dispatch={dispatch} />)

    await user.click(screen.getByRole('button', { name: /target yield/i }))
    rerender(<Step4Resin state={state} dispatch={dispatch} />)

    expect(screen.queryByLabelText(/resin mass per vessel/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/target yield/i)).toBeInTheDocument()
  })

  it('Continue is disabled when target yield is selected but not set', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step4Resin state={state} dispatch={dispatch} />)

    await user.click(screen.getByRole('button', { name: /target yield/i }))
    rerender(<Step4Resin state={state} dispatch={dispatch} />)

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('Back dispatches SET_STEP to 3, Continue dispatches SET_STEP to 5', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep4()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 3 })

    await user.click(screen.getByRole('button', { name: /continue/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 5 })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step4Resin.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./Step4Resin`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/Step4Resin.tsx`:

```tsx
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step4Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

function StrategyPill({
  active,
  onClick,
  children
}: {
  active: boolean
  onClick: () => void
  children: string
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'bg-teal-dim text-teal border border-teal px-3 py-1.5 rounded text-xs font-medium mr-2'
          : 'bg-bg3 text-text3 border border-transparent px-3 py-1.5 rounded text-xs font-medium mr-2'
      }
    >
      {children}
    </button>
  )
}

export default function Step4Resin({ state, dispatch }: Step4Props): React.JSX.Element {
  const { resin } = state
  const isValid =
    resin.substitutionMmolG > 0 &&
    (resin.strategy === 'fixed' ? resin.fixedResinMassG > 0 : (resin.targetYieldMg ?? 0) > 0)

  return (
    <div>
      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Resin mass strategy</p>
        <StrategyPill
          active={resin.strategy === 'fixed'}
          onClick={() => dispatch({ type: 'SET_RESIN', resin: { strategy: 'fixed' } })}
        >
          Fixed mass
        </StrategyPill>
        <StrategyPill
          active={resin.strategy === 'target'}
          onClick={() => dispatch({ type: 'SET_RESIN', resin: { strategy: 'target' } })}
        >
          Target yield
        </StrategyPill>
      </div>

      <div className="mb-4">
        <label className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
          Substitution value (mmol/g)
        </label>
        <input
          className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
          type="number"
          step="0.01"
          value={resin.substitutionMmolG}
          onChange={(e) =>
            dispatch({ type: 'SET_RESIN', resin: { substitutionMmolG: Number(e.target.value) } })
          }
        />
      </div>

      {resin.strategy === 'fixed' ? (
        <div className="mb-4">
          <label className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
            Resin mass per vessel (g)
          </label>
          <input
            className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
            type="number"
            step="0.01"
            value={resin.fixedResinMassG}
            onChange={(e) =>
              dispatch({ type: 'SET_RESIN', resin: { fixedResinMassG: Number(e.target.value) } })
            }
          />
        </div>
      ) : (
        <div className="mb-4">
          <label className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
            Target yield (mg)
          </label>
          <input
            className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
            type="number"
            step="1"
            value={resin.targetYieldMg ?? ''}
            onChange={(e) =>
              dispatch({ type: 'SET_RESIN', resin: { targetYieldMg: Number(e.target.value) } })
            }
          />
        </div>
      )}

      <div className="flex justify-between mt-4">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 3 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => dispatch({ type: 'SET_STEP', step: 5 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step4Resin.test.tsx`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/Step4Resin.tsx desktop/src/renderer/src/views/new-synthesis/Step4Resin.test.tsx
git commit -m "feat(desktop): add wizard Step 4 (Resin)"
```

---

### Task 11: Step 5 — Confirm

**Files:**
- Create: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`
- Test: `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`

**Interfaces:**
- Consumes: `WizardState`, `WizardAction` from `./wizardReducer` (Task 4); `window.spps.pickOutputDirectory`, `.generateSynthesis`, `.openFolder` (Task 5/6).
- Produces: `Step5Confirm` — default-exported React component taking `{ state, dispatch, onDone: () => void }`, importable from `./Step5Confirm`. Task 12's shell renders it when `state.step === 5`, passing its own `onDone` prop through.
- Per the design spec §4/§5: shows a raw-selection summary (no calculated yield/solubility preview), and on success shows generated file paths, an "Open folder" button, and a "Done" button that calls `onDone`.

- [ ] **Step 1: Write the failing tests**

Create `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step5Confirm from './Step5Confirm'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

const READY_STATE: WizardState = {
  ...initialWizardState,
  fastaPath: '/tmp/seqs.fasta',
  outputDirectory: '/tmp/output',
  vessels: [
    {
      number: 1,
      name: 'Pep1',
      original_tokens: ['A'],
      reversed_tokens: ['A'],
      resin_mass_g: 0.1,
      substitution_mmol_g: 0.3
    }
  ],
  residueMap: {
    A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08, origin: 'db' }
  }
}

function renderStep5(state: WizardState, onDone = vi.fn()) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step5Confirm state={currentState} dispatch={dispatch} onDone={onDone} />)
  return { ...utils, dispatch, onDone, getState: () => currentState }
}

describe('Step5Confirm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a raw-selection summary of Steps 1-4', () => {
    vi.stubGlobal('spps', { generateSynthesis: vi.fn(), pickOutputDirectory: vi.fn(), openFolder: vi.fn() })

    renderStep5(READY_STATE)

    expect(screen.getByText(/1 vessel/i)).toBeInTheDocument()
    expect(screen.getByText(/1 unique token/i)).toBeInTheDocument()
    expect(screen.getByText(/HBTU \/ DIEA \/ Piperidine 20%/)).toBeInTheDocument()
  })

  it('Generate calls generateSynthesis with the accumulated wizard state and shows a success state', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.type(screen.getByLabelText(/synthesis name/i), 'X')
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText(/generated successfully/i)).toBeInTheDocument())
    expect(generateSynthesis).toHaveBeenCalledTimes(1)
    const payload = generateSynthesis.mock.calls[0][0]
    expect(payload.vessels).toHaveLength(1)
    expect(payload.residue_info_map.A.fmoc_mw).toBe(311.3)
    expect(payload.config_overrides.output_directory).toBe('/tmp/output')
  })

  it('shows an error banner if generation fails, without losing the entered data', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: false,
      error: { code: 'generate_failed', message: 'Disk full' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText('Disk full')).toBeInTheDocument())
    expect(screen.getByText(/1 vessel/i)).toBeInTheDocument()
  })

  it('clicking Done after a successful generate calls onDone', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onDone } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /^done$/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /^done$/i }))

    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('clicking Open folder calls window.spps.openFolder with a generated path', async () => {
    const openFolder = vi.fn().mockResolvedValue(undefined)
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /open folder/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /open folder/i }))

    expect(openFolder).toHaveBeenCalledWith('/tmp/output/Test_cycle_guide.pdf')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./Step5Confirm`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx`:

```tsx
import { useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step5Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
  onDone: () => void
}

export default function Step5Confirm({ state, dispatch, onDone }: Step5Props): React.JSX.Element {
  const [name, setName] = useState(state.synthesisName)

  async function handleGenerate(): Promise<void> {
    dispatch({ type: 'SET_SYNTHESIS_NAME', name })
    dispatch({ type: 'GENERATE_START' })

    const outputDirectory = state.outputDirectory || (await window.spps.pickOutputDirectory()) || 'spps_output'

    const envelope = await window.spps.generateSynthesis({
      vessels: state.vessels.map((v) => ({
        ...v,
        resin_mass_g: state.resin.fixedResinMassG,
        substitution_mmol_g: state.resin.substitutionMmolG
      })),
      residue_info_map: Object.fromEntries(
        Object.entries(state.residueMap).map(([token, entry]) => [
          token,
          {
            base_code: entry.base_code,
            protection: entry.protection,
            fmoc_mw: entry.fmoc_mw,
            free_mw: entry.free_mw
          }
        ])
      ),
      config_overrides: {
        name,
        deprotection_reagent: state.reagents.deprotectionReagent,
        activator: state.reagents.activator,
        use_oxyma: state.reagents.useOxyma,
        base: state.reagents.base,
        volume_mode: state.reagents.volumeMode,
        include_bb_test: state.reagents.completenessTest === 'bromophenol',
        include_kaiser_test: state.reagents.completenessTest === 'kaiser',
        resin_mass_strategy: state.resin.strategy,
        fixed_resin_mass_g: state.resin.fixedResinMassG,
        target_yield_mg: state.resin.targetYieldMg,
        output_directory: outputDirectory
      }
    })

    if (!envelope.ok || !envelope.data) {
      dispatch({ type: 'GENERATE_ERROR', error: envelope.error?.message ?? 'Generation failed.' })
      return
    }
    dispatch({ type: 'GENERATE_SUCCESS', paths: envelope.data })
  }

  if (state.generateResult.status === 'success') {
    const firstPath = Object.values(state.generateResult.paths ?? {})[0]
    return (
      <Card className="bg-bg2">
        <CardContent className="py-10 text-center">
          <p className="text-teal font-sans text-sm mb-4">Synthesis generated successfully.</p>
          <ul className="mb-4">
            {Object.entries(state.generateResult.paths ?? {}).map(([label, path]) => (
              <li key={label} className="text-text3 font-mono text-xs">
                {label}: {path}
              </li>
            ))}
          </ul>
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
        </CardContent>
      </Card>
    )
  }

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          <div className="mb-4">
            <label className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
              Synthesis name
            </label>
            <input
              className="bg-bg3 text-text font-sans text-sm px-2 py-1 w-64"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Sequences</dt>
              <dd className="text-text font-mono text-sm">
                {state.vessels.length} vessel(s) ({state.fastaPath})
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Residue MW</dt>
              <dd className="text-text font-mono text-sm">
                {Object.keys(state.residueMap).length} unique token(s) confirmed
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Reagents</dt>
              <dd className="text-text font-mono text-sm">
                {state.reagents.activator} / {state.reagents.base} / {state.reagents.deprotectionReagent}
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Resin</dt>
              <dd className="text-text font-mono text-sm">
                {state.resin.strategy === 'fixed'
                  ? `Fixed mass, ${state.resin.fixedResinMassG} g`
                  : `Target yield, ${state.resin.targetYieldMg} mg`}
                , sub {state.resin.substitutionMmolG} mmol/g
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Output directory</dt>
              <dd className="text-text font-mono text-sm">{state.outputDirectory || '(choose on generate)'}</dd>
            </div>
          </dl>

          {state.generateResult.status === 'error' && (
            <p className="text-red font-sans text-sm mt-4">{state.generateResult.error}</p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 4 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={state.generateResult.status === 'generating'}
          onClick={handleGenerate}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          {state.generateResult.status === 'generating' ? 'Generating…' : 'Generate →'}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/new-synthesis/Step5Confirm.tsx desktop/src/renderer/src/views/new-synthesis/Step5Confirm.test.tsx
git commit -m "feat(desktop): add wizard Step 5 (Confirm) with the real generate call"
```

---

### Task 12: NewSynthesis wizard shell

**Files:**
- Create: `desktop/src/renderer/src/views/NewSynthesis.tsx`
- Test: `desktop/src/renderer/src/views/NewSynthesis.test.tsx`

**Interfaces:**
- Consumes: `wizardReducer`, `initialWizardState` from `./new-synthesis/wizardReducer` (Task 4); `Step1Sequences` … `Step5Confirm` from `./new-synthesis/Step1Sequences` … `./new-synthesis/Step5Confirm` (Tasks 7–11).
- Produces: `NewSynthesis` — default-exported React component taking `{ onDone: () => void }`, importable from `./NewSynthesis`. Task 13's `App.tsx` renders it.

- [ ] **Step 1: Write the failing test**

Create `desktop/src/renderer/src/views/NewSynthesis.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NewSynthesis from './NewSynthesis'

function stubSpps(): void {
  vi.stubGlobal('spps', {
    pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
    pickMaterialsFile: vi.fn().mockResolvedValue(null),
    pickOutputDirectory: vi.fn().mockResolvedValue('/tmp/output'),
    openFolder: vi.fn().mockResolvedValue(undefined),
    parseSequences: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        vessels: [
          {
            number: 1,
            name: 'Pep1',
            original_tokens: ['A', 'G'],
            reversed_tokens: ['G', 'A'],
            resin_mass_g: 0.1,
            substitution_mmol_g: 0.3
          }
        ]
      }
    }),
    getResidues: vi.fn().mockResolvedValue({
      ok: true,
      data: [
        { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
        { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
      ]
    }),
    saveResidue: vi.fn().mockResolvedValue({ ok: true, data: {} }),
    generateSynthesis: vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    }),
    getLastSynthesis: vi.fn().mockResolvedValue({ ok: true, data: null })
  })
}

describe('NewSynthesis wizard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('drives all 5 steps end-to-end to a successful generate', async () => {
    stubSpps()
    const user = userEvent.setup()
    const onDone = vi.fn()

    render(<NewSynthesis onDone={onDone} />)

    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await user.click(screen.getByRole('button', { name: /continue/i }))
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await user.type(screen.getByLabelText(/synthesis name/i), 'IntegrationTest')
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText(/generated successfully/i)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /^done$/i }))
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/renderer/src/views/NewSynthesis.test.tsx` (from `desktop/`)
Expected: FAIL with a module-not-found error for `./NewSynthesis`.

- [ ] **Step 3: Write the minimal implementation**

Create `desktop/src/renderer/src/views/NewSynthesis.tsx`:

```tsx
import { useReducer } from 'react'
import { initialWizardState, wizardReducer } from './new-synthesis/wizardReducer'
import Step1Sequences from './new-synthesis/Step1Sequences'
import Step2ResidueMW from './new-synthesis/Step2ResidueMW'
import Step3Reagents from './new-synthesis/Step3Reagents'
import Step4Resin from './new-synthesis/Step4Resin'
import Step5Confirm from './new-synthesis/Step5Confirm'

const STEP_LABELS = ['Sequences', 'Residue MW', 'Reagents', 'Resin', 'Confirm'] as const

interface NewSynthesisProps {
  onDone: () => void
}

export default function NewSynthesis({ onDone }: NewSynthesisProps): React.JSX.Element {
  const [state, dispatch] = useReducer(wizardReducer, initialWizardState)

  return (
    <div className="bg-bg p-5">
      <div className="mb-5">
        <h1 className="text-text font-sans text-base font-medium">New synthesis</h1>
        <p className="text-text3 font-sans text-xs">Configure parameters before generating guides</p>
      </div>

      <div className="flex mb-5">
        {STEP_LABELS.map((label, index) => {
          const stepNum = (index + 1) as 1 | 2 | 3 | 4 | 5
          const status = stepNum < state.step ? 'done' : stepNum === state.step ? 'active' : 'upcoming'
          return (
            <div
              key={label}
              className={
                status === 'done'
                  ? 'text-teal bg-teal-dim flex-1 text-center py-2 text-xs font-medium'
                  : status === 'active'
                    ? 'text-text bg-bg3 flex-1 text-center py-2 text-xs font-medium'
                    : 'text-text3 flex-1 text-center py-2 text-xs font-medium'
              }
            >
              <span className="font-mono block">{String(stepNum).padStart(2, '0')}</span>
              {label}
            </div>
          )
        })}
      </div>

      {state.step === 1 && <Step1Sequences state={state} dispatch={dispatch} />}
      {state.step === 2 && <Step2ResidueMW state={state} dispatch={dispatch} />}
      {state.step === 3 && <Step3Reagents state={state} dispatch={dispatch} />}
      {state.step === 4 && <Step4Resin state={state} dispatch={dispatch} />}
      {state.step === 5 && <Step5Confirm state={state} dispatch={dispatch} onDone={onDone} />}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/renderer/src/views/NewSynthesis.test.tsx`
Expected: 1 passed. If a specific selector doesn't match (e.g. a button's accessible name differs slightly from what an earlier task's implementation actually produced), inspect the real rendered output (`screen.debug()`) and adjust the selector to match reality — the step components themselves (Tasks 7–11) are already committed and correct; this integration test adapts to them, not the reverse.

- [ ] **Step 5: Run the full desktop test suite**

Run: `npx vitest run` (from `desktop/`)
Expected: all tests from every task so far pass, 0 failed.

- [ ] **Step 6: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/views/NewSynthesis.tsx desktop/src/renderer/src/views/NewSynthesis.test.tsx
git commit -m "feat(desktop): add NewSynthesis wizard shell wiring all 5 steps"
```

---

### Task 13: Wire App.tsx navigation + Dashboard active-synthesis integration

**Files:**
- Modify: `desktop/src/renderer/src/App.tsx`
- Modify: `desktop/src/renderer/src/App.test.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.tsx`
- Modify: `desktop/src/renderer/src/views/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `NewSynthesis` from `./views/NewSynthesis` (Task 12); `window.spps.getLastSynthesis` (Task 6).
- Produces: the app's real navigation — clicking the "New synthesis" tab or either of Dashboard's "+ New synthesis" buttons switches to the wizard; a successful generate (Task 11's `onDone`) returns to the Dashboard, which now shows the active-synthesis summary instead of the empty state. This is the final integration point for this phase — nothing later depends on it.

- [ ] **Step 1: Write the failing tests**

Modify `desktop/src/renderer/src/views/Dashboard.test.tsx` to its full new state:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'

function baseStub(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    getConfig: () => Promise.resolve({ ok: true, data: {} }),
    setConfig: () => Promise.resolve({ ok: true, data: {} }),
    getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
    ...overrides
  }
}

describe('Dashboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state, then the fetched config values once loaded', async () => {
    vi.stubGlobal(
      'spps',
      baseStub({
        getConfig: () =>
          Promise.resolve({
            ok: true,
            data: {
              activator: 'HBTU',
              base: 'DIEA',
              deprotection_reagent: 'Piperidine 20%',
              aa_equivalents: 3.0,
              vessel_method: 'Teabag'
            }
          })
      })
    )

    render(<Dashboard onNewSynthesis={() => {}} />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('HBTU')).toBeInTheDocument()
    })
    expect(screen.getByText('DIEA')).toBeInTheDocument()
    expect(screen.getByText('Piperidine 20%')).toBeInTheDocument()
    expect(screen.getByText('Teabag')).toBeInTheDocument()
  })

  it('shows an error state if the sidecar call fails', async () => {
    vi.stubGlobal('spps', baseStub({ getConfig: () => Promise.reject(new Error('sidecar unreachable')) }))

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText(/couldn.t load configuration/i)).toBeInTheDocument()
    })
  })

  it('shows an empty state with a New Synthesis call to action when none has been generated', async () => {
    vi.stubGlobal(
      'spps',
      baseStub({ getConfig: () => Promise.resolve({ ok: true, data: { activator: 'HBTU' } }) })
    )

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText(/no active synthes/i)).toBeInTheDocument()
    })
    // Two "+ New synthesis" buttons are expected by design: one always-visible
    // in the page header, one contextual inside the empty-state card.
    const newSynthesisButtons = screen.getAllByRole('button', { name: /new synthesis/i })
    expect(newSynthesisButtons).toHaveLength(2)
  })

  it('shows the last generated synthesis instead of the empty state when one exists', async () => {
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

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText('BatchA')).toBeInTheDocument()
    })
    expect(screen.queryByText(/no active synthes/i)).not.toBeInTheDocument()
  })
})
```

Modify `desktop/src/renderer/src/App.test.tsx` to its full new state:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function stubSpps(): void {
  vi.stubGlobal('spps', {
    getConfig: () => Promise.resolve({ ok: true, data: {} }),
    setConfig: () => Promise.resolve({ ok: true, data: {} }),
    getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
    pickFastaFile: vi.fn().mockResolvedValue(null)
  })
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders all 5 tabs with only Dashboard and New synthesis enabled', async () => {
    stubSpps()

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    const dashboardTab = nav.getByText('Dashboard')
    expect(dashboardTab.className).toContain('text-teal')

    const newSynthesisTab = nav.getByText('New synthesis')
    expect(newSynthesisTab.className).not.toContain('cursor-not-allowed')

    for (const label of ['Cycle guide', 'Materials', 'Peptide info']) {
      const tab = nav.getByText(label)
      expect(tab.className).toContain('cursor-not-allowed')
    }

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument())
  })

  it('clicking the New synthesis tab switches to the wizard', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument())

    await user.click(screen.getByText('New synthesis'))

    expect(screen.getByRole('heading', { name: 'New synthesis' })).toBeInTheDocument()
  })

  it('clicking Dashboard\'s "+ New synthesis" button also switches to the wizard', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /new synthesis/i })[0]).toBeInTheDocument()
    )

    await user.click(screen.getAllByRole('button', { name: /new synthesis/i })[0])

    expect(screen.getByRole('heading', { name: 'New synthesis' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/renderer/src/views/Dashboard.test.tsx src/renderer/src/App.test.tsx` (from `desktop/`)
Expected: FAIL — `Dashboard`/`App` don't yet accept the props these tests pass, and `getLastSynthesis` isn't called yet, so the new/changed assertions (active-synthesis card, tab navigation) fail against the current implementation.

- [ ] **Step 3: Write the minimal implementation**

Modify `desktop/src/renderer/src/views/Dashboard.tsx` to its full new state:

```tsx
import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import type { SppsConfig } from '../../../preload/index.d'

type LoadState =
  { status: 'loading' } | { status: 'error' } | { status: 'loaded'; config: SppsConfig }

type LastSynthesisState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'active'; name: string; vesselCount: number; generatedAt: string }

const CONFIG_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'activator', label: 'Activator' },
  { key: 'base', label: 'Base' },
  { key: 'deprotection_reagent', label: 'Deprotection reagent' },
  { key: 'aa_equivalents', label: 'AA equivalents' },
  { key: 'vessel_method', label: 'Vessel method' }
]

interface DashboardProps {
  onNewSynthesis: () => void
}

export default function Dashboard({ onNewSynthesis }: DashboardProps): React.JSX.Element {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [lastSynthesis, setLastSynthesis] = useState<LastSynthesisState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    window.spps
      .getConfig()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data) {
          setState({ status: 'loaded', config: envelope.data })
        } else {
          setState({ status: 'error' })
        }
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data) {
          setLastSynthesis({
            status: 'active',
            name: envelope.data.name,
            vesselCount: envelope.data.vessel_count,
            generatedAt: envelope.data.generated_at
          })
        } else {
          setLastSynthesis({ status: 'none' })
        }
      })
      .catch(() => {
        if (!cancelled) setLastSynthesis({ status: 'none' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-text font-sans text-base font-medium">Dashboard</h1>
        <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
          + New synthesis
        </Button>
      </div>

      <Card className="bg-bg2 mb-4">
        <CardHeader>
          <CardTitle className="text-text text-sm font-medium">
            Current synthesis defaults
          </CardTitle>
        </CardHeader>
        <CardContent>
          {state.status === 'loading' && (
            <p className="text-text3 font-sans text-sm">Loading configuration…</p>
          )}
          {state.status === 'error' && (
            <p className="text-red font-sans text-sm">
              Couldn&apos;t load configuration. Is the sidecar running?
            </p>
          )}
          {state.status === 'loaded' && (
            <dl className="grid grid-cols-2 gap-3">
              {CONFIG_FIELDS.map(({ key, label }) => (
                <div key={key}>
                  <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
                    {label}
                  </dt>
                  <dd className="text-text font-mono text-sm">
                    {String(state.config[key] ?? '—')}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </CardContent>
      </Card>

      <Card className="bg-bg2">
        <CardContent className="flex flex-col items-center justify-center py-10 text-center">
          {lastSynthesis.status === 'active' ? (
            <>
              <p className="text-text font-sans text-sm mb-1">{lastSynthesis.name}</p>
              <p className="text-text3 font-mono text-xs">
                {lastSynthesis.vesselCount} vessel(s) — generated {lastSynthesis.generatedAt}
              </p>
            </>
          ) : (
            <>
              <p className="text-text2 font-sans text-sm mb-4">No active syntheses</p>
              <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
                + New synthesis
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
```

Modify `desktop/src/renderer/src/App.tsx` to its full new state:

```tsx
import { useState } from 'react'
import Dashboard from './views/Dashboard'
import NewSynthesis from './views/NewSynthesis'

const TABS = ['Dashboard', 'New synthesis', 'Cycle guide', 'Materials', 'Peptide info'] as const
type Tab = (typeof TABS)[number]

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>('Dashboard')

  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab) => {
          const enabled = tab === 'Dashboard' || tab === 'New synthesis'
          const active = tab === activeTab
          return (
            <div
              key={tab}
              onClick={enabled ? () => setActiveTab(tab) : undefined}
              className={
                active
                  ? 'text-teal border-b-2 border-teal px-4 py-3 text-xs font-medium cursor-pointer'
                  : enabled
                    ? 'text-text2 px-4 py-3 text-xs font-medium cursor-pointer'
                    : 'text-text3 px-4 py-3 text-xs font-medium cursor-not-allowed'
              }
            >
              {tab}
            </div>
          )
        })}
      </nav>
      {activeTab === 'Dashboard' && <Dashboard onNewSynthesis={() => setActiveTab('New synthesis')} />}
      {activeTab === 'New synthesis' && <NewSynthesis onDone={() => setActiveTab('Dashboard')} />}
    </div>
  )
}

export default App
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/renderer/src/views/Dashboard.test.tsx src/renderer/src/App.test.tsx`
Expected: 7 passed (4 from `Dashboard.test.tsx`, 3 from `App.test.tsx`).

- [ ] **Step 5: Run the full desktop test suite and typecheck**

Run: `npm run typecheck && npx vitest run` (from `desktop/`)
Expected: no typecheck errors; every test from every task in this plan passes, 0 failed.

- [ ] **Step 6: Run the full backend test suite one more time**

Run: `pytest -v` (from the repo root)
Expected: all tests pass, 0 failed — confirms nothing in this phase's frontend work broke the backend.

- [ ] **Step 7: Full manual end-to-end smoke test**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant/desktop
npm run dev
```

Confirm, in the actual running Electron window:
1. The "New synthesis" tab is now clickable (not greyed out); clicking it, or either Dashboard "+ New synthesis" button, opens the 5-step wizard.
2. Walk through all 5 real steps with a real FASTA file: browse for a `.fasta` file (create a throwaway one, e.g. `>Test\nAGWK\n`, if you don't have one handy), confirm the parsed vessel preview shows correctly, continue through Residue MW (values pre-fill from the real residue DB — enter any missing ones manually), Reagents, Resin, and Confirm.
3. Click Generate. Confirm real PDF/DOCX files appear in the chosen output directory, and the success screen shows their paths.
4. Click "Open folder" and confirm the OS file manager opens to the right directory.
5. Click "Done" and confirm the Dashboard now shows the just-generated synthesis's name and vessel count instead of "No active syntheses".
6. Compare one generated PDF against the equivalent v1.0 CLI output for the same FASTA/parameters (`spps-assistant generate --input <same file> --non-interactive`) — confirm the cycle guide content matches (same regression-check discipline as Phase 2's Dashboard verification and the parent plan's Phase 7 packaging smoke-test note).
7. Close the app and confirm (`ps aux | grep spps_assistant.api`) the sidecar process is no longer running.

- [ ] **Step 8: Commit**

```bash
cd /Users/cristiansalinas/Desktop/spps/spps-assistant
git add desktop/src/renderer/src/App.tsx desktop/src/renderer/src/App.test.tsx desktop/src/renderer/src/views/Dashboard.tsx desktop/src/renderer/src/views/Dashboard.test.tsx
git commit -m "feat(desktop): wire New Synthesis navigation and Dashboard active-synthesis card"
```

---

## After This Plan

Phase 3 is complete once all 13 tasks are committed, `npx vitest run` and `pytest` both pass cleanly, and the manual smoke test in Task 13 Step 7 confirms a real FASTA file can be walked through all 5 steps to real generated PDF/DOCX output matching the v1.0 CLI's own output for the same input.

Per the parent migration plan and this phase's design spec, explicitly deferred to later work (do not attempt in this branch/PR):
- Drag-and-drop file input (native "Browse" dialog only, per the design spec).
- A calculated yield/solubility preview on Step 5.
- Sidecar crash/restart detection after startup (flagged by Phase 2's whole-branch review, still open).
- Windows `python3.11` launcher support (project is macOS-first).
- `electron-builder.yml`'s packaging placeholders (tracked for the packaging phase).

Open a PR for this branch (`feature/gui-phase3-new-synthesis-wizard` or similar) against `main` and let CodeRabbit/SonarCloud review it — no new CI/Sonar/CodeRabbit configuration should be needed (Phase 2 already extended all three to cover `desktop/src/**` generally), but watch the first real CI run per the established "iterate on real findings until green" pattern from Phases 1 and 2, and check `GET /pulls/{n}/reviews` for a fresh CodeRabbit approval (not just a passing check-run) before merging.

Phase 4 (Coupling Cycle Guide view) is a separate plan — do not start it in this branch/PR.
