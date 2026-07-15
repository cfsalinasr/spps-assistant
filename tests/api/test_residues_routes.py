"""Tests for the /residues routes."""

import pytest


@pytest.fixture
def app(app_with_db):
    """Flask app wired to a throwaway SQLite DB, not the real user database."""
    return app_with_db


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


def test_post_residue_zero_fmoc_mw_returns_400(app):
    client = app.test_client()

    resp = client.post('/residues', json={'token': 'A', 'fmoc_mw': 0, 'free_mw': 71.08})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_post_residue_negative_fmoc_mw_returns_400(app):
    client = app.test_client()

    resp = client.post('/residues', json={'token': 'A', 'fmoc_mw': -5, 'free_mw': 71.08})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'


def test_post_residue_negative_free_mw_returns_400(app):
    client = app.test_client()

    resp = client.post('/residues', json={'token': 'A', 'fmoc_mw': 311.3, 'free_mw': -1.0})

    assert resp.status_code == 400
    body = resp.get_json()
    assert body['ok'] is False
    assert body['error']['code'] == 'invalid_body'
