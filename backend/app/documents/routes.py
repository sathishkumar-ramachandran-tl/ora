from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from .models import Document
from . import storage

document_bp = Blueprint('document', __name__)


def _extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


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

    safe_name = secure_filename(file.filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 400

    allowed_extensions = current_app.config.get("DOCUMENT_ALLOWED_EXTENSIONS", set())
    if allowed_extensions and _extension(safe_name) not in allowed_extensions:
        return jsonify({"error": "File type is not allowed"}), 400

    max_upload_bytes = current_app.config.get("DOCUMENT_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    if request.content_length and request.content_length > max_upload_bytes:
        return jsonify({"error": "File is too large"}), 413

    tags = request.form.getlist('tags')
    tags = [tag.strip()[:64] for tag in tags if tag and tag.strip()][:20]

    try:
        bucket_path = storage.upload_file(workspace_id, safe_name, file.stream, content_type=file.mimetype)
    except storage.StorageNotConfigured as e:
        return jsonify({"error": str(e)}), 503

    doc = Document(
        workspace_id=workspace_id,
        name=safe_name,
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
