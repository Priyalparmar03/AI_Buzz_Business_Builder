from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Idea

history = Blueprint("history", __name__)


@history.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()
    user = User.query.filter_by(public_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    ideas = (
        Idea.query.filter_by(user_id=user.id)
        .order_by(Idea.created_at.desc())
        .all()
    )

    return jsonify({
        "total": len(ideas),
        "history": [
            {
                "id": i.project_id,
                "title": i.title,
                "idea": i.idea,
                "startup_score": i.startup_score,
                "website_url": i.website_url,
                "website_generated": i.website_generated,
                "created_at": i.created_at.isoformat(),
            }
            for i in ideas
        ]
    }), 200


@history.route("/history/<project_id>", methods=["GET"])
@jwt_required()
def get_single(project_id):
    user_id = get_jwt_identity()
    user = User.query.filter_by(public_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    idea = Idea.query.filter_by(project_id=project_id, user_id=user.id).first()
    if not idea:
        return jsonify({"error": "Project not found"}), 404

    return jsonify({"data": idea.to_dict()}), 200


@history.route("/history/<project_id>", methods=["DELETE"])
@jwt_required()
def delete_idea(project_id):
    user_id = get_jwt_identity()
    user = User.query.filter_by(public_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    idea = Idea.query.filter_by(project_id=project_id, user_id=user.id).first()
    if not idea:
        return jsonify({"error": "Project not found"}), 404

    db.session.delete(idea)
    db.session.commit()

    return jsonify({"message": "Project deleted successfully"}), 200