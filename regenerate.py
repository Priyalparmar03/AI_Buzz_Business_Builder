import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Idea
from services.ai_service import apply_website_changes, generate_website_html

regenerate = Blueprint("regenerate", __name__)


@regenerate.route("/regenerate/<project_id>", methods=["POST"])
@jwt_required()
def regenerate_site(project_id):
    user_id = get_jwt_identity()
    user = User.query.filter_by(public_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    idea = Idea.query.filter_by(project_id=project_id, user_id=user.id).first()
    if not idea:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json()
    instructions = data.get("instructions", "").strip()

    if not instructions or len(instructions) < 3:
        return jsonify({"error": "Please describe what you want to change"}), 400

    if len(instructions) > 1000:
        return jsonify({"error": "Instructions too long. Keep under 1000 characters."}), 400

    try:
        website_content = json.loads(idea.website_content or "{}")

        # CRITICAL: inject template_style from DB into content so apply_website_changes
        # can read and potentially change it
        if "template_style" not in website_content:
            website_content["template_style"] = idea.template_style or "bold"

        # Apply AI changes (handles both content + style/theme switches)
        updated_content = apply_website_changes(
            website_content=website_content,
            instructions=instructions,
            business_name=idea.title,
            original_idea=idea.idea,
        )

        # If style changed, update the DB column too
        new_style = updated_content.get("template_style", idea.template_style)
        if new_style != idea.template_style:
            idea.template_style = new_style
            current_app.logger.info(
                f"Style changed: {idea.template_style} → {new_style}"
            )

        # Re-generate the HTML with updated content
        html = generate_website_html(
            project_id=idea.project_id,
            business_name=idea.title,
            content=updated_content,
        )

        # Save updated HTML
        site_dir = os.path.join(
            current_app.config["GENERATED_SITES_DIR"], idea.project_id
        )
        os.makedirs(site_dir, exist_ok=True)
        with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

        # Save updated content to DB
        idea.website_content = json.dumps(updated_content)
        db.session.commit()

        return jsonify({
            "message": "Website updated successfully",
            "website_url": idea.website_url,
            "new_style": new_style,
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Regenerate error: {e}")
        return jsonify({"error": "Failed to apply changes. Please try again."}), 500