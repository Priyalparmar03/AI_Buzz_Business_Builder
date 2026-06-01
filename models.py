from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, default=generate_uuid, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    gender = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ideas = db.relationship("Idea", backref="user", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.public_id,
            "name": self.name,
            "email": self.email,
            "gender": self.gender,
            "phone": self.phone,
            "created_at": self.created_at.isoformat(),
        }


class Idea(db.Model):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(36), unique=True, default=generate_uuid, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    idea = db.Column(db.Text, nullable=False)

    # AI generated fields
    business_plan = db.Column(db.Text, nullable=True)
    target_audience = db.Column(db.Text, nullable=True)
    pricing_strategy = db.Column(db.Text, nullable=True)
    competitor_analysis = db.Column(db.Text, nullable=True)
    marketing_strategy = db.Column(db.Text, nullable=True)
    swot_analysis = db.Column(db.Text, nullable=True)  # JSON string
    startup_score = db.Column(db.Integer, nullable=True)
    score_breakdown = db.Column(db.Text, nullable=True)  # JSON string

    # Website
    website_content = db.Column(db.Text, nullable=True)  # JSON string
    template_style = db.Column(db.String(50), default="bold", nullable=False)
    website_generated = db.Column(db.Boolean, default=False)
    website_url = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json

        def safe_json(val):
            if val is None:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val

        return {
            "id": self.project_id,
            "title": self.title,
            "idea": self.idea,
            "business_plan": self.business_plan,
            "target_audience": self.target_audience,
            "pricing_strategy": self.pricing_strategy,
            "competitor_analysis": self.competitor_analysis,
            "marketing_strategy": self.marketing_strategy,
            "swot_analysis": safe_json(self.swot_analysis),
            "startup_score": self.startup_score,
            "score_breakdown": safe_json(self.score_breakdown),
            "template_style": self.template_style,
            "website_content": safe_json(self.website_content),
            "website_generated": self.website_generated,
            "website_url": self.website_url,
            "created_at": self.created_at.isoformat(),
        }