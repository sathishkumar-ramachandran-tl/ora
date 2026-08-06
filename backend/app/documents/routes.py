from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from .models import Document
from . import storage

document_bp = Blueprint('document', __name__)


@document_bp.route('/documents', methods=['POST'])
@jwt_required()
def upload_document():
    """Multipart upload — streams the file straight to GCS, then persists metadata
    pointing at the real bucket_path (no separate client-side storage step)."""
    workspace_id = request.form.get('workspaceId')
    if not user_can_access_workspace(get_jwt_identity(), workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400

    tags = request.form.getlist('tags')

    try:
        bucket_path = storage.upload_file(workspace_id, file.filename, file.stream, content_type=file.mimetype)
    except storage.StorageNotConfigured as e:
        return jsonify({"error": str(e)}), 503

    doc = Document(
        workspace_id=workspace_id,
        name=file.filename,
        size=request.content_length or 0,
        type=file.mimetype,
        bucket_path=bucket_path,
        tags=tags,
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({
        'id': doc.id, 'name': doc.name, 'size': doc.size, 'type': doc.type,
        'uploadedAt': doc.uploaded_at.isoformat(), 'bucketPath': doc.bucket_path, 'tags': doc.tags,
    }), 201


@document_bp.route('/workspaces/<ws_id>/documents', methods=['GET'])
@jwt_required()
def get_documents(ws_id):
    if not user_can_access_workspace(get_jwt_identity(), ws_id):
        return jsonify({"error": "Forbidden"}), 403
    docs = Document.query.filter_by(workspace_id=ws_id).order_by(Document.uploaded_at.desc()).all()
    return jsonify([{
        'id': d.id, 'name': d.name, 'size': d.size, 'type': d.type,
        'uploadedAt': d.uploaded_at.isoformat(), 'bucketPath': d.bucket_path, 'tags': d.tags,
    } for d in docs])


@document_bp.route('/documents/<doc_id>/download', methods=['GET'])
@jwt_required()
def download_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), doc.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    try:
        url = storage.generate_signed_url(doc.bucket_path)
    except storage.StorageNotConfigured as e:
        return jsonify({"error": str(e)}), 503
    return jsonify({"url": url})


@document_bp.route('/documents/<doc_id>', methods=['DELETE'])
@jwt_required()
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), doc.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    if doc.bucket_path:
        try:
            storage.delete_file(doc.bucket_path)
        except storage.StorageNotConfigured:
            pass

    db.session.delete(doc)
    db.session.commit()
    return jsonify({"status": "deleted"})
