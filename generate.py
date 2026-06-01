import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Idea
from services.ai_service import generate_business_analysis, generate_website_html

generate = Blueprint("generate", __name__)


@generate.route("/generate", methods=["POST"])
@jwt_required()
def generate_idea():
    user_id = get_jwt_identity()
    user = User.query.filter_by(public_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    idea_text = data.get("idea", "").strip()
    template_style = data.get("template_style", "bold").strip().lower()

    valid_styles = ["elegant", "bold", "minimal", "dark", "playful", "corporate"]
    if template_style not in valid_styles:
        template_style = "bold"

    if not idea_text or len(idea_text) < 10:
        return jsonify({"error": "Please provide a meaningful business idea (at least 10 characters)"}), 400

    if len(idea_text) > 5000:
        return jsonify({"error": "Idea is too long. Please keep it under 5000 characters."}), 400

    # --- AI Generation with retry (handles malformed JSON) ---
    analysis = None
    for attempt in range(3):
        try:
            analysis = generate_business_analysis(idea_text, template_style)
            break
        except ValueError as e:
            current_app.logger.warning(f"Attempt {attempt+1}: {e}")
            if attempt == 2:
                return jsonify({
                    "error": "The AI returned an unexpected response. Please rephrase your idea and try again."
                }), 503
        except Exception as e:
            current_app.logger.error(f"Groq API error attempt {attempt+1}: {e}")
            if attempt == 2:
                return jsonify({
                    "error": "AI service temporarily unavailable. Please try again in a moment."
                }), 503

    if not analysis:
        return jsonify({"error": "Could not generate analysis. Please try again."}), 503

    # --- Persist to DB ---
    try:
        website_content = analysis.get("website_content", {})

        idea_record = Idea(
            user_id=user.id,
            title=analysis.get("title", idea_text[:60]),
            idea=idea_text,
            business_plan=analysis.get("business_plan"),
            target_audience=analysis.get("target_audience"),
            pricing_strategy=analysis.get("pricing_strategy"),
            competitor_analysis=analysis.get("competitor_analysis"),
            marketing_strategy=analysis.get("marketing_strategy"),
            swot_analysis=json.dumps(analysis.get("swot_analysis", {})),
            startup_score=int(analysis.get("startup_score", 0)),
            score_breakdown=json.dumps(analysis.get("score_breakdown", {})),
            website_content=json.dumps(website_content),
            template_style=template_style,
        )
        db.session.add(idea_record)
        db.session.flush()

        business_name = analysis.get("title", "My Business")
        html_content = generate_website_html(
            idea_record.project_id, business_name, website_content
        )

        site_dir = os.path.join(
            current_app.config["GENERATED_SITES_DIR"], idea_record.project_id
        )
        os.makedirs(site_dir, exist_ok=True)
        with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        site_url = f"{current_app.config['SITE_BASE_URL']}/sites/{idea_record.project_id}/"
        idea_record.website_generated = True
        idea_record.website_url = site_url
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB/Website generation error: {e}")
        return jsonify({"error": "Failed to save results. Please try again."}), 500

    return jsonify({
        "message": "Analysis complete",
        "data": idea_record.to_dict()
    }), 201