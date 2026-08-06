import io
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from app.core.extensions import db
from app.documents.models import Document
from app.auth.models import User
from app.workspaces.models import Workspace
from app.core.security import hash_password


def _seed_user_ws(db, uid="doc-u1", ws_id="doc-ws1"):
    user = User(id=uid, email=f"{uid}@example.com", name="Doc User",
                password_hash=hash_password("pw"), email_verified=True)
    db.session.add(user)
    ws = Workspace(id=ws_id, name="Doc WS", context="personal", owner_id=uid)
    db.session.add(ws)
    db.session.commit()
    return user, ws


def test_upload_document_without_gcs_bucket_configured_fails_cleanly(app, db):
    ws_id = "doc-ws1"
    with app.app_context():
        user, _ = _seed_user_ws(db, ws_id=ws_id)
        token = create_access_token(identity=user.id)

    resp = app.test_client().post(
        '/api/v1/documents',
        data={'workspaceId': ws_id, 'file': (io.BytesIO(b"hello"), 'note.txt')},
        content_type='multipart/form-data',
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert 'GCS_BUCKET_NAME' in resp.json['error']


def test_upload_document_streams_to_gcs_and_persists_metadata(app, db):
    ws_id = "doc-ws2"
    with app.app_context():
        user, _ = _seed_user_ws(db, uid="doc-u2", ws_id=ws_id)
        token = create_access_token(identity=user.id)

    with patch('app.documents.storage.upload_file', return_value='vault/doc-ws2/fake-key_note.txt') as mock_upload:
        resp = app.test_client().post(
            '/api/v1/documents',
            data={'workspaceId': ws_id, 'file': (io.BytesIO(b"hello world"), 'note.txt'), 'tags': ['important']},
            content_type='multipart/form-data',
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.json
    assert resp.json['name'] == 'note.txt'
    assert resp.json['bucketPath'] == 'vault/doc-ws2/fake-key_note.txt'
    assert resp.json['tags'] == ['important']
    mock_upload.assert_called_once()

    with app.app_context():
        doc = Document.query.filter_by(workspace_id=ws_id).first()
        assert doc is not None
        assert doc.bucket_path == 'vault/doc-ws2/fake-key_note.txt'


def test_upload_document_forbidden_for_non_member(app, db):
    ws_id = "doc-ws3"
    with app.app_context():
        _seed_user_ws(db, uid="doc-u3", ws_id=ws_id)
        outsider = User(id="doc-u3b", email="outsider@example.com", name="Outsider",
                         password_hash=hash_password("pw"), email_verified=True)
        db.session.add(outsider)
        db.session.commit()
        token = create_access_token(identity=outsider.id)

    resp = app.test_client().post(
        '/api/v1/documents',
        data={'workspaceId': ws_id, 'file': (io.BytesIO(b"hello"), 'note.txt')},
        content_type='multipart/form-data',
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_download_document_returns_signed_url(app, db):
    with app.app_context():
        user, ws = _seed_user_ws(db, uid="doc-u4", ws_id="doc-ws4")
        doc = Document(workspace_id=ws.id, name="report.pdf", size=100, type="application/pdf",
                        bucket_path="vault/doc-ws4/abc_report.pdf", tags=[])
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id
        token = create_access_token(identity=user.id)

    with patch('app.documents.storage.generate_signed_url', return_value='https://storage.example/signed') as mock_sign:
        resp = app.test_client().get(
            f'/api/v1/documents/{doc_id}/download',
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json['url'] == 'https://storage.example/signed'
    mock_sign.assert_called_once_with('vault/doc-ws4/abc_report.pdf')


def test_delete_document_removes_row_and_calls_storage_delete(app, db):
    with app.app_context():
        user, ws = _seed_user_ws(db, uid="doc-u5", ws_id="doc-ws5")
        doc = Document(workspace_id=ws.id, name="old.txt", size=10, type="text/plain",
                        bucket_path="vault/doc-ws5/xyz_old.txt", tags=[])
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id
        token = create_access_token(identity=user.id)

    with patch('app.documents.storage.delete_file') as mock_delete:
        resp = app.test_client().delete(
            f'/api/v1/documents/{doc_id}',
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    mock_delete.assert_called_once_with('vault/doc-ws5/xyz_old.txt')

    with app.app_context():
        assert db.session.get(Document, doc_id) is None
