"""Tests for the /sequences/parse route."""

import pytest

SIMPLE_FASTA = ">Peptide1\nAGLK\n>Peptide2\nFW\n"
SIMPLE_CSV = (
    "ResidueCode,ProtectionGroup,FmocMW_g_mol,FreeAA_MW_g_mol,Density_g_mL,Notes\n"
    "A,,311.3,71.08,,Fmoc-Ala-OH\n"
    "G,,297.3,57.05,,Fmoc-Gly-OH\n"
)


@pytest.fixture
def app(app_with_config_and_db):
    """Flask app wired to throwaway config/DB, not the real user config or database."""
    return app_with_config_and_db


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


def test_parse_numeric_fasta_path_returns_400(app):
    """Test that non-string fasta_path (e.g., a JSON number) returns 400, not 500."""
    client = app.test_client()

    resp = client.post('/sequences/parse', json={'fasta_path': 123})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_parse_numeric_materials_path_returns_400(app, fasta_file):
    """Test that non-string materials_path (e.g., a JSON array) returns 400, not 500."""
    client = app.test_client()

    resp = client.post('/sequences/parse', json={'fasta_path': str(fasta_file), 'materials_path': [1, 2, 3]})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'
