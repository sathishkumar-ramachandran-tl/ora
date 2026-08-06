from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from ..workspaces.models import Workspace
from .models import Note

note_bp = Blueprint('note', __name__)


@note_bp.route('/workspaces/<ws_id>/notes', methods=['GET'])
@jwt_required()
def get_notes(ws_id):
    """
    Notes with privacy filtering:
    - Owner of the note always sees it.
    - Workspace owner sees everything.
    - Everyone else sees only 'public'/'team' notes.
    """
    current_user_id = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    context_id = request.args.get('contextId')
    query = Note.query.filter_by(workspace_id=ws_id)
    if context_id:
        query = query.filter_by(context_id=context_id)

    visible_notes = []
    for note in query.all():
        if note.owner_id == current_user_id or workspace.owner_id == current_user_id:
            visible_notes.append(note)
        elif note.visibility in ('public', 'team'):
            visible_notes.append(note)

    return jsonify([{
        "id": n.id, "content": n.content, "type": n.type, "color": n.color,
        "ownerId": n.owner_id, "visibility": n.visibility, "createdAt": n.created_at.isoformat(),
    } for n in visible_notes])


@note_bp.route('/workspaces/<ws_id>/notes', methods=['POST'])
@jwt_required()
def create_note(ws_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}

    note = Note(
        workspace_id=ws_id,
        context_id=data.get('contextId'),
        owner_id=current_user_id,
        visibility=data.get('visibility', 'private'),
        content=data.get('content', ''),
        type=data.get('type', 'general'),
        color=data.get('color', 'yellow'),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"status": "created", "id": note.id, "visibility": note.visibility}), 201


@note_bp.route('/notes/<note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    current_user_id = get_jwt_identity()
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "Note not found"}), 404
    if note.owner_id != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(note)
    db.session.commit()
    return jsonify({"status": "deleted"}), 200
