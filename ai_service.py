import json
import re
import requests
from flask import current_app

GROQ_API_URL = "YOUR_GROQ_API"


# ── GROQ CALL ─────────────────────────────────────────────────────────────────

def call_groq(prompt, system=None, max_tokens=8192):
    api_key = current_app.config.get("GROQ_API_KEY", "")
    model = current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    r = requests.post(GROQ_API_URL,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                      json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
                      timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_json(text):
    """Robustly extract JSON from AI response, with multiple fallback strategies."""
    # Strategy 1: extract from code fence
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 2: find outermost { } block
    s, e = text.find("{"), text.rfind("}") + 1
    if s != -1 and e > s:
        candidate = text[s:e]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Strategy 3: try to fix common issues
            # Remove trailing commas before } or ]
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            # Fix unescaped newlines inside strings
            fixed = re.sub(r"(?<!\\)\n", " ", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    # Strategy 4: ask AI to fix it (fallback — raise clear error)
    raise ValueError(f"AI returned malformed JSON. Please try again with a clearer idea description.")


# ── WEBSITE TYPE DETECTION ────────────────────────────────────────────────────

def detect_website_type(idea):
    il = idea.lower()

    # SaaS/service signals always win — even if ecommerce words appear
    strong_saas = [
        "saas", "software as a service", "service-based", "consulting", "agency",
        "web app", "mobile app", "crm system", "erp system", "workflow automation",
        "api service", "service provider", "service business", "b2b",
        "platform", "dashboard", "management system", "role-based", "admin panel",
        "seller dashboard", "multi-role", "subscription platform", "digital platform",
    ]
    if any(k in il for k in strong_saas):
        return "saas"

    # Only PURE ecommerce signals — physical products, no platform language
    strong_ecom = [
        "online store", "online shop", "sell products", "selling products",
        "retail store", "shopping cart", "add to cart", "buy products",
    ]
    if any(k in il for k in strong_ecom):
        return "ecommerce"

    # Restaurant signals
    strong_restaurant = [
        "restaurant", "cafe", "food menu", "dining", "catering",
        "pizza", "burger", "bakery", "chef",
    ]
    if any(k in il for k in strong_restaurant):
        return "restaurant"

    # Score-based for remaining ambiguous ideas
    scores = {
        "ecommerce": sum(1 for k in [
            "store", "shop", "buy", "purchase", "cart", "inventory",
            "retail", "jewelry store", "clothing store", "electronics store",
        ] if k in il),
        "saas": sum(1 for k in [
            "app", "analytics", "crm", "erp", "workflow", "service",
            "software", "tool", "automation", "subscription",
        ] if k in il),
    }

    # Always prefer saas when tied or close
    if scores["saas"] >= scores["ecommerce"] - 1:
        return "saas"

    return "ecommerce" if scores["ecommerce"] > scores["saas"] else "saas"


# ── AI ANALYSIS ───────────────────────────────────────────────────────────────

def generate_business_analysis(idea, template_style="bold"):
    website_type = detect_website_type(idea)
    is_saas = website_type == "saas"

    system = """You are an expert business analyst and web content strategist. Respond ONLY with valid JSON.
No markdown outside JSON. Never use null — use empty strings or empty arrays.
Make ALL content 100% specific to the business idea provided."""

    # ── SaaS / Service prompt ─────────────────────────────────────────────────
    if is_saas:
        prompt = f"""Analyze this business idea and return a detailed JSON report.

Business Idea: "{idea}"

IMPORTANT RULES:
1. Generate content 100% SPECIFIC to this exact business idea — not generic templates.
2. If the idea is a software company → use tech/dev language.
3. If it is a yoga studio → use wellness language. If a law firm → use legal language. Adapt to the idea.
4. NO shopping cart, NO "Add to Cart", NO retail product pricing.
5. Services should NOT have prices — clients enquire first.

Return ONLY this JSON (no extra text):
{{
  "title": "2-4 word brand name that fits THIS specific idea",
  "business_plan": "3-paragraph plan specific to this idea: concept, operations, revenue model",
  "target_audience": "Specific audiences for this business with demographics and psychographics",
  "pricing_strategy": "How this type of business typically prices — describe the model",
  "competitor_analysis": "3-4 real competitors in this exact space and your differentiation",
  "marketing_strategy": "Marketing channels that actually make sense for this type of business",
  "swot_analysis": {{
    "strengths": ["strength specific to this idea", "strength 2", "strength 3", "strength 4"],
    "weaknesses": ["weakness 1", "weakness 2", "weakness 3"],
    "opportunities": ["opportunity 1", "opportunity 2", "opportunity 3", "opportunity 4"],
    "threats": ["threat 1", "threat 2", "threat 3"]
  }},
  "startup_score": <HONESTLY evaluate this specific idea from 1-100. Use the FULL range: weak ideas get 40-55, average ideas 56-70, good ideas 71-84, exceptional ideas 85-95. Do NOT always use 82.>,
  "score_breakdown": {{
    "market_potential": <1-100 honest score for this idea>,
    "innovation": <1-100 honest score>,
    "feasibility": <1-100 honest score>,
    "competition": <1-100 honest score>,
    "profitability": <1-100 honest score>
  }},
  "website_content": {{
    "type": "saas",
    "tagline": "One powerful sentence capturing what THIS specific business does — not generic",
    "announcement_bar": "Relevant announcement e.g. a special offer, milestone, or news specific to this business",
    "hero": {{
      "title": "Bold, specific headline for this business — max 7 words, sounds like a real brand",
      "subtitle": "2 clear sentences about what THIS business does and the value it gives clients",
      "cta_primary": "CTA that fits this business e.g. Book a Free Call / Get a Quote / Start Today",
      "cta_secondary": "Secondary CTA e.g. See Our Work / View Portfolio / Learn More",
      "badge": "Trust signal e.g. 200+ happy clients / 5★ rated / Award-winning / Since 2018"
    }},
    "services": [
      {{"name": "Actual service this business offers — real name", "icon": "fitting emoji", "badge": "Most Popular", "rating": 4.9, "reviews": 48, "description": "Clear 10-12 word description of the real value this service gives"}},
      {{"name": "Second real service", "icon": "fitting emoji", "badge": "", "rating": 4.8, "reviews": 32, "description": "10-12 word description"}},
      {{"name": "Third real service", "icon": "fitting emoji", "badge": "New", "rating": 4.7, "reviews": 24, "description": "10-12 word description"}},
      {{"name": "Fourth real service", "icon": "fitting emoji", "badge": "", "rating": 4.9, "reviews": 19, "description": "10-12 word description"}},
      {{"name": "Fifth real service", "icon": "fitting emoji", "badge": "", "rating": 4.6, "reviews": 15, "description": "10-12 word description"}},
      {{"name": "Sixth real service", "icon": "fitting emoji", "badge": "Enterprise", "rating": 4.8, "reviews": 11, "description": "10-12 word description"}}
    ],
    "categories": [
      {{"name": "Real type of client or industry this business serves", "icon": "fitting emoji", "count": "X+ clients/projects", "color": "#EEF2FF"}},
      {{"name": "Client/industry type 2", "icon": "fitting emoji", "count": "X+ served", "color": "#F0FDF4"}},
      {{"name": "Client/industry type 3", "icon": "fitting emoji", "count": "X+ projects", "color": "#FFF7ED"}},
      {{"name": "Client/industry type 4", "icon": "fitting emoji", "count": "X+ clients", "color": "#FDF4FF"}},
      {{"name": "Client/industry type 5", "icon": "fitting emoji", "count": "X+ delivered", "color": "#F0F9FF"}},
      {{"name": "Client/industry type 6", "icon": "fitting emoji", "count": "X+ partners", "color": "#FEFCE8"}}
    ],
    "process_steps": [
      {{"step": "01", "title": "Step 1 name for THIS business process", "desc": "What actually happens in this step for clients of this business."}},
      {{"step": "02", "title": "Step 2 name", "desc": "Description of step 2."}},
      {{"step": "03", "title": "Step 3 name", "desc": "Description of step 3."}},
      {{"step": "04", "title": "Step 4 name", "desc": "Description of step 4."}}
    ],
    "features": [
      {{"icon": "fitting emoji", "title": "Real strength of this specific business", "desc": "Why this actually matters to clients of this business"}},
      {{"icon": "fitting emoji", "title": "Real strength 2", "desc": "Why this matters"}},
      {{"icon": "fitting emoji", "title": "Real strength 3", "desc": "Why this matters"}},
      {{"icon": "fitting emoji", "title": "Real strength 4", "desc": "Why this matters"}}
    ],
    "testimonials": [
      {{"name": "Realistic client name and company for this type of business", "location": "Their industry", "avatar": "First letter", "rating": 5, "text": "15-word testimonial about the specific results THIS business delivered", "verified": true}},
      {{"name": "Client 2", "location": "Industry", "avatar": "Letter", "rating": 5, "text": "15-word specific testimonial", "verified": true}},
      {{"name": "Client 3", "location": "Industry", "avatar": "Letter", "rating": 5, "text": "15-word specific testimonial", "verified": true}}
    ],
    "stats": [
      {{"number": "realistic stat for this business", "label": "metric that fits this business"}},
      {{"number": "realistic stat", "label": "relevant metric"}},
      {{"number": "realistic stat", "label": "relevant metric"}},
      {{"number": "realistic stat", "label": "relevant metric"}}
    ],
    "about": {{
      "title": "About headline for this specific brand",
      "mission": "Mission statement 100% written for THIS business idea",
      "story": "Founding story and vision for THIS specific business — reads like a real company",
      "values": ["Value that reflects this business", "Value 2", "Value 3", "Value 4"]
    }},
    "blog_posts": [
      {{"title": "Article title relevant to this business niche", "excerpt": "2-sentence summary relevant to this industry.", "date": "Mar 15, 2025", "category": "Insights", "emoji": "fitting emoji"}},
      {{"title": "Article 2 relevant to this niche", "excerpt": "2-sentence summary.", "date": "Mar 8, 2025", "category": "Guide", "emoji": "fitting emoji"}},
      {{"title": "Article 3 relevant to this niche", "excerpt": "2-sentence summary.", "date": "Feb 28, 2025", "category": "Trends", "emoji": "fitting emoji"}}
    ],
    "faq": [
      {{"question": "Real question clients of THIS business actually ask", "answer": "Helpful answer specific to this business"}},
      {{"question": "FAQ 2 specific to this business", "answer": "Helpful answer"}},
      {{"question": "FAQ 3 specific to this business", "answer": "Helpful answer"}},
      {{"question": "FAQ 4 specific to this business", "answer": "Helpful answer"}}
    ],
CRITICAL:
- This is a SERVICE business — services array replaces products. NO "Add to Cart".
- All service names must be REAL specific services for this exact business idea.
- startup_score = integer 1-100. All score_breakdown values = integers 1-100.
- Color scheme should match the brand personality: blue/purple for tech, green for sustainability, etc.
"""
    else:
        # ── Ecommerce / Restaurant prompt ─────────────────────────────────────
        prompt = f"""Analyze this business idea and return a detailed JSON report.

Business Idea: "{idea}"

Return ONLY this JSON (no extra text):
{{
  "title": "Catchy brand name (2-4 words, specific to idea)",
  "business_plan": "Detailed 3-paragraph business plan: concept, operations, revenue model",
  "target_audience": "Primary and secondary audiences with demographics and psychographics",
  "pricing_strategy": "Specific pricing tiers with real price points and justification",
  "competitor_analysis": "3-4 real competitors, their weaknesses, your differentiation",
  "marketing_strategy": "Multi-channel strategy: social, content, influencer, SEO, paid ads",
  "swot_analysis": {{
    "strengths": ["specific strength 1", "specific strength 2", "specific strength 3", "specific strength 4"],
    "weaknesses": ["weakness 1", "weakness 2", "weakness 3"],
    "opportunities": ["opportunity 1", "opportunity 2", "opportunity 3", "opportunity 4"],
    "threats": ["threat 1", "threat 2", "threat 3"]
  }},
  "startup_score": <HONESTLY evaluate this specific idea from 1-100. Use the FULL range: weak ideas get 40-55, average ideas 56-70, good ideas 71-84, exceptional ideas 85-95. Do NOT always use 82.>,
  "score_breakdown": {{
    "market_potential": <1-100 honest score for this idea>,
    "innovation": <1-100 honest score>,
    "feasibility": <1-100 honest score>,
    "competition": <1-100 honest score>,
    "profitability": <1-100 honest score>
  }},
  "website_content": {{
    "type": "{website_type}",
    "tagline": "Compelling one-line brand tagline",
    "announcement_bar": "Promotional message e.g. Free shipping on orders over $50 | Use WELCOME10 for 10% off",
    "hero": {{
      "title": "Bold punchy headline max 7 words",
      "subtitle": "2 sentences describing unique value proposition",
      "cta_primary": "Primary CTA button text",
      "cta_secondary": "Secondary CTA button text",
      "badge": "Short trust badge text e.g. Trusted by 10,000+ customers"
    }},
    "categories": [
      {{"name": "Real category for this business", "icon": "💄", "count": "120+ items", "color": "#FFE4F3"}},
      {{"name": "Real category 2", "icon": "✨", "count": "80+ items", "color": "#E8F4FD"}},
      {{"name": "Real category 3", "icon": "🌿", "count": "60+ items", "color": "#F0FFF4"}},
      {{"name": "Real category 4", "icon": "🎨", "count": "95+ items", "color": "#FFF8E1"}},
      {{"name": "Real category 5", "icon": "💅", "count": "75+ items", "color": "#F3E5F5"}},
      {{"name": "Real category 6", "icon": "🧴", "count": "50+ items", "color": "#FBE9E7"}}
    ],
    "products": [
      {{"name": "Real specific product name", "price": "$24.99", "original_price": "$34.99", "badge": "Best Seller", "rating": 4.8, "reviews": 234, "emoji": "💄", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 2", "price": "$18.99", "original_price": "", "badge": "New", "rating": 4.6, "reviews": 89, "emoji": "✨", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 3", "price": "$32.00", "original_price": "$45.00", "badge": "Sale", "rating": 4.9, "reviews": 456, "emoji": "🌿", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 4", "price": "$15.99", "original_price": "", "badge": "", "rating": 4.5, "reviews": 123, "emoji": "💅", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 5", "price": "$28.50", "original_price": "$38.00", "badge": "Trending", "rating": 4.7, "reviews": 312, "emoji": "🎨", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 6", "price": "$22.00", "original_price": "", "badge": "", "rating": 4.4, "reviews": 67, "emoji": "🧴", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 7", "price": "$45.00", "original_price": "$60.00", "badge": "Premium", "rating": 4.9, "reviews": 198, "emoji": "💎", "description": "Enticing 10-word product description", "category": "category-name"}},
      {{"name": "Real specific product 8", "price": "$12.99", "original_price": "", "badge": "Popular", "rating": 4.6, "reviews": 145, "emoji": "🌸", "description": "Enticing 10-word product description", "category": "category-name"}}
    ],
    "features": [
      {{"icon": "🚚", "title": "Free Shipping", "desc": "On all orders over $50"}},
      {{"icon": "↩️", "title": "Easy Returns", "desc": "30-day hassle-free returns"}},
      {{"icon": "🔒", "title": "Secure Payment", "desc": "256-bit SSL encryption"}},
      {{"icon": "💬", "title": "24/7 Support", "desc": "Always here to help"}}
    ],
    "testimonials": [
      {{"name": "Sarah M.", "location": "New York, USA", "avatar": "S", "rating": 5, "text": "Specific 15-word review about the products/service", "verified": true}},
      {{"name": "Emma R.", "location": "London, UK", "avatar": "E", "rating": 5, "text": "Another specific authentic 15-word review", "verified": true}},
      {{"name": "Priya K.", "location": "Mumbai, India", "avatar": "P", "rating": 5, "text": "A third specific glowing 15-word review", "verified": true}}
    ],
    "stats": [
      {{"number": "50K+", "label": "Happy Customers"}},
      {{"number": "1,000+", "label": "Products"}},
      {{"number": "4.8★", "label": "Avg Rating"}},
      {{"number": "99%", "label": "Satisfaction"}}
    ],
    "about": {{
      "title": "About Us",
      "mission": "One sentence mission statement",
      "story": "Two paragraphs — founding story and vision",
      "values": ["Value 1", "Value 2", "Value 3", "Value 4"]
    }},
    "blog_posts": [
      {{"title": "Blog post title 1 relevant to this business", "excerpt": "2-sentence summary of post 1", "date": "Mar 15, 2025", "category": "Tips", "emoji": "📝"}},
      {{"title": "Blog post title 2 relevant to this business", "excerpt": "2-sentence summary of post 2", "date": "Mar 8, 2025", "category": "Guide", "emoji": "🌟"}},
      {{"title": "Blog post title 3 relevant to this business", "excerpt": "2-sentence summary of post 3", "date": "Feb 28, 2025", "category": "News", "emoji": "💡"}}
    ],
    "faq": [
      {{"question": "Frequently asked question 1 specific to this business?", "answer": "Clear helpful answer to question 1"}},
      {{"question": "Frequently asked question 2?", "answer": "Clear helpful answer to question 2"}},
      {{"question": "Frequently asked question 3?", "answer": "Clear helpful answer to question 3"}},
      {{"question": "Frequently asked question 4?", "answer": "Clear helpful answer to question 4"}}
    ],
    "contact": {{
      "email": "hello@brand.com",
      "phone": "+1 (555) 000-0000",
      "address": "123 Brand Street, New York, NY 10001"
    }},
    "social": {{
      "instagram": "@brandname",
      "tiktok": "@brandname",
      "twitter": "@brandname"
    }},
    "color_scheme": {{
      "primary": "#E91E8C",
      "secondary": "#C2185B",
      "accent": "#FF6B35",
      "text": "#1A1A2E",
      "bg": "#FAFAFA"
    }}
  }}
}}

CRITICAL:
- Each product must have a "category" field matching one of the category names (lowercase, hyphenated).
- startup_score = integer 1-100. All score_breakdown values = integers 1-100.
- ALL product names must be REAL specific products for this exact business.
- Color scheme must match brand: pink/rose for beauty, green for organic, blue for tech.
- website_content.type must stay exactly: "{website_type}"
"""
    raw = call_groq(prompt, system, max_tokens=8192)
    result = extract_json(raw)
    if "website_content" in result:
        result["website_content"]["type"] = website_type
        result["website_content"]["template_style"] = template_style
    return result


# ── HTML GENERATION ROUTER ────────────────────────────────────────────────────

def generate_website_html(project_id, business_name, content):
    style = content.get("template_style", "bold")
    wtype = content.get("type", "saas")
    is_ecom = wtype in ("ecommerce", "restaurant")
    is_saas = wtype == "saas"

    cs      = content.get("color_scheme", {})
    primary = cs.get("primary", "#2563EB")
    accent  = cs.get("accent",  "#7C3AED")

    # E-commerce → full role-based platform
    if is_ecom:
        return _build_ecom_platform(business_name, content)

    # SaaS/Service → dedicated service layout (no cart, no products)
    if is_saas:
        return _build_saas_site(business_name, content, style)

    # Fallback → style template + 6-page router
    builders = {
        "elegant":   _build_elegant,
        "bold":      _build_bold,
        "minimal":   _build_minimal,
        "dark":      _build_dark,
        "playful":   _build_playful,
        "corporate": _build_corporate,
    }
    builder = builders.get(style, _build_bold)
    single_page_html = builder(business_name, content, is_ecom)
    return _wrap_with_page_router(single_page_html, content, primary, accent)


# ── CHANGE REQUEST HANDLER ────────────────────────────────────────────────────

def apply_website_changes(website_content: dict, instructions: str, business_name: str, original_idea: str) -> dict:
    """Apply user-requested changes to existing website content via AI."""
    import json as _json
    import re as _re

    current_style = website_content.get("template_style", "bold")
    current_cs    = website_content.get("color_scheme", {})

    # ── Step 1: Detect style/theme change requests BEFORE calling AI ──────────
    # If user asks for a theme/style change, handle it directly — don't rely on AI
    instr_lower = instructions.lower()

    STYLE_TRIGGERS = {
        "dark":      ["dark","night","black","neon","cyber","dark mode","dark theme","dark style"],
        "light":     ["light","white","bright","clean","minimal","minimalist","light mode","light theme","light colour","light color"],
        "elegant":   ["elegant","luxury","premium","gold","serif","classic","sophisticated","classy"],
        "playful":   ["playful","fun","colorful","colourful","warm","friendly","bright","orange","rounded"],
        "corporate": ["corporate","professional","enterprise","navy","formal","business","conservative"],
        "bold":      ["bold","startup","energetic","strong","impact","chunky"],
        "minimal":   ["minimal","minimalist","simple","clean","whitespace","white","black and white"],
    }

    # Color scheme presets for each style
    STYLE_COLORS = {
        "dark":      {"primary":"#6C63FF","secondary":"#5A52D5","accent":"#FF6B9D","text":"#E8E8F5","bg":"#0A0A14"},
        "light":     {"primary":"#2563EB","secondary":"#1D4ED8","accent":"#7C3AED","text":"#111827","bg":"#F9FAFB"},
        "elegant":   {"primary":"#1A1A2E","secondary":"#16213E","accent":"#C9A84C","text":"#1A1A1A","bg":"#FAFAF8"},
        "playful":   {"primary":"#FF6B35","secondary":"#E64A19","accent":"#4CAF50","text":"#2D1B00","bg":"#FFF9F0"},
        "corporate": {"primary":"#1A3A6B","secondary":"#0D2044","accent":"#2563EB","text":"#1A2B4A","bg":"#F4F6FA"},
        "bold":      {"primary":"#2563EB","secondary":"#1D4ED8","accent":"#F59E0B","text":"#0F172A","bg":"#F8FAFC"},
        "minimal":   {"primary":"#111111","secondary":"#333333","accent":"#555555","text":"#111111","bg":"#FFFFFF"},
    }

    new_style = None
    for style_name, triggers in STYLE_TRIGGERS.items():
        if any(t in instr_lower for t in triggers):
            new_style = style_name
            break

    # ── Step 2: Build editable fields for AI ──────────────────────────────────
    editable = {
        "tagline":          website_content.get("tagline", ""),
        "announcement_bar": website_content.get("announcement_bar", ""),
        "hero":             website_content.get("hero", {}),
        "about":            website_content.get("about", {}),
        "services":         website_content.get("services", []),
        "features":         website_content.get("features", []),
        "stats":            website_content.get("stats", []),
        "testimonials":     website_content.get("testimonials", []),
        "blog_posts":       website_content.get("blog_posts", []),
        "faq":              website_content.get("faq", []),
        "contact":          website_content.get("contact", {}),
        "color_scheme":     current_cs,
    }

    # Only call AI if the request is about content (not just a style/theme switch)
    is_style_only = new_style and not any(
        kw in instr_lower for kw in [
            "title","headline","text","content","service","about","hero","tagline",
            "contact","faq","blog","testimonial","stat","feature","add","change the",
            "update","remove","replace","rewrite"
        ]
    )

    if not is_style_only:
        # Call AI for content changes
        system = """You are a website content editor. Apply ONLY the changes the user requests.
Keep all other fields EXACTLY as they are. Return ONLY valid JSON with the same structure. No markdown."""

        prompt = f"""Website: "{business_name}"
Original idea: "{original_idea}"

Current content:
{_json.dumps(editable, indent=2)}

User request: "{instructions}"

Apply the requested changes and return the complete JSON. Rules:
- Change ONLY what the user asked for
- If color/theme change requested, update color_scheme with appropriate hex values
- Keep all array structures (services, faq etc.) intact unless user asked to change them
- Return full JSON with same keys"""

        raw = call_groq(prompt, system, max_tokens=8192)
        updated_editable = extract_json(raw)

        # Merge back
        merged = dict(website_content)
        for key, val in updated_editable.items():
            if val is not None and val != "" and val != [] and val != {}:
                merged[key] = val
    else:
        merged = dict(website_content)

    # ── Step 3: Apply style change if detected ────────────────────────────────
    if new_style:
        # Map "light" theme request to actual style name
        actual_style = "bold" if new_style == "light" else new_style
        merged["template_style"] = actual_style
        # Apply the matching color scheme
        if new_style in STYLE_COLORS:
            merged["color_scheme"] = STYLE_COLORS[new_style]

    # ── Step 4: Always preserve critical fields ───────────────────────────────
    merged["type"] = website_content.get("type", "saas")
    if not new_style:
        merged["template_style"] = current_style

    return merged



# ── SHARED DATA HELPERS ───────────────────────────────────────────────────────

def _products_block(products, btn_class="btn-add"):
    import json as _json
    html = ""
    for i, p in enumerate(products):
        badge = f'<span class="p-badge">{p.get("badge")}</span>' if p.get("badge") else ""
        r = p.get("rating", 5)
        stars = "★" * int(r) + "☆" * (5 - int(r))
        orig = f'<s class="p-orig">{p["original_price"]}</s>' if p.get("original_price") else ""
        # Sanitise for data attribute
        cat = p.get("category", "all").lower().replace(" ", "-")
        pd = _json.dumps({
            "name": p.get("name",""),
            "price": p.get("price",""),
            "original_price": p.get("original_price",""),
            "description": p.get("description",""),
            "emoji": p.get("emoji","🛍️"),
            "rating": p.get("rating", 5),
            "reviews": p.get("reviews", 0),
            "badge": p.get("badge",""),
        }).replace("'","&#39;").replace('"','&quot;')
        html += f"""<div class="p-card" data-cat="{cat}" data-name="{p.get('name','').lower()}" data-pid="{i}">
      {badge}
      <div class="p-img" onclick="openModal({i})" style="cursor:pointer">{p.get("emoji","🛍️")}</div>
      <div class="p-body">
        <h4 class="p-name" onclick="openModal({i})" style="cursor:pointer">{p.get("name","")}</h4>
        <p class="p-desc">{p.get("description","")}</p>
        <div class="p-stars">{stars} <span class="p-rev">({p.get("reviews",0)})</span></div>
        <div class="p-foot">
          <div><span class="p-price">{p.get("price","")}</span>{orig}</div>
          <button class="{btn_class}" onclick="addToCart('{p.get('name','').replace(chr(39),'')}')">Add to Cart</button>
        </div>
      </div>
    </div>"""
    return html

# Map category keywords to Phosphor SVG icon paths
CAT_ICONS = {
    "foundation": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M200,64H168V56a40,40,0,0,0-80,0v8H56A16,16,0,0,0,40,80V200a16,16,0,0,0,16,16H200a16,16,0,0,0,16-16V80A16,16,0,0,0,200,64ZM104,56a24,24,0,0,1,48,0v8H104ZM200,200H56V80H88v24a8,8,0,0,0,16,0V80h48v24a8,8,0,0,0,16,0V80h32Z" fill="currentColor"/></svg>',
    "lipstick": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M213.66,82.34l-40-40a8,8,0,0,0-11.32,0L120,94.06,103.66,77.66A8,8,0,0,0,88,80v24H40a16,16,0,0,0-16,16v88a16,16,0,0,0,16,16H216a16,16,0,0,0,16-16V120a16,16,0,0,0-16-16H184V80a8,8,0,0,0-2.34-5.66ZM168,80h0v24H104V95.31l18.34,18.35a8,8,0,0,0,11.32,0ZM216,208H40V120H216Z" fill="currentColor"/></svg>',
    "eyeshadow": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M247.31,124.76c-.35-.79-8.82-19.58-27.65-38.41C194.57,61.26,162.88,48,128,48S61.43,61.26,36.34,86.35C17.51,105.18,9,124,8.69,124.76a8,8,0,0,0,0,6.48c.35.79,8.82,19.57,27.65,38.41C61.43,194.74,93.12,208,128,208s66.57-13.26,91.66-38.35c18.83-18.84,27.3-37.62,27.65-38.41A8,8,0,0,0,247.31,124.76ZM128,192c-30.78,0-57.67-11.19-79.93-33.25A133.47,133.47,0,0,1,25,128,133.33,133.33,0,0,1,48.07,97.25C70.33,75.19,97.22,64,128,64s57.67,11.19,79.93,33.25A133.46,133.46,0,0,1,231.05,128C223.84,141.46,192.43,192,128,192Zm0-112a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160Z" fill="currentColor"/></svg>',
    "mascara": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M176,88a47.72,47.72,0,0,0-20.08,4.43L143.6,73.29A48,48,0,1,0,80,137.29v45.42A48,48,0,1,0,168,200V135.6A48.22,48.22,0,0,0,176,88ZM64,88a32,32,0,1,1,32,32A32,32,0,0,1,64,88Zm80,112a32,32,0,1,1-32-32A32,32,0,0,1,144,200Z" fill="currentColor"/></svg>',
    "blush": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216Zm48-88a48,48,0,1,1-48-48A48.05,48.05,0,0,1,176,128Z" fill="currentColor"/></svg>',
    "highlighter": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M216,128a8,8,0,0,1-8,8H168a8,8,0,0,1,0-16h40A8,8,0,0,1,216,128ZM88,128a8,8,0,0,0-8-8H40a8,8,0,0,0,0,16H80A8,8,0,0,0,88,128Zm40,40a8,8,0,0,0-8,8v40a8,8,0,0,0,16,0V176A8,8,0,0,0,128,168ZM128,88a8,8,0,0,0,8-8V40a8,8,0,0,0-16,0V80A8,8,0,0,0,128,88Z" fill="currentColor"/></svg>',
    "skincare": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M205.66,61.64,194.36,50.34A16,16,0,0,0,172,49.18L89.15,132.06a24,24,0,0,0-5.65,24.79L69.05,171.3a24,24,0,0,0,0,33.94l4.71,4.71a24,24,0,0,0,33.94,0l14.45-14.45a24,24,0,0,0,24.79-5.65L229.82,73A16,16,0,0,0,228.66,50.68ZM96.34,198.63a8,8,0,0,1-11.32,0l-4.71-4.71a8,8,0,0,1,0-11.32l13.16-13.16,16,16ZM220.29,61.64,137.43,144.5a8,8,0,0,1-11.32,0l-14.63-14.63L183.35,58.1a.34.34,0,0,1,.29,0l11.3,11.3Z" fill="currentColor"/></svg>',
    "fragrance": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M216,120H176V56h8a8,8,0,0,0,0-16H72a8,8,0,0,0,0,16h8V120H40a16,16,0,0,0-16,16v64a16,16,0,0,0,16,16H216a16,16,0,0,0,16-16V136A16,16,0,0,0,216,120ZM96,56h64V120H96ZM216,200H40V136H216Z" fill="currentColor"/></svg>',
    "tools": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M226.76,69a8,8,0,0,0-6.76-3H176V56a24,24,0,0,0-48,0V66H84.5L58.43,21.87A8,8,0,0,0,43.57,26.13L67.5,66H36a16,16,0,0,0-16,16v48a16,16,0,0,0,16,16H76.43L55.08,216H200.92L179.57,146H220a16,16,0,0,0,16-16V82A8,8,0,0,0,226.76,69ZM144,56a8,8,0,0,1,16,0V66H144ZM220,130H36V82H220Z" fill="currentColor"/></svg>',
    "nails": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M173.66,58.34a8,8,0,0,0-11.32,0L136,84.69,115.31,64A16,16,0,0,0,92.69,64L50.34,106.35a16,16,0,0,0,0,22.62l96,96a16,16,0,0,0,22.62,0l42.35-42.34a16,16,0,0,0,0-22.63L191,139.66l26.35-26.35a8,8,0,0,0,0-11.31ZM157.65,213.65,61.66,117.66,104,75.31,200,171.31Z" fill="currentColor"/></svg>',
    "hair": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M236.8,188.09,149.35,36.75a24.76,24.76,0,0,0-42.7,0L19.2,188.09a23.51,23.51,0,0,0,0,23.72A24.35,24.35,0,0,0,40.55,224h174.9a24.35,24.35,0,0,0,21.33-12.19A23.51,23.51,0,0,0,236.8,188.09ZM222.93,204a8.5,8.5,0,0,1-7.48,4H40.55a8.5,8.5,0,0,1-7.48-4,7.59,7.59,0,0,1,0-7.72L120.52,44.9a8.75,8.75,0,0,1,15,0l87.45,151.38A7.59,7.59,0,0,1,222.93,204Z" fill="currentColor"/></svg>',
    "default": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 256 256"><path d="M222.14,58.87l-96-32a8,8,0,0,0-5.08,0l-96,32A8,8,0,0,0,20,66.43V186.43a8,8,0,0,0,5.14,7.44l96,35.2a7.92,7.92,0,0,0,5.72,0l96-35.2a8,8,0,0,0,5.14-7.44V66.43A8,8,0,0,0,222.14,58.87ZM128,39l72.28,24.1L128,100.73,55.72,63.1ZM36,75.36l84,44.13V207.1L36,179.86Zm100,131.74V119.49l84-44.13V179.86Z" fill="currentColor"/></svg>'
}

def _get_cat_svg(name):
    n = name.lower()
    for k, v in CAT_ICONS.items():
        if k in n:
            return v
    return CAT_ICONS["default"]

def _cats_block(cats):
    html = ""
    for c in cats:
        cat_name = c.get("name", "")
        cat_slug = cat_name.lower().replace(" ", "-")
        svg = _get_cat_svg(cat_name)
        html += f'''<div class="cat-item" data-cat="{cat_slug}" style="--cat-color:{c.get("color","#f5f5f5")}" onclick="filterByCategory(\'{cat_slug}\')">
      <div class="cat-svg-wrap">{svg}</div>
      <span class="cat-nm">{cat_name}</span>
      <span class="cat-ct">{c.get("count","")}</span>
    </div>'''
    return html

def _testis_block(ts, avatar_bg):
    html = ""
    for t in ts:
        stars = "★" * int(t.get("rating", 5))
        html += f"""<div class="t-card">
      <div class="t-stars">{stars}</div>
      <p class="t-text">"{t.get("text","")}"</p>
      <div class="t-author">
        <div class="t-av" style="background:{avatar_bg}">{t.get("avatar","?")}</div>
        <div><div class="t-name">{t.get("name","")}</div><div class="t-loc">{t.get("location","")}</div></div>
      </div>
    </div>"""
    return html

def _stats_block(stats):
    return "".join(f'<div class="stat"><div class="stat-n">{s.get("number","")}</div><div class="stat-l">{s.get("label","")}</div></div>' for s in stats)

def _footer_cats(cats):
    return "".join(f'<li><a href="#products">{c.get("name","")}</a></li>' for c in cats[:5])


# ══════════════════════════════════════════════════════════════════════════════
# 1. ELEGANT & LUXURY
# ══════════════════════════════════════════════════════════════════════════════

def _build_elegant(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")
    sc = c.get("social", {})

    ph = _products_block(c.get("products", []), "el-btn-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), "#C9A84C")
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="el-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="el-feat"><span>{f["icon"]}</span><div><strong>{f["title"]}</strong><p>{f["desc"]}</p></div></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400;1,600&family=Montserrat:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--gold:#C9A84C;--gold2:#8B6914;--dark:#0D0D0D;--dark2:#1A1A1A;--dark3:#252525;--cream:#F5E6C8;--muted:#8B7355;--border:#2A2400;--r:2px}}
html{{scroll-behavior:smooth}}
body{{font-family:'Montserrat',sans-serif;background:var(--dark);color:var(--cream);line-height:1.7;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}
/* ANNOUNCE */
.ann{{background:var(--border);color:var(--gold);text-align:center;padding:.55rem 1rem;font-size:.75rem;letter-spacing:.15em;text-transform:uppercase;border-bottom:1px solid var(--gold)30}}
/* NAV */
nav{{background:rgba(13,13,13,.97);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:0 6%;display:flex;align-items:center;justify-content:space-between;height:76px;position:sticky;top:0;z-index:100}}
.nav-brand{{font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:600;font-style:italic;color:var(--gold);letter-spacing:.1em}}
.nav-links{{display:flex;gap:2.5rem;list-style:none}}
.nav-links a{{font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);transition:color .2s}}
.nav-links a:hover{{color:var(--gold)}}
.nav-cta{{background:transparent;border:1px solid var(--gold);color:var(--gold);padding:.5rem 1.5rem;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;cursor:pointer;transition:all .25s;font-family:inherit}}
.nav-cta:hover{{background:var(--gold);color:var(--dark)}}
/* HERO */
.hero{{min-height:92vh;background:linear-gradient(160deg,#0D0D0D 0%,#1A1200 60%,#0D0D0D 100%);display:flex;align-items:center;padding:0 6%;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;width:600px;height:600px;border-radius:50%;border:1px solid var(--gold)15;top:50%;left:50%;transform:translate(-50%,-50%)}}
.hero::after{{content:'';position:absolute;width:900px;height:900px;border-radius:50%;border:1px solid var(--gold)08;top:50%;left:50%;transform:translate(-50%,-50%)}}
.hero-inner{{max-width:700px;position:relative;z-index:1}}
.hero-eyebrow{{display:inline-block;color:var(--gold);font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;margin-bottom:1.5rem;padding-bottom:.5rem;border-bottom:1px solid var(--gold)40}}
.hero-title{{font-family:'Cormorant Garamond',serif;font-size:clamp(3rem,6vw,6rem);font-weight:300;font-style:italic;line-height:1.1;letter-spacing:.02em;margin-bottom:1.5rem;color:var(--cream)}}
.hero-title em{{font-style:normal;color:var(--gold)}}
.hero-sub{{font-size:.9rem;color:var(--muted);margin-bottom:2.5rem;max-width:480px;line-height:1.8;font-weight:300}}
.hero-btns{{display:flex;gap:1rem}}
.btn-gold{{background:var(--gold);color:var(--dark);padding:.85rem 2.5rem;font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;border:none;cursor:pointer;transition:all .25s;font-family:inherit;font-weight:600}}
.btn-gold:hover{{background:var(--cream);transform:translateY(-2px)}}
.btn-outline-gold{{background:transparent;color:var(--gold);padding:.85rem 2.5rem;font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;border:1px solid var(--gold);cursor:pointer;transition:all .25s;font-family:inherit}}
.btn-outline-gold:hover{{background:var(--gold);color:var(--dark)}}
.hero-right{{position:absolute;right:0;top:0;width:45%;height:100%;background:linear-gradient(90deg,var(--dark) 0%,transparent 30%);display:flex;align-items:center;justify-content:center;gap:1.5rem;flex-wrap:wrap;padding:2rem 3rem 2rem 4rem}}
.hero-prod{{background:var(--dark2);border:1px solid var(--border);padding:1.5rem;text-align:center;min-width:120px;transition:all .3s}}
.hero-prod:hover{{border-color:var(--gold);transform:translateY(-4px)}}
.hero-prod-ico{{font-size:2.5rem;margin-bottom:.5rem}}
.hero-prod-name{{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}}
.hero-prod-price{{font-family:'Cormorant Garamond',serif;font-size:1.1rem;color:var(--gold)}}
/* FEATS BAR */
.feat-bar{{background:var(--dark2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:1.5rem 6%;display:flex;gap:3rem;justify-content:center;flex-wrap:wrap}}
.el-feat{{display:flex;align-items:center;gap:.8rem;font-size:.75rem}}
.el-feat span{{font-size:1.3rem}}
.el-feat strong{{display:block;letter-spacing:.08em;text-transform:uppercase;font-size:.7rem;color:var(--cream);margin-bottom:.1rem}}
.el-feat p{{color:var(--muted);font-size:.7rem;margin:0}}
/* SECTIONS */
section{{padding:6rem 6%}}
.sec-eyebrow{{text-align:center;color:var(--gold);font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;margin-bottom:1rem}}
.sec-title{{text-align:center;font-family:'Cormorant Garamond',serif;font-size:clamp(2rem,4vw,3.5rem);font-weight:300;font-style:italic;margin-bottom:.8rem;color:var(--cream)}}
.sec-div{{width:60px;height:1px;background:var(--gold);margin:0 auto 3rem}}
/* CATS */
#categories{{background:var(--dark)}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1px;max-width:1200px;margin:0 auto;background:var(--border)}}
.cat-item{{background:var(--dark2);padding:2rem 1.5rem;text-align:center;cursor:pointer;transition:all .25s;display:flex;flex-direction:column;align-items:center;gap:.5rem}}
.cat-item:hover{{background:var(--dark3);}}
.cat-ico{{font-size:2rem}}
.cat-nm{{font-size:.75rem;letter-spacing:.1em;text-transform:uppercase;color:var(--cream)}}
.cat-ct{{font-size:.68rem;color:var(--muted)}}
/* PRODUCTS */
#products{{background:var(--dark2)}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1px;max-width:1200px;margin:0 auto;background:var(--border)}}
.p-card{{background:var(--dark);position:relative;transition:all .3s;display:flex;flex-direction:column}}
.p-card:hover{{background:var(--dark3)}}
.p-badge{{position:absolute;top:1rem;left:1rem;background:var(--gold);color:var(--dark);font-size:.65rem;font-weight:700;padding:.2rem .6rem;letter-spacing:.08em;text-transform:uppercase;z-index:1}}
.p-img{{height:200px;display:flex;align-items:center;justify-content:center;font-size:5rem;background:linear-gradient(135deg,#1A1200,#0D0D0D);border-bottom:1px solid var(--border)}}
.p-body{{padding:1.5rem;flex:1;display:flex;flex-direction:column}}
.p-name{{font-family:'Cormorant Garamond',serif;font-size:1.15rem;font-weight:500;color:var(--cream);margin-bottom:.4rem}}
.p-desc{{font-size:.78rem;color:var(--muted);margin-bottom:.8rem;line-height:1.6;flex:1}}
.p-stars{{color:var(--gold);font-size:.8rem;margin-bottom:1rem;letter-spacing:.05em}}
.p-rev{{color:var(--muted);font-size:.72rem}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-family:'Cormorant Garamond',serif;font-size:1.3rem;color:var(--gold)}}
.p-orig{{font-size:.78rem;color:var(--muted);margin-left:.4rem}}
.el-btn-add{{background:transparent;border:1px solid var(--gold);color:var(--gold);padding:.45rem 1rem;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:all .25s;font-family:inherit}}
.el-btn-add:hover{{background:var(--gold);color:var(--dark)}}
/* STATS */
.stats-bar{{background:#1A1200;border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:4rem 6%;display:flex;justify-content:center;gap:6rem;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-n{{font-family:'Cormorant Garamond',serif;font-size:3.5rem;font-weight:300;color:var(--gold);line-height:1}}
.stat-l{{font-size:.68rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:.5rem}}
/* TESTIS */
#testimonials{{background:var(--dark)}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1px;max-width:1100px;margin:0 auto;background:var(--border)}}
.t-card{{background:var(--dark2);padding:2.5rem}}
.t-stars{{color:var(--gold);font-size:1rem;letter-spacing:.1em;margin-bottom:1rem}}
.t-text{{font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-style:italic;color:var(--cream);line-height:1.7;margin-bottom:1.5rem}}
.t-author{{display:flex;align-items:center;gap:1rem}}
.t-av{{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:.95rem;color:var(--dark);flex-shrink:0}}
.t-name{{font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--cream)}}
.t-loc{{font-size:.7rem;color:var(--muted)}}
/* ABOUT */
#about{{background:var(--dark2)}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:6rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:linear-gradient(160deg,#1A1200,#0D0D0D);height:500px;display:flex;align-items:center;justify-content:center;font-size:8rem;border:1px solid var(--border)}}
.ab-text .sec-eyebrow{{text-align:left}}
.ab-text .sec-title{{text-align:left}}
.ab-text .sec-div{{margin:0 0 2rem}}
.ab-mission{{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-style:italic;color:var(--gold);margin-bottom:1.5rem;padding-left:1.5rem;border-left:1px solid var(--gold)}}
.ab-story{{color:var(--muted);line-height:1.9;font-size:.88rem;margin-bottom:2rem}}
.el-val{{display:inline-block;border:1px solid var(--gold)40;color:var(--gold);padding:.35rem 1rem;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;margin:.3rem}}
/* CONTACT */
#contact{{background:var(--dark)}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-info h3{{font-family:'Cormorant Garamond',serif;font-size:2rem;font-style:italic;font-weight:300;color:var(--cream);margin-bottom:2rem}}
.ct-item{{display:flex;gap:1rem;margin-bottom:1.5rem;align-items:flex-start}}
.ct-ico{{font-size:1.1rem;margin-top:.1rem}}
.ct-item strong{{display:block;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--cream);margin-bottom:.2rem}}
.ct-item span{{font-size:.8rem;color:var(--muted)}}
.ct-social{{display:flex;gap:.75rem;margin-top:2rem}}
.ct-soc{{background:transparent;border:1px solid var(--border);color:var(--muted);padding:.5rem 1rem;font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:all .25s;font-family:inherit}}
.ct-soc:hover{{border-color:var(--gold);color:var(--gold)}}
.ct-form{{background:var(--dark2);border:1px solid var(--border);padding:2.5rem}}
.ct-form h3{{font-family:'Cormorant Garamond',serif;font-size:1.4rem;font-style:italic;font-weight:300;color:var(--cream);margin-bottom:2rem}}
.fg{{margin-bottom:1.25rem}}
.fg label{{display:block;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.75rem 1rem;background:var(--dark3);border:1px solid var(--border);color:var(--cream);font-family:inherit;font-size:.85rem;outline:none;transition:border-color .2s}}
.fg input:focus,.fg textarea:focus{{border-color:var(--gold)}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.9rem;background:var(--gold);color:var(--dark);border:none;font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;cursor:pointer;transition:all .25s;font-family:inherit;font-weight:600}}
.btn-send:hover{{background:var(--cream)}}
/* FOOTER */
footer{{background:#080808;border-top:1px solid var(--border);padding:4rem 6% 2rem}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-family:'Cormorant Garamond',serif;font-size:1.8rem;font-style:italic;font-weight:300;color:var(--gold);margin-bottom:.5rem}}
.ft-tg{{font-size:.75rem;color:var(--muted);line-height:1.7;max-width:220px}}
.ft-col h4{{font-size:.65rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.6rem}}
.ft-col ul li a{{font-size:.78rem;color:var(--muted);transition:color .2s}}
.ft-col ul li a:hover{{color:var(--gold)}}
.ft-bot{{border-top:1px solid var(--border);padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.7rem;color:var(--muted);letter-spacing:.05em}}
@media(max-width:960px){{.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:3rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}.hero-right{{display:none}}.feat-bar{{gap:1.5rem}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:3rem}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-eyebrow{{animation:fadeUp .6s ease both .1s}}.hero-title{{animation:fadeUp .6s ease both .2s}}.hero-sub{{animation:fadeUp .6s ease both .3s}}.hero-btns{{animation:fadeUp .6s ease both .4s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an}</div>
<nav>
  <a href="#home" class="nav-brand">{name}</a>
  <ul class="nav-links">
    <li><a href="#categories">Collections</a></li>
    <li><a href="#products">Shop</a></li>
    <li><a href="#about">Maison</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <button class="nav-cta" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Shop Now')}</button>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">{h.get('badge','New Collection')}</div>
      <h1 class="hero-title">{h.get('title',name).replace(' ','<br/><em>',1)}</em></h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-gold" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Discover Now')}</button>
        <button class="btn-outline-gold" onclick="document.getElementById('categories').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','View Collections')}</button>
      </div>
    </div>
    <div class="hero-right">
      {''.join(f'<div class="hero-prod"><div class="hero-prod-ico">{p.get("emoji","")}</div><div class="hero-prod-name">{p.get("name","")[:20]}</div><div class="hero-prod-price">{p.get("price","")}</div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-bar">{feats}</div>
<section id="categories">
  <div class="sec-eyebrow">Our World</div>
  <h2 class="sec-title">The Collections</h2>
  <div class="sec-div"></div>
  <div class="cat-grid">{ch}</div>
</section>
<section id="products">
  <div class="sec-eyebrow">Curated Selection</div>
  <h2 class="sec-title">Featured Pieces</h2>
  <div class="sec-div"></div>
  <div class="p-grid">{ph}</div>
</section>
<div class="stats-bar">{sh}</div>
<section id="testimonials">
  <div class="sec-eyebrow">Clientele</div>
  <h2 class="sec-title">Their Words</h2>
  <div class="sec-div"></div>
  <div class="t-grid">{th}</div>
</section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">🌹</div>
    <div class="ab-text">
      <div class="sec-eyebrow">Our Maison</div>
      <h2 class="sec-title">The Story of {name}</h2>
      <div class="sec-div"></div>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div>{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-eyebrow">Reach Us</div>
  <h2 class="sec-title">Get In Touch</h2>
  <div class="sec-div"></div>
  <div class="ct-grid">
    <div class="ct-info">
      <h3>We'd love to hear from you</h3>
      <div class="ct-item"><div class="ct-ico">📧</div><div><strong>Email</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📞</div><div><strong>Phone</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📍</div><div><strong>Address</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social">
        <button class="ct-soc">Instagram</button>
        <button class="ct-soc">TikTok</button>
        <button class="ct-soc">Twitter</button>
      </div>
    </div>
    <div class="ct-form">
      <h3>Send a Message</h3>
      <div class="fg"><label>Name</label><input type="text" placeholder="Your full name"/></div>
      <div class="fg"><label>Email</label><input type="email" placeholder="your@email.com"/></div>
      <div class="fg"><label>Subject</label><select><option>General Enquiry</option><option>Order Support</option><option>Returns</option><option>Partnership</option></select></div>
      <div class="fg"><label>Message</label><textarea placeholder="How may we assist you?"></textarea></div>
      <button class="btn-send" onclick="alert('Thank you. We will respond within 24 hours.')">Send Message</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name}</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Shop</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Help</h4><ul><li><a href="#">FAQ</a></li><li><a href="#">Shipping</a></li><li><a href="#">Returns</a></li><li><a href="#">Track Order</a></li></ul></div>
    <div class="ft-col"><h4>Company</h4><ul><li><a href="#about">About</a></li><li><a href="#contact">Contact</a></li><li><a href="#">Privacy</a></li><li><a href="#">Terms</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Generated by BizBuilder AI.</span></div>
</footer>
{_interactive_block(c.get("products",[]), "#C9A84C", "#E8D5A3", "#1A1A1A", "#F5E6C8", "#2A2400")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 2. BOLD & COLORFUL
# ══════════════════════════════════════════════════════════════════════════════

def _build_bold(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")
    cs = c.get("color_scheme", {})
    p1 = cs.get("primary", "#FF3366")
    p2 = cs.get("secondary", "#CC1144")
    acc = cs.get("accent", "#FFE600")

    ph = _products_block(c.get("products", []), "bl-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), p1)
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="bl-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="bl-feat"><div class="bl-feat-ico">{f["icon"]}</div><strong>{f["title"]}</strong><p>{f["desc"]}</p></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--p:{p1};--s:{p2};--a:{acc};--bg:#FAFAFA;--white:#fff;--dark:#111;--border:#E0E0E0;--text:#1A1A1A;--muted:#666}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}}
.ann{{background:var(--dark);color:var(--a);text-align:center;padding:.55rem;font-size:.82rem;font-weight:700;letter-spacing:.05em}}
nav{{background:var(--white);border-bottom:3px solid var(--p);padding:0 5%;display:flex;align-items:center;justify-content:space-between;height:70px;position:sticky;top:0;z-index:100;box-shadow:4px 0 0 0 var(--p)}}
.nav-brand{{font-family:'Bebas Neue',sans-serif;font-size:2rem;color:var(--p);letter-spacing:.06em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.88rem;font-weight:700;color:var(--text);text-decoration:none;text-transform:uppercase;letter-spacing:.05em;transition:color .15s}}
.nav-links a:hover{{color:var(--p)}}
.nav-right{{display:flex;gap:.75rem;align-items:center}}
.nav-search{{background:#f0f0f0;border:none;padding:.5rem 1rem;font-size:.82rem;cursor:pointer;font-family:inherit}}
.nav-cart{{background:var(--p);color:#fff;border:none;padding:.55rem 1.3rem;font-weight:800;font-size:.85rem;cursor:pointer;text-transform:uppercase;letter-spacing:.05em;transition:all .15s;font-family:inherit}}
.nav-cart:hover{{background:var(--s);transform:scale(1.02)}}
.hero{{background:linear-gradient(135deg,var(--p) 0%,{p2} 40%,var(--a) 100%);padding:6rem 5%;position:relative;overflow:hidden;min-height:90vh;display:flex;align-items:center}}
.hero::before{{content:'SHOP';position:absolute;font-family:'Bebas Neue',sans-serif;font-size:28vw;color:rgba(255,255,255,0.05);top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;line-height:1}}
.hero-content{{flex:1;max-width:600px;position:relative;z-index:1}}
.hero-tag{{display:inline-block;background:var(--a);color:var(--dark);padding:.35rem .9rem;font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1.5rem}}
.hero-title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(4rem,8vw,8rem);line-height:.95;letter-spacing:.04em;color:#fff;margin-bottom:1.5rem;text-shadow:4px 4px 0 rgba(0,0,0,0.2)}}
.hero-sub{{font-size:1rem;color:rgba(255,255,255,.85);margin-bottom:2.5rem;max-width:460px;line-height:1.7;font-weight:500}}
.hero-btns{{display:flex;gap:1rem;flex-wrap:wrap}}
.btn-white{{background:#fff;color:var(--p);padding:.9rem 2.5rem;font-weight:800;font-size:.9rem;border:none;cursor:pointer;text-transform:uppercase;letter-spacing:.06em;transition:all .2s;font-family:inherit}}
.btn-white:hover{{background:var(--a);color:var(--dark);transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,0.2)}}
.btn-outline-white{{background:transparent;color:#fff;padding:.9rem 2.5rem;font-weight:700;font-size:.9rem;border:3px solid #fff;cursor:pointer;text-transform:uppercase;letter-spacing:.06em;transition:all .2s;font-family:inherit}}
.btn-outline-white:hover{{background:#fff;color:var(--p)}}
.hero-cards{{position:absolute;right:5%;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:1rem}}
.hero-pcard{{background:rgba(255,255,255,.15);backdrop-filter:blur(10px);border:2px solid rgba(255,255,255,.3);padding:1rem 1.25rem;display:flex;align-items:center;gap:.75rem;transition:all .2s;min-width:200px}}
.hero-pcard:hover{{background:rgba(255,255,255,.25);transform:translateX(-4px)}}
.hpc-ico{{font-size:2rem}}
.hpc-info{{flex:1}}
.hpc-name{{font-size:.78rem;font-weight:700;color:#fff}}
.hpc-price{{font-size:.9rem;font-weight:800;color:var(--a)}}
.feat-bar{{background:var(--white);border-bottom:3px solid var(--a);padding:1.5rem 5%;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}}
.bl-feat{{display:flex;align-items:center;gap:.75rem;padding:.5rem}}
.bl-feat-ico{{font-size:1.8rem;flex-shrink:0}}
.bl-feat strong{{font-size:.85rem;font-weight:800;display:block;text-transform:uppercase;letter-spacing:.04em}}
.bl-feat p{{font-size:.78rem;color:var(--muted);margin:0}}
section{{padding:5rem 5%}}
.sec-label{{text-align:center;color:var(--p);font-weight:800;font-size:.75rem;letter-spacing:.15em;text-transform:uppercase;margin-bottom:.5rem}}
.sec-title{{text-align:center;font-family:'Bebas Neue',sans-serif;font-size:clamp(2.5rem,5vw,4rem);letter-spacing:.04em;margin-bottom:.5rem}}
.sec-line{{width:60px;height:4px;background:var(--p);margin:0 auto 3rem}}
#categories{{background:var(--white)}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem;max-width:1100px;margin:0 auto}}
.cat-item{{background:var(--cat-color,#f5f5f5);padding:1.75rem 1rem;text-align:center;cursor:pointer;border:3px solid transparent;transition:all .2s}}
.cat-item:hover{{border-color:var(--p);transform:translateY(-4px);box-shadow:6px 6px 0 var(--p)}}
.cat-ico{{font-size:2.2rem;margin-bottom:.5rem}}
.cat-nm{{font-size:.82rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}}
.cat-ct{{font-size:.72rem;color:var(--muted);margin-top:.2rem}}
#products{{background:var(--bg)}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1.5rem;max-width:1200px;margin:0 auto}}
.p-card{{background:var(--white);border:3px solid var(--border);position:relative;transition:all .2s}}
.p-card:hover{{border-color:var(--p);transform:translateY(-4px);box-shadow:6px 6px 0 var(--p)}}
.p-badge{{position:absolute;top:0;left:0;background:var(--p);color:#fff;font-size:.7rem;font-weight:800;padding:.3rem .7rem;letter-spacing:.05em;text-transform:uppercase;z-index:1}}
.p-img{{height:200px;display:flex;align-items:center;justify-content:center;font-size:5rem;background:linear-gradient(135deg,{p1}15,{acc}15);border-bottom:3px solid var(--border)}}
.p-body{{padding:1.25rem}}
.p-name{{font-size:1rem;font-weight:800;margin-bottom:.3rem;text-transform:uppercase;letter-spacing:.02em}}
.p-desc{{font-size:.8rem;color:var(--muted);margin-bottom:.75rem;line-height:1.5}}
.p-stars{{color:var(--p);font-size:.85rem;font-weight:700;margin-bottom:.75rem}}
.p-rev{{color:var(--muted);font-size:.75rem;font-weight:400}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-size:1.3rem;font-weight:800;color:var(--p)}}
.p-orig{{font-size:.78rem;color:var(--muted);text-decoration:line-through;margin-left:.4rem}}
.bl-add{{background:var(--dark);color:#fff;border:none;padding:.55rem 1.1rem;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;cursor:pointer;transition:all .2s;font-family:inherit}}
.bl-add:hover{{background:var(--p)}}
.stats-bar{{background:var(--dark);padding:4rem 5%;display:flex;justify-content:center;gap:5rem;flex-wrap:wrap;border-top:4px solid var(--p)}}
.stat{{text-align:center}}
.stat-n{{font-family:'Bebas Neue',sans-serif;font-size:4rem;color:var(--a);line-height:1;letter-spacing:.04em}}
.stat-l{{font-size:.75rem;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:.1em;margin-top:.3rem}}
#testimonials{{background:var(--white)}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}}
.t-card{{background:var(--bg);border:3px solid var(--border);padding:2rem;transition:all .2s}}
.t-card:hover{{border-color:var(--p);transform:translateY(-3px);box-shadow:5px 5px 0 var(--p)}}
.t-stars{{color:var(--p);font-size:1.1rem;margin-bottom:.75rem}}
.t-text{{font-size:.95rem;line-height:1.7;margin-bottom:1.25rem;font-weight:500}}
.t-author{{display:flex;align-items:center;gap:.75rem}}
.t-av{{width:44px;height:44px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1rem;color:#fff;flex-shrink:0}}
.t-name{{font-weight:800;font-size:.9rem;text-transform:uppercase;letter-spacing:.04em}}
.t-loc{{font-size:.75rem;color:var(--muted)}}
#about{{background:var(--bg)}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:linear-gradient(135deg,var(--p),var(--a));height:420px;display:flex;align-items:center;justify-content:center;font-size:8rem;border:4px solid var(--dark)}}
.ab-text .sec-label{{text-align:left}}
.ab-text .sec-title{{text-align:left}}
.ab-text .sec-line{{margin:0 0 1.5rem}}
.ab-mission{{font-size:1.1rem;font-weight:700;color:var(--p);margin-bottom:1rem;padding-left:1rem;border-left:4px solid var(--p)}}
.ab-story{{color:var(--muted);line-height:1.8;margin-bottom:1.5rem;font-size:.9rem}}
.bl-val{{display:inline-block;background:var(--p);color:#fff;padding:.35rem .9rem;font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;margin:.3rem}}
#contact{{background:var(--white)}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-info h3{{font-family:'Bebas Neue',sans-serif;font-size:2.5rem;letter-spacing:.04em;margin-bottom:1.5rem}}
.ct-item{{display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.25rem}}
.ct-ico{{font-size:1.2rem}}
.ct-item strong{{display:block;font-weight:800;font-size:.85rem;text-transform:uppercase;letter-spacing:.04em}}
.ct-item span{{font-size:.82rem;color:var(--muted)}}
.ct-social{{display:flex;gap:.75rem;margin-top:1.5rem;flex-wrap:wrap}}
.ct-soc{{background:var(--dark);color:#fff;border:none;padding:.5rem 1.1rem;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;cursor:pointer;transition:all .2s;font-family:inherit}}
.ct-soc:hover{{background:var(--p)}}
.ct-form{{background:var(--bg);border:3px solid var(--border);padding:2rem}}
.ct-form h3{{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;letter-spacing:.04em;margin-bottom:1.5rem}}
.fg{{margin-bottom:1rem}}
.fg label{{display:block;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35rem}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.72rem .9rem;border:3px solid var(--border);background:var(--white);font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s}}
.fg input:focus,.fg textarea:focus{{border-color:var(--p)}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.9rem;background:var(--p);color:#fff;border:none;font-weight:800;font-size:.88rem;text-transform:uppercase;letter-spacing:.08em;cursor:pointer;transition:all .2s;font-family:inherit}}
.btn-send:hover{{background:var(--s)}}
footer{{background:var(--dark);padding:4rem 5% 2rem;border-top:4px solid var(--p)}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-family:'Bebas Neue',sans-serif;font-size:2rem;color:var(--p);letter-spacing:.06em;margin-bottom:.5rem}}
.ft-tg{{font-size:.8rem;color:#888;line-height:1.7}}
.ft-col h4{{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.15em;color:#888;margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.55rem}}
.ft-col ul li a{{font-size:.82rem;color:#888;text-decoration:none;transition:color .15s}}
.ft-col ul li a:hover{{color:var(--p)}}
.ft-bot{{border-top:1px solid #333;padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.75rem;color:#555}}
@media(max-width:960px){{.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:2.5rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}.hero-cards{{display:none}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:2.5rem}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(24px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-tag{{animation:fadeUp .5s ease both .05s}}.hero-title{{animation:fadeUp .5s ease both .15s}}.hero-sub{{animation:fadeUp .5s ease both .25s}}.hero-btns{{animation:fadeUp .5s ease both .35s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an}</div>
<nav>
  <a href="#home" class="nav-brand">{name}</a>
  <ul class="nav-links">
    <li><a href="#categories">Categories</a></li>
    <li><a href="#products">Shop</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="nav-right">
    <button class="nav-search">🔍 Search</button>
    <button class="nav-cart" onclick="alert('Cart coming soon!')">🛒 Cart (0)</button>
  </div>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-tag">{h.get('badge','New Drop 🔥')}</div>
      <h1 class="hero-title">{h.get('title',name)}</h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-white" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Shop Now')}</button>
        <button class="btn-outline-white" onclick="document.getElementById('categories').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','Browse All')}</button>
      </div>
    </div>
    <div class="hero-cards">
      {''.join(f'<div class="hero-pcard"><div class="hpc-ico">{p.get("emoji","")}</div><div class="hpc-info"><div class="hpc-name">{p.get("name","")[:22]}</div><div class="hpc-price">{p.get("price","")}</div></div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-bar">{feats}</div>
<section id="categories"><div class="sec-label">Browse</div><h2 class="sec-title">Shop by Category</h2><div class="sec-line"></div><div class="cat-grid">{ch}</div></section>
<section id="products"><div class="sec-label">Featured</div><h2 class="sec-title">Hot Right Now 🔥</h2><div class="sec-line"></div><div class="p-grid">{ph}</div></section>
<div class="stats-bar">{sh}</div>
<section id="testimonials"><div class="sec-label">Reviews</div><h2 class="sec-title">The People Have Spoken</h2><div class="sec-line"></div><div class="t-grid">{th}</div></section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">🎨</div>
    <div class="ab-text">
      <div class="sec-label">Our Story</div><h2 class="sec-title">About {name}</h2><div class="sec-line"></div>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div>{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-label">Reach Out</div><h2 class="sec-title">Contact Us</h2><div class="sec-line"></div>
  <div class="ct-grid">
    <div class="ct-info">
      <h3>Let's Talk</h3>
      <div class="ct-item"><div class="ct-ico">📧</div><div><strong>Email</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📞</div><div><strong>Phone</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📍</div><div><strong>Address</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social"><button class="ct-soc">Instagram</button><button class="ct-soc">TikTok</button><button class="ct-soc">Twitter</button></div>
    </div>
    <div class="ct-form">
      <h3>Send a Message</h3>
      <div class="fg"><label>Name</label><input type="text" placeholder="Your name"/></div>
      <div class="fg"><label>Email</label><input type="email" placeholder="your@email.com"/></div>
      <div class="fg"><label>Message</label><textarea placeholder="What's up?"></textarea></div>
      <button class="btn-send" onclick="alert('Message sent! We will get back to you soon.')">Send It 🚀</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name}</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Shop</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Help</h4><ul><li><a href="#">FAQ</a></li><li><a href="#">Shipping</a></li><li><a href="#">Returns</a></li></ul></div>
    <div class="ft-col"><h4>Company</h4><ul><li><a href="#about">About</a></li><li><a href="#contact">Contact</a></li><li><a href="#">Press</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Generated by BizBuilder AI.</span></div>
</footer>
{_interactive_block(c.get("products",[]), p1, acc, "#FFFFFF", "#1A1A1A", "#E0E0E0")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 3. MINIMAL & CLEAN
# ══════════════════════════════════════════════════════════════════════════════

def _build_minimal(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")
    cs = c.get("color_scheme", {})
    p1 = cs.get("primary", "#111111")

    ph = _products_block(c.get("products", []), "mn-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), "#111")
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="mn-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="mn-feat"><div class="mn-feat-ico">{f["icon"]}</div><div><strong>{f["title"]}</strong><p>{f["desc"]}</p></div></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:'DM Sans',sans-serif;background:#fff;color:#111;line-height:1.7;-webkit-font-smoothing:antialiased}}
.ann{{background:#111;color:#fff;text-align:center;padding:.5rem;font-size:.78rem;letter-spacing:.08em}}
nav{{background:#fff;border-bottom:1px solid #EBEBEB;padding:0 6%;display:flex;align-items:center;justify-content:space-between;height:68px;position:sticky;top:0;z-index:100}}
.nav-brand{{font-family:'DM Serif Display',serif;font-size:1.4rem;color:#111;letter-spacing:.03em}}
.nav-links{{display:flex;gap:2.5rem;list-style:none}}
.nav-links a{{font-size:.85rem;font-weight:400;color:#666;text-decoration:none;transition:color .2s;letter-spacing:.02em}}
.nav-links a:hover{{color:#111}}
.nav-right{{display:flex;gap:1rem;align-items:center}}
.nav-search{{background:transparent;border:1px solid #EBEBEB;padding:.45rem 1rem;font-size:.82rem;cursor:pointer;font-family:inherit;color:#666}}
.nav-cart{{background:#111;color:#fff;border:none;padding:.5rem 1.2rem;font-weight:500;font-size:.82rem;cursor:pointer;transition:all .2s;font-family:inherit}}
.nav-cart:hover{{background:#333}}
.hero{{padding:7rem 6%;background:#fff;display:flex;align-items:center;gap:6rem;min-height:88vh}}
.hero-content{{flex:1;max-width:520px}}
.hero-eyebrow{{font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;color:#999;margin-bottom:1.5rem}}
.hero-title{{font-family:'DM Serif Display',serif;font-size:clamp(2.8rem,5vw,5rem);font-weight:400;line-height:1.1;letter-spacing:-.01em;margin-bottom:1.5rem;color:#111}}
.hero-sub{{font-size:.95rem;color:#666;margin-bottom:2.5rem;line-height:1.8;font-weight:300}}
.hero-btns{{display:flex;gap:1rem;flex-wrap:wrap}}
.btn-dark{{background:#111;color:#fff;padding:.8rem 2rem;font-size:.82rem;font-weight:500;border:none;cursor:pointer;transition:all .2s;letter-spacing:.04em;font-family:inherit}}
.btn-dark:hover{{background:#333;transform:translateY(-1px)}}
.btn-outline-dark{{background:transparent;color:#111;padding:.8rem 2rem;font-size:.82rem;font-weight:500;border:1px solid #111;cursor:pointer;transition:all .2s;letter-spacing:.04em;font-family:inherit}}
.btn-outline-dark:hover{{background:#111;color:#fff}}
.hero-right{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#EBEBEB}}
.hero-pcard{{background:#fff;padding:2rem;display:flex;flex-direction:column;align-items:center;text-align:center;gap:.5rem;transition:background .2s;cursor:pointer}}
.hero-pcard:hover{{background:#FAFAFA}}
.hp-ico{{font-size:3rem;margin-bottom:.25rem}}
.hp-name{{font-size:.78rem;letter-spacing:.05em;text-transform:uppercase;color:#666}}
.hp-price{{font-family:'DM Serif Display',serif;font-size:1.1rem;color:#111}}
.feat-bar{{background:#FAFAFA;border-top:1px solid #EBEBEB;border-bottom:1px solid #EBEBEB;padding:1.5rem 6%;display:flex;gap:3rem;justify-content:center;flex-wrap:wrap}}
.mn-feat{{display:flex;align-items:center;gap:.75rem}}
.mn-feat-ico{{font-size:1.2rem}}
.mn-feat strong{{font-size:.82rem;font-weight:600;display:block;letter-spacing:.03em}}
.mn-feat p{{font-size:.75rem;color:#999;margin:0}}
section{{padding:6rem 6%}}
.sec-eyebrow{{text-align:center;font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:#999;margin-bottom:.75rem}}
.sec-title{{text-align:center;font-family:'DM Serif Display',serif;font-size:clamp(2rem,3.5vw,3rem);font-weight:400;margin-bottom:.75rem;color:#111}}
.sec-rule{{width:40px;height:1px;background:#111;margin:0 auto 3rem}}
#categories{{background:#fff}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:1px;max-width:1100px;margin:0 auto;background:#EBEBEB}}
.cat-item{{background:#fff;padding:2rem 1rem;text-align:center;cursor:pointer;transition:background .2s;display:flex;flex-direction:column;align-items:center;gap:.4rem}}
.cat-item:hover{{background:#FAFAFA}}
.cat-ico{{font-size:1.8rem}}
.cat-nm{{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:#111;font-weight:500}}
.cat-ct{{font-size:.7rem;color:#999}}
#products{{background:#FAFAFA}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:1px;max-width:1200px;margin:0 auto;background:#EBEBEB}}
.p-card{{background:#fff;position:relative;transition:background .2s;display:flex;flex-direction:column}}
.p-card:hover{{background:#FAFAFA}}
.p-badge{{position:absolute;top:1rem;left:1rem;background:#111;color:#fff;font-size:.65rem;font-weight:500;padding:.2rem .55rem;letter-spacing:.08em;text-transform:uppercase;z-index:1}}
.p-img{{height:220px;display:flex;align-items:center;justify-content:center;font-size:5rem;background:#F8F8F8;border-bottom:1px solid #EBEBEB}}
.p-body{{padding:1.5rem;flex:1;display:flex;flex-direction:column}}
.p-name{{font-family:'DM Serif Display',serif;font-size:1.05rem;font-weight:400;margin-bottom:.3rem;color:#111}}
.p-desc{{font-size:.78rem;color:#888;margin-bottom:.75rem;line-height:1.6;flex:1}}
.p-stars{{color:#111;font-size:.8rem;margin-bottom:.75rem;letter-spacing:.08em}}
.p-rev{{color:#bbb;font-size:.72rem}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-family:'DM Serif Display',serif;font-size:1.2rem;color:#111}}
.p-orig{{font-size:.75rem;color:#bbb;text-decoration:line-through;margin-left:.3rem}}
.mn-add{{background:transparent;border:1px solid #111;color:#111;padding:.45rem 1rem;font-size:.72rem;font-weight:500;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;transition:all .2s;font-family:inherit}}
.mn-add:hover{{background:#111;color:#fff}}
.stats-bar{{background:#111;padding:4rem 6%;display:flex;justify-content:center;gap:6rem;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-n{{font-family:'DM Serif Display',serif;font-size:3.5rem;font-weight:400;color:#fff;line-height:1}}
.stat-l{{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#666;margin-top:.5rem}}
#testimonials{{background:#fff}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1px;max-width:1100px;margin:0 auto;background:#EBEBEB}}
.t-card{{background:#fff;padding:2.5rem}}
.t-stars{{color:#111;font-size:.9rem;letter-spacing:.1em;margin-bottom:1rem}}
.t-text{{font-family:'DM Serif Display',serif;font-size:1rem;font-style:italic;line-height:1.7;margin-bottom:1.5rem;color:#333}}
.t-author{{display:flex;align-items:center;gap:.75rem}}
.t-av{{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:.9rem;color:#fff;flex-shrink:0}}
.t-name{{font-size:.8rem;font-weight:600;letter-spacing:.04em;color:#111}}
.t-loc{{font-size:.72rem;color:#999}}
#about{{background:#FAFAFA}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:6rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:#EBEBEB;height:480px;display:flex;align-items:center;justify-content:center;font-size:8rem}}
.ab-text .sec-eyebrow{{text-align:left}}
.ab-text .sec-title{{text-align:left}}
.ab-text .sec-rule{{margin:0 0 2rem}}
.ab-mission{{font-family:'DM Serif Display',serif;font-size:1.1rem;font-style:italic;color:#333;margin-bottom:1.25rem;padding-left:1.25rem;border-left:2px solid #111;line-height:1.6}}
.ab-story{{color:#666;line-height:1.9;margin-bottom:1.75rem;font-size:.88rem;font-weight:300}}
.mn-val{{display:inline-block;border:1px solid #DDD;color:#666;padding:.3rem .85rem;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;margin:.25rem}}
#contact{{background:#fff}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-info h3{{font-family:'DM Serif Display',serif;font-size:2rem;font-weight:400;margin-bottom:2rem;color:#111}}
.ct-item{{display:flex;gap:1rem;margin-bottom:1.25rem;align-items:flex-start}}
.ct-ico{{font-size:1rem;margin-top:.15rem;color:#999}}
.ct-item strong{{display:block;font-size:.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.2rem}}
.ct-item span{{font-size:.82rem;color:#666}}
.ct-social{{display:flex;gap:.6rem;margin-top:1.5rem;flex-wrap:wrap}}
.ct-soc{{background:transparent;border:1px solid #DDD;color:#666;padding:.45rem .9rem;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;transition:all .2s;font-family:inherit}}
.ct-soc:hover{{border-color:#111;color:#111}}
.ct-form{{background:#FAFAFA;padding:2.5rem;border:1px solid #EBEBEB}}
.ct-form h3{{font-family:'DM Serif Display',serif;font-size:1.3rem;font-weight:400;margin-bottom:1.75rem}}
.fg{{margin-bottom:1.1rem}}
.fg label{{display:block;font-size:.72rem;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#999;margin-bottom:.35rem}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.7rem .9rem;border:1px solid #DDD;background:#fff;font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s;color:#111}}
.fg input:focus,.fg textarea:focus{{border-color:#111}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.85rem;background:#111;color:#fff;border:none;font-weight:500;font-size:.82rem;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;transition:all .2s;font-family:inherit}}
.btn-send:hover{{background:#333}}
footer{{background:#111;padding:4rem 6% 2rem}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-family:'DM Serif Display',serif;font-size:1.5rem;font-weight:400;color:#fff;margin-bottom:.5rem}}
.ft-tg{{font-size:.78rem;color:#555;line-height:1.7}}
.ft-col h4{{font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;color:#555;margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.55rem}}
.ft-col ul li a{{font-size:.8rem;color:#555;text-decoration:none;transition:color .2s}}
.ft-col ul li a:hover{{color:#fff}}
.ft-bot{{border-top:1px solid #222;padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.72rem;color:#444}}
@media(max-width:960px){{.hero{{flex-direction:column;min-height:auto;padding:4rem 6%}}.hero-right{{display:none}}.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:3rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:3rem}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-eyebrow{{animation:fadeUp .6s ease both .05s}}.hero-title{{animation:fadeUp .6s ease both .15s}}.hero-sub{{animation:fadeUp .6s ease both .25s}}.hero-btns{{animation:fadeUp .6s ease both .35s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an}</div>
<nav>
  <a href="#home" class="nav-brand">{name}</a>
  <ul class="nav-links">
    <li><a href="#categories">Collections</a></li>
    <li><a href="#products">Shop</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="nav-right">
    <button class="nav-search">Search</button>
    <button class="nav-cart" onclick="alert('Cart coming soon!')">Bag (0)</button>
  </div>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-eyebrow">{h.get('badge','New Collection')}</div>
      <h1 class="hero-title">{h.get('title',name)}</h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-dark" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Shop Now')}</button>
        <button class="btn-outline-dark" onclick="document.getElementById('about').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','Our Story')}</button>
      </div>
    </div>
    <div class="hero-right">
      {''.join(f'<div class="hero-pcard"><div class="hp-ico">{p.get("emoji","")}</div><div class="hp-name">{p.get("name","")[:20]}</div><div class="hp-price">{p.get("price","")}</div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-bar">{feats}</div>
<section id="categories"><div class="sec-eyebrow">Collections</div><h2 class="sec-title">Shop by Category</h2><div class="sec-rule"></div><div class="cat-grid">{ch}</div></section>
<section id="products"><div class="sec-eyebrow">Selection</div><h2 class="sec-title">Featured Products</h2><div class="sec-rule"></div><div class="p-grid">{ph}</div></section>
<div class="stats-bar">{sh}</div>
<section id="testimonials"><div class="sec-eyebrow">Testimonials</div><h2 class="sec-title">What People Say</h2><div class="sec-rule"></div><div class="t-grid">{th}</div></section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">○</div>
    <div class="ab-text">
      <div class="sec-eyebrow">Our Story</div><h2 class="sec-title">About {name}</h2><div class="sec-rule"></div>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div style="margin-top:1rem">{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-eyebrow">Connect</div><h2 class="sec-title">Get In Touch</h2><div class="sec-rule"></div>
  <div class="ct-grid">
    <div class="ct-info">
      <h3>We're here for you</h3>
      <div class="ct-item"><div class="ct-ico">✉</div><div><strong>Email</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">◎</div><div><strong>Phone</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">◈</div><div><strong>Address</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social"><button class="ct-soc">Instagram</button><button class="ct-soc">TikTok</button><button class="ct-soc">Twitter</button></div>
    </div>
    <div class="ct-form">
      <h3>Send us a message</h3>
      <div class="fg"><label>Name</label><input type="text" placeholder="Your name"/></div>
      <div class="fg"><label>Email</label><input type="email" placeholder="your@email.com"/></div>
      <div class="fg"><label>Message</label><textarea placeholder="Tell us how we can help"></textarea></div>
      <button class="btn-send" onclick="alert('Message sent. We will respond shortly.')">Send Message</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name}</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Shop</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Help</h4><ul><li><a href="#">FAQ</a></li><li><a href="#">Shipping</a></li><li><a href="#">Returns</a></li></ul></div>
    <div class="ft-col"><h4>Company</h4><ul><li><a href="#about">About</a></li><li><a href="#contact">Contact</a></li><li><a href="#">Privacy</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Generated by BizBuilder AI.</span></div>
</footer>
{_interactive_block(c.get("products",[]), "#111111", "#555555", "#FFFFFF", "#111111", "#EBEBEB")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 4. DARK & MODERN  (reuse bold structure, dark palette)
# ══════════════════════════════════════════════════════════════════════════════

def _build_dark(name, c, is_ecom):
    # Swap color scheme to dark neon then delegate
    c2 = dict(c)
    c2["color_scheme"] = {"primary":"#6C63FF","secondary":"#5A52D5","accent":"#FF6B9D","text":"#E8E8F5","bg":"#0A0A14"}
    return _build_dark_inner(name, c2, is_ecom)

def _build_dark_inner(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")

    ph = _products_block(c.get("products", []), "dk-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), "#6C63FF")
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="dk-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="dk-feat"><div class="dk-ficon">{f["icon"]}</div><h4>{f["title"]}</h4><p>{f["desc"]}</p></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--p:#6C63FF;--s:#5A52D5;--a:#FF6B9D;--bg:#0A0A14;--bg2:#12122A;--bg3:#1A1A35;--border:#2A2A45;--text:#E8E8F5;--muted:#8888AA;--r:14px}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased}}
.ann{{background:var(--bg2);color:var(--p);text-align:center;padding:.55rem;font-size:.82rem;font-weight:500;border-bottom:1px solid var(--border)}}
nav{{background:rgba(10,10,20,.97);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:0 5%;display:flex;align-items:center;justify-content:space-between;height:68px;position:sticky;top:0;z-index:100}}
.nav-brand{{font-family:'Outfit',sans-serif;font-weight:900;font-size:1.4rem;color:var(--p);letter-spacing:-.03em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.87rem;font-weight:500;color:var(--muted);text-decoration:none;transition:color .2s}}
.nav-links a:hover{{color:var(--text)}}
.nav-right{{display:flex;gap:.75rem;align-items:center}}
.nav-search{{background:var(--bg2);border:1px solid var(--border);color:var(--muted);padding:.45rem 1rem;font-size:.82rem;cursor:pointer;font-family:inherit;border-radius:var(--r)}}
.nav-cart{{background:var(--p);color:#fff;border:none;padding:.5rem 1.3rem;font-weight:700;font-size:.85rem;cursor:pointer;transition:all .2s;font-family:inherit;border-radius:var(--r)}}
.nav-cart:hover{{background:var(--s)}}
.hero{{min-height:92vh;background:radial-gradient(ellipse at 30% 50%,rgba(108,99,255,.15) 0%,transparent 60%),radial-gradient(ellipse at 80% 20%,rgba(255,107,157,.1) 0%,transparent 50%),var(--bg);padding:0 5%;display:flex;align-items:center;gap:4rem;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;width:800px;height:800px;border-radius:50%;border:1px solid rgba(108,99,255,.08);top:50%;left:50%;transform:translate(-50%,-50%)}}
.hero-content{{flex:1;max-width:580px;position:relative;z-index:1}}
.hero-badge{{display:inline-flex;align-items:center;gap:.4rem;background:rgba(108,99,255,.12);border:1px solid rgba(108,99,255,.25);color:var(--p);padding:.35rem 1rem;border-radius:50px;font-size:.78rem;font-weight:600;margin-bottom:1.5rem;letter-spacing:.02em}}
.hero-title{{font-family:'Outfit',sans-serif;font-size:clamp(2.5rem,5vw,4.5rem);font-weight:900;line-height:1.05;letter-spacing:-.04em;margin-bottom:1.25rem}}
.hero-title .hl{{background:linear-gradient(135deg,var(--p),var(--a));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.hero-sub{{font-size:1rem;color:var(--muted);margin-bottom:2.5rem;max-width:460px;line-height:1.75}}
.hero-btns{{display:flex;gap:1rem;flex-wrap:wrap}}
.btn-glow{{background:var(--p);color:#fff;padding:.88rem 2.2rem;font-weight:700;font-size:.95rem;border:none;cursor:pointer;border-radius:50px;transition:all .2s;box-shadow:0 0 30px rgba(108,99,255,.4);font-family:inherit}}
.btn-glow:hover{{background:var(--s);box-shadow:0 0 40px rgba(108,99,255,.6);transform:translateY(-2px)}}
.btn-ghost{{background:transparent;color:var(--text);padding:.88rem 2.2rem;font-weight:600;font-size:.95rem;border:1px solid var(--border);cursor:pointer;border-radius:50px;transition:all .2s;font-family:inherit}}
.btn-ghost:hover{{border-color:var(--p);color:var(--p)}}
.hero-right{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:1rem;position:relative;z-index:1}}
.hero-pcard{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;text-align:center;transition:all .25s;cursor:pointer}}
.hero-pcard:hover{{border-color:var(--p);box-shadow:0 0 20px rgba(108,99,255,.2);transform:translateY(-3px)}}
.hp-ico{{font-size:2.5rem;margin-bottom:.5rem}}
.hp-name{{font-size:.75rem;color:var(--muted);margin-bottom:.25rem;font-weight:500}}
.hp-price{{font-size:1rem;font-weight:700;color:var(--p)}}
.feat-section{{background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:3rem 5%}}
.dk-feat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}}
.dk-feat{{background:var(--bg3);border:1px solid var(--border);border-radius:var(--r);padding:1.75rem;transition:all .25s}}
.dk-feat:hover{{border-color:var(--p);box-shadow:0 0 20px rgba(108,99,255,.15)}}
.dk-ficon{{font-size:2rem;margin-bottom:.75rem}}
.dk-feat h4{{font-weight:700;margin-bottom:.3rem;font-size:.95rem}}
.dk-feat p{{font-size:.82rem;color:var(--muted)}}
section{{padding:5rem 5%}}
.sec-badge{{text-align:center;display:inline-block;background:rgba(108,99,255,.1);border:1px solid rgba(108,99,255,.2);color:var(--p);padding:.25rem .9rem;border-radius:50px;font-size:.72rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.75rem}}
.sec-wrap{{text-align:center;margin-bottom:3rem}}
.sec-title{{font-family:'Outfit',sans-serif;font-size:clamp(1.9rem,3vw,2.8rem);font-weight:800;letter-spacing:-.035em;margin-bottom:.5rem}}
.sec-sub{{font-size:.9rem;color:var(--muted);max-width:500px;margin:0 auto}}
#categories{{background:var(--bg)}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem;max-width:1100px;margin:0 auto}}
.cat-item{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:1.75rem 1rem;text-align:center;cursor:pointer;transition:all .22s;display:flex;flex-direction:column;align-items:center;gap:.5rem}}
.cat-item:hover{{border-color:var(--p);box-shadow:0 0 16px rgba(108,99,255,.2);transform:translateY(-3px)}}
.cat-ico{{font-size:2rem}}
.cat-nm{{font-size:.82rem;font-weight:600;color:var(--text)}}
.cat-ct{{font-size:.72rem;color:var(--muted)}}
#products{{background:var(--bg2)}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:1.5rem;max-width:1200px;margin:0 auto}}
.p-card{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;position:relative;transition:all .25s;display:flex;flex-direction:column}}
.p-card:hover{{border-color:var(--p);box-shadow:0 8px 32px rgba(108,99,255,.2);transform:translateY(-4px)}}
.p-badge{{position:absolute;top:12px;left:12px;background:var(--a);color:#fff;font-size:.68rem;font-weight:700;padding:.22rem .6rem;border-radius:50px;z-index:1}}
.p-img{{height:190px;display:flex;align-items:center;justify-content:center;font-size:4.5rem;background:linear-gradient(135deg,rgba(108,99,255,.12),rgba(255,107,157,.08));border-bottom:1px solid var(--border)}}
.p-body{{padding:1.25rem;flex:1;display:flex;flex-direction:column}}
.p-name{{font-weight:700;font-size:.95rem;margin-bottom:.3rem;color:var(--text)}}
.p-desc{{font-size:.78rem;color:var(--muted);margin-bottom:.75rem;line-height:1.5;flex:1}}
.p-stars{{color:#FFB800;font-size:.82rem;margin-bottom:.75rem;letter-spacing:.05em}}
.p-rev{{color:var(--muted);font-size:.72rem}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-weight:800;font-size:1.1rem;color:var(--p)}}
.p-orig{{font-size:.75rem;color:var(--muted);text-decoration:line-through;margin-left:.35rem}}
.dk-add{{background:var(--p);color:#fff;border:none;border-radius:50px;padding:.48rem 1.05rem;font-size:.78rem;font-weight:700;cursor:pointer;transition:all .2s;font-family:inherit}}
.dk-add:hover{{background:var(--s);transform:scale(1.04)}}
.stats-bar{{background:linear-gradient(135deg,rgba(108,99,255,.15),rgba(255,107,157,.1));border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:3.5rem 5%;display:flex;justify-content:center;gap:5rem;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-n{{font-family:'Outfit',sans-serif;font-size:3rem;font-weight:900;background:linear-gradient(135deg,var(--p),var(--a));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1}}
.stat-l{{font-size:.78rem;color:var(--muted);margin-top:.4rem}}
#testimonials{{background:var(--bg)}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.25rem;max-width:1100px;margin:0 auto}}
.t-card{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:2rem;transition:all .25s}}
.t-card:hover{{border-color:var(--p);box-shadow:0 0 20px rgba(108,99,255,.15)}}
.t-stars{{color:#FFB800;font-size:1rem;margin-bottom:.8rem}}
.t-text{{font-size:.9rem;color:var(--text);line-height:1.75;margin-bottom:1.25rem;font-style:italic}}
.t-author{{display:flex;align-items:center;gap:.75rem}}
.t-av{{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;color:#fff;flex-shrink:0}}
.t-name{{font-weight:700;font-size:.88rem;color:var(--text)}}
.t-loc{{font-size:.72rem;color:var(--muted)}}
#about{{background:var(--bg2)}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:linear-gradient(135deg,var(--p),var(--a));border-radius:24px;height:420px;display:flex;align-items:center;justify-content:center;font-size:7rem;box-shadow:0 0 60px rgba(108,99,255,.3)}}
.ab-text .sec-badge{{display:block;text-align:left;margin-bottom:.75rem}}
.ab-text .sec-title{{text-align:left}}
.ab-mission{{font-size:1rem;color:var(--p);font-weight:600;margin-bottom:1.2rem;padding-left:1rem;border-left:2px solid var(--p);font-style:italic}}
.ab-story{{color:var(--muted);line-height:1.85;margin-bottom:1.75rem;font-size:.9rem}}
.dk-val{{display:inline-block;background:rgba(108,99,255,.12);border:1px solid rgba(108,99,255,.25);color:var(--p);border-radius:50px;padding:.35rem .9rem;font-size:.78rem;font-weight:600;margin:.25rem}}
#contact{{background:var(--bg)}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-info h3{{font-family:'Outfit',sans-serif;font-size:1.8rem;font-weight:800;letter-spacing:-.03em;margin-bottom:1.75rem;color:var(--text)}}
.ct-item{{display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.3rem}}
.ct-ico{{width:44px;height:44px;border-radius:12px;background:rgba(108,99,255,.12);display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0}}
.ct-item strong{{display:block;font-weight:700;font-size:.85rem;color:var(--text);margin-bottom:.15rem}}
.ct-item span{{font-size:.8rem;color:var(--muted)}}
.ct-social{{display:flex;gap:.6rem;margin-top:1.5rem;flex-wrap:wrap}}
.ct-soc{{background:var(--bg2);border:1px solid var(--border);color:var(--muted);padding:.45rem .9rem;border-radius:8px;font-size:.78rem;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}}
.ct-soc:hover{{border-color:var(--p);color:var(--p)}}
.ct-form{{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:2.2rem}}
.ct-form h3{{font-family:'Outfit',sans-serif;font-size:1.2rem;font-weight:700;margin-bottom:1.5rem;color:var(--text)}}
.fg{{margin-bottom:1.1rem}}
.fg label{{display:block;font-size:.78rem;font-weight:600;color:var(--muted);margin-bottom:.35rem}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.72rem .9rem;background:var(--bg3);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s;border-radius:8px}}
.fg input:focus,.fg textarea:focus{{border-color:var(--p)}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.88rem;background:var(--p);color:#fff;border:none;border-radius:50px;font-weight:700;font-size:.9rem;cursor:pointer;transition:all .2s;font-family:inherit;box-shadow:0 0 20px rgba(108,99,255,.3)}}
.btn-send:hover{{background:var(--s)}}
footer{{background:#050508;border-top:1px solid var(--border);padding:4rem 5% 2rem}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-family:'Outfit',sans-serif;font-weight:900;font-size:1.4rem;color:var(--p);letter-spacing:-.03em;margin-bottom:.5rem}}
.ft-tg{{font-size:.82rem;color:var(--muted);line-height:1.7}}
.ft-col h4{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.55rem}}
.ft-col ul li a{{font-size:.8rem;color:var(--muted);text-decoration:none;transition:color .2s}}
.ft-col ul li a:hover{{color:var(--p)}}
.ft-bot{{border-top:1px solid var(--border);padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.75rem;color:var(--muted)}}
@media(max-width:960px){{.hero{{flex-direction:column;min-height:auto;padding:4rem 5%}}.hero-right{{display:none}}.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:2.5rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:2.5rem}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-badge{{animation:fadeUp .5s ease both .05s}}.hero-title{{animation:fadeUp .5s ease both .15s}}.hero-sub{{animation:fadeUp .5s ease both .25s}}.hero-btns{{animation:fadeUp .5s ease both .35s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an}</div>
<nav>
  <a href="#home" class="nav-brand">{name}</a>
  <ul class="nav-links">
    <li><a href="#categories">Categories</a></li>
    <li><a href="#products">Products</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="nav-right">
    <button class="nav-search">🔍 Search</button>
    <button class="nav-cart" onclick="alert('Cart coming soon!')">🛒 Cart (0)</button>
  </div>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-badge">✦ {h.get('badge','Now Available')}</div>
      <h1 class="hero-title"><span class="hl">{h.get('title',name)}</span></h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-glow" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Explore Now')}</button>
        <button class="btn-ghost" onclick="document.getElementById('categories').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','Browse All')}</button>
      </div>
    </div>
    <div class="hero-right">
      {''.join(f'<div class="hero-pcard"><div class="hp-ico">{p.get("emoji","")}</div><div class="hp-name">{p.get("name","")[:20]}</div><div class="hp-price">{p.get("price","")}</div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-section"><div class="dk-feat-grid">{feats}</div></div>
<section id="categories"><div class="sec-wrap"><div class="sec-badge">Browse</div><h2 class="sec-title">Shop by Category</h2><p class="sec-sub">Explore our curated collections.</p></div><div class="cat-grid">{ch}</div></section>
<section id="products"><div class="sec-wrap"><div class="sec-badge">Featured</div><h2 class="sec-title">Top Products</h2><p class="sec-sub">Loved by thousands of customers worldwide.</p></div><div class="p-grid">{ph}</div></section>
<div class="stats-bar">{sh}</div>
<section id="testimonials"><div class="sec-wrap"><div class="sec-badge">Reviews</div><h2 class="sec-title">What They're Saying</h2><p class="sec-sub">Real experiences from real people.</p></div><div class="t-grid">{th}</div></section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">⚡</div>
    <div class="ab-text">
      <div class="sec-badge">Our Story</div><h2 class="sec-title" style="text-align:left">About {name}</h2>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div>{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-wrap"><div class="sec-badge">Contact</div><h2 class="sec-title">Get In Touch</h2><p class="sec-sub">Our team is ready to help.</p></div>
  <div class="ct-grid">
    <div class="ct-info">
      <h3>Let's Connect</h3>
      <div class="ct-item"><div class="ct-ico">📧</div><div><strong>Email</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📞</div><div><strong>Phone</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📍</div><div><strong>Address</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social"><button class="ct-soc">Instagram</button><button class="ct-soc">TikTok</button><button class="ct-soc">Twitter</button></div>
    </div>
    <div class="ct-form">
      <h3>Send a Message</h3>
      <div class="fg"><label>Name</label><input type="text" placeholder="Your name"/></div>
      <div class="fg"><label>Email</label><input type="email" placeholder="your@email.com"/></div>
      <div class="fg"><label>Message</label><textarea placeholder="How can we help?"></textarea></div>
      <button class="btn-send" onclick="alert('Message sent! We will respond within 24 hours.')">Send Message ✦</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name}</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Shop</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Help</h4><ul><li><a href="#">FAQ</a></li><li><a href="#">Shipping</a></li><li><a href="#">Returns</a></li></ul></div>
    <div class="ft-col"><h4>Legal</h4><ul><li><a href="#">Privacy</a></li><li><a href="#">Terms</a></li><li><a href="#">Cookies</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Generated by BizBuilder AI.</span></div>
</footer>
{_interactive_block(c.get("products",[]), "#6C63FF", "#FF6B9D", "#12122A", "#E8E8F5", "#2A2A45")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 5. PLAYFUL & FUN
# ══════════════════════════════════════════════════════════════════════════════

def _build_playful(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")
    cs = c.get("color_scheme", {})
    p1 = cs.get("primary", "#FF7043")
    acc = cs.get("accent", "#4CAF50")

    ph = _products_block(c.get("products", []), "pl-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), p1)
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="pl-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="pl-feat"><div class="pl-ficon">{f["icon"]}</div><strong>{f["title"]}</strong><p>{f["desc"]}</p></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900;1000&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--p:{p1};--s:#E64A19;--a:{acc};--bg:#FFF9F0;--white:#fff;--card:#FFFDF8;--border:#FFE0B2;--text:#2D1B00;--muted:#7A5C00;--r:24px}}
html{{scroll-behavior:smooth}}
body{{font-family:'Nunito',sans-serif;background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased}}
.ann{{background:linear-gradient(90deg,var(--p),#FF8A65);color:#fff;text-align:center;padding:.55rem;font-size:.85rem;font-weight:700}}
nav{{background:var(--white);border-bottom:3px solid var(--border);padding:0 5%;display:flex;align-items:center;justify-content:space-between;height:70px;position:sticky;top:0;z-index:100;border-radius:0 0 20px 20px;box-shadow:0 4px 20px rgba(255,112,67,.1)}}
.nav-brand{{font-size:1.5rem;font-weight:900;color:var(--p)}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.88rem;font-weight:700;color:var(--text);text-decoration:none;transition:color .2s}}
.nav-links a:hover{{color:var(--p)}}
.nav-right{{display:flex;gap:.75rem;align-items:center}}
.nav-search{{background:#FFF5E6;border:2px solid var(--border);padding:.45rem 1rem;font-size:.82rem;cursor:pointer;font-family:inherit;border-radius:50px;color:var(--muted)}}
.nav-cart{{background:var(--p);color:#fff;border:none;padding:.55rem 1.3rem;font-weight:800;font-size:.85rem;cursor:pointer;border-radius:50px;transition:all .2s;font-family:inherit;box-shadow:0 4px 12px rgba(255,112,67,.35)}}
.nav-cart:hover{{background:var(--s);transform:scale(1.05)}}
.hero{{background:linear-gradient(135deg,#FFF9F0 0%,#FFE0B2 50%,#FFF9F0 100%);padding:5.5rem 5%;display:flex;align-items:center;gap:4rem;min-height:88vh;position:relative;overflow:hidden}}
.hero::before{{content:'✦';position:absolute;font-size:20rem;color:rgba(255,112,67,.05);top:-4rem;right:5%;line-height:1;pointer-events:none}}
.hero-content{{flex:1;max-width:560px;position:relative;z-index:1}}
.hero-emoji{{font-size:3rem;margin-bottom:1rem;display:block}}
.hero-tag{{display:inline-block;background:var(--a);color:#fff;padding:.38rem 1rem;border-radius:50px;font-size:.8rem;font-weight:800;margin-bottom:1.25rem;box-shadow:0 4px 12px rgba(76,175,80,.3)}}
.hero-title{{font-size:clamp(2.5rem,5vw,4.5rem);font-weight:900;line-height:1.1;margin-bottom:1.25rem;color:var(--text)}}
.hero-title span{{color:var(--p)}}
.hero-sub{{font-size:1rem;color:var(--muted);margin-bottom:2.5rem;max-width:460px;line-height:1.75}}
.hero-btns{{display:flex;gap:1rem;flex-wrap:wrap}}
.btn-fun{{background:var(--p);color:#fff;padding:.9rem 2.2rem;font-weight:800;font-size:1rem;border:none;cursor:pointer;border-radius:50px;transition:all .2s;box-shadow:0 6px 20px rgba(255,112,67,.35);font-family:inherit}}
.btn-fun:hover{{background:var(--s);transform:translateY(-3px);box-shadow:0 10px 28px rgba(255,112,67,.45)}}
.btn-fun-out{{background:transparent;color:var(--p);padding:.9rem 2.2rem;font-weight:700;font-size:1rem;border:3px solid var(--p);cursor:pointer;border-radius:50px;transition:all .2s;font-family:inherit}}
.btn-fun-out:hover{{background:var(--p);color:#fff}}
.hero-right{{flex:1;display:flex;flex-wrap:wrap;gap:1rem;justify-content:center;position:relative;z-index:1}}
.hero-pcard{{background:var(--white);border:3px solid var(--border);border-radius:20px;padding:1.25rem;text-align:center;min-width:130px;transition:all .25s;box-shadow:0 4px 16px rgba(255,112,67,.08)}}
.hero-pcard:hover{{transform:translateY(-6px) rotate(-2deg);border-color:var(--p);box-shadow:0 12px 32px rgba(255,112,67,.2)}}
.hp-ico{{font-size:2.8rem;margin-bottom:.5rem}}
.hp-name{{font-size:.76rem;font-weight:700;color:var(--text);margin-bottom:.25rem}}
.hp-price{{font-size:1rem;font-weight:800;color:var(--p)}}
.feat-bar{{background:var(--white);border-top:3px solid var(--border);border-bottom:3px solid var(--border);padding:1.5rem 5%;display:flex;gap:2rem;justify-content:center;flex-wrap:wrap}}
.pl-feat{{display:flex;align-items:center;gap:.65rem;background:#FFF5E6;border-radius:50px;padding:.6rem 1.2rem;border:2px solid var(--border)}}
.pl-ficon{{font-size:1.3rem}}
.pl-feat strong{{font-size:.82rem;font-weight:800;display:block}}
.pl-feat p{{font-size:.74rem;color:var(--muted);margin:0}}
section{{padding:5rem 5%}}
.sec-emoji{{text-align:center;font-size:2.5rem;margin-bottom:.5rem}}
.sec-title{{text-align:center;font-size:clamp(2rem,4vw,3rem);font-weight:900;margin-bottom:.6rem;color:var(--text)}}
.sec-sub{{text-align:center;color:var(--muted);max-width:500px;margin:0 auto 3rem;font-size:.92rem}}
#categories{{background:var(--white)}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:1.2rem;max-width:1100px;margin:0 auto}}
.cat-item{{background:var(--cat-color,#FFF5E6);border:3px solid var(--border);border-radius:var(--r);padding:1.75rem 1rem;text-align:center;cursor:pointer;transition:all .22s;display:flex;flex-direction:column;align-items:center;gap:.5rem}}
.cat-item:hover{{border-color:var(--p);transform:translateY(-5px) rotate(1deg);box-shadow:0 10px 28px rgba(255,112,67,.15)}}
.cat-ico{{font-size:2.3rem}}
.cat-nm{{font-size:.84rem;font-weight:800;color:var(--text)}}
.cat-ct{{font-size:.74rem;color:var(--muted)}}
#products{{background:var(--bg)}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:1.5rem;max-width:1200px;margin:0 auto}}
.p-card{{background:var(--white);border:3px solid var(--border);border-radius:var(--r);overflow:hidden;position:relative;transition:all .25s;display:flex;flex-direction:column}}
.p-card:hover{{border-color:var(--p);transform:translateY(-5px);box-shadow:0 12px 36px rgba(255,112,67,.18)}}
.p-badge{{position:absolute;top:12px;left:12px;background:var(--p);color:#fff;font-size:.7rem;font-weight:800;padding:.22rem .65rem;border-radius:50px;z-index:1}}
.p-img{{height:200px;display:flex;align-items:center;justify-content:center;font-size:5rem;background:linear-gradient(135deg,#FFF5E6,#FFE0B2);border-bottom:3px solid var(--border)}}
.p-body{{padding:1.25rem;flex:1;display:flex;flex-direction:column}}
.p-name{{font-size:.95rem;font-weight:800;margin-bottom:.3rem;color:var(--text)}}
.p-desc{{font-size:.78rem;color:var(--muted);margin-bottom:.75rem;line-height:1.5;flex:1}}
.p-stars{{color:var(--p);font-size:.85rem;font-weight:700;margin-bottom:.75rem}}
.p-rev{{color:var(--muted);font-size:.75rem;font-weight:400}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-size:1.2rem;font-weight:900;color:var(--p)}}
.p-orig{{font-size:.76rem;color:#bbb;text-decoration:line-through;margin-left:.35rem}}
.pl-add{{background:var(--p);color:#fff;border:none;border-radius:50px;padding:.5rem 1.1rem;font-size:.78rem;font-weight:800;cursor:pointer;transition:all .2s;font-family:inherit}}
.pl-add:hover{{background:var(--s);transform:scale(1.06)}}
.stats-bar{{background:linear-gradient(135deg,var(--p),var(--s));padding:4rem 5%;display:flex;justify-content:center;gap:5rem;flex-wrap:wrap;border-radius:32px;margin:0 5%;}}
.stat{{text-align:center}}
.stat-n{{font-size:3.5rem;font-weight:900;color:#fff;line-height:1}}
.stat-l{{font-size:.82rem;color:rgba(255,255,255,.8);margin-top:.4rem;font-weight:700}}
#testimonials{{background:var(--white)}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1.25rem;max-width:1100px;margin:0 auto}}
.t-card{{background:var(--bg);border:3px solid var(--border);border-radius:var(--r);padding:2rem;transition:all .25s}}
.t-card:hover{{border-color:var(--p);transform:translateY(-3px);box-shadow:0 8px 24px rgba(255,112,67,.12)}}
.t-stars{{color:var(--p);font-size:1.1rem;margin-bottom:.75rem}}
.t-text{{font-size:.95rem;line-height:1.7;margin-bottom:1.25rem;font-weight:600}}
.t-author{{display:flex;align-items:center;gap:.75rem}}
.t-av{{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1rem;color:#fff;flex-shrink:0}}
.t-name{{font-weight:800;font-size:.9rem}}
.t-loc{{font-size:.74rem;color:var(--muted)}}
#about{{background:var(--bg)}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:linear-gradient(135deg,var(--p),var(--a));border-radius:40px;height:420px;display:flex;align-items:center;justify-content:center;font-size:8rem;box-shadow:0 20px 50px rgba(255,112,67,.25);transform:rotate(-2deg)}}
.ab-title{{font-size:2rem;font-weight:900;margin-bottom:1rem;color:var(--text)}}
.ab-mission{{font-size:1rem;color:var(--p);font-weight:700;margin-bottom:1.1rem;padding-left:1rem;border-left:4px solid var(--p)}}
.ab-story{{color:var(--muted);line-height:1.85;margin-bottom:1.5rem;font-size:.9rem}}
.pl-val{{display:inline-block;background:var(--p);color:#fff;padding:.38rem .9rem;border-radius:50px;font-size:.78rem;font-weight:800;margin:.25rem;box-shadow:0 3px 10px rgba(255,112,67,.25)}}
#contact{{background:var(--white)}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-title{{font-size:2rem;font-weight:900;margin-bottom:1.75rem}}
.ct-item{{display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.25rem}}
.ct-ico{{width:46px;height:46px;border-radius:16px;background:#FFF5E6;border:2px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0}}
.ct-item strong{{display:block;font-weight:800;font-size:.88rem;margin-bottom:.15rem}}
.ct-item span{{font-size:.8rem;color:var(--muted)}}
.ct-social{{display:flex;gap:.6rem;margin-top:1.5rem;flex-wrap:wrap}}
.ct-soc{{background:#FFF5E6;border:2px solid var(--border);color:var(--text);padding:.48rem 1rem;border-radius:50px;font-size:.78rem;font-weight:700;cursor:pointer;transition:all .2s;font-family:inherit}}
.ct-soc:hover{{background:var(--p);border-color:var(--p);color:#fff}}
.ct-form{{background:var(--bg);border:3px solid var(--border);border-radius:var(--r);padding:2.2rem}}
.ct-form-title{{font-size:1.3rem;font-weight:900;margin-bottom:1.5rem}}
.fg{{margin-bottom:1.1rem}}
.fg label{{display:block;font-size:.8rem;font-weight:700;margin-bottom:.38rem;color:var(--muted)}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.72rem .95rem;border:3px solid var(--border);background:var(--white);font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s;border-radius:16px;color:var(--text)}}
.fg input:focus,.fg textarea:focus{{border-color:var(--p)}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.9rem;background:var(--p);color:#fff;border:none;border-radius:50px;font-weight:800;font-size:.95rem;cursor:pointer;transition:all .2s;font-family:inherit;box-shadow:0 6px 20px rgba(255,112,67,.3)}}
.btn-send:hover{{background:var(--s)}}
footer{{background:var(--text);padding:4rem 5% 2rem;border-radius:32px 32px 0 0;margin-top:2rem}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-size:1.6rem;font-weight:900;color:var(--p);margin-bottom:.5rem}}
.ft-tg{{font-size:.8rem;color:#7A5C4A;line-height:1.7}}
.ft-col h4{{font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#7A5C4A;margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.55rem}}
.ft-col ul li a{{font-size:.82rem;color:#7A5C4A;text-decoration:none;transition:color .2s}}
.ft-col ul li a:hover{{color:var(--p)}}
.ft-bot{{border-top:1px solid rgba(255,255,255,.1);padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.76rem;color:#7A5C4A}}
@media(max-width:960px){{.hero{{flex-direction:column;min-height:auto;padding:3.5rem 5%}}.hero-right{{display:none}}.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:2.5rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:2.5rem;margin:0}}}}
@keyframes bounceIn{{from{{opacity:0;transform:scale(.8)}}to{{opacity:1;transform:scale(1)}}}}
.hero-emoji{{animation:bounceIn .5s ease both}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-tag{{animation:fadeUp .5s ease both .1s}}.hero-title{{animation:fadeUp .5s ease both .2s}}.hero-sub{{animation:fadeUp .5s ease both .3s}}.hero-btns{{animation:fadeUp .5s ease both .4s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an} 🎉</div>
<nav>
  <a href="#home" class="nav-brand">{name} ✨</a>
  <ul class="nav-links">
    <li><a href="#categories">Categories</a></li>
    <li><a href="#products">Shop 🛍️</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="nav-right">
    <button class="nav-search">🔍 Search</button>
    <button class="nav-cart" onclick="alert('Cart coming soon! 🛒')">🛒 Cart (0)</button>
  </div>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-content">
      <span class="hero-emoji">🎉</span>
      <div class="hero-tag">{h.get('badge','New & Exciting!')}</div>
      <h1 class="hero-title"><span>{h.get('title',name)}</span></h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-fun" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Shop Now 🛍️')}</button>
        <button class="btn-fun-out" onclick="document.getElementById('categories').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','Explore All')}</button>
      </div>
    </div>
    <div class="hero-right">
      {''.join(f'<div class="hero-pcard"><div class="hp-ico">{p.get("emoji","")}</div><div class="hp-name">{p.get("name","")[:20]}</div><div class="hp-price">{p.get("price","")}</div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-bar">{feats}</div>
<section id="categories"><div class="sec-emoji">🗂️</div><h2 class="sec-title">Shop by Category</h2><p class="sec-sub">Find your favorites easily!</p><div class="cat-grid">{ch}</div></section>
<section id="products"><div class="sec-emoji">🌟</div><h2 class="sec-title">Featured Products</h2><p class="sec-sub">Our most loved items, picked just for you!</p><div class="p-grid">{ph}</div></section>
<div style="padding:3rem 5%"><div class="stats-bar">{sh}</div></div>
<section id="testimonials"><div class="sec-emoji">💬</div><h2 class="sec-title">Happy Customers</h2><p class="sec-sub">Don't just take our word for it!</p><div class="t-grid">{th}</div></section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">😊</div>
    <div>
      <div class="sec-emoji" style="text-align:left">🌈</div>
      <div class="ab-title">About {name}</div>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div>{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-emoji">👋</div><h2 class="sec-title">Say Hello!</h2><p class="sec-sub">We'd love to hear from you!</p>
  <div class="ct-grid">
    <div>
      <div class="ct-title">Let's Chat! 💬</div>
      <div class="ct-item"><div class="ct-ico">📧</div><div><strong>Email Us</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📞</div><div><strong>Call Us</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📍</div><div><strong>Find Us</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social"><button class="ct-soc">Instagram</button><button class="ct-soc">🎵 TikTok</button><button class="ct-soc">Twitter</button></div>
    </div>
    <div class="ct-form">
      <div class="ct-form-title">Drop us a message! 💌</div>
      <div class="fg"><label>Your Name</label><input type="text" placeholder="What's your name?"/></div>
      <div class="fg"><label>Email</label><input type="email" placeholder="your@email.com"/></div>
      <div class="fg"><label>Message</label><textarea placeholder="Tell us what's on your mind! 😊"></textarea></div>
      <button class="btn-send" onclick="alert('Yay! Message sent! 🎉 We will get back to you soon!')">Send it! 🚀</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name} ✨</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Shop</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Help</h4><ul><li><a href="#">FAQ</a></li><li><a href="#">Shipping</a></li><li><a href="#">Returns</a></li></ul></div>
    <div class="ft-col"><h4>Us</h4><ul><li><a href="#about">About</a></li><li><a href="#contact">Contact</a></li><li><a href="#">Privacy</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Made with ❤️ by BizBuilder AI.</span></div>
</footer>
{_interactive_block(c.get("products",[]), p1, acc, "#FFFFFF", "#2D1B00", "#FFE0B2")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# 6. CORPORATE & PROFESSIONAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_corporate(name, c, is_ecom):
    h = c.get("hero", {})
    ab = c.get("about", {})
    ct = c.get("contact", {})
    tg = c.get("tagline", "")
    an = c.get("announcement_bar", "")
    cs = c.get("color_scheme", {})
    p1 = cs.get("primary", "#1A3A6B")
    p2 = cs.get("secondary", "#0D2044")
    acc = cs.get("accent", "#2563EB")

    ph = _products_block(c.get("products", []), "cp-add")
    ch = _cats_block(c.get("categories", []))
    th = _testis_block(c.get("testimonials", []), p1)
    sh = _stats_block(c.get("stats", []))
    vals = "".join(f'<span class="cp-val">{v}</span>' for v in ab.get("values", []))
    fcat = _footer_cats(c.get("categories", []))
    feats = "".join(f'<div class="cp-feat"><div class="cp-ficon">{f["icon"]}</div><h4>{f["title"]}</h4><p>{f["desc"]}</p></div>' for f in c.get("features", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--p:{p1};--s:{p2};--a:{acc};--bg:#F4F6FA;--white:#fff;--border:#DDE3EE;--text:#1A2B4A;--muted:#5A6A85;--r:8px}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);line-height:1.65;-webkit-font-smoothing:antialiased}}
.ann{{background:var(--s);color:#fff;text-align:center;padding:.5rem;font-size:.8rem;font-weight:500;letter-spacing:.03em}}
.topbar{{background:var(--p);color:rgba(255,255,255,.7);padding:.4rem 6%;display:flex;justify-content:space-between;align-items:center;font-size:.75rem}}
.topbar a{{color:rgba(255,255,255,.7);text-decoration:none;transition:color .2s}}
.topbar a:hover{{color:#fff}}
nav{{background:var(--white);border-bottom:2px solid var(--border);padding:0 6%;display:flex;align-items:center;justify-content:space-between;height:72px;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(26,58,107,.08)}}
.nav-brand{{font-size:1.3rem;font-weight:800;color:var(--p);letter-spacing:-.02em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.85rem;font-weight:500;color:var(--text);text-decoration:none;transition:color .2s}}
.nav-links a:hover{{color:var(--p)}}
.nav-right{{display:flex;gap:.75rem;align-items:center}}
.nav-search{{background:var(--bg);border:1px solid var(--border);padding:.45rem 1rem;font-size:.82rem;cursor:pointer;font-family:inherit;border-radius:var(--r);color:var(--muted)}}
.nav-cart{{background:var(--p);color:#fff;border:none;padding:.5rem 1.3rem;font-weight:600;font-size:.82rem;cursor:pointer;transition:all .2s;font-family:inherit;border-radius:var(--r)}}
.nav-cart:hover{{background:var(--s)}}
.hero{{background:linear-gradient(160deg,var(--p) 0%,var(--s) 100%);padding:6rem 6%;display:flex;align-items:center;gap:5rem;min-height:88vh;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;width:500px;height:500px;border:1px solid rgba(255,255,255,.08);border-radius:50%;right:-100px;top:-100px}}
.hero::after{{content:'';position:absolute;width:300px;height:300px;border:1px solid rgba(255,255,255,.06);border-radius:50%;left:-50px;bottom:-50px}}
.hero-content{{flex:1;max-width:560px;position:relative;z-index:1}}
.hero-trust{{display:inline-flex;align-items:center;gap:.5rem;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.9);padding:.35rem 1rem;border-radius:var(--r);font-size:.75rem;font-weight:500;margin-bottom:1.5rem;letter-spacing:.03em}}
.hero-title{{font-size:clamp(2.2rem,4.5vw,3.8rem);font-weight:800;line-height:1.1;letter-spacing:-.03em;margin-bottom:1.25rem;color:#fff}}
.hero-sub{{font-size:.95rem;color:rgba(255,255,255,.75);margin-bottom:2.5rem;max-width:460px;line-height:1.75}}
.hero-btns{{display:flex;gap:1rem;flex-wrap:wrap}}
.btn-white{{background:#fff;color:var(--p);padding:.85rem 2.2rem;font-weight:700;font-size:.9rem;border:none;cursor:pointer;border-radius:var(--r);transition:all .2s;font-family:inherit}}
.btn-white:hover{{background:var(--bg);transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.15)}}
.btn-outline-white{{background:transparent;color:#fff;padding:.85rem 2.2rem;font-weight:600;font-size:.9rem;border:2px solid rgba(255,255,255,.4);cursor:pointer;border-radius:var(--r);transition:all .2s;font-family:inherit}}
.btn-outline-white:hover{{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.7)}}
.hero-right{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:1rem;position:relative;z-index:1}}
.hero-pcard{{background:rgba(255,255,255,.1);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.2);border-radius:var(--r);padding:1.5rem;text-align:center;transition:all .25s}}
.hero-pcard:hover{{background:rgba(255,255,255,.18);transform:translateY(-3px)}}
.hp-ico{{font-size:2.5rem;margin-bottom:.5rem}}
.hp-name{{font-size:.75rem;font-weight:600;color:rgba(255,255,255,.85);margin-bottom:.3rem}}
.hp-price{{font-size:1rem;font-weight:700;color:#fff}}
.feat-section{{background:var(--white);border-bottom:2px solid var(--border);padding:3rem 6%}}
.cp-feat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}}
.cp-feat{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:1.75rem;transition:all .22s;border-left:3px solid var(--p)}}
.cp-feat:hover{{box-shadow:0 4px 20px rgba(26,58,107,.1);transform:translateY(-2px)}}
.cp-ficon{{font-size:1.8rem;margin-bottom:.65rem}}
.cp-feat h4{{font-weight:700;margin-bottom:.3rem;font-size:.9rem;color:var(--text)}}
.cp-feat p{{font-size:.8rem;color:var(--muted)}}
section{{padding:5rem 6%}}
.sec-kicker{{text-align:center;color:var(--a);font-weight:700;font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;margin-bottom:.6rem}}
.sec-title{{text-align:center;font-size:clamp(1.8rem,3vw,2.5rem);font-weight:800;letter-spacing:-.025em;margin-bottom:.7rem;color:var(--text)}}
.sec-sub{{text-align:center;color:var(--muted);max-width:520px;margin:0 auto 3rem;font-size:.9rem}}
#categories{{background:var(--white)}}
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:1rem;max-width:1100px;margin:0 auto}}
.cat-item{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:1.6rem 1rem;text-align:center;cursor:pointer;transition:all .22s;display:flex;flex-direction:column;align-items:center;gap:.5rem}}
.cat-item:hover{{border-color:var(--p);box-shadow:0 4px 16px rgba(26,58,107,.1);transform:translateY(-3px)}}
.cat-ico{{font-size:2rem}}
.cat-nm{{font-size:.82rem;font-weight:600;color:var(--text);letter-spacing:.02em}}
.cat-ct{{font-size:.72rem;color:var(--muted)}}
#products{{background:var(--bg)}}
.p-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:1.5rem;max-width:1200px;margin:0 auto}}
.p-card{{background:var(--white);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;position:relative;transition:all .22s;display:flex;flex-direction:column;border-left:3px solid var(--p)}}
.p-card:hover{{box-shadow:0 8px 28px rgba(26,58,107,.12);transform:translateY(-3px)}}
.p-badge{{position:absolute;top:12px;left:12px;background:var(--p);color:#fff;font-size:.68rem;font-weight:700;padding:.22rem .6rem;border-radius:4px;z-index:1}}
.p-img{{height:185px;display:flex;align-items:center;justify-content:center;font-size:4rem;background:linear-gradient(135deg,rgba(26,58,107,.08),rgba(37,99,235,.06));border-bottom:1px solid var(--border)}}
.p-body{{padding:1.25rem;flex:1;display:flex;flex-direction:column}}
.p-name{{font-weight:700;font-size:.92rem;margin-bottom:.3rem;color:var(--text)}}
.p-desc{{font-size:.78rem;color:var(--muted);margin-bottom:.75rem;line-height:1.5;flex:1}}
.p-stars{{color:#F59E0B;font-size:.82rem;margin-bottom:.75rem}}
.p-rev{{color:var(--muted);font-size:.72rem}}
.p-foot{{display:flex;align-items:center;justify-content:space-between}}
.p-price{{font-weight:800;font-size:1.1rem;color:var(--p)}}
.p-orig{{font-size:.75rem;color:#bbb;text-decoration:line-through;margin-left:.35rem}}
.cp-add{{background:var(--p);color:#fff;border:none;border-radius:var(--r);padding:.5rem 1.05rem;font-size:.78rem;font-weight:700;cursor:pointer;transition:all .2s;font-family:inherit}}
.cp-add:hover{{background:var(--s)}}
.stats-bar{{background:linear-gradient(135deg,var(--p),var(--s));padding:4rem 6%;display:flex;justify-content:center;gap:6rem;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-n{{font-size:3rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-.03em}}
.stat-l{{font-size:.78rem;color:rgba(255,255,255,.7);margin-top:.4rem;letter-spacing:.04em;text-transform:uppercase}}
#testimonials{{background:var(--white)}}
.t-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}}
.t-card{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:2rem;transition:all .22s;border-top:3px solid var(--p)}}
.t-card:hover{{box-shadow:0 4px 20px rgba(26,58,107,.1)}}
.t-stars{{color:#F59E0B;font-size:1rem;margin-bottom:.75rem}}
.t-text{{font-size:.9rem;line-height:1.7;margin-bottom:1.25rem;color:var(--text);font-style:italic}}
.t-author{{display:flex;align-items:center;gap:.75rem}}
.t-av{{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;color:#fff;flex-shrink:0}}
.t-name{{font-weight:700;font-size:.88rem;color:var(--text)}}
.t-loc{{font-size:.72rem;color:var(--muted)}}
#about{{background:var(--bg)}}
.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5rem;align-items:center;max-width:1100px;margin:0 auto}}
.ab-img{{background:linear-gradient(135deg,var(--p),var(--s));border-radius:var(--r);height:420px;display:flex;align-items:center;justify-content:center;font-size:7rem;box-shadow:0 20px 48px rgba(26,58,107,.2)}}
.ab-text .sec-kicker{{text-align:left}}
.ab-text .sec-title{{text-align:left}}
.ab-mission{{font-size:.95rem;color:var(--p);font-weight:600;margin-bottom:1.1rem;padding-left:1rem;border-left:3px solid var(--p)}}
.ab-story{{color:var(--muted);line-height:1.85;margin-bottom:1.5rem;font-size:.88rem}}
.cp-val{{display:inline-block;background:rgba(26,58,107,.08);border:1px solid rgba(26,58,107,.15);color:var(--p);border-radius:var(--r);padding:.32rem .85rem;font-size:.78rem;font-weight:600;margin:.25rem}}
#contact{{background:var(--white)}}
.ct-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;max-width:1100px;margin:0 auto;align-items:start}}
.ct-info h3{{font-size:1.6rem;font-weight:800;letter-spacing:-.02em;margin-bottom:1.6rem;color:var(--text)}}
.ct-item{{display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.25rem}}
.ct-ico{{width:46px;height:46px;border-radius:var(--r);background:rgba(26,58,107,.08);display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0}}
.ct-item strong{{display:block;font-weight:700;font-size:.85rem;color:var(--text);margin-bottom:.15rem}}
.ct-item span{{font-size:.8rem;color:var(--muted)}}
.ct-social{{display:flex;gap:.6rem;margin-top:1.5rem;flex-wrap:wrap}}
.ct-soc{{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:.45rem .95rem;border-radius:var(--r);font-size:.78rem;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}}
.ct-soc:hover{{background:var(--p);border-color:var(--p);color:#fff}}
.ct-form{{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:2.2rem}}
.ct-form h3{{font-size:1.15rem;font-weight:700;margin-bottom:1.5rem;color:var(--text)}}
.fg{{margin-bottom:1.1rem}}
.fg label{{display:block;font-size:.78rem;font-weight:600;color:var(--muted);margin-bottom:.35rem}}
.fg input,.fg textarea,.fg select{{width:100%;padding:.72rem .9rem;border:1px solid var(--border);background:var(--white);font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s;border-radius:var(--r);color:var(--text)}}
.fg input:focus,.fg textarea:focus{{border-color:var(--p)}}
.fg textarea{{resize:vertical;min-height:110px}}
.btn-send{{width:100%;padding:.88rem;background:var(--p);color:#fff;border:none;border-radius:var(--r);font-weight:700;font-size:.9rem;cursor:pointer;transition:all .2s;font-family:inherit}}
.btn-send:hover{{background:var(--s)}}
footer{{background:var(--s);padding:4rem 6% 2rem}}
.ft-top{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:3rem}}
.ft-brand{{font-size:1.35rem;font-weight:800;color:#fff;letter-spacing:-.02em;margin-bottom:.5rem}}
.ft-tg{{font-size:.8rem;color:rgba(255,255,255,.5);line-height:1.7}}
.ft-col h4{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:rgba(255,255,255,.5);margin-bottom:1rem}}
.ft-col ul{{list-style:none}}
.ft-col ul li{{margin-bottom:.55rem}}
.ft-col ul li a{{font-size:.8rem;color:rgba(255,255,255,.5);text-decoration:none;transition:color .2s}}
.ft-col ul li a:hover{{color:#fff}}
.ft-bot{{border-top:1px solid rgba(255,255,255,.1);padding-top:1.5rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:1rem}}
.ft-copy{{font-size:.75rem;color:rgba(255,255,255,.35)}}
@media(max-width:960px){{.hero{{flex-direction:column;min-height:auto;padding:4rem 6%}}.hero-right{{display:none}}.ab-grid,.ct-grid{{grid-template-columns:1fr;gap:2.5rem}}.ft-top{{grid-template-columns:1fr 1fr}}.nav-links{{display:none}}}}
@media(max-width:600px){{.ft-top{{grid-template-columns:1fr}}.stats-bar{{gap:3rem}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(18px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero-trust{{animation:fadeUp .5s ease both .05s}}.hero-title{{animation:fadeUp .5s ease both .15s}}.hero-sub{{animation:fadeUp .5s ease both .25s}}.hero-btns{{animation:fadeUp .5s ease both .35s}}
    .cat-svg-wrap{{width:44px;height:44px;margin:0 auto .6rem;display:flex;align-items:center;justify-content:center}}
    .cat-item:hover .cat-svg-wrap{{transform:scale(1.1);transition:transform .2s}}
    .cat-item{{cursor:pointer}}
</style>
</head>
<body>
<div class="ann">{an}</div>
<div class="topbar">
  <div>📧 {ct.get('email','')} &nbsp;|&nbsp; 📞 {ct.get('phone','')}</div>
  <div><a href="#">Investor Relations</a> &nbsp;|&nbsp; <a href="#">Careers</a> &nbsp;|&nbsp; <a href="#">News</a></div>
</div>
<nav>
  <a href="#home" class="nav-brand">{name}</a>
  <ul class="nav-links">
    <li><a href="#categories">Products</a></li>
    <li><a href="#products">Solutions</a></li>
    <li><a href="#about">Company</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
  <div class="nav-right">
    <button class="nav-search">🔍 Search</button>
    <button class="nav-cart" onclick="alert('Request a demo coming soon!')">Request Demo</button>
  </div>
</nav>
<section id="home">
  <div class="hero">
    <div class="hero-content">
      <div class="hero-trust">✓ {h.get('badge','ISO 27001 Certified')}</div>
      <h1 class="hero-title">{h.get('title',name)}</h1>
      <p class="hero-sub">{h.get('subtitle',tg)}</p>
      <div class="hero-btns">
        <button class="btn-white" onclick="document.getElementById('products').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_primary','Get Started')}</button>
        <button class="btn-outline-white" onclick="document.getElementById('about').scrollIntoView({{behavior:'smooth'}})">{h.get('cta_secondary','Learn More')}</button>
      </div>
    </div>
    <div class="hero-right">
      {''.join(f'<div class="hero-pcard"><div class="hp-ico">{p.get("emoji","")}</div><div class="hp-name">{p.get("name","")[:20]}</div><div class="hp-price">{p.get("price","")}</div></div>' for p in c.get('products',[])[:4])}
    </div>
  </div>
</section>
<div class="feat-section"><div class="cp-feat-grid">{feats}</div></div>
<section id="categories"><div class="sec-kicker">Browse</div><h2 class="sec-title">Product Categories</h2><p class="sec-sub">Explore our comprehensive range of solutions.</p><div class="cat-grid">{ch}</div></section>
<section id="products"><div class="sec-kicker">Portfolio</div><h2 class="sec-title">Our Products & Solutions</h2><p class="sec-sub">Trusted by enterprises worldwide to drive results.</p><div class="p-grid">{ph}</div></section>
<div class="stats-bar">{sh}</div>
<section id="testimonials"><div class="sec-kicker">Testimonials</div><h2 class="sec-title">Trusted by Industry Leaders</h2><p class="sec-sub">Real results from real organizations.</p><div class="t-grid">{th}</div></section>
<section id="about">
  <div class="ab-grid">
    <div class="ab-img">🏢</div>
    <div class="ab-text">
      <div class="sec-kicker">About Us</div>
      <h2 class="sec-title" style="text-align:left">About {name}</h2>
      <p class="ab-mission">{ab.get('mission','')}</p>
      <p class="ab-story">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div style="margin-top:1.25rem">{vals}</div>
    </div>
  </div>
</section>
<section id="contact">
  <div class="sec-kicker">Contact</div><h2 class="sec-title">Get In Touch</h2><p class="sec-sub">Our team of experts is ready to help.</p>
  <div class="ct-grid">
    <div class="ct-info">
      <h3>Contact Our Team</h3>
      <div class="ct-item"><div class="ct-ico">📧</div><div><strong>Email</strong><span>{ct.get('email','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📞</div><div><strong>Phone</strong><span>{ct.get('phone','')}</span></div></div>
      <div class="ct-item"><div class="ct-ico">📍</div><div><strong>Address</strong><span>{ct.get('address','')}</span></div></div>
      <div class="ct-social"><button class="ct-soc">LinkedIn</button><button class="ct-soc">Twitter</button><button class="ct-soc">YouTube</button></div>
    </div>
    <div class="ct-form">
      <h3>Send a Message</h3>
      <div class="fg"><label>Full Name</label><input type="text" placeholder="John Smith"/></div>
      <div class="fg"><label>Business Email</label><input type="email" placeholder="john@company.com"/></div>
      <div class="fg"><label>Company</label><input type="text" placeholder="Your company name"/></div>
      <div class="fg"><label>Message</label><textarea placeholder="How can we help your organization?"></textarea></div>
      <button class="btn-send" onclick="alert('Thank you for your inquiry. Our team will respond within 1 business day.')">Submit Inquiry</button>
    </div>
  </div>
</section>
<footer>
  <div class="ft-top">
    <div><div class="ft-brand">{name}</div><p class="ft-tg">{tg}</p></div>
    <div class="ft-col"><h4>Products</h4><ul>{fcat}</ul></div>
    <div class="ft-col"><h4>Company</h4><ul><li><a href="#about">About</a></li><li><a href="#">Careers</a></li><li><a href="#">Press</a></li><li><a href="#">Investors</a></li></ul></div>
    <div class="ft-col"><h4>Legal</h4><ul><li><a href="#">Privacy</a></li><li><a href="#">Terms</a></li><li><a href="#">Security</a></li><li><a href="#">Compliance</a></li></ul></div>
  </div>
  <div class="ft-bot"><span class="ft-copy">© 2025 {name}. Generated by BizBuilder AI. All rights reserved.</span></div>
</footer>
{_interactive_block(c.get("products",[]), p1, acc, "#FFFFFF", "#1A2B4A", "#DDE3EE")}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# SHARED INTERACTIVE JS + CSS BLOCK
# Injected into every template's <head> or just before </body>
# Provides: search bar, category filtering, product modal, cart
# ══════════════════════════════════════════════════════════════════════════════

def _interactive_block(products, primary_color="#6C63FF", accent_color="#FF6B9D", surface_color="#fff", text_color="#111", border_color="#eee", btn_class="btn-add"):
    """Return the full <style> + <HTML> + <script> interactive block."""
    import json as _json

    # Embed all product data as JSON for the modal
    product_data = _json.dumps([{
        "id": i,
        "name": p.get("name",""),
        "price": p.get("price",""),
        "original_price": p.get("original_price",""),
        "description": p.get("description",""),
        "emoji": p.get("emoji","🛍️"),
        "rating": p.get("rating",5),
        "reviews": p.get("reviews",0),
        "badge": p.get("badge",""),
        "category": p.get("category","General"),
    } for i, p in enumerate(products)])

    return f"""
<!-- ═══ INTERACTIVE TOOLBAR ═══ -->
<div id="shop-toolbar" style="
  max-width:1200px;margin:0 auto 2rem;padding:0 5%;
  display:flex;gap:1rem;align-items:center;flex-wrap:wrap;
">
  <div style="flex:1;min-width:220px;position:relative;">
    <svg style="position:absolute;left:14px;top:50%;transform:translateY(-50%);opacity:.5" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 256 256">
      <path d="M229.66,218.34l-50.07-50.07a88,88,0,1,0-11.31,11.31l50.06,50.07a8,8,0,0,0,11.32-11.31ZM40,112a72,72,0,1,1,72,72A72.08,72.08,0,0,1,40,112Z" fill="currentColor"/>
    </svg>
    <input id="search-input" type="text" placeholder="Search products..."
      oninput="handleSearch(this.value)"
      style="
        width:100%;padding:.75rem 1rem .75rem 2.8rem;
        border:1.5px solid {border_color};border-radius:50px;
        font-size:.9rem;outline:none;font-family:inherit;
        background:{surface_color};color:{text_color};
        transition:border-color .2s;
      "
      onfocus="this.style.borderColor='{primary_color}'"
      onblur="this.style.borderColor='{border_color}'"
    />
  </div>
  <div id="active-filter" style="
    display:none;align-items:center;gap:.5rem;
    background:{primary_color}18;border:1px solid {primary_color}44;
    border-radius:50px;padding:.45rem 1rem;font-size:.82rem;
    color:{primary_color};font-weight:600;
  ">
    <span id="filter-label">All</span>
    <button onclick="clearFilter()" style="
      background:none;border:none;cursor:pointer;
      color:{primary_color};font-size:1rem;line-height:1;padding:0;
    ">✕</button>
  </div>
  <div id="results-count" style="font-size:.82rem;color:#888;white-space:nowrap;"></div>
</div>

<!-- ═══ PRODUCT MODAL ═══ -->
<div id="prod-modal" onclick="if(event.target===this)closeModal()" style="
  display:none;position:fixed;inset:0;z-index:9999;
  background:rgba(0,0,0,.7);backdrop-filter:blur(6px);
  align-items:center;justify-content:center;padding:1rem;
">
  <div style="
    background:{surface_color};border-radius:20px;
    max-width:600px;width:100%;max-height:90vh;overflow-y:auto;
    position:relative;box-shadow:0 24px 80px rgba(0,0,0,.4);
  ">
    <!-- Close btn -->
    <button onclick="closeModal()" style="
      position:absolute;top:1rem;right:1rem;
      background:{border_color};border:none;
      width:36px;height:36px;border-radius:50%;
      cursor:pointer;font-size:1.1rem;z-index:1;
      display:flex;align-items:center;justify-content:center;
    ">✕</button>
    <!-- Image area -->
    <div id="modal-img" style="
      height:260px;display:flex;align-items:center;
      justify-content:center;font-size:7rem;
      background:linear-gradient(135deg,{primary_color}12,{accent_color}08);
      border-radius:20px 20px 0 0;
    "></div>
    <!-- Body -->
    <div style="padding:1.75rem">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
        <div>
          <div id="modal-badge" style="
            display:none;background:{accent_color};color:#fff;
            font-size:.7rem;font-weight:700;padding:.2rem .65rem;
            border-radius:50px;margin-bottom:.5rem;letter-spacing:.04em;
            text-transform:uppercase;
          "></div>
          <h2 id="modal-name" style="font-size:1.35rem;font-weight:800;color:{text_color};margin-bottom:.25rem;"></h2>
          <div id="modal-stars" style="color:#F59E0B;font-size:.95rem;margin-bottom:.25rem;"></div>
          <div id="modal-rev" style="font-size:.8rem;color:#999;"></div>
        </div>
        <div style="text-align:right;flex-shrink:0;">
          <div id="modal-price" style="font-size:1.8rem;font-weight:900;color:{primary_color};"></div>
          <div id="modal-orig" style="font-size:.85rem;color:#bbb;text-decoration:line-through;"></div>
        </div>
      </div>
      <p id="modal-desc" style="font-size:.92rem;color:#666;line-height:1.7;margin-bottom:1.5rem;"></p>
      <!-- Qty selector -->
      <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.25rem;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:.5rem;border:1.5px solid {border_color};border-radius:50px;padding:.3rem .75rem;">
          <button onclick="changeQty(-1)" style="background:none;border:none;cursor:pointer;font-size:1.1rem;color:{text_color};padding:0 .3rem;">−</button>
          <span id="qty-val" style="font-weight:700;min-width:24px;text-align:center;color:{text_color};">1</span>
          <button onclick="changeQty(1)" style="background:none;border:none;cursor:pointer;font-size:1.1rem;color:{text_color};padding:0 .3rem;">+</button>
        </div>
        <span style="font-size:.78rem;color:#888;">In stock</span>
      </div>
      <button id="modal-add-btn" onclick="addToCartFromModal()" style="
        width:100%;padding:1rem;
        background:{primary_color};color:#fff;
        border:none;border-radius:50px;
        font-weight:700;font-size:1rem;cursor:pointer;
        transition:all .2s;font-family:inherit;
        box-shadow:0 6px 20px {primary_color}40;
      " onmouseover="this.style.opacity='.88'" onmouseout="this.style.opacity='1'">
        Add to Cart 🛒
      </button>
      <div style="display:flex;gap:.75rem;margin-top:1rem;">
        <button onclick="toggleWishlist()" id="wish-btn" style="
          flex:1;padding:.75rem;background:transparent;
          border:1.5px solid {border_color};border-radius:50px;
          font-weight:600;font-size:.88rem;cursor:pointer;
          font-family:inherit;color:{text_color};transition:all .2s;
        ">♡ Wishlist</button>
        <button onclick="shareProduct()" style="
          flex:1;padding:.75rem;background:transparent;
          border:1.5px solid {border_color};border-radius:50px;
          font-weight:600;font-size:.88rem;cursor:pointer;
          font-family:inherit;color:{text_color};transition:all .2s;
        ">↗ Share</button>
      </div>
    </div>
  </div>
</div>

<!-- ═══ FLOATING CART ═══ -->
<div id="cart-float" onclick="showCart()" style="
  position:fixed;bottom:2rem;right:2rem;z-index:999;
  background:{primary_color};color:#fff;
  width:56px;height:56px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;box-shadow:0 8px 24px {primary_color}50;
  transition:transform .2s;font-size:1.4rem;
" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
  🛒
  <span id="cart-count" style="
    position:absolute;top:-4px;right:-4px;
    background:{accent_color};color:#fff;
    min-width:20px;height:20px;border-radius:50%;
    font-size:.68rem;font-weight:800;
    display:none;align-items:center;justify-content:center;
  ">0</span>
</div>

<!-- ═══ CART DRAWER ═══ -->
<div id="cart-drawer" style="
  display:none;position:fixed;top:0;right:0;bottom:0;
  width:min(380px,100vw);background:{surface_color};
  z-index:10000;box-shadow:-8px 0 40px rgba(0,0,0,.2);
  flex-direction:column;
">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:1.25rem 1.5rem;border-bottom:1px solid {border_color};">
    <h3 style="font-size:1.1rem;font-weight:700;color:{text_color};">🛒 Your Cart</h3>
    <button onclick="closeCart()" style="background:none;border:none;cursor:pointer;font-size:1.2rem;color:{text_color};">✕</button>
  </div>
  <div id="cart-items" style="flex:1;overflow-y:auto;padding:1rem 1.5rem;"></div>
  <div style="padding:1.25rem 1.5rem;border-top:1px solid {border_color};">
    <div style="display:flex;justify-content:space-between;margin-bottom:1rem;">
      <span style="font-weight:600;color:{text_color};">Total</span>
      <span id="cart-total" style="font-weight:800;font-size:1.2rem;color:{primary_color};">$0.00</span>
    </div>
    <button onclick="checkout()" style="
      width:100%;padding:.9rem;background:{primary_color};color:#fff;
      border:none;border-radius:50px;font-weight:700;font-size:.95rem;
      cursor:pointer;font-family:inherit;
    ">Proceed to Checkout</button>
  </div>
</div>
<div id="cart-overlay" onclick="closeCart()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;"></div>

<!-- ═══ TOAST ═══ -->
<div id="toast" style="
  position:fixed;bottom:6rem;right:2rem;z-index:99999;
  background:#1a1a2e;color:#fff;padding:.75rem 1.25rem;
  border-radius:50px;font-size:.85rem;font-weight:600;
  transform:translateY(20px);opacity:0;transition:all .3s;
  pointer-events:none;max-width:280px;
"></div>

<script>
// ─── Product Data ─────────────────────────────────────────────────────────
const PRODUCTS = {product_data};
let cart = [];
let modalQty = 1;
let currentModalId = null;
let wishlist = new Set();
let activeCategory = "all";

// ─── Search ───────────────────────────────────────────────────────────────
function handleSearch(q) {{
  const cards = document.querySelectorAll('.p-card');
  const term = q.toLowerCase().trim();
  let visible = 0;
  cards.forEach(card => {{
    const name = card.dataset.name || '';
    const cat = card.dataset.cat || '';
    const matchSearch = !term || name.includes(term);
    const matchCat = activeCategory === 'all' || cat === activeCategory;
    if (matchSearch && matchCat) {{
      card.style.display = '';
      visible++;
    }} else {{
      card.style.display = 'none';
    }}
  }});
  updateResultsCount(visible, cards.length);
}}

// ─── Category Filtering ───────────────────────────────────────────────────
function filterByCategory(slug) {{
  // Scroll to products
  const sec = document.getElementById('products');
  if (sec) sec.scrollIntoView({{behavior:'smooth', block:'start'}});
  setTimeout(() => {{
    activeCategory = slug;
    const label = slug.replace(/-/g,' ').replace(/(^|-)([a-z])/g,(_,s,c)=>s+c.toUpperCase());
    // Highlight active cat
    document.querySelectorAll('.cat-item').forEach(el => {{
      el.style.outline = el.dataset.cat === slug ? '2px solid {primary_color}' : 'none';
      el.style.transform = el.dataset.cat === slug ? 'translateY(-4px) scale(1.03)' : '';
    }});
    // Show active filter pill
    const pill = document.getElementById('active-filter');
    if (pill) {{ pill.style.display = 'flex'; document.getElementById('filter-label').textContent = label; }}
    // Filter cards
    const searchTerm = (document.getElementById('search-input')||{{}}).value?.toLowerCase()||'';
    const cards = document.querySelectorAll('.p-card');
    let visible = 0;
    cards.forEach(card => {{
      const matchCat = card.dataset.cat === slug;
      const matchSearch = !searchTerm || (card.dataset.name||'').includes(searchTerm);
      if (matchCat && matchSearch) {{ card.style.display=''; visible++; }} else {{ card.style.display='none'; }}
    }});
    updateResultsCount(visible, cards.length);
  }}, 400);
}}

function clearFilter() {{
  activeCategory = 'all';
  document.querySelectorAll('.cat-item').forEach(el=>{{el.style.outline='';el.style.transform='';}});
  const pill = document.getElementById('active-filter');
  if (pill) pill.style.display = 'none';
  document.querySelectorAll('.p-card').forEach(c=>c.style.display='');
  updateResultsCount(document.querySelectorAll('.p-card').length, document.querySelectorAll('.p-card').length);
}}

function updateResultsCount(visible, total) {{
  const el = document.getElementById('results-count');
  if (el) el.textContent = visible < total ? `${{visible}} of ${{total}} products` : '';
}}

// ─── Product Modal ────────────────────────────────────────────────────────
function openModal(id) {{
  const p = PRODUCTS[id];
  if (!p) return;
  currentModalId = id;
  modalQty = 1;
  document.getElementById('qty-val').textContent = 1;
  document.getElementById('modal-img').textContent = p.emoji;
  document.getElementById('modal-name').textContent = p.name;
  const stars = '★'.repeat(Math.floor(p.rating)) + '☆'.repeat(5-Math.floor(p.rating));
  document.getElementById('modal-stars').textContent = stars + ' ' + p.rating;
  document.getElementById('modal-rev').textContent = p.reviews + ' verified reviews';
  document.getElementById('modal-price').textContent = p.price;
  document.getElementById('modal-orig').textContent = p.original_price || '';
  document.getElementById('modal-desc').textContent = p.description;
  const badgeEl = document.getElementById('modal-badge');
  if (p.badge) {{ badgeEl.style.display='block'; badgeEl.textContent=p.badge; }} else {{ badgeEl.style.display='none'; }}
  // Wishlist state
  document.getElementById('wish-btn').textContent = wishlist.has(id) ? '♥ Wishlisted' : '♡ Wishlist';
  const modal = document.getElementById('prod-modal');
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}}

function closeModal() {{
  document.getElementById('prod-modal').style.display = 'none';
  document.body.style.overflow = '';
  currentModalId = null;
}}

function changeQty(delta) {{
  modalQty = Math.max(1, modalQty + delta);
  document.getElementById('qty-val').textContent = modalQty;
}}

// ─── Cart ─────────────────────────────────────────────────────────────────
function addToCart(name) {{
  const p = PRODUCTS.find(x => x.name === name);
  if (!p) {{ showToast('Added to cart! 🛒'); updateCartUI(); return; }}
  const existing = cart.find(c => c.id === p.id);
  if (existing) {{ existing.qty++; }} else {{ cart.push({{...p, qty:1}}); }}
  updateCartUI();
  showToast(p.name + ' added to cart! 🛒');
}}

function addToCartFromModal() {{
  if (currentModalId === null) return;
  const p = PRODUCTS[currentModalId];
  const existing = cart.find(c => c.id === p.id);
  if (existing) {{ existing.qty += modalQty; }} else {{ cart.push({{...p, qty:modalQty}}); }}
  updateCartUI();
  showToast(p.name + ' × ' + modalQty + ' added! 🛒');
  closeModal();
}}

function updateCartUI() {{
  const total = cart.reduce((s,c)=>s+c.qty,0);
  const el = document.getElementById('cart-count');
  if (el) {{ el.style.display = total ? 'flex' : 'none'; el.textContent = total; }}
  // Render cart items
  const itemsEl = document.getElementById('cart-items');
  if (itemsEl) {{
    if (!cart.length) {{
      itemsEl.innerHTML = '<div style="text-align:center;padding:3rem;color:#999;"><div style="font-size:3rem;margin-bottom:1rem">🛒</div><p>Your cart is empty</p></div>';
    }} else {{
      itemsEl.innerHTML = cart.map(item => `
        <div style="display:flex;gap:1rem;align-items:center;padding:.85rem 0;border-bottom:1px solid {border_color};">
          <div style="font-size:2.2rem;flex-shrink:0;">${{item.emoji}}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-weight:700;font-size:.88rem;color:{text_color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${{item.name}}</div>
            <div style="font-size:.82rem;color:{primary_color};font-weight:700;">${{item.price}}</div>
          </div>
          <div style="display:flex;align-items:center;gap:.4rem;flex-shrink:0;">
            <button onclick="changeCartQty(${{item.id}},-1)" style="background:{border_color};border:none;width:24px;height:24px;border-radius:50%;cursor:pointer;font-weight:700;">−</button>
            <span style="font-weight:700;min-width:20px;text-align:center;color:{text_color};">${{item.qty}}</span>
            <button onclick="changeCartQty(${{item.id}},1)" style="background:{border_color};border:none;width:24px;height:24px;border-radius:50%;cursor:pointer;font-weight:700;">+</button>
          </div>
        </div>`).join('');
    }}
  }}
  // Update total
  const totalEl = document.getElementById('cart-total');
  if (totalEl) {{
    const sum = cart.reduce((s,c)=>{{
      const price = parseFloat((c.price||'0').replace(/[^0-9.]/g,''))||0;
      return s + price*c.qty;
    }},0);
    totalEl.textContent = '$' + sum.toFixed(2);
  }}
}}

function changeCartQty(id, delta) {{
  const idx = cart.findIndex(c => c.id === id);
  if (idx === -1) return;
  cart[idx].qty += delta;
  if (cart[idx].qty <= 0) cart.splice(idx, 1);
  updateCartUI();
}}

function showCart() {{
  document.getElementById('cart-drawer').style.display = 'flex';
  document.getElementById('cart-overlay').style.display = 'block';
  document.body.style.overflow = 'hidden';
  updateCartUI();
}}

function closeCart() {{
  document.getElementById('cart-drawer').style.display = 'none';
  document.getElementById('cart-overlay').style.display = 'none';
  document.body.style.overflow = '';
}}

function checkout() {{
  if (!cart.length) {{ showToast('Your cart is empty!'); return; }}
  showToast('Redirecting to checkout... 🎉');
  setTimeout(() => alert('Checkout coming soon! This is a demo website generated by BizBuilder AI.'), 800);
}}

// ─── Wishlist ─────────────────────────────────────────────────────────────
function toggleWishlist() {{
  if (currentModalId === null) return;
  const btn = document.getElementById('wish-btn');
  if (wishlist.has(currentModalId)) {{
    wishlist.delete(currentModalId);
    btn.textContent = '♡ Wishlist';
    showToast('Removed from wishlist');
  }} else {{
    wishlist.add(currentModalId);
    btn.textContent = '♥ Wishlisted';
    showToast('Added to wishlist ♥');
  }}
}}

// ─── Share ────────────────────────────────────────────────────────────────
function shareProduct() {{
  if (currentModalId === null) return;
  const p = PRODUCTS[currentModalId];
  if (navigator.share) {{
    navigator.share({{title: p.name, text: p.description, url: window.location.href}});
  }} else {{
    navigator.clipboard?.writeText(window.location.href);
    showToast('Link copied to clipboard!');
  }}
}}

// ─── Toast ────────────────────────────────────────────────────────────────
function showToast(msg) {{
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.style.opacity = '1';
  t.style.transform = 'translateY(0)';
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => {{
    t.style.opacity = '0';
    t.style.transform = 'translateY(20px)';
  }}, 2500);
}}

// ─── Keyboard close ───────────────────────────────────────────────────────
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{ closeModal(); closeCart(); }}
}});
</script>
"""


# ══════════════════════════════════════════════════════════════════════════════
# SHARED 6-PAGE NAV + JS ROUTER
# Injected into every non-ecommerce template
# Pages: Home, About, Services, Contact, Testimonials, Blog
# ══════════════════════════════════════════════════════════════════════════════

def _page_nav_css(primary, accent):
    return f"""
    /* ── Page Nav Bar ── */
    .page-nav {{
      background:#fff;border-bottom:1px solid #eee;
      display:flex;align-items:center;justify-content:center;
      gap:.25rem;padding:.5rem 1rem;position:sticky;top:64px;z-index:90;
      flex-wrap:wrap;box-shadow:0 2px 8px rgba(0,0,0,.04);
    }}
    .page-nav-btn {{
      background:transparent;border:none;cursor:pointer;
      font-family:inherit;font-size:.82rem;font-weight:600;
      color:#777;padding:.45rem .9rem;border-radius:50px;
      transition:all .18s;letter-spacing:.01em;
    }}
    .page-nav-btn:hover{{background:{primary}12;color:{primary}}}
    .page-nav-btn.active{{background:{primary};color:#fff;box-shadow:0 3px 12px {primary}40}}
    /* ── Page sections ── */
    .page-section{{display:none}}
    .page-section.visible{{display:block}}
    /* ── Blog grid ── */
    .blog-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto}}
    .blog-card{{background:#fff;border-radius:16px;overflow:hidden;border:1px solid #eee;transition:all .2s;cursor:pointer}}
    .blog-card:hover{{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.1)}}
    .blog-card-img{{height:160px;display:flex;align-items:center;justify-content:center;font-size:4rem;background:linear-gradient(135deg,{primary}10,{accent}08)}}
    .blog-card-body{{padding:1.25rem}}
    .blog-cat{{display:inline-block;background:{primary}15;color:{primary};font-size:.7rem;font-weight:700;padding:.2rem .6rem;border-radius:50px;margin-bottom:.6rem;letter-spacing:.05em;text-transform:uppercase}}
    .blog-title{{font-weight:700;font-size:1rem;margin-bottom:.5rem;line-height:1.4}}
    .blog-excerpt{{font-size:.82rem;color:#777;line-height:1.6;margin-bottom:.75rem}}
    .blog-date{{font-size:.75rem;color:#aaa}}
    /* ── FAQ ── */
    .faq-wrap{{max-width:720px;margin:0 auto}}
    .faq-item{{border:1px solid #eee;border-radius:12px;margin-bottom:.75rem;overflow:hidden}}
    .faq-q{{display:flex;align-items:center;justify-content:space-between;padding:1.1rem 1.25rem;cursor:pointer;font-weight:600;font-size:.92rem;background:#fff;transition:background .15s}}
    .faq-q:hover{{background:{primary}06}}
    .faq-q.open{{background:{primary}10;color:{primary}}}
    .faq-icon{{font-size:1rem;transition:transform .2s;flex-shrink:0}}
    .faq-q.open .faq-icon{{transform:rotate(45deg)}}
    .faq-a{{display:none;padding:0 1.25rem 1.1rem;font-size:.875rem;color:#666;line-height:1.7}}
    .faq-a.open{{display:block}}
"""

def _page_nav_html(pages, primary):
    btns = ""
    for i, (pid, label, icon) in enumerate(pages):
        active = "active" if i == 0 else ""
        btns += f'<button class="page-nav-btn {active}" onclick="showSection(\'{pid}\')" id="nav-{pid}">{icon} {label}</button>'
    return f'<div class="page-nav">{btns}</div>'

def _page_nav_js():
    return """
<script>
function showSection(id) {
  document.querySelectorAll('.page-section').forEach(s => s.classList.remove('visible'));
  document.querySelectorAll('.page-nav-btn').forEach(b => b.classList.remove('active'));
  const sec = document.getElementById('sec-' + id);
  const btn = document.getElementById('nav-' + id);
  if (sec) sec.classList.add('visible');
  if (btn) btn.classList.add('active');
  window.scrollTo({top: 0, behavior: 'smooth'});
}
function toggleFaq(el) {
  const item = el.closest('.faq-item');
  const ans = item.querySelector('.faq-a');
  const isOpen = el.classList.contains('open');
  // close all
  document.querySelectorAll('.faq-q').forEach(q => { q.classList.remove('open'); q.querySelector('.faq-icon').style.transform = ''; });
  document.querySelectorAll('.faq-a').forEach(a => a.classList.remove('open'));
  if (!isOpen) { el.classList.add('open'); if(ans) ans.classList.add('open'); }
}
// Init: show home
document.addEventListener('DOMContentLoaded', () => showSection('home'));
</script>"""

def _build_blog_section(posts, primary, accent, bg, surface, border, text, muted, sec_title_style=""):
    if not posts:
        return ""
    cards = ""
    for p in posts:
        cards += f"""<div class="blog-card" onclick="alert('Full article coming soon!')">
      <div class="blog-card-img">{p.get('emoji','📝')}</div>
      <div class="blog-card-body">
        <span class="blog-cat">{p.get('category','Tips')}</span>
        <div class="blog-title">{p.get('title','')}</div>
        <div class="blog-excerpt">{p.get('excerpt','')}</div>
        <div class="blog-date">📅 {p.get('date','')}</div>
      </div>
    </div>"""
    return cards

def _build_faq_section(faqs):
    if not faqs:
        return ""
    items = ""
    for f in faqs:
        items += f"""<div class="faq-item">
      <div class="faq-q" onclick="toggleFaq(this)">
        <span>{f.get('question','')}</span>
        <span class="faq-icon">+</span>
      </div>
      <div class="faq-a">{f.get('answer','')}</div>
    </div>"""
    return items


# ══════════════════════════════════════════════════════════════════════════════
# HTML POST-PROCESSOR  — wraps any single-page HTML into 6-page routed site
# Called from generate_website_html for non-ecommerce sites
# ══════════════════════════════════════════════════════════════════════════════

def _wrap_with_page_router(html: str, content: dict, primary: str, accent: str) -> str:
    """
    Takes existing single-page HTML and converts it to a 6-page routed site.
    Pages: Home, About, Services/Products, Testimonials, Blog, Contact
    All content is already in `content` dict from AI.
    """
    import json as _json

    ab    = content.get("about", {})
    ct    = content.get("contact", {})
    sc    = content.get("social", {})
    tg    = content.get("tagline", "")
    prods = content.get("products", [])
    cats  = content.get("categories", [])
    testis= content.get("testimonials", [])
    feats = content.get("features", [])
    stats = content.get("stats", [])
    hero  = content.get("hero", {})
    posts = content.get("blog_posts", [])
    faqs  = content.get("faq", [])
    name  = content.get("title", "Brand")

    # Colours from content
    cs   = content.get("color_scheme", {})
    p    = cs.get("primary",   primary)
    s    = cs.get("secondary", primary)
    a    = cs.get("accent",    accent)
    t    = cs.get("text",      "#1A1A2E")
    bg   = cs.get("bg",        "#FAFAFA")

    vals_html  = "".join(f'<span style="display:inline-block;background:{p}18;color:{p};border:1px solid {p}30;border-radius:50px;padding:.3rem .85rem;font-size:.82rem;font-weight:600;margin:.25rem">{v}</span>' for v in ab.get("values", []))
    stars_row  = lambda r: "★"*int(r)+"☆"*(5-int(r))

    # ── About page ────────────────────────────────────────────────────────────
    about_page = f"""
<section style="padding:5rem 6%;background:{bg}">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:5rem;align-items:center;max-width:1100px;margin:0 auto">
    <div style="background:linear-gradient(135deg,{p},{a});border-radius:24px;height:420px;display:flex;align-items:center;justify-content:center;font-size:8rem;box-shadow:0 20px 50px {p}25">🌸</div>
    <div>
      <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.6rem">Our Story</div>
      <h2 style="font-size:2.2rem;font-weight:800;letter-spacing:-.025em;margin-bottom:1rem;line-height:1.15">{ab.get('title','About Us')}</h2>
      <p style="font-size:1rem;color:{p};font-weight:600;font-style:italic;margin-bottom:1.25rem;padding-left:1rem;border-left:3px solid {p};line-height:1.6">{ab.get('mission','')}</p>
      <p style="color:#666;line-height:1.9;margin-bottom:1.75rem;font-size:.92rem">{ab.get('story','').replace(chr(10),'<br><br>')}</p>
      <div>{vals_html}</div>
    </div>
  </div>
</section>
<section style="padding:3.5rem 6%;background:{p};text-align:center">
  <h3 style="color:#fff;font-size:1.1rem;font-weight:700;margin-bottom:.5rem;opacity:.85;letter-spacing:.05em;text-transform:uppercase">Why Choose Us</h3>
  <div style="display:flex;justify-content:center;gap:5rem;flex-wrap:wrap;margin-top:1.5rem">
    {''.join(f'<div style="text-align:center;color:#fff"><div style="font-size:2.8rem;font-weight:900;line-height:1">{s.get("number","")}</div><div style="font-size:.82rem;opacity:.8;margin-top:.3rem">{s.get("label","")}</div></div>' for s in stats)}
  </div>
</section>"""

    # ── Services / Products page ───────────────────────────────────────────────
    # Category filter buttons
    cat_btns = f'<button onclick="filterServCat(\'all\')" class="scat-btn scat-active" id="scat-all">All</button>'
    for cat in cats:
        slug = cat.get("name","").lower().replace(" ","-")
        cat_btns += f'<button onclick="filterServCat(\'{slug}\')" class="scat-btn" id="scat-{slug}">{cat.get("icon","")} {cat.get("name","")}</button>'

    prod_cards = ""
    for i, pr in enumerate(prods):
        badge = f'<span style="position:absolute;top:.6rem;left:.6rem;background:{a};color:#fff;font-size:.68rem;font-weight:700;padding:.2rem .55rem;border-radius:50px;z-index:1">{pr.get("badge","")}</span>' if pr.get("badge") else ""
        orig  = f'<s style="font-size:.75rem;color:#bbb;margin-left:.3rem">{pr.get("original_price","")}</s>' if pr.get("original_price") else ""
        cat_slug = pr.get("category","all").lower().replace(" ","-")
        stars = stars_row(pr.get("rating",4.5))
        prod_cards += f"""<div class="sprod-card" data-cat="{cat_slug}" style="background:#fff;border-radius:16px;border:1px solid #eee;overflow:hidden;transition:all .2s;position:relative">
      {badge}
      <div style="height:180px;display:flex;align-items:center;justify-content:center;font-size:4.5rem;background:linear-gradient(135deg,{p}12,{a}08)">{pr.get("emoji","🛍️")}</div>
      <div style="padding:1.1rem">
        <div style="font-weight:700;font-size:.92rem;margin-bottom:.25rem">{pr.get("name","")}</div>
        <div style="font-size:.78rem;color:#888;margin-bottom:.6rem;line-height:1.4">{pr.get("description","")}</div>
        <div style="color:{a};font-size:.8rem;margin-bottom:.7rem;letter-spacing:.04em">{stars} <span style="color:#bbb;font-size:.72rem">({pr.get("reviews",0)})</span></div>
        <div style="display:flex;align-items:center;justify-content:space-between">
          <div><span style="font-weight:800;font-size:1.05rem;color:{p}">{pr.get("price","")}</span>{orig}</div>
          <button onclick="alert('Added to cart! 🛒')" style="background:{p};color:#fff;border:none;border-radius:50px;padding:.42rem .95rem;font-size:.76rem;font-weight:700;cursor:pointer;font-family:inherit">{hero.get('cta_primary','Buy Now')}</button>
        </div>
      </div>
    </div>"""

    services_page = f"""
<section style="padding:5rem 6%;background:{bg}">
  <div style="text-align:center;margin-bottom:2.5rem">
    <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.6rem">What We Offer</div>
    <h2 style="font-size:2.2rem;font-weight:800;letter-spacing:-.025em">Products &amp; Services</h2>
    <p style="color:#666;max-width:520px;margin:.6rem auto 0;font-size:.92rem">{tg}</p>
  </div>
  <!-- Category filter -->
  <div style="display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center;margin-bottom:2rem">
    {cat_btns}
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1.5rem;max-width:1200px;margin:0 auto" id="serv-grid">
    {prod_cards}
  </div>
</section>
<style>
  .scat-btn{{background:#fff;border:1.5px solid #eee;border-radius:50px;padding:.45rem 1rem;font-size:.8rem;font-weight:600;cursor:pointer;font-family:inherit;transition:all .18s;color:#777}}
  .scat-btn:hover,.scat-btn.scat-active{{background:{p};color:#fff;border-color:{p}}}
  .sprod-card:hover{{transform:translateY(-4px);box-shadow:0 12px 36px rgba(0,0,0,.12)}}
</style>
<script>
function filterServCat(cat) {{
  document.querySelectorAll('.scat-btn').forEach(b=>b.classList.remove('scat-active'));
  const btn = document.getElementById('scat-'+cat);
  if(btn) btn.classList.add('scat-active');
  document.querySelectorAll('.sprod-card').forEach(c=>{{
    c.style.display = (cat==='all'||c.dataset.cat===cat) ? '' : 'none';
  }});
}}
</script>"""

    # ── Testimonials page ─────────────────────────────────────────────────────
    testi_cards = ""
    for ti in testis:
        stars = stars_row(ti.get("rating",5))
        verified = '<span style="font-size:.72rem;color:'+p+';font-weight:600">✓ Verified</span>' if ti.get("verified") else ""
        testi_cards += f"""<div style="background:#fff;border:1px solid #eee;border-radius:16px;padding:1.75rem;transition:all .2s">
      <div style="color:{a};font-size:1.1rem;margin-bottom:.75rem;letter-spacing:.06em">{stars}</div>
      <p style="font-size:.95rem;color:#444;line-height:1.75;margin-bottom:1.25rem;font-style:italic">"{ti.get('text','')}"</p>
      <div style="display:flex;align-items:center;gap:.75rem">
        <div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,{p},{a});display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:.95rem;flex-shrink:0">{ti.get('avatar','?')}</div>
        <div>
          <div style="font-weight:700;font-size:.9rem">{ti.get('name','')}</div>
          <div style="font-size:.75rem;color:#aaa">{ti.get('location','')}</div>
          {verified}
        </div>
      </div>
    </div>"""

    # Add fake extra testimonials to make the page look fuller
    extra_testis = [
        {"name":"Alex Johnson","avatar":"A","rating":5,"text":"Exceptional quality and service. Highly recommend to anyone looking for the best.","location":"Chicago, USA","verified":True},
        {"name":"Mia Chen","avatar":"M","rating":5,"text":"I was amazed by how quickly everything arrived and how well it matched the description.","location":"Sydney, Australia","verified":True},
        {"name":"Carlos M.","avatar":"C","rating":4,"text":"Great value for money. Will definitely be ordering again very soon.","location":"Madrid, Spain","verified":False},
    ]
    for ti in extra_testis:
        stars = stars_row(ti["rating"])
        testi_cards += f"""<div style="background:#fff;border:1px solid #eee;border-radius:16px;padding:1.75rem;transition:all .2s">
      <div style="color:{a};font-size:1.1rem;margin-bottom:.75rem">{stars}</div>
      <p style="font-size:.95rem;color:#444;line-height:1.75;margin-bottom:1.25rem;font-style:italic">"{ti['text']}"</p>
      <div style="display:flex;align-items:center;gap:.75rem">
        <div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,{p},{a});display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:.95rem;flex-shrink:0">{ti['avatar']}</div>
        <div>
          <div style="font-weight:700;font-size:.9rem">{ti['name']}</div>
          <div style="font-size:.75rem;color:#aaa">{ti['location']}</div>
          {'<span style="font-size:.72rem;color:'+p+';font-weight:600">✓ Verified</span>' if ti['verified'] else ''}
        </div>
      </div>
    </div>"""

    testimonials_page = f"""
<section style="padding:5rem 6%;background:{bg}">
  <div style="text-align:center;margin-bottom:3rem">
    <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.6rem">Reviews</div>
    <h2 style="font-size:2.2rem;font-weight:800;letter-spacing:-.025em">What Our Customers Say</h2>
    <p style="color:#666;max-width:480px;margin:.6rem auto 0;font-size:.92rem">Real experiences from real customers who love what we do.</p>
  </div>
  <!-- Rating summary -->
  <div style="display:flex;justify-content:center;gap:3rem;flex-wrap:wrap;margin-bottom:3rem">
    <div style="text-align:center"><div style="font-size:3rem;font-weight:900;color:{p}">4.8</div><div style="color:{a};font-size:1.2rem">★★★★★</div><div style="font-size:.8rem;color:#888;margin-top:.25rem">Average Rating</div></div>
    <div style="text-align:center"><div style="font-size:3rem;font-weight:900;color:{p}">2,400+</div><div style="font-size:.8rem;color:#888;margin-top:.25rem">Total Reviews</div></div>
    <div style="text-align:center"><div style="font-size:3rem;font-weight:900;color:{p}">97%</div><div style="font-size:.8rem;color:#888;margin-top:.25rem">Would Recommend</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1.5rem;max-width:1100px;margin:0 auto">
    {testi_cards}
  </div>
</section>"""

    # ── Blog page ─────────────────────────────────────────────────────────────
    blog_cards = _build_blog_section(posts, p, a, bg, "#fff", "#eee", t, "#888")

    # Add extra blog posts to fill the page
    extra_posts = [
        {"title": f"How {name} Is Changing the Game", "excerpt": "Discover how our approach is setting new industry standards and why customers keep coming back.", "date":"Feb 20, 2025","category":"Story","emoji":"🚀"},
        {"title": "Top Tips for Getting the Best Results", "excerpt": "Expert advice from our team on how to make the most of what we offer.", "date":"Feb 12, 2025","category":"Tips","emoji":"💡"},
        {"title": "Behind the Scenes: Our Process", "excerpt": "A look at how we work, who we are, and what drives us to deliver excellence every single day.", "date":"Jan 30, 2025","category":"Culture","emoji":"🏭"},
    ]
    for ep in extra_posts:
        blog_cards += f"""<div class="blog-card" onclick="alert('Full article coming soon!')">
      <div class="blog-card-img">{ep['emoji']}</div>
      <div class="blog-card-body">
        <span class="blog-cat">{ep['category']}</span>
        <div class="blog-title">{ep['title']}</div>
        <div class="blog-excerpt">{ep['excerpt']}</div>
        <div class="blog-date">📅 {ep['date']}</div>
      </div>
    </div>"""

    faq_html = _build_faq_section(faqs)

    faq_section = (
        '<section style="padding:4rem 6%;background:#fff">' +
        '<div style="text-align:center;margin-bottom:2.5rem">' +
        '<h2 style="font-size:1.8rem;font-weight:800">Frequently Asked Questions</h2>' +
        '<p style="color:#888;margin-top:.4rem">Everything you need to know</p>' +
        '</div><div class="faq-wrap">' + faq_html + '</div></section>'
    ) if faq_html else ''

    blog_page = f"""
<section style="padding:5rem 6%;background:{bg}">
  <div style="text-align:center;margin-bottom:3rem">
    <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.6rem">Latest</div>
    <h2 style="font-size:2.2rem;font-weight:800;letter-spacing:-.025em">Blog &amp; News</h2>
    <p style="color:#666;max-width:480px;margin:.6rem auto 0;font-size:.92rem">Insights, stories and updates from our team.</p>
  </div>
  <div class="blog-grid">{blog_cards}</div>
</section>
{faq_section}"""

    # ── Contact page ──────────────────────────────────────────────────────────
    contact_page = f"""
<section style="padding:5rem 6%;background:{bg}">
  <div style="text-align:center;margin-bottom:3rem">
    <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.6rem">Get in Touch</div>
    <h2 style="font-size:2.2rem;font-weight:800;letter-spacing:-.025em">Contact Us</h2>
    <p style="color:#666;max-width:480px;margin:.6rem auto 0;font-size:.92rem">We'd love to hear from you. Our team is always ready to help.</p>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4rem;max-width:1100px;margin:0 auto;align-items:start">
    <div>
      <h3 style="font-size:1.6rem;font-weight:800;letter-spacing:-.02em;margin-bottom:1.75rem">Let's Talk</h3>
      <div style="display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.3rem">
        <div style="width:46px;height:46px;border-radius:12px;background:{p}15;display:flex;align-items:center;justify-content:center;font-size:1.15rem;flex-shrink:0">📧</div>
        <div><strong style="display:block;font-weight:700;font-size:.88rem">{ct.get('email','hello@brand.com')}</strong><span style="font-size:.8rem;color:#888">Email us anytime</span></div>
      </div>
      <div style="display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.3rem">
        <div style="width:46px;height:46px;border-radius:12px;background:{p}15;display:flex;align-items:center;justify-content:center;font-size:1.15rem;flex-shrink:0">📞</div>
        <div><strong style="display:block;font-weight:700;font-size:.88rem">{ct.get('phone','+1 (555) 000-0000')}</strong><span style="font-size:.8rem;color:#888">Mon–Fri, 9am–6pm</span></div>
      </div>
      <div style="display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.75rem">
        <div style="width:46px;height:46px;border-radius:12px;background:{p}15;display:flex;align-items:center;justify-content:center;font-size:1.15rem;flex-shrink:0">📍</div>
        <div><strong style="display:block;font-weight:700;font-size:.88rem">{ct.get('address','123 Brand Street')}</strong><span style="font-size:.8rem;color:#888">Our headquarters</span></div>
      </div>
      <div style="display:flex;gap:.6rem;flex-wrap:wrap">
        <button onclick="alert('Instagram coming soon!')" style="background:{bg};border:1px solid #ddd;border-radius:10px;padding:.48rem 1rem;font-size:.78rem;font-weight:600;cursor:pointer;font-family:inherit;transition:all .2s">📸 {sc.get('instagram','@brand')}</button>
        <button onclick="alert('TikTok coming soon!')" style="background:{bg};border:1px solid #ddd;border-radius:10px;padding:.48rem 1rem;font-size:.78rem;font-weight:600;cursor:pointer;font-family:inherit">🎵 TikTok</button>
        <button onclick="alert('Twitter coming soon!')" style="background:{bg};border:1px solid #ddd;border-radius:10px;padding:.48rem 1rem;font-size:.78rem;font-weight:600;cursor:pointer;font-family:inherit">Twitter</button>
      </div>
    </div>
    <div style="background:#fff;border:1px solid #eee;border-radius:16px;padding:2.2rem">
      <h3 style="font-size:1.2rem;font-weight:700;margin-bottom:1.5rem">Send a Message</h3>
      <div style="margin-bottom:1rem"><label style="display:block;font-size:.8rem;font-weight:600;color:#888;margin-bottom:.35rem">Full Name</label><input type="text" placeholder="Your name" style="width:100%;padding:.72rem .95rem;border:1.5px solid #eee;border-radius:10px;font-family:inherit;font-size:.88rem;outline:none;transition:border-color .2s" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#eee'"/></div>
      <div style="margin-bottom:1rem"><label style="display:block;font-size:.8rem;font-weight:600;color:#888;margin-bottom:.35rem">Email</label><input type="email" placeholder="your@email.com" style="width:100%;padding:.72rem .95rem;border:1.5px solid #eee;border-radius:10px;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#eee'"/></div>
      <div style="margin-bottom:1rem"><label style="display:block;font-size:.8rem;font-weight:600;color:#888;margin-bottom:.35rem">Subject</label><select style="width:100%;padding:.72rem .95rem;border:1.5px solid #eee;border-radius:10px;font-family:inherit;font-size:.88rem;outline:none;background:#fff"><option>General Enquiry</option><option>Order Support</option><option>Partnership</option><option>Other</option></select></div>
      <div style="margin-bottom:1.25rem"><label style="display:block;font-size:.8rem;font-weight:600;color:#888;margin-bottom:.35rem">Message</label><textarea placeholder="How can we help?" style="width:100%;padding:.72rem .95rem;border:1.5px solid #eee;border-radius:10px;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:110px" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#eee'"></textarea></div>
      <button onclick="alert('Message sent! We will respond within 24 hours ✅')" style="width:100%;padding:.88rem;background:{p};color:#fff;border:none;border-radius:50px;font-weight:700;font-size:.95rem;cursor:pointer;font-family:inherit;transition:all .2s">Send Message ✉️</button>
    </div>
  </div>
</section>"""

    # ── HOME page: inject blog preview + testimonials preview at bottom ────────
    # We add these after the existing main sections
    # Pre-build blog preview cards (avoids backslash-in-f-string)
    _blog_preview_cards = ""
    for post in (posts or [])[:3]:
        _blog_preview_cards += (
            f'<div style="background:{bg};border:1px solid #eee;border-radius:14px;overflow:hidden;cursor:pointer;transition:all .2s"' +
            ' onclick="showSection(\'blog\')" ' +
            f'onmouseover="this.style.transform=\'translateY(-3px)\';this.style.boxShadow=\'0 8px 24px rgba(0,0,0,.1)\'"' +
            ' onmouseout="this.style.transform=\'\';this.style.boxShadow=\'\'"><div ' +
            f'style="height:120px;display:flex;align-items:center;justify-content:center;font-size:3rem;background:linear-gradient(135deg,{p}10,{a}08)">' +
            f'{post.get("emoji","📝")}</div><div style="padding:1rem">' +
            f'<span style="background:{p}15;color:{p};font-size:.68rem;font-weight:700;padding:.18rem .55rem;border-radius:50px;text-transform:uppercase;letter-spacing:.05em">{post.get("category","")}</span>' +
            f'<div style="font-weight:700;font-size:.88rem;margin-top:.5rem;line-height:1.4">{post.get("title","")}</div></div></div>'
        )

    # Pre-build testimonial preview cards
    _testi_preview_cards = ""
    for ti in (testis or [])[:3]:
        _stars = "★" * int(ti.get("rating", 5))
        _testi_preview_cards += (
            f'<div style="background:#fff;border:1px solid #eee;border-radius:14px;padding:1.5rem">' +
            f'<div style="color:{a};margin-bottom:.6rem">{_stars}</div>' +
            f'<p style="font-size:.88rem;color:#555;line-height:1.65;font-style:italic;margin-bottom:1rem">&ldquo;{ti.get("text","")}&rdquo;</p>' +
            f'<div style="display:flex;align-items:center;gap:.6rem">' +
            f'<div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,{p},{a});display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:.85rem">{ti.get("avatar","?")}</div>' +
            f'<div style="font-weight:700;font-size:.82rem">{ti.get("name","")}</div>' +
            '</div></div>'
        )

    home_addons = f"""
<!-- Blog preview on home -->
<section style="padding:4rem 6%;background:#fff">
  <div style="display:flex;align-items:center;justify-content:space-between;max-width:1100px;margin:0 auto 2rem">
    <div>
      <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.4rem">Latest</div>
      <h2 style="font-size:1.8rem;font-weight:800;letter-spacing:-.025em">From Our Blog</h2>
    </div>
    <button onclick="showSection('blog')" style="background:transparent;border:1.5px solid {p};color:{p};border-radius:50px;padding:.55rem 1.3rem;font-weight:600;font-size:.85rem;cursor:pointer;font-family:inherit">View All →</button>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.25rem;max-width:1100px;margin:0 auto">
    {_blog_preview_cards}
  </div>
</section>
<!-- Testimonials preview on home -->
<section style="padding:4rem 6%;background:{bg}">
  <div style="display:flex;align-items:center;justify-content:space-between;max-width:1100px;margin:0 auto 2rem">
    <div>
      <div style="color:{p};font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.4rem">Reviews</div>
      <h2 style="font-size:1.8rem;font-weight:800;letter-spacing:-.025em">What Customers Say</h2>
    </div>
    <button onclick="showSection('testimonials')" style="background:transparent;border:1.5px solid {p};color:{p};border-radius:50px;padding:.55rem 1.3rem;font-weight:600;font-size:.85rem;cursor:pointer;font-family:inherit">All Reviews →</button>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1.25rem;max-width:1100px;margin:0 auto">
    {_testi_preview_cards}
  </div>
</section>"""


    # ── Inject page system into existing HTML ─────────────────────────────────
    page_css = _page_nav_css(p, a)
    page_nav = _page_nav_html([
        ('home',         'Home',         '🏠'),
        ('about',        'About Us',     '👤'),
        ('services',     'Services',     '⚡'),
        ('testimonials', 'Reviews',      '⭐'),
        ('blog',         'Blog',         '📝'),
        ('contact',      'Contact',      '📞'),
    ], p)
    page_js = _page_nav_js()

    # Insert page nav CSS before </style>
    if '</style>' in html:
        html = html.replace('</style>', page_css + '\n</style>', 1)

    # Insert page nav after <body> tag or after the announce bar / existing nav
    # Strategy: inject right before the first <section or before <nav
    nav_pos = html.find('<nav')
    if nav_pos != -1:
        # Find the closing </nav> tag
        nav_end = html.find('</nav>', nav_pos) + len('</nav>')
        # Insert page nav after the existing top nav
        html = html[:nav_end] + '\n' + page_nav + '\n<div class="page-section visible" id="sec-home">' + html[nav_end:]
    else:
        html = html.replace('<body>', '<body>\n' + page_nav + '\n<div class="page-section visible" id="sec-home">')

    # Find </body> and inject all pages before it
    # First, close the home section div before footer
    footer_pos = html.rfind('<footer')
    if footer_pos != -1:
        # Insert home addons + close home section + other pages before footer
        other_pages = (
            home_addons +
            '\n</div><!-- end home section -->\n' +
            f'<div class="page-section" id="sec-about">{about_page}</div>\n' +
            f'<div class="page-section" id="sec-services">{services_page}</div>\n' +
            f'<div class="page-section" id="sec-testimonials">{testimonials_page}</div>\n' +
            f'<div class="page-section" id="sec-blog">{blog_page}</div>\n' +
            f'<div class="page-section" id="sec-contact">{contact_page}</div>\n'
        )
        html = html[:footer_pos] + other_pages + html[footer_pos:]
    else:
        # No footer — inject before </body>
        html = html.replace('</body>', other_pages + '\n</body>')

    # Inject JS before </body>
    html = html.replace('</body>', page_js + '\n</body>')

    return html


# ══════════════════════════════════════════════════════════════════════════════
# SAAS / SERVICE WEBSITE BUILDER
# Clean professional layout: no cart, no products grid
# Sections: Hero, Features, Services, Process, Stats, Testimonials,
#           Blog preview, FAQ, Contact — all in one 6-page routed site
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# REAL AGENCY / SAAS WEBSITE BUILDER
# Inspired by qrioustech.com — no prices, real agency feel
# Sections: Hero, Partner strip, About, Services (no price),
#           Industries, Process, Why Us, Stats, Testimonials,
#           Technologies, Blog, Contact/Appointment
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# REAL-WORLD AGENCY WEBSITE BUILDER
# Features: Real Unsplash photos, SVG line icons, dynamic content,
#           professional layout matching qrioustech.com quality
# ══════════════════════════════════════════════════════════════════════════════

# ── SVG Icon Library (line-art style, like real agency sites) ─────────────────
SVG_ICONS = {
    # Service icons
    "web":      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    "mobile":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>',
    "ai":       '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 0 6h-1v1a4 4 0 0 1-8 0v-1H7a3 3 0 0 1 0-6h1V6a4 4 0 0 1 4-4z"/><circle cx="12" cy="12" r="2"/></svg>',
    "cloud":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>',
    "design":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>',
    "security": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "data":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
    "api":      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    "analytics":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "ecommerce":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>',
    "crm":      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "testing":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    "consulting":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "default":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    # Industry icons
    "health":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    "finance":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    "education":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
    "retail":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>',
    "startup":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    "enterprise":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    "logistics":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>',
    "media":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
    "sports":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>',
    "inddefault":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    # Process / feature icons
    "discovery":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "strategy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/></svg>',
    "build":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    "launch":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12H3l9-9 9 9h-2"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/><rect x="9" y="12" width="6" height="9"/></svg>',
    "fast":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    "support":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "quality":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    "shield":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
}

def _get_service_icon(name):
    """Pick the best SVG icon based on service name keywords."""
    n = name.lower()
    if any(k in n for k in ["web","website","frontend","react","next","vue"]): return SVG_ICONS["web"]
    if any(k in n for k in ["mobile","app","ios","android","flutter"]): return SVG_ICONS["mobile"]
    if any(k in n for k in ["ai","machine","ml","neural","intelligence","automation"]): return SVG_ICONS["ai"]
    if any(k in n for k in ["cloud","aws","azure","gcp","infra","devops","deploy"]): return SVG_ICONS["cloud"]
    if any(k in n for k in ["design","ui","ux","figma","brand","visual"]): return SVG_ICONS["design"]
    if any(k in n for k in ["security","secure","cyber","protect","compliance"]): return SVG_ICONS["security"]
    if any(k in n for k in ["data","database","analytics","bi","report","insight"]): return SVG_ICONS["analytics"]
    if any(k in n for k in ["api","integration","backend","microservice"]): return SVG_ICONS["api"]
    if any(k in n for k in ["ecommerce","shop","store","commerce","market"]): return SVG_ICONS["ecommerce"]
    if any(k in n for k in ["crm","erp","customer","relationship","sales"]): return SVG_ICONS["crm"]
    if any(k in n for k in ["test","qa","quality","audit"]): return SVG_ICONS["testing"]
    if any(k in n for k in ["consult","strategy","advisory","plan"]): return SVG_ICONS["consulting"]
    return SVG_ICONS["default"]

def _get_industry_icon(name):
    """Pick SVG icon for industry/category."""
    n = name.lower()
    if any(k in n for k in ["health","medical","hospital","pharma","care"]): return SVG_ICONS["health"]
    if any(k in n for k in ["finance","fintech","bank","payment","insurance","invest"]): return SVG_ICONS["finance"]
    if any(k in n for k in ["education","school","learn","university","edtech"]): return SVG_ICONS["education"]
    if any(k in n for k in ["retail","ecommerce","shop","store","commerce"]): return SVG_ICONS["retail"]
    if any(k in n for k in ["startup","early","seed","venture"]): return SVG_ICONS["startup"]
    if any(k in n for k in ["enterprise","corporate","large","fortune"]): return SVG_ICONS["enterprise"]
    if any(k in n for k in ["logistics","supply","transport","delivery","shipping"]): return SVG_ICONS["logistics"]
    if any(k in n for k in ["media","entertainment","content","music","film"]): return SVG_ICONS["media"]
    if any(k in n for k in ["sport","fitness","game","athletic"]): return SVG_ICONS["sports"]
    if any(k in n for k in ["saas","software","tech","it","digital"]): return SVG_ICONS["web"]
    return SVG_ICONS["inddefault"]

def _get_process_icon(title):
    """Pick SVG icon for process step."""
    n = title.lower()
    if any(k in n for k in ["discover","understand","learn","research","call","meet"]): return SVG_ICONS["discovery"]
    if any(k in n for k in ["strategy","plan","proposal","scope","design","architect"]): return SVG_ICONS["strategy"]
    if any(k in n for k in ["build","develop","code","execut","implement","creat"]): return SVG_ICONS["build"]
    if any(k in n for k in ["launch","deploy","live","ship","release","support","deliver"]): return SVG_ICONS["launch"]
    return SVG_ICONS["build"]

def _get_feature_icon(title):
    """Pick SVG icon for feature/differentiator."""
    n = title.lower()
    if any(k in n for k in ["fast","quick","speed","time","deliver","deadline"]): return SVG_ICONS["fast"]
    if any(k in n for k in ["support","help","available","communicat","team"]): return SVG_ICONS["support"]
    if any(k in n for k in ["quality","test","review","standard","guarantee"]): return SVG_ICONS["quality"]
    if any(k in n for k in ["secure","safe","protect","ip","nda","privacy","data"]): return SVG_ICONS["shield"]
    if any(k in n for k in ["consult","expert","experience","proven","skill"]): return SVG_ICONS["consulting"]
    if any(k in n for k in ["analy","insight","data","report","metric"]): return SVG_ICONS["analytics"]
    return SVG_ICONS["default"]

# Unsplash photo URLs — real photos, categorized by business type keyword
# ── Photo library — wide variety per category ────────────────────────────────
_PHOTO_LIBRARY = {
    "software":   [
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600&q=80",
        "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&q=80",
        "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&q=80",
        "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=600&q=80",
        "https://images.unsplash.com/photo-1571171637578-41bc2dd41cd2?w=600&q=80",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=600&q=80",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=600&q=80",
        "https://images.unsplash.com/photo-1504639725590-34d0984388bd?w=600&q=80",
    ],
    "design":     [
        "https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=600&q=80",
        "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=600&q=80",
        "https://images.unsplash.com/photo-1559136555-9303baea8ebd?w=600&q=80",
        "https://images.unsplash.com/photo-1572021335469-31706a17aaef?w=600&q=80",
        "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&q=80",
        "https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=600&q=80",
        "https://images.unsplash.com/photo-1609921212029-bb5a28e60960?w=600&q=80",
        "https://images.unsplash.com/photo-1636633762833-5d1658f1e29b?w=600&q=80",
    ],
    "consulting": [
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&q=80",
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=600&q=80",
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=600&q=80",
        "https://images.unsplash.com/photo-1551836022-4c4c79ecde51?w=600&q=80",
        "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=600&q=80",
        "https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?w=600&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=600&q=80",
    ],
    "health":     [
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&q=80",
        "https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=600&q=80",
        "https://images.unsplash.com/photo-1551601651-2a8555f1a136?w=600&q=80",
        "https://images.unsplash.com/photo-1584432810601-6c7f27d2362b?w=600&q=80",
        "https://images.unsplash.com/photo-1530026405186-ed1f139313f8?w=600&q=80",
        "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=600&q=80",
        "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=600&q=80",
        "https://images.unsplash.com/photo-1666214280557-f1b5022eb634?w=600&q=80",
    ],
    "education":  [
        "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=600&q=80",
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=600&q=80",
        "https://images.unsplash.com/photo-1546410531-bb4caa6b424d?w=600&q=80",
        "https://images.unsplash.com/photo-1427504494785-3a9ca7044f45?w=600&q=80",
        "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=600&q=80",
        "https://images.unsplash.com/photo-1581726707445-75cbe4efc586?w=600&q=80",
        "https://images.unsplash.com/photo-1488190211105-8b0e65b80b4e?w=600&q=80",
        "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=600&q=80",
    ],
    "finance":    [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&q=80",
        "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?w=600&q=80",
        "https://images.unsplash.com/photo-1565514020179-026b92b2d70b?w=600&q=80",
        "https://images.unsplash.com/photo-1559526324-593bc073d938?w=600&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&q=80",
        "https://images.unsplash.com/photo-1638913662252-70efce1e60a7?w=600&q=80",
        "https://images.unsplash.com/photo-1604594849809-dfedbc827105?w=600&q=80",
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&q=80",
    ],
    "food":       [
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600&q=80",
        "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80",
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&q=80",
        "https://images.unsplash.com/photo-1466978913421-dad2ebd01d17?w=600&q=80",
        "https://images.unsplash.com/photo-1567529692333-de9fd6772897?w=600&q=80",
        "https://images.unsplash.com/photo-1600891964092-4316c288032e?w=600&q=80",
        "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?w=600&q=80",
    ],
    "fitness":    [
        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80",
        "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&q=80",
        "https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=600&q=80",
        "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600&q=80",
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=600&q=80",
        "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?w=600&q=80",
        "https://images.unsplash.com/photo-1576678927484-cc907957088c?w=600&q=80",
        "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=600&q=80",
    ],
    "retail":     [
        "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600&q=80",
        "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=600&q=80",
        "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=600&q=80",
        "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=600&q=80",
        "https://images.unsplash.com/photo-1582719471384-894fbb16e074?w=600&q=80",
        "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&q=80",
        "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&q=80",
        "https://images.unsplash.com/photo-1612817288484-6f916006741a?w=600&q=80",
    ],
    "travel":     [
        "https://images.unsplash.com/photo-1488085061387-422e29b40080?w=600&q=80",
        "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=600&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&q=80",
        "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=600&q=80",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600&q=80",
        "https://images.unsplash.com/photo-1530521954074-e64f6810b32d?w=600&q=80",
        "https://images.unsplash.com/photo-1501555088652-021faa106b9b?w=600&q=80",
        "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=600&q=80",
    ],
    "real_estate":[
        "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=600&q=80",
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600&q=80",
        "https://images.unsplash.com/photo-1582407947304-fd86f028f716?w=600&q=80",
        "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=600&q=80",
        "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=600&q=80",
        "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=600&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600&q=80",
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&q=80",
    ],
    "beauty":     [
        "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600&q=80",
        "https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=600&q=80",
        "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=600&q=80",
        "https://images.unsplash.com/photo-1519415943484-9fa1873496d4?w=600&q=80",
        "https://images.unsplash.com/photo-1571646034647-52e6ea84b28c?w=600&q=80",
        "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&q=80",
        "https://images.unsplash.com/photo-1512207736890-6ffed8a84e8d?w=600&q=80",
        "https://images.unsplash.com/photo-1543148297-1792051dbbe0?w=600&q=80",
    ],
    "default":    [
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600&q=80",
        "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=600&q=80",
        "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&q=80",
        "https://images.unsplash.com/photo-1551836022-4c4c79ecde51?w=600&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=600&q=80",
        "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=600&q=80",
        "https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?w=600&q=80",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&q=80",
    ],
}

_HERO_LIBRARY = {
    "ai":         [
        "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=800&q=80",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80",
        "https://images.unsplash.com/photo-1531746790731-6c087fecd65a?w=800&q=80",
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800&q=80",
    ],
    "software":   [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=800&q=80",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&q=80",
        "https://images.unsplash.com/photo-1504639725590-34d0984388bd?w=800&q=80",
        "https://images.unsplash.com/photo-1571171637578-41bc2dd41cd2?w=800&q=80",
    ],
    "design":     [
        "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=800&q=80",
        "https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=800&q=80",
        "https://images.unsplash.com/photo-1636633762833-5d1658f1e29b?w=800&q=80",
        "https://images.unsplash.com/photo-1609921212029-bb5a28e60960?w=800&q=80",
    ],
    "consulting": [
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=800&q=80",
        "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=800&q=80",
        "https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?w=800&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
    ],
    "health":     [
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800&q=80",
        "https://images.unsplash.com/photo-1530521954074-e64f6810b32d?w=800&q=80",
        "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=800&q=80",
        "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=800&q=80",
    ],
    "education":  [
        "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&q=80",
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800&q=80",
        "https://images.unsplash.com/photo-1581726707445-75cbe4efc586?w=800&q=80",
        "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=800&q=80",
    ],
    "finance":    [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&q=80",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&q=80",
        "https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?w=800&q=80",
        "https://images.unsplash.com/photo-1565514020179-026b92b2d70b?w=800&q=80",
    ],
    "food":       [
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&q=80",
        "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&q=80",
        "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?w=800&q=80",
    ],
    "fitness":    [
        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800&q=80",
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800&q=80",
        "https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=800&q=80",
        "https://images.unsplash.com/photo-1576678927484-cc907957088c?w=800&q=80",
    ],
    "retail":     [
        "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800&q=80",
        "https://images.unsplash.com/photo-1472851294608-062f824d29cc?w=800&q=80",
        "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=800&q=80",
        "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800&q=80",
    ],
    "travel":     [
        "https://images.unsplash.com/photo-1488085061387-422e29b40080?w=800&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80",
        "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&q=80",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=800&q=80",
    ],
    "real_estate":[
        "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&q=80",
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800&q=80",
        "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
    ],
    "beauty":     [
        "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=800&q=80",
        "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800&q=80",
        "https://images.unsplash.com/photo-1487412912498-0447578fcca8?w=800&q=80",
        "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800&q=80",
    ],
    "default":    [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&q=80",
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&q=80",
        "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=800&q=80",
        "https://images.unsplash.com/photo-1521791136064-7986c2920216?w=800&q=80",
    ],
}

def _detect_photo_category(idea_keywords: str) -> str:
    """Map idea keywords to a photo category. Specific checks first, generic last."""
    k = idea_keywords.lower()

    # ── Very specific categories first ────────────────────────────────────────
    if any(w in k for w in ["real estate","property","house","home listing","apartment","rent","lease","realtor","landlord","construction site"]):
        return "real_estate"
    if any(w in k for w in ["beauty","salon","hair salon","makeup","cosmetic","skincare","nail","barber","grooming","lash","brow","waxing","facial"]):
        return "beauty"
    if any(w in k for w in ["restaurant","cafe","coffee shop","bakery","catering","meal plan","recipe","chef","cuisine","food delivery","dining","snack","beverage","bar","eatery","bistro","pizz","sushi","burger"]):
        return "food"
    if any(w in k for w in ["travel","tourism","hotel","hostel","airbnb","holiday","vacation","trip","adventure tour","destination","flight","cruise","resort","safari"]):
        return "travel"
    if any(w in k for w in ["fashion","clothing","apparel","jewel","accessory","merchandise","outfit","wear","garment","shoe","bag","luxury good"]):
        return "retail"
    if any(w in k for w in ["gym","crossfit","pilates","fitness","workout","personal train","athletic","sport","running club","cycling","weightlift","martial art","dance studio","swim"]):
        return "fitness"
    if any(w in k for w in ["clinic","hospital","doctor","dental","pharma","therapy","therapist","mental health","wellness","wellness center","meditation","yoga studio","yoga class","yoga","spa retreat","rehab","physio","chiropract"]):
        return "health"
    if any(w in k for w in ["school","university","tutoring","e-learning","online course","teaching","tutor","classroom","lesson","academy","edtech","training institute","student"]):
        return "education"
    if any(w in k for w in ["invest","trading","hedge fund","crypto","payment gateway","loan","mortgage","insurance","accounting","tax","wealth management","fintech","bank"]):
        return "finance"

    # ── Broader / overlapping checks ──────────────────────────────────────────
    if any(w in k for w in ["artificial intelligence","machine learning","deep learning","neural network","llm","gpt","chatbot","ai-powered","intelligent automat"]):
        return "ai"
    if any(w in k for w in ["graphic design","ui design","ux design","brand design","creative agency","visual identity","motion graphic","illustration studio"]):
        return "design"
    if any(w in k for w in ["coaching","life coach","business coach","executive coach","mentor","personal development"]):
        return "consulting"
    if any(w in k for w in ["online shop","ecommerce","marketplace","sell product","retail store"]):
        return "retail"
    if any(w in k for w in ["health","medical","wellness","pharma"]):
        return "health"
    if any(w in k for w in ["finance","financial"]):
        return "finance"
    if any(w in k for w in ["learn","course","educat"]):
        return "education"
    if any(w in k for w in ["food","meal","kitchen"]):
        return "food"

    # ── Generic tech / software (most common, check last) ─────────────────────
    if any(w in k for w in ["software","saas","web app","mobile app","platform","api","devops","cloud infra","database","it solution","develop","coding","tech startup"]):
        return "software"
    if any(w in k for w in ["consult","strategy","advisory","management consulting"]):
        return "consulting"
    if any(w in k for w in ["design","creative","agency","brand"]):
        return "design"
    if any(w in k for w in ["tech","app","digital"]):
        return "software"
    return "default"

def _get_about_photos(name, idea_keywords=""):
    """Return 4 varied photo URLs based on business category. Uses a wide library."""
    import hashlib
    category = _detect_photo_category(idea_keywords)
    # For "ai" fall back to software photos
    pool_key = "software" if category == "ai" else category
    if pool_key not in _PHOTO_LIBRARY:
        pool_key = "default"
    pool = _PHOTO_LIBRARY[pool_key]
    # Use business name as seed so same business always gets same photos
    # but different businesses get different photos from the pool
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    indices = [(seed + i * 3) % len(pool) for i in range(4)]
    # Ensure no duplicates
    seen = set()
    result = []
    for idx in indices:
        while idx in seen:
            idx = (idx + 1) % len(pool)
        seen.add(idx)
        result.append(pool[idx])
    return result

def _get_hero_image(idea_keywords="", seed_name=""):
    """Return a random hero image URL from the category pool — different each time."""
    import hashlib as _hl
    category = _detect_photo_category(idea_keywords)
    pool_key = "software" if category == "ai" else category
    pool = _HERO_LIBRARY.get(pool_key, _HERO_LIBRARY["default"])
    # Use seed_name (business name) for consistent but varied selection
    seed = int(_hl.md5((seed_name + idea_keywords[:20]).encode()).hexdigest()[:8], 16)
    return pool[seed % len(pool)]



# ══════════════════════════════════════════════════════════════════════════════
# SAAS SITE BUILDER — 6 completely distinct style layouts
# Each style has different: colors, fonts, hero layout, card style, spacing
# ══════════════════════════════════════════════════════════════════════════════

SVG_ICONS = {
    "web":       '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    "mobile":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>',
    "ai":        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1l2.1-2.1M17 7l2.1-2.1"/></svg>',
    "cloud":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>',
    "design":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>',
    "security":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    "analytics": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "consulting":'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "default":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    "health":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    "finance":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    "education": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
    "startup":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    "check":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
    "arrow":     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    "fast":      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    "support":   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "shield":    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
}

def _svc_icon(name):
    n = name.lower()
    if any(k in n for k in ["web","site","frontend","react","next"]): return SVG_ICONS["web"]
    if any(k in n for k in ["mobile","app","ios","android","flutter"]): return SVG_ICONS["mobile"]
    if any(k in n for k in ["ai","machine","ml","intelligence","automat"]): return SVG_ICONS["ai"]
    if any(k in n for k in ["cloud","aws","azure","devops","infra"]): return SVG_ICONS["cloud"]
    if any(k in n for k in ["design","ui","ux","brand","visual"]): return SVG_ICONS["design"]
    if any(k in n for k in ["security","cyber","secure","compliance"]): return SVG_ICONS["security"]
    if any(k in n for k in ["data","analytics","bi","report","insight"]): return SVG_ICONS["analytics"]
    if any(k in n for k in ["consult","strategy","advisory"]): return SVG_ICONS["consulting"]
    if any(k in n for k in ["health","medical","care","pharma"]): return SVG_ICONS["health"]
    if any(k in n for k in ["finance","fintech","bank","payment"]): return SVG_ICONS["finance"]
    return SVG_ICONS["default"]

def _ind_icon(name):
    n = name.lower()
    if any(k in n for k in ["health","medical"]): return SVG_ICONS["health"]
    if any(k in n for k in ["finance","fintech","bank"]): return SVG_ICONS["finance"]
    if any(k in n for k in ["edu","school","learn"]): return SVG_ICONS["education"]
    if any(k in n for k in ["start","early","seed"]): return SVG_ICONS["startup"]
    return SVG_ICONS["default"]

def _feat_icon(title):
    n = title.lower()
    if any(k in n for k in ["fast","quick","speed","time"]): return SVG_ICONS["fast"]
    if any(k in n for k in ["support","help","communicat"]): return SVG_ICONS["support"]
    if any(k in n for k in ["secure","safe","protect","ip"]): return SVG_ICONS["shield"]
    if any(k in n for k in ["quality","test","guarantee"]): return SVG_ICONS["check"]
    return SVG_ICONS["default"]

def _photos(idea):
    k = idea.lower()
    if any(w in k for w in ["software","tech","develop","code","it","app","web"]):
        return [
            "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600&q=80",
            "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&q=80",
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&q=80",
            "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=600&q=80",
        ]
    elif any(w in k for w in ["design","creative","brand","market"]):
        return [
            "https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=600&q=80",
            "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=600&q=80",
            "https://images.unsplash.com/photo-1559136555-9303baea8ebd?w=600&q=80",
            "https://images.unsplash.com/photo-1572021335469-31706a17aaef?w=600&q=80",
        ]
    elif any(w in k for w in ["consult","strategy","finance","legal","business"]):
        return [
            "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&q=80",
            "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=600&q=80",
            "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=600&q=80",
            "https://images.unsplash.com/photo-1551836022-4c4c79ecde51?w=600&q=80",
        ]
    else:
        return [
            "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600&q=80",
            "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=600&q=80",
            "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&q=80",
            "https://images.unsplash.com/photo-1551836022-4c4c79ecde51?w=600&q=80",
        ]


def _build_saas_site(name, c, style="bold"):
    h     = c.get("hero", {})
    ab    = c.get("about", {})
    ct    = c.get("contact", {})
    tg    = c.get("tagline", "")
    an    = c.get("announcement_bar", "")
    feats = c.get("features", [])
    stats = c.get("stats", [])
    testis= c.get("testimonials", [])
    svcs  = c.get("services", [])
    cats  = c.get("categories", [])
    procs = c.get("process_steps", [])
    posts = c.get("blog_posts", [])
    faqs  = c.get("faq", [])

    idea_text = tg + " " + h.get("subtitle","") + " " + ab.get("mission","")
    # Use the full dynamic photo library (13 categories, 8 photos each)
    photos   = _get_about_photos(name, idea_text)
    hero_img = _get_hero_image(idea_text, name)

    # Route to correct style builder
    builders = {
        "bold":      _saas_bold,
        "elegant":   _saas_elegant,
        "minimal":   _saas_minimal,
        "dark":      _saas_dark,
        "playful":   _saas_playful,
        "corporate": _saas_corporate,
    }
    fn = builders.get(style, _saas_bold)
    return fn(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img)


# ── Shared page JS ────────────────────────────────────────────────────────────
_PAGE_JS = """<script>
function showSection(id){
  document.querySelectorAll('.psec').forEach(s=>s.classList.remove('visible'));
  var sec=document.getElementById('sec-'+id);
  if(sec) sec.classList.add('visible');
  window.scrollTo({top:0,behavior:'smooth'});
}
document.addEventListener('DOMContentLoaded',function(){showSection('home');});
</script>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 1 — BOLD  (high-contrast, chunky, startup energy)
# Colors: deep navy + electric blue accent, big type
# ══════════════════════════════════════════════════════════════════════════════
def _saas_bold(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    cs = c.get("color_scheme", {})
    p  = cs.get("primary",   "#2563EB")
    s  = cs.get("secondary", "#1D4ED8")
    a  = cs.get("accent",    "#F59E0B")

    svc_cards = ""
    for sv in svcs:
        badge = f'<span style="position:absolute;top:1rem;right:1rem;background:{a};color:#000;font-size:.62rem;font-weight:800;padding:.2rem .6rem;border-radius:4px;text-transform:uppercase">{sv.get("badge","")}</span>' if sv.get("badge") else ""
        ico = _svc_icon(sv.get("name",""))
        stars = "★" * int(sv.get("rating",4.8)) + "☆" * (5 - int(sv.get("rating",4.8)))
        svc_cards += f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:8px;padding:2rem;position:relative;border-top:4px solid {p};transition:all .2s" onmouseover="this.style.transform=\'translateY(-4px)\';this.style.boxShadow=\'8px 8px 0 {p}20\'" onmouseout="this.style.transform=\'\';this.style.boxShadow=\'\'">{badge}<div style="width:48px;height:48px;border:2px solid {p};border-radius:8px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin-bottom:1rem">{ico}</div><h3 style="font-size:1.05rem;font-weight:800;color:#0F172A;margin-bottom:.5rem">{sv.get("name","")}</h3><p style="font-size:.84rem;color:#64748B;line-height:1.6;margin-bottom:1rem;min-height:56px">{sv.get("description","")}</p><div style="font-size:.75rem;color:#94A3B8;margin-bottom:1rem">{stars} {sv.get("reviews",0)} reviews</div><button onclick="showSection(\'contact\')" style="width:100%;padding:.7rem;background:{p};color:#fff;border:none;border-radius:6px;font-weight:700;font-size:.85rem;cursor:pointer;font-family:inherit;transition:background .2s" onmouseover="this.style.background=\'{s}\'" onmouseout="this.style.background=\'{p}\'">Talk to Us →</button></div>'

    feat_html = ""
    for f in feats:
        ico = _feat_icon(f.get("title",""))
        feat_html += f'<div style="display:flex;gap:1rem;align-items:flex-start"><div style="width:44px;height:44px;border:2px solid {p};border-radius:8px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{ico}</div><div><h4 style="font-weight:800;font-size:.95rem;color:#0F172A;margin-bottom:.25rem">{f.get("title","")}</h4><p style="font-size:.84rem;color:#64748B;line-height:1.6">{f.get("desc","")}</p></div></div>'

    stats_html = "".join(f'<div style="text-align:center"><div style="font-size:3rem;font-weight:900;color:{a};line-height:1">{st.get("number","")}</div><div style="font-size:.8rem;color:#fff;margin-top:.3rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em">{st.get("label","")}</div></div>' for st in stats)

    testi_html = ""
    for ti in testis:
        stars = "★" * int(ti.get("rating",5))
        testi_html += f'<div style="background:#fff;border-left:4px solid {p};border-radius:0 8px 8px 0;padding:1.75rem"><div style="color:{a};font-size:1rem;margin-bottom:.75rem">{stars}</div><p style="font-size:.92rem;color:#1E293B;line-height:1.7;font-weight:500;margin-bottom:1rem">"{ti.get("text","")}"</p><div style="font-weight:800;font-size:.85rem;color:#0F172A">{ti.get("name","")}</div><div style="font-size:.75rem;color:#64748B">{ti.get("location","")}</div></div>'

    blog_html = ""
    for i, post in enumerate(posts):
        _bg = f"linear-gradient(135deg,{p},{s})" if i%2==0 else f"linear-gradient(135deg,{s},{a})"
        _cat, _title, _exc, _date = post.get("category",""), post.get("title",""), post.get("excerpt",""), post.get("date","")
        blog_html += (f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;cursor:pointer" onclick="alert(chr(39)Coming soon!chr(39))">'
            + f'<div style="height:120px;background:{_bg};display:flex;align-items:flex-end;padding:.85rem">'
            + f'<span style="background:rgba(0,0,0,.3);color:#fff;font-size:.68rem;font-weight:700;padding:.2rem .55rem;border-radius:4px;text-transform:uppercase">{_cat}</span></div>'
            + f'<div style="padding:1.25rem"><div style="font-weight:800;font-size:.95rem;color:#0F172A;margin-bottom:.4rem">{_title}</div>'
            + f'<div style="font-size:.78rem;color:#64748B;line-height:1.5;margin-bottom:.6rem">{_exc}</div>'
            + f'<div style="font-size:.72rem;color:#94A3B8">{_date}</div></div></div>')

    ind_html = ""
    for cat in cats:
        ico = _ind_icon(cat.get("name",""))
        ind_html += f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:8px;padding:1.5rem;text-align:center;cursor:pointer;transition:all .2s;border-bottom:3px solid transparent" onmouseover="this.style.borderBottomColor=\'{p}\';this.style.boxShadow=\'4px 4px 0 {p}20\'" onmouseout="this.style.borderBottomColor=\'transparent\';this.style.boxShadow=\'\'"><div style="width:48px;height:48px;border:2px solid {p}30;border-radius:8px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin:0 auto .65rem">{ico}</div><div style="font-weight:800;font-size:.88rem;color:#0F172A;margin-bottom:.2rem">{cat.get("name","")}</div><div style="font-size:.74rem;color:#94A3B8">{cat.get("count","")}</div></div>'

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="border-bottom:2px solid #E5E7EB;padding:1.1rem 0"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-weight:800;font-size:.92rem;color:#0F172A"><span>{fq.get("question","")}</span><span style="color:{p};font-size:1.2rem;font-weight:400">+</span></div><div style="display:none;padding:.65rem 0 0;font-size:.875rem;color:#64748B;line-height:1.7">{fq.get("answer","")}</div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    vals_html = "".join(f'<span style="display:inline-block;background:{p};color:#fff;border-radius:4px;padding:.25rem .8rem;font-size:.8rem;font-weight:700;margin:.25rem;text-transform:uppercase;letter-spacing:.04em">{v}</span>' for v in ab.get("values",[]))

    proc_html = ""
    for i, pr in enumerate(procs):
        _conn = (f'<div style="flex:1;height:2px;background:{p};opacity:.2;margin-top:28px;min-width:20px"></div>' if i < len(procs)-1 else "")
        _st = pr.get("step","01"); _ti = pr.get("title",""); _de = pr.get("desc","")
        proc_html += (
            f'<div style="flex:1;min-width:150px;text-align:center">'
            f'<div style="width:56px;height:56px;background:{p};border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;font-weight:900;color:#fff;margin:0 auto 1rem">{_st}</div>'
            f'<h4 style="font-weight:800;font-size:.95rem;color:#0F172A;margin-bottom:.4rem">{_ti}</h4>'
            f'<p style="font-size:.82rem;color:#64748B;line-height:1.6;max-width:160px;margin:0 auto">{_de}</p>'
            f'</div>{_conn}')

    # Pre-built footer nav links (avoids backslash in nested f-string)
    _svc_li = []
    for sv in svcs[:5]:
        _sn = sv.get("name","")
        _svc_li.append(f'<li style="margin-bottom:.45rem"><a style="font-size:.8rem;color:rgba(255,255,255,.45);cursor:pointer;text-decoration:none">{_sn}</a></li>')
    _ft_svc_links = "".join(_svc_li)
    _co_li = []
    for _pg_id, _pg_nm in [("about","About Us"),("blog","Blog"),("reviews","Reviews"),("contact","Contact")]:
        _co_li.append(f'<li style="margin-bottom:.45rem"><a style="font-size:.8rem;color:rgba(255,255,255,.45);cursor:pointer;text-decoration:none">{_pg_nm}</a></li>')
    _ft_co_links = "".join(_co_li)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Inter',sans-serif;background:#F8FAFC;color:#0F172A;line-height:1.6;-webkit-font-smoothing:antialiased}}
.ann{{background:{p};color:#fff;text-align:center;padding:.5rem;font-size:.82rem;font-weight:600}}
.nav{{background:#fff;border-bottom:3px solid {p};height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300}}
.nav-brand{{font-size:1.3rem;font-weight:900;color:{p};letter-spacing:-.04em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.875rem;font-weight:700;color:#334155;cursor:pointer;text-decoration:none;text-transform:uppercase;letter-spacing:.04em;transition:color .15s}}
.nav-links a:hover{{color:{p}}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1140px;margin:0 auto}}
.g3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.5rem}}
.g4{{display:grid;grid-template-columns:repeat(auto-fill,minmax(195px,1fr));gap:1rem}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:3rem;align-items:center}}
.kicker{{font-size:.72rem;font-weight:900;color:{p};text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem}}
.h2{{font-size:clamp(1.8rem,3vw,2.5rem);font-weight:900;color:#0F172A;letter-spacing:-.04em;line-height:1.1;margin-bottom:.7rem}}
.sub{{color:#64748B;font-size:.92rem;line-height:1.75;max-width:540px}}
.btn-p{{background:{p};color:#fff;border:none;padding:.85rem 2rem;border-radius:6px;font-weight:800;font-size:.9rem;cursor:pointer;font-family:inherit;transition:background .2s;text-transform:uppercase;letter-spacing:.04em}}
.btn-p:hover{{background:{s}}}
.btn-o{{background:transparent;color:{p};border:2px solid {p};padding:.85rem 2rem;border-radius:6px;font-weight:800;font-size:.9rem;cursor:pointer;font-family:inherit;transition:all .2s;text-transform:uppercase;letter-spacing:.04em}}
.btn-o:hover{{background:{p};color:#fff}}
img{{max-width:100%;object-fit:cover}}
footer{{background:#0F172A;padding:4rem 5% 2rem;color:rgba(255,255,255,.5)}}
@media(max-width:768px){{.g2{{grid-template-columns:1fr}}.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand">{name}</div>
  <ul class="nav-links">
    <li><a onclick="showSection('home')">Home</a></li>
    <li><a onclick="showSection('about')">About</a></li>
    <li><a onclick="showSection('services')">Services</a></li>
    <li><a onclick="showSection('blog')">Blog</a></li>
    <li><a onclick="showSection('contact')">Contact</a></li>
  </ul>
  <div style="display:flex;gap:.75rem">
    <button class="btn-o" onclick="showSection('contact')">Book a Call</button>
    <button class="btn-p" onclick="showSection('contact')">{h.get("cta_primary","Get Started")}</button>
  </div>
</nav>

<div class="psec visible" id="sec-home">
<!-- HERO -->
<section style="background:#0F172A;padding:6rem 5%;min-height:85vh;display:flex;align-items:center;gap:4rem">
  <div style="flex:1;max-width:580px">
    <div style="display:inline-flex;align-items:center;gap:.5rem;border:2px solid {a};color:{a};padding:.3rem 1rem;border-radius:4px;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;margin-bottom:1.5rem">&bull; {h.get("badge","Trusted by 200+ clients")}</div>
    <h1 style="font-size:clamp(2.8rem,5vw,4.5rem);font-weight:900;line-height:1.05;letter-spacing:-.05em;color:#fff;margin-bottom:1.25rem">{h.get("title",name)}</h1>
    <p style="font-size:1rem;color:rgba(255,255,255,.65);margin-bottom:2.5rem;max-width:460px;line-height:1.75">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
      <button class="btn-p" onclick="showSection('contact')">{h.get("cta_primary","Get Started")} →</button>
      <button onclick="showSection('services')" style="background:transparent;color:#fff;border:2px solid rgba(255,255,255,.3);padding:.85rem 2rem;border-radius:6px;font-weight:800;font-size:.9rem;cursor:pointer;font-family:inherit;transition:all .2s;text-transform:uppercase;letter-spacing:.04em" onmouseover="this.style.borderColor='rgba(255,255,255,.8)'" onmouseout="this.style.borderColor='rgba(255,255,255,.3)'">{h.get("cta_secondary","Our Work")}</button>
    </div>
  </div>
  <div style="flex:1;max-width:440px">
    <img src="{hero_img or photos[0]}" style="width:100%;height:280px;border-radius:8px;border:3px solid {p}" alt="Team"/>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem">
      {"".join(f'<div style="background:#1E293B;border:1px solid #334155;border-left:3px solid {p};border-radius:6px;padding:1rem"><div style="font-size:.72rem;font-weight:800;color:{p};text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem">{sv.get("name","")[:18]}</div><div style="font-size:.78rem;color:rgba(255,255,255,.55)">{sv.get("description","")[:40]}...</div></div>' for sv in svcs[:4])}
    </div>
  </div>
</section>
<!-- SERVICES PREVIEW -->
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap">
    <div class="kicker">What We Offer</div><h2 class="h2">Solutions &amp; Focus Areas</h2>
    <p class="sub" style="margin-bottom:2.5rem">{tg}</p>
    <div class="g3">{svc_cards}</div>
  </div>
</section>
<!-- INDUSTRIES -->
<section style="background:#F8FAFC;padding:5rem 5%">
  <div class="wrap"><div class="kicker">Industries</div><h2 class="h2" style="margin-bottom:2.5rem">Who We Serve</h2>
  <div class="g4">{ind_html}</div></div>
</section>
<!-- STATS + WHY US -->
<section style="background:#0F172A;padding:5rem 5%">
  <div class="wrap g2" style="gap:5rem">
    <div>
      <div class="kicker" style="color:{a}">Why Choose Us</div>
      <h2 style="font-size:clamp(1.8rem,3vw,2.4rem);font-weight:900;color:#fff;letter-spacing:-.04em;margin-bottom:1rem">{ab.get("mission","")}</h2>
      <div style="display:flex;flex-direction:column;gap:1.25rem;margin-top:1.5rem">{feat_html}</div>
    </div>
    <div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#334155;border-radius:8px;overflow:hidden;margin-bottom:1.5rem">{stats_html}</div>
      <div style="background:#1E293B;border:1px solid #334155;border-radius:8px;padding:1.5rem;text-align:center">
        <div style="font-weight:800;color:#fff;margin-bottom:.5rem">Ready to start?</div>
        <p style="font-size:.84rem;color:rgba(255,255,255,.55);margin-bottom:1.25rem">Free discovery call, no commitment.</p>
        <button class="btn-p" onclick="showSection('contact')">Book Free Call →</button>
      </div>
    </div>
  </div>
</section>
<!-- PROCESS -->
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap"><div class="kicker">How It Works</div><h2 class="h2" style="margin-bottom:3rem">Our Process</h2>
  <div style="display:flex;align-items:flex-start;flex-wrap:wrap;gap:0;justify-content:center;max-width:960px;margin:0 auto">{proc_html}</div></div>
</section>
<!-- TESTIMONIALS -->
<section style="background:#F8FAFC;padding:5rem 5%">
  <div class="wrap"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2.5rem;flex-wrap:wrap;gap:1rem"><div><div class="kicker">Client Stories</div><h2 class="h2" style="margin-bottom:0">What Clients Say</h2></div><button class="btn-o" onclick="showSection('reviews')">All Reviews →</button></div>
  <div class="g3">{testi_html}</div></div>
</section>
<!-- BLOG -->
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2.5rem;flex-wrap:wrap;gap:1rem"><div><div class="kicker">Insights</div><h2 class="h2" style="margin-bottom:0">Latest Articles</h2></div><button class="btn-o" onclick="showSection('blog')">View All →</button></div>
  <div class="g3">{blog_html}</div></div>
</section>
</div>

<!-- ABOUT -->
<div class="psec" id="sec-about">
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap g2">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
      <img src="{photos[0]}" style="width:100%;height:210px;border-radius:8px" alt="Team"/>
      <img src="{photos[1]}" style="width:100%;height:210px;border-radius:8px;margin-top:1.5rem" alt="Office"/>
      <img src="{photos[2]}" style="width:100%;height:210px;border-radius:8px" alt="Work"/>
      <img src="{photos[3]}" style="width:100%;height:210px;border-radius:8px;margin-top:-1.5rem" alt="Collab"/>
    </div>
    <div>
      <div class="kicker">Our Story</div><h2 class="h2">{ab.get("title","About Us")}</h2>
      <p style="font-size:1rem;color:{p};font-weight:700;border-left:4px solid {p};padding-left:1rem;margin-bottom:1.25rem;line-height:1.6">{ab.get("mission","")}</p>
      <p style="color:#64748B;line-height:1.85;font-size:.9rem;margin-bottom:1.5rem">{ab.get("story","")}</p>
      <div style="margin-bottom:1.75rem">{vals_html}</div>
      <button class="btn-p" onclick="showSection('contact')">Work With Us →</button>
    </div>
  </div>
</section>
</div>

<!-- SERVICES -->
<div class="psec" id="sec-services">
<section style="background:#F8FAFC;padding:5rem 5%">
  <div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:3rem">What We Offer</h2>
  <div class="g3">{svc_cards}</div></div>
</section>
</div>

<!-- REVIEWS -->
<div class="psec" id="sec-reviews">
<section style="background:#F8FAFC;padding:5rem 5%">
  <div class="wrap"><div class="kicker">Reviews</div><h2 class="h2" style="margin-bottom:3rem">Client Stories</h2>
  <div class="g3">{testi_html}</div></div>
</section>
</div>

<!-- BLOG -->
<div class="psec" id="sec-blog">
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap"><div class="kicker">Blog</div><h2 class="h2" style="margin-bottom:3rem">News &amp; Articles</h2>
  <div class="g3">{blog_html}</div></div>
</section>
<section style="background:#F8FAFC;padding:4rem 5%">
  <div class="wrap"><div class="kicker">FAQ</div><h2 class="h2" style="margin-bottom:2rem">Common Questions</h2>
  <div style="max-width:720px;margin:0 auto">{faq_html}</div></div>
</section>
</div>

<!-- CONTACT -->
<div class="psec" id="sec-contact">
<section style="background:#fff;padding:5rem 5%">
  <div class="wrap"><div class="kicker">Contact</div><h2 class="h2" style="margin-bottom:.5rem">Book Free Consultation</h2>
  <p class="sub" style="margin-bottom:3rem">We respond within 24 hours.</p>
  <div class="g2" style="align-items:start;gap:4rem">
    <div>
      <img src="{photos[1]}" style="width:100%;height:200px;border-radius:8px;margin-bottom:1.5rem" alt="Office"/>
      <div style="display:flex;flex-direction:column;gap:1rem">
        <div style="display:flex;gap:.75rem;align-items:center"><div style="width:40px;height:40px;border:2px solid {p};border-radius:6px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["support"]}</div><div><strong style="font-size:.88rem">{ct.get("email","hello@brand.com")}</strong></div></div>
        <div style="display:flex;gap:.75rem;align-items:center"><div style="width:40px;height:40px;border:2px solid {p};border-radius:6px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["fast"]}</div><div><strong style="font-size:.88rem">{ct.get("phone","+1 555 000 0000")}</strong></div></div>
        <div style="display:flex;gap:.75rem;align-items:center"><div style="width:40px;height:40px;border:2px solid {p};border-radius:6px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["default"]}</div><div><strong style="font-size:.88rem">{ct.get("address","123 Business Street")}</strong></div></div>
      </div>
    </div>
    <div style="background:#F8FAFC;border:2px solid #E2E8F0;border-radius:8px;padding:2.5rem">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
        <div><label style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.35rem">First Name</label><input type="text" placeholder="John" style="width:100%;padding:.75rem;border:2px solid #E2E8F0;border-radius:6px;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#E2E8F0'"/></div>
        <div><label style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.35rem">Last Name</label><input type="text" placeholder="Smith" style="width:100%;padding:.75rem;border:2px solid #E2E8F0;border-radius:6px;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#E2E8F0'"/></div>
      </div>
      <div style="margin-bottom:1rem"><label style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.35rem">Email</label><input type="email" placeholder="john@company.com" style="width:100%;padding:.75rem;border:2px solid #E2E8F0;border-radius:6px;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#E2E8F0'"/></div>
      <div style="margin-bottom:1rem"><label style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.35rem">Service</label><select style="width:100%;padding:.75rem;border:2px solid #E2E8F0;border-radius:6px;font-family:inherit;font-size:.88rem;outline:none;background:#fff"><option value="">Select service</option>{svc_options}</select></div>
      <div style="margin-bottom:1.5rem"><label style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.35rem">Message</label><textarea placeholder="Tell us about your project..." style="width:100%;padding:.75rem;border:2px solid #E2E8F0;border-radius:6px;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#E2E8F0'"></textarea></div>
      <button class="btn-p" style="width:100%;padding:.9rem" onclick="alert('Submitted! We will contact you within 24 hours.')">Submit Request →</button>
    </div>
  </div></div>
</section>
</div>

<footer>
  <div style="max-width:1140px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr;gap:3rem;margin-bottom:2.5rem">
    <div><div style="font-size:1.3rem;font-weight:900;color:#fff;margin-bottom:.5rem">{name}</div><p style="font-size:.82rem;color:rgba(255,255,255,.4);line-height:1.7;max-width:220px">{tg}</p></div>
    <div><h4 style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:rgba(255,255,255,.35);margin-bottom:1rem">Services</h4><ul style="list-style:none">{_ft_svc_links}</ul></div>
    <div><h4 style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:rgba(255,255,255,.35);margin-bottom:1rem">Company</h4><ul style="list-style:none">{_ft_co_links}</ul></div>
  </div>
  <div style="max-width:1140px;margin:0 auto;border-top:1px solid rgba(255,255,255,.08);padding-top:1.5rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem">
    <span style="font-size:.75rem;color:rgba(255,255,255,.25)">© 2025 {name}. Generated by BizBuilder AI.</span>
  </div>
</footer>
""" + _PAGE_JS + """</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 2 — ELEGANT  (serif fonts, gold accents, luxury/premium feel)
# ══════════════════════════════════════════════════════════════════════════════
def _saas_elegant(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    p  = "#1A1A2E"
    s  = "#16213E"
    a  = "#C9A84C"   # gold
    bg = "#FAFAF8"
    txt = "#1A1A1A"

    svc_cards = ""
    for sv in svcs:
        ico = _svc_icon(sv.get("name",""))
        badge = f'<span style="font-size:.62rem;font-weight:600;color:{a};text-transform:uppercase;letter-spacing:.12em">{sv.get("badge","")}</span>' if sv.get("badge") else ""
        stars = "★" * int(sv.get("rating",4.8))
        svc_cards += f'<div style="background:#fff;border:1px solid #E8E8E0;padding:2.25rem;transition:all .3s" onmouseover="this.style.borderColor=\'{a}\';this.style.transform=\'translateY(-3px)\'" onmouseout="this.style.borderColor=\'#E8E8E0\';this.style.transform=\'\'">{badge}<div style="width:44px;height:44px;border:1px solid {a}60;display:flex;align-items:center;justify-content:center;color:{a};padding:10px;margin-bottom:1rem">{ico}</div><h3 style="font-family:\'Cormorant Garamond\',serif;font-size:1.3rem;font-weight:400;color:{txt};margin-bottom:.5rem;letter-spacing:-.01em">{sv.get("name","")}</h3><p style="font-size:.84rem;color:#6B6B6B;line-height:1.75;margin-bottom:1rem;min-height:56px">{sv.get("description","")}</p><div style="font-size:.75rem;color:{a};margin-bottom:1rem">{stars} {sv.get("reviews",0)} reviews</div><button onclick="showSection(\'contact\')" style="width:100%;padding:.7rem;background:transparent;color:{p};border:1px solid {p};font-size:.82rem;font-weight:600;cursor:pointer;font-family:inherit;letter-spacing:.06em;text-transform:uppercase;transition:all .2s" onmouseover="this.style.background=\'{p}\';this.style.color=\'#fff\'" onmouseout="this.style.background=\'transparent\';this.style.color=\'{p}\'">Enquire Now</button></div>'

    testi_html = ""
    for ti in testis:
        stars = "★" * int(ti.get("rating",5))
        testi_html += f'<div style="border:1px solid #E8E8E0;padding:2rem;background:#fff"><div style="color:{a};font-size:1.8rem;line-height:1;margin-bottom:.75rem;font-family:Georgia,serif">"</div><p style="font-size:.92rem;color:#3A3A3A;line-height:1.85;font-style:italic;margin-bottom:1.25rem">{ti.get("text","")}</p><div style="font-weight:600;font-size:.85rem;color:{txt}">{ti.get("name","")}</div><div style="font-size:.75rem;color:#888;letter-spacing:.04em;text-transform:uppercase;margin-top:.2rem">{ti.get("location","")}</div></div>'

    feat_html = ""
    for f in feats:
        feat_html += f'<div style="padding:1.5rem;border-bottom:1px solid #E8E8E0"><div style="font-family:\'Cormorant Garamond\',serif;font-size:1.1rem;font-weight:400;color:{txt};margin-bottom:.4rem;display:flex;align-items:center;gap:.75rem"><span style="width:24px;height:1px;background:{a};display:inline-block"></span>{f.get("title","")}</div><p style="font-size:.84rem;color:#6B6B6B;line-height:1.7;padding-left:2.25rem">{f.get("desc","")}</p></div>'

    blog_html = ""
    for post in posts:
        blog_html += f'<div style="cursor:pointer;border-bottom:1px solid #E8E8E0;padding:1.75rem 0;transition:all .2s" onclick="alert(\'Coming soon!\')" onmouseover="this.style.paddingLeft=\'1rem\'" onmouseout="this.style.paddingLeft=\'0\'"><span style="font-size:.7rem;font-weight:600;color:{a};text-transform:uppercase;letter-spacing:.12em">{post.get("category","")}</span><div style="font-family:\'Cormorant Garamond\',serif;font-size:1.2rem;color:{txt};margin:.4rem 0">{post.get("title","")}</div><div style="font-size:.8rem;color:#888;line-height:1.5">{post.get("excerpt","")}</div><div style="font-size:.72rem;color:#AAA;margin-top:.5rem">{post.get("date","")}</div></div>'

    ind_html = "".join(f'<div style="text-align:center;padding:1.5rem;border:1px solid #E8E8E0;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor=\'{a}\'" onmouseout="this.style.borderColor=\'#E8E8E0\'"><div style="font-family:\'Cormorant Garamond\',serif;font-size:1.1rem;color:{txt};margin-bottom:.25rem">{cat.get("name","")}</div><div style="font-size:.75rem;color:#AAA;letter-spacing:.06em;text-transform:uppercase">{cat.get("count","")}</div></div>' for cat in cats)

    stats_html = "".join(f'<div style="text-align:center;padding:2rem;border-right:1px solid rgba(201,168,76,.3)"><div style="font-family:\'Cormorant Garamond\',serif;font-size:3.5rem;font-weight:300;color:{a};line-height:1">{st.get("number","")}</div><div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.5);margin-top:.4rem">{st.get("label","")}</div></div>' for st in stats)

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="border-bottom:1px solid #E8E8E0;padding:1.1rem 0"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="display:flex;justify-content:space-between;cursor:pointer;font-family:\'Cormorant Garamond\',serif;font-size:1.05rem;color:{txt}"><span>{fq.get("question","")}</span><span style="color:{a}">+</span></div><div style="display:none;padding:.65rem 0 0;font-size:.875rem;color:#6B6B6B;line-height:1.7">{fq.get("answer","")}</div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    vals_html = "".join(f'<span style="display:inline-block;border:1px solid {a};color:{a};padding:.25rem .8rem;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;margin:.25rem">{v}</span>' for v in ab.get("values",[]))
    proc_html = "".join(f'<div style="flex:1;min-width:150px;text-align:center;padding:1rem"><div style="font-family:\'Cormorant Garamond\',serif;font-size:3rem;color:{a};font-weight:300;line-height:1;margin-bottom:.5rem">{pr.get("step","01")}</div><div style="width:30px;height:1px;background:{a};margin:.6rem auto;"></div><h4 style="font-family:\'Cormorant Garamond\',serif;font-size:1.05rem;font-weight:400;color:{txt};margin-bottom:.4rem">{pr.get("title","")}</h4><p style="font-size:.82rem;color:#6B6B6B;line-height:1.6;max-width:160px;margin:0 auto">{pr.get("desc","")}</p></div>' for pr in procs)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Montserrat:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Montserrat',sans-serif;background:{bg};color:{txt};line-height:1.65;-webkit-font-smoothing:antialiased}}
.ann{{background:{p};color:rgba(255,255,255,.6);text-align:center;padding:.5rem;font-size:.75rem;letter-spacing:.1em;text-transform:uppercase}}
.nav{{background:{bg};border-bottom:1px solid #E8E8E0;height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300}}
.nav-brand{{font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:300;color:{p};letter-spacing:.05em}}
.nav-links{{display:flex;gap:2.5rem;list-style:none}}
.nav-links a{{font-size:.78rem;font-weight:400;color:#888;cursor:pointer;text-decoration:none;letter-spacing:.1em;text-transform:uppercase;transition:color .15s}}
.nav-links a:hover{{color:{p}}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1140px;margin:0 auto}}
.g3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.5rem}}
.g4{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1px;background:#E8E8E0}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center}}
.h1{{font-family:'Cormorant Garamond',serif;font-size:clamp(3rem,6vw,5.5rem);font-weight:300;line-height:1.05;letter-spacing:-.02em}}
.h2{{font-family:'Cormorant Garamond',serif;font-size:clamp(2rem,4vw,3rem);font-weight:300;letter-spacing:-.01em;margin-bottom:.6rem}}
.kicker{{font-size:.7rem;font-weight:600;color:{a};text-transform:uppercase;letter-spacing:.2em;margin-bottom:.75rem}}
.sub{{color:#888;font-size:.88rem;line-height:1.85;max-width:520px}}
img{{max-width:100%;object-fit:cover}}
footer{{background:{p};padding:4rem 5% 2rem}}
@media(max-width:768px){{.g2{{grid-template-columns:1fr}}.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand">{name}</div>
  <ul class="nav-links"><li><a onclick="showSection('home')">Home</a></li><li><a onclick="showSection('about')">About</a></li><li><a onclick="showSection('services')">Services</a></li><li><a onclick="showSection('blog')">Blog</a></li><li><a onclick="showSection('contact')">Contact</a></li></ul>
  <button onclick="showSection('contact')" style="background:transparent;color:{p};border:1px solid {p};padding:.55rem 1.5rem;font-size:.78rem;font-weight:600;cursor:pointer;font-family:inherit;letter-spacing:.1em;text-transform:uppercase;transition:all .2s" onmouseover="this.style.background='{p}';this.style.color='#fff'" onmouseout="this.style.background='transparent';this.style.color='{p}'">Enquire</button>
</nav>

<div class="psec visible" id="sec-home">
<section style="background:{p};padding:7rem 5%;min-height:88vh;display:flex;align-items:center;gap:6rem">
  <div style="flex:1;max-width:580px">
    <div class="kicker" style="color:{a}">{h.get("badge","Est. 2018")}</div>
    <h1 class="h1" style="color:#fff;margin-bottom:1.5rem">{h.get("title",name)}</h1>
    <p style="font-size:.95rem;color:rgba(255,255,255,.55);margin-bottom:3rem;max-width:440px;line-height:1.85">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1.25rem">
      <button onclick="showSection('contact')" style="background:{a};color:{p};border:none;padding:.9rem 2.5rem;font-size:.8rem;font-weight:600;cursor:pointer;font-family:inherit;letter-spacing:.1em;text-transform:uppercase;transition:all .2s" onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">{h.get("cta_primary","Enquire Now")}</button>
      <button onclick="showSection('services')" style="background:transparent;color:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.2);padding:.9rem 2.5rem;font-size:.8rem;font-weight:600;cursor:pointer;font-family:inherit;letter-spacing:.1em;text-transform:uppercase;transition:all .2s" onmouseover="this.style.borderColor='rgba(255,255,255,.6)'" onmouseout="this.style.borderColor='rgba(255,255,255,.2)'">{h.get("cta_secondary","Our Services")}</button>
    </div>
  </div>
  <div style="flex:1;max-width:400px"><img src="{hero_img or photos[0]}" style="width:100%;height:320px;border-radius:2px;opacity:.8" alt="Team"/></div>
</section>
<section style="background:{bg};padding:5rem 5%"><div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:3rem">Our Expertise</h2><div class="g3">{svc_cards}</div></div></section>
<section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Industries</div><h2 class="h2" style="margin-bottom:2.5rem">Sectors We Serve</h2><div class="g4" style="gap:1px">{ind_html}</div></div></section>
<section style="background:{p};padding:5rem 5%"><div class="wrap" style="display:flex;justify-content:center;gap:0;flex-wrap:wrap">{stats_html}</div></section>
<section style="background:{bg};padding:5rem 5%"><div class="wrap"><div class="kicker">Process</div><h2 class="h2" style="margin-bottom:3rem">How We Work</h2><div style="display:flex;flex-wrap:wrap;justify-content:center;gap:0">{proc_html}</div></div></section>
<section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Testimonials</div><h2 class="h2" style="margin-bottom:3rem">Client Voices</h2><div class="g3">{testi_html}</div></div></section>
<section style="background:{bg};padding:5rem 5%"><div class="wrap"><div class="kicker">Journal</div><h2 class="h2" style="margin-bottom:1rem">Latest Articles</h2><div>{blog_html}</div></div></section>
</div>

<div class="psec" id="sec-about"><section style="background:#fff;padding:5rem 5%"><div class="wrap g2"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem"><img src="{photos[0]}" style="width:100%;height:210px" alt=""/><img src="{photos[1]}" style="width:100%;height:210px;margin-top:1.5rem" alt=""/><img src="{photos[2]}" style="width:100%;height:210px" alt=""/><img src="{photos[3]}" style="width:100%;height:210px;margin-top:-1.5rem" alt=""/></div><div><div class="kicker">Our Story</div><h2 class="h2">{ab.get("title","About Us")}</h2><p style="font-size:.95rem;color:{a};font-style:italic;margin-bottom:1.25rem;border-left:2px solid {a};padding-left:1rem">{ab.get("mission","")}</p><p style="color:#6B6B6B;line-height:1.85;font-size:.88rem;margin-bottom:1.5rem">{ab.get("story","")}</p><div style="margin-bottom:1.5rem">{vals_html}</div><button onclick="showSection('contact')" style="background:{a};color:{p};border:none;padding:.85rem 2rem;font-size:.8rem;font-weight:600;cursor:pointer;font-family:inherit;letter-spacing:.1em;text-transform:uppercase">Work With Us →</button></div></div></section><section style="background:{bg};padding:3rem 5%"><div class="wrap"><div>{feat_html}</div></div></section></div>

<div class="psec" id="sec-services"><section style="background:{bg};padding:5rem 5%"><div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:3rem">Our Expertise</h2><div class="g3">{svc_cards}</div></div></section></div>
<div class="psec" id="sec-reviews"><section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Testimonials</div><h2 class="h2" style="margin-bottom:3rem">Client Voices</h2><div class="g3">{testi_html}</div></div></section></div>
<div class="psec" id="sec-blog"><section style="background:{bg};padding:5rem 5%"><div class="wrap"><div class="kicker">Journal</div><h2 class="h2" style="margin-bottom:1rem">Latest Articles</h2><div>{blog_html}</div></div></section><section style="background:#fff;padding:4rem 5%"><div class="wrap"><div class="kicker">FAQ</div><h2 class="h2" style="margin-bottom:1.5rem">Questions</h2><div style="max-width:640px">{faq_html}</div></div></section></div>
<div class="psec" id="sec-contact"><section style="background:#fff;padding:5rem 5%"><div class="wrap g2" style="align-items:start;gap:4rem"><div><div class="kicker">Contact</div><h2 class="h2">Get In Touch</h2><p class="sub" style="margin:1rem 0 2rem">We respond within 24 hours.</p><p style="font-size:.88rem;color:#888;margin-bottom:.5rem"><strong style="color:{txt}">{ct.get("email","")}</strong></p><p style="font-size:.88rem;color:#888;margin-bottom:.5rem"><strong style="color:{txt}">{ct.get("phone","")}</strong></p><p style="font-size:.88rem;color:#888"><strong style="color:{txt}">{ct.get("address","")}</strong></p></div><div style="background:{bg};border:1px solid #E8E8E0;padding:2.5rem"><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Full Name</label><input type="text" placeholder="Your name" style="width:100%;padding:.75rem;border:1px solid #E8E8E0;background:#fff;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{a}'" onblur="this.style.borderColor='#E8E8E0'"/></div><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Email</label><input type="email" placeholder="your@email.com" style="width:100%;padding:.75rem;border:1px solid #E8E8E0;background:#fff;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='{a}'" onblur="this.style.borderColor='#E8E8E0'"/></div><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Service</label><select style="width:100%;padding:.75rem;border:1px solid #E8E8E0;background:#fff;font-family:inherit;font-size:.88rem;outline:none"><option>Select service</option>{svc_options}</select></div><div style="margin-bottom:1.5rem"><label style="font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Message</label><textarea placeholder="Tell us about your project..." style="width:100%;padding:.75rem;border:1px solid #E8E8E0;background:#fff;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px" onfocus="this.style.borderColor='{a}'" onblur="this.style.borderColor='#E8E8E0'"></textarea></div><button style="width:100%;padding:.85rem;background:{a};color:{p};border:none;font-size:.8rem;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:.1em;text-transform:uppercase" onclick="alert('Submitted!')">Send Enquiry</button></div></div></div></section></div>

<footer><div style="max-width:1140px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;padding-bottom:2rem;border-bottom:1px solid rgba(201,168,76,.2)"><div style="font-family:'Cormorant Garamond',serif;font-size:1.4rem;font-weight:300;color:#fff">{name}</div><p style="font-size:.78rem;color:rgba(255,255,255,.35);max-width:280px;text-align:right">{tg}</p></div><div style="max-width:1140px;margin:.75rem auto 0;font-size:.72rem;color:rgba(255,255,255,.25)">© 2025 {name}. Generated by BizBuilder AI.</div></footer>
""" + _PAGE_JS + """</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 3 — MINIMAL (stark white, black type, swiss grid, no decoration)
# ══════════════════════════════════════════════════════════════════════════════
def _saas_minimal(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    p = "#111111"
    a = "#111111"

    svc_cards = ""
    for i, sv in enumerate(svcs):
        _badge = f'<span style="font-size:.68rem;font-weight:700;background:#111;color:#fff;padding:.2rem .55rem;text-transform:uppercase;letter-spacing:.06em">{sv.get("badge","")}</span>' if sv.get("badge") else ""
        _nm = sv.get("name",""); _desc = sv.get("description","")
        svc_cards += (f'<div style="border-top:2px solid #111;padding:2rem 0;cursor:pointer;transition:all .2s">'
            + f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.75rem">'
            + f'<h3 style="font-size:1.05rem;font-weight:700;color:#111;flex:1">{_nm}</h3>{_badge}</div>'
            + f'<p style="font-size:.84rem;color:#555;line-height:1.7;margin-bottom:1rem">{_desc}</p>'
            + '<a onclick="showSection(\'contact\')" style="font-size:.82rem;font-weight:700;color:#111;text-decoration:none;border-bottom:1px solid #111;cursor:pointer">Talk to us →</a></div>'
        )

    testi_html = ""
    for ti in testis:
        testi_html += f'<div style="border-top:1px solid #E5E5E5;padding:2rem 0"><p style="font-size:.95rem;color:#333;line-height:1.8;margin-bottom:1rem">"{ti.get("text","")}"</p><div style="font-weight:700;font-size:.82rem;color:#111">{ti.get("name","")}</div><div style="font-size:.75rem;color:#888">{ti.get("location","")}</div></div>'

    blog_html = ""
    for post in posts:
        blog_html += f'<div style="border-top:1px solid #E5E5E5;padding:1.75rem 0;cursor:pointer;transition:all .2s" onclick="alert(\'Coming soon!\')" onmouseover="this.style.paddingLeft=\'1rem\'" onmouseout="this.style.paddingLeft=\'0\'"><div style="font-size:.7rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.4rem">{post.get("category","")}</div><div style="font-size:1rem;font-weight:700;color:#111;margin-bottom:.4rem">{post.get("title","")}</div><div style="font-size:.82rem;color:#555;line-height:1.6">{post.get("excerpt","")}</div></div>'

    stats_html = "".join(f'<div style="padding:2rem;border-right:1px solid #E5E5E5"><div style="font-size:3.5rem;font-weight:900;color:#111;letter-spacing:-.05em;line-height:1">{st.get("number","")}</div><div style="font-size:.75rem;color:#888;margin-top:.3rem;text-transform:uppercase;letter-spacing:.1em">{st.get("label","")}</div></div>' for st in stats)

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="border-top:1px solid #E5E5E5;padding:1.1rem 0"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="display:flex;justify-content:space-between;cursor:pointer;font-weight:700;font-size:.92rem;color:#111"><span>{fq.get("question","")}</span><span>+</span></div><div style="display:none;padding:.65rem 0 0;font-size:.875rem;color:#555;line-height:1.7">{fq.get("answer","")}</div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    _proc_parts = []
    for i, pr in enumerate(procs):
        _bl = "2px solid #111" if i == 0 else "1px solid #E5E5E5"
        _st = pr.get("step","01"); _ti = pr.get("title",""); _de = pr.get("desc","")
        _proc_parts.append(
            f'<div style="flex:1;min-width:150px;padding:0 1.5rem;border-left:{_bl}">'
            f'<div style="font-size:.7rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem">Step {_st}</div>'
            f'<h4 style="font-weight:700;font-size:.95rem;color:#111;margin-bottom:.35rem">{_ti}</h4>'
            f'<p style="font-size:.82rem;color:#555;line-height:1.6">{_de}</p></div>'
        )
    proc_html = "".join(_proc_parts)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#fff;color:#111;line-height:1.6;-webkit-font-smoothing:antialiased}}
.ann{{background:#111;color:#fff;text-align:center;padding:.5rem;font-size:.78rem;letter-spacing:.1em}}
.nav{{background:#fff;border-bottom:1px solid #E5E5E5;height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300}}
.nav-brand{{font-family:'DM Serif Display',serif;font-size:1.3rem;color:#111}}
.nav-links{{display:flex;gap:2.5rem;list-style:none}}
.nav-links a{{font-size:.82rem;color:#555;cursor:pointer;text-decoration:none;transition:color .15s}}
.nav-links a:hover{{color:#111}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1100px;margin:0 auto}}
.h1{{font-family:'DM Serif Display',serif;font-size:clamp(3rem,6vw,5.5rem);font-weight:400;line-height:1.05;letter-spacing:-.02em}}
.h2{{font-family:'DM Serif Display',serif;font-size:clamp(2rem,4vw,3rem);font-weight:400;letter-spacing:-.02em;margin-bottom:.6rem}}
.sub{{color:#666;font-size:.9rem;line-height:1.8;max-width:520px}}
img{{max-width:100%;object-fit:cover}}
footer{{background:#111;padding:3rem 5%;color:rgba(255,255,255,.4)}}
@media(max-width:768px){{.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand">{name}</div>
  <ul class="nav-links"><li><a onclick="showSection('home')">Home</a></li><li><a onclick="showSection('about')">About</a></li><li><a onclick="showSection('services')">Services</a></li><li><a onclick="showSection('blog')">Blog</a></li><li><a onclick="showSection('contact')">Contact</a></li></ul>
  <button onclick="showSection('contact')" style="background:#111;color:#fff;border:none;padding:.55rem 1.5rem;font-size:.82rem;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity .2s" onmouseover="this.style.opacity='.75'" onmouseout="this.style.opacity='1'">Contact →</button>
</nav>

<div class="psec visible" id="sec-home">
<section style="padding:7rem 5%;border-bottom:1px solid #E5E5E5;display:flex;align-items:center;gap:6rem">
  <div style="flex:1">
    <div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:1.25rem">{h.get("badge","")}</div>
    <h1 class="h1" style="margin-bottom:1.5rem">{h.get("title",name)}</h1>
    <p style="font-size:1rem;color:#555;max-width:420px;line-height:1.8;margin-bottom:2.5rem">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1rem">
      <button onclick="showSection('contact')" style="background:#111;color:#fff;border:none;padding:.85rem 2rem;font-size:.85rem;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity .2s" onmouseover="this.style.opacity='.75'" onmouseout="this.style.opacity='1'">{h.get("cta_primary","Get Started")} →</button>
      <button onclick="showSection('services')" style="background:transparent;color:#111;border:1px solid #111;padding:.85rem 2rem;font-size:.85rem;font-weight:600;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.background='#111';this.style.color='#fff'" onmouseout="this.style.background='transparent';this.style.color='#111'">{h.get("cta_secondary","Our Work")}</button>
    </div>
  </div>
  <div style="flex:1;max-width:420px"><img src="{hero_img or photos[0]}" style="width:100%;height:340px" alt="Team"/></div>
</section>
<section style="padding:5rem 5%;border-bottom:1px solid #E5E5E5"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:1.5rem">Services</div>{svc_cards}</div></section>
<section style="background:#F8F8F8;padding:5rem 5%"><div class="wrap"><div style="display:flex;flex-wrap:wrap;justify-content:center">{stats_html}</div></div></section>
<section style="padding:5rem 5%;border-bottom:1px solid #E5E5E5"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:1.5rem">Process</div><div style="display:flex;flex-wrap:wrap;gap:0;max-width:880px">{proc_html}</div></div></section>
<section style="background:#F8F8F8;padding:5rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:1.5rem">Testimonials</div>{testi_html}</div></section>
<section style="padding:5rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem">Articles</div>{blog_html}</div></section>
</div>

<div class="psec" id="sec-about"><section style="padding:5rem 5%"><div class="wrap" style="display:grid;grid-template-columns:1fr 1fr;gap:5rem;align-items:start"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem"><img src="{photos[0]}" style="width:100%;height:200px" alt=""/><img src="{photos[1]}" style="width:100%;height:200px;margin-top:1.5rem" alt=""/><img src="{photos[2]}" style="width:100%;height:200px" alt=""/><img src="{photos[3]}" style="width:100%;height:200px;margin-top:-1.5rem" alt=""/></div><div><h2 class="h2">{ab.get("title","About")}</h2><p style="font-size:.95rem;color:#333;line-height:1.85;margin-bottom:1.5rem;border-left:2px solid #111;padding-left:1rem">{ab.get("mission","")}</p><p style="font-size:.88rem;color:#555;line-height:1.85;margin-bottom:1.5rem">{ab.get("story","")}</p><button onclick="showSection('contact')" style="background:#111;color:#fff;border:none;padding:.85rem 2rem;font-size:.85rem;font-weight:600;cursor:pointer;font-family:inherit">Work With Us →</button></div></div></section></div>

<div class="psec" id="sec-services"><section style="padding:5rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:1.5rem">Services</div>{svc_cards}</div></section></div>
<div class="psec" id="sec-reviews"><section style="background:#F8F8F8;padding:5rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem">Testimonials</div>{testi_html}</div></section></div>
<div class="psec" id="sec-blog"><section style="padding:5rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem">Articles</div>{blog_html}</div></section><section style="background:#F8F8F8;padding:4rem 5%"><div class="wrap"><div style="font-size:.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem">FAQ</div><div style="max-width:680px">{faq_html}</div></div></section></div>
<div class="psec" id="sec-contact"><section style="padding:5rem 5%"><div class="wrap" style="display:grid;grid-template-columns:1fr 1.2fr;gap:5rem;align-items:start"><div><h2 class="h2">Let's Talk</h2><p style="color:#555;font-size:.9rem;line-height:1.8;margin:1rem 0 2rem">We respond within 24 hours.</p><p style="font-size:.88rem;margin-bottom:.5rem"><strong>{ct.get("email","")}</strong></p><p style="font-size:.88rem;margin-bottom:.5rem"><strong>{ct.get("phone","")}</strong></p><p style="font-size:.88rem"><strong>{ct.get("address","")}</strong></p></div><div><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Name</label><input type="text" placeholder="Your name" style="width:100%;padding:.75rem;border:1px solid #E5E5E5;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='#111'" onblur="this.style.borderColor='#E5E5E5'"/></div><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Email</label><input type="email" placeholder="your@email.com" style="width:100%;padding:.75rem;border:1px solid #E5E5E5;font-family:inherit;font-size:.88rem;outline:none" onfocus="this.style.borderColor='#111'" onblur="this.style.borderColor='#E5E5E5'"/></div><div style="margin-bottom:1rem"><label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Service</label><select style="width:100%;padding:.75rem;border:1px solid #E5E5E5;font-family:inherit;font-size:.88rem;outline:none;background:#fff"><option>Select</option>{svc_options}</select></div><div style="margin-bottom:1.5rem"><label style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:.35rem">Message</label><textarea placeholder="Your project details..." style="width:100%;padding:.75rem;border:1px solid #E5E5E5;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px" onfocus="this.style.borderColor='#111'" onblur="this.style.borderColor='#E5E5E5'"></textarea></div><button style="width:100%;padding:.9rem;background:#111;color:#fff;border:none;font-size:.85rem;font-weight:700;cursor:pointer;font-family:inherit" onclick="alert('Submitted!')">Send Message →</button></div></div></section></div>

<footer><div style="max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem"><div style="font-size:1.2rem;font-weight:700;color:#fff">{name}</div><span style="font-size:.75rem">© 2025 {name}. Generated by BizBuilder AI.</span></div></footer>
""" + _PAGE_JS + """</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 4 — DARK (neon glows, dark bg, cyber/tech aesthetic)
# ══════════════════════════════════════════════════════════════════════════════
def _saas_dark(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    p  = "#6C63FF"
    s  = "#5A52D5"
    a  = "#FF6B9D"

    svc_cards = ""
    for sv in svcs:
        ico = _svc_icon(sv.get("name",""))
        badge = f'<span style="position:absolute;top:1rem;right:1rem;background:{a};color:#fff;font-size:.6rem;font-weight:700;padding:.15rem .55rem;border-radius:50px;text-transform:uppercase">{sv.get("badge","")}</span>' if sv.get("badge") else ""
        stars = "★" * int(sv.get("rating",4.8))
        svc_cards += f'<div style="background:#12122A;border:1px solid #2A2A45;border-radius:16px;padding:2rem;position:relative;transition:all .3s" onmouseover="this.style.borderColor=\'{p}\';this.style.boxShadow=\'0 0 20px {p}40\'" onmouseout="this.style.borderColor=\'#2A2A45\';this.style.boxShadow=\'\'">{badge}<div style="width:48px;height:48px;background:{p}20;border:1px solid {p}50;border-radius:12px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin-bottom:1.1rem">{ico}</div><h3 style="font-size:1rem;font-weight:700;color:#E8E8F5;margin-bottom:.5rem">{sv.get("name","")}</h3><p style="font-size:.84rem;color:#8888AA;line-height:1.65;margin-bottom:1rem;min-height:56px">{sv.get("description","")}</p><div style="font-size:.74rem;color:{p};margin-bottom:1rem">{stars} {sv.get("reviews",0)} reviews</div><button onclick="showSection(\'contact\')" style="width:100%;padding:.7rem;background:{p};color:#fff;border:none;border-radius:50px;font-weight:700;font-size:.85rem;cursor:pointer;font-family:inherit;transition:all .2s;box-shadow:0 0 12px {p}50" onmouseover="this.style.boxShadow=\'0 0 24px {p}80\'" onmouseout="this.style.boxShadow=\'0 0 12px {p}50\'">Talk to Us →</button></div>'

    testi_html = ""
    for ti in testis:
        testi_html += f'<div style="background:#12122A;border:1px solid #2A2A45;border-radius:16px;padding:2rem;transition:all .2s" onmouseover="this.style.borderColor=\'{p}\'" onmouseout="this.style.borderColor=\'#2A2A45\'"><div style="color:{a};font-size:.95rem;margin-bottom:.8rem">★★★★★</div><p style="font-size:.92rem;color:#AAAAC8;line-height:1.75;font-style:italic;margin-bottom:1.25rem">"{ti.get("text","")}"</p><div style="font-weight:700;font-size:.88rem;color:#E8E8F5">{ti.get("name","")}</div><div style="font-size:.74rem;color:#5A5A7A">{ti.get("location","")}</div></div>'

    feat_html = ""
    for f in feats:
        ico = _feat_icon(f.get("title",""))
        feat_html += f'<div style="display:flex;gap:1rem;align-items:flex-start"><div style="width:44px;height:44px;background:{p}20;border:1px solid {p}40;border-radius:12px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{ico}</div><div><h4 style="font-weight:700;color:#E8E8F5;font-size:.95rem;margin-bottom:.25rem">{f.get("title","")}</h4><p style="font-size:.84rem;color:#8888AA;line-height:1.6">{f.get("desc","")}</p></div></div>'

    blog_html = ""
    for i, post in enumerate(posts):
        col = p if i % 2 == 0 else a
        blog_html += f'<div style="background:#12122A;border:1px solid #2A2A45;border-radius:16px;overflow:hidden;cursor:pointer;transition:all .2s" onclick="alert(\'Coming soon!\')" onmouseover="this.style.borderColor=\'{col}\'" onmouseout="this.style.borderColor=\'#2A2A45\'"><div style="height:120px;background:linear-gradient(135deg,{col}30,{col}10);display:flex;align-items:flex-end;padding:.85rem"><span style="background:{col}40;color:{col};font-size:.68rem;font-weight:700;padding:.2rem .55rem;border-radius:50px;text-transform:uppercase">{post.get("category","")}</span></div><div style="padding:1.25rem"><div style="font-weight:700;color:#E8E8F5;font-size:.95rem;margin-bottom:.4rem;line-height:1.35">{post.get("title","")}</div><div style="font-size:.78rem;color:#8888AA;line-height:1.5;margin-bottom:.6rem">{post.get("excerpt","")}</div><div style="font-size:.72rem;color:#5A5A7A">{post.get("date","")}</div></div></div>'

    stats_html = "".join(f'<div style="text-align:center;padding:1.5rem"><div style="font-size:2.8rem;font-weight:900;color:{p};line-height:1;letter-spacing:-.04em;text-shadow:0 0 20px {p}80">{st.get("number","")}</div><div style="font-size:.78rem;color:#8888AA;margin-top:.4rem;text-transform:uppercase;letter-spacing:.1em">{st.get("label","")}</div></div>' for st in stats)

    ind_html = "".join(f'<div style="background:#12122A;border:1px solid #2A2A45;border-radius:12px;padding:1.5rem;text-align:center;cursor:pointer;transition:all .2s" onmouseover="this.style.borderColor=\'{p}\';this.style.boxShadow=\'0 0 15px {p}30\'" onmouseout="this.style.borderColor=\'#2A2A45\';this.style.boxShadow=\'\'"><div style="width:44px;height:44px;background:{p}20;border:1px solid {p}40;border-radius:10px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin:0 auto .65rem">{_ind_icon(cat.get("name",""))}</div><div style="font-weight:700;font-size:.88rem;color:#E8E8F5;margin-bottom:.2rem">{cat.get("name","")}</div><div style="font-size:.74rem;color:#5A5A7A">{cat.get("count","")}</div></div>' for cat in cats)

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="border:1px solid #2A2A45;border-radius:12px;margin-bottom:.75rem;overflow:hidden;background:#12122A"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="padding:1.1rem 1.5rem;cursor:pointer;font-weight:600;font-size:.92rem;color:#E8E8F5;display:flex;justify-content:space-between;user-select:none"><span>{fq.get("question","")}</span><span style="color:{p}">+</span></div><div style="display:none;padding:.75rem 1.5rem 1.1rem;font-size:.875rem;color:#8888AA;line-height:1.7">{fq.get("answer","")}</div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    _proc_parts = []
    for i, pr in enumerate(procs):
        _conn = (f'<div style="flex:1;height:1px;background:linear-gradient(90deg,{p},transparent);margin-top:26px;min-width:20px"></div>' if i < len(procs)-1 else "")
        _st = pr.get("step","01"); _ti = pr.get("title",""); _de = pr.get("desc","")
        _proc_parts.append(
            f'<div style="flex:1;min-width:150px;text-align:center">'
            f'<div style="width:52px;height:52px;background:{p};border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;color:#fff;margin:0 auto 1rem;font-size:1rem;box-shadow:0 0 20px {p}60">{_st}</div>'
            f'<h4 style="font-weight:700;color:#E8E8F5;font-size:.95rem;margin-bottom:.4rem">{_ti}</h4>'
            f'<p style="font-size:.82rem;color:#8888AA;line-height:1.6;max-width:160px;margin:0 auto">{_de}</p>'
            f'</div>{_conn}'
        )
    proc_html = "".join(_proc_parts)
    vals_html = "".join(f'<span style="display:inline-block;border:1px solid {p}50;color:{p};border-radius:50px;padding:.25rem .8rem;font-size:.8rem;margin:.25rem">{v}</span>' for v in ab.get("values",[]))

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Outfit',sans-serif;background:#0A0A14;color:#E8E8F5;line-height:1.6;-webkit-font-smoothing:antialiased}}
.ann{{background:linear-gradient(90deg,{p},{a});color:#fff;text-align:center;padding:.5rem;font-size:.82rem;font-weight:500}}
.nav{{background:#0A0A14;border-bottom:1px solid #1A1A30;height:70px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300;backdrop-filter:blur(10px)}}
.nav-brand{{font-size:1.3rem;font-weight:800;background:linear-gradient(135deg,{p},{a});-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-.03em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.875rem;font-weight:500;color:#8888AA;cursor:pointer;text-decoration:none;transition:color .15s}}
.nav-links a:hover{{color:#E8E8F5}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1140px;margin:0 auto}}
.g3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1.25rem}}
.g4{{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:1rem}}
.kicker{{font-size:.72rem;font-weight:700;color:{p};text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem}}
.h2{{font-size:clamp(1.8rem,3vw,2.5rem);font-weight:800;color:#E8E8F5;letter-spacing:-.04em;line-height:1.1;margin-bottom:.7rem}}
.sub{{color:#8888AA;font-size:.9rem;line-height:1.75;max-width:520px}}
img{{max-width:100%;object-fit:cover}}
footer{{background:#06060F;border-top:1px solid #1A1A30;padding:4rem 5% 2rem}}
@media(max-width:768px){{.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand">{name}</div>
  <ul class="nav-links"><li><a onclick="showSection('home')">Home</a></li><li><a onclick="showSection('about')">About</a></li><li><a onclick="showSection('services')">Services</a></li><li><a onclick="showSection('blog')">Blog</a></li><li><a onclick="showSection('contact')">Contact</a></li></ul>
  <div style="display:flex;gap:.75rem">
    <button onclick="showSection('contact')" style="background:transparent;color:{p};border:1px solid {p}50;padding:.55rem 1.25rem;border-radius:50px;font-weight:600;font-size:.85rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.borderColor='{p}'" onmouseout="this.style.borderColor='{p}50'">Book a Call</button>
    <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.55rem 1.4rem;border-radius:50px;font-weight:700;font-size:.85rem;cursor:pointer;font-family:inherit;box-shadow:0 0 15px {p}50">{h.get("cta_primary","Get Started")}</button>
  </div>
</nav>

<div class="psec visible" id="sec-home">
<section style="padding:6rem 5%;min-height:88vh;display:flex;align-items:center;gap:4rem;position:relative;overflow:hidden">
  <div style="position:absolute;width:600px;height:600px;border-radius:50%;background:radial-gradient({p}15,transparent 70%);right:-100px;top:-100px;pointer-events:none"></div>
  <div style="flex:1;max-width:580px;position:relative;z-index:1">
    <div style="display:inline-flex;align-items:center;gap:.5rem;background:{p}20;border:1px solid {p}40;color:{p};padding:.38rem 1rem;border-radius:50px;font-size:.78rem;font-weight:600;margin-bottom:1.5rem"><span style="width:6px;height:6px;border-radius:50%;background:{p};animation:blink 1.5s infinite;display:inline-block"></span>{h.get("badge","Active & Taking Projects")}</div>
    <h1 style="font-size:clamp(2.8rem,5vw,4.5rem);font-weight:900;line-height:1.05;letter-spacing:-.05em;color:#E8E8F5;margin-bottom:1.25rem">{h.get("title",name)}</h1>
    <p style="font-size:1rem;color:#8888AA;margin-bottom:2.5rem;max-width:460px;line-height:1.75">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
      <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.9rem 2.2rem;border-radius:50px;font-weight:700;font-size:.95rem;cursor:pointer;font-family:inherit;box-shadow:0 0 20px {p}60;transition:all .2s">{h.get("cta_primary","Get Started")} →</button>
      <button onclick="showSection('services')" style="background:transparent;color:#E8E8F5;border:1px solid #2A2A45;padding:.9rem 2.2rem;border-radius:50px;font-weight:600;font-size:.95rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.borderColor='#5A5A7A'" onmouseout="this.style.borderColor='#2A2A45'">{h.get("cta_secondary","Our Services")}</button>
    </div>
  </div>
  <div style="flex:1;max-width:420px;position:relative;z-index:1">
    <div style="position:relative"><img src="{photos[0]}" style="width:100%;height:280px;border-radius:16px;border:1px solid #2A2A45;opacity:.85" alt="Team"/>
    <div style="position:absolute;bottom:-1rem;right:-1rem;background:#12122A;border:1px solid {p}50;border-radius:12px;padding:1rem;min-width:160px;box-shadow:0 0 20px {p}30"><div style="font-size:.72rem;color:{p};font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.25rem">Available</div><div style="font-size:.88rem;color:#E8E8F5;font-weight:600">Taking new projects</div></div></div>
  </div>
</section>
<section style="background:#0D0D1F;padding:5rem 5%"><div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:2.5rem">What We Build</h2><div class="g3">{svc_cards}</div></div></section>
<section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Industries</div><h2 class="h2" style="margin-bottom:2.5rem">Who We Serve</h2><div class="g4">{ind_html}</div></div></section>
<section style="background:#0D0D1F;padding:4rem 5%"><div class="wrap" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:#1A1A30;border-radius:16px;overflow:hidden">{stats_html}</div></section>
<section style="padding:5rem 5%"><div class="wrap g2" style="gap:5rem"><div><div class="kicker">Why Us</div><h2 class="h2">{ab.get("mission","")}</h2><div style="display:flex;flex-direction:column;gap:1.25rem;margin-top:1.5rem">{feat_html}</div></div><div><div style="background:#0D0D1F;border:1px solid #1A1A30;border-radius:16px;padding:2rem;text-align:center"><div style="font-weight:700;color:#E8E8F5;margin-bottom:.5rem">Start your project</div><p style="font-size:.84rem;color:#8888AA;margin-bottom:1.25rem">Free discovery call today.</p><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:50px;padding:.8rem 2rem;font-weight:700;cursor:pointer;font-family:inherit;box-shadow:0 0 15px {p}50">Book Free Call →</button></div></div></div></section>
<section style="background:#0D0D1F;padding:5rem 5%"><div class="wrap"><div class="kicker">Testimonials</div><h2 class="h2" style="margin-bottom:2.5rem">Client Stories</h2><div class="g3">{testi_html}</div></div></section>
<section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Blog</div><h2 class="h2" style="margin-bottom:2.5rem">Latest Articles</h2><div class="g3">{blog_html}</div></div></section>
</div>

<div class="psec" id="sec-about"><section style="padding:5rem 5%"><div class="wrap g2"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem"><img src="{photos[0]}" style="width:100%;height:200px;border-radius:12px;border:1px solid #1A1A30;opacity:.8" alt=""/><img src="{photos[1]}" style="width:100%;height:200px;border-radius:12px;border:1px solid #1A1A30;opacity:.8;margin-top:1.5rem" alt=""/><img src="{photos[2]}" style="width:100%;height:200px;border-radius:12px;border:1px solid #1A1A30;opacity:.8" alt=""/><img src="{photos[3]}" style="width:100%;height:200px;border-radius:12px;border:1px solid #1A1A30;opacity:.8;margin-top:-1.5rem" alt=""/></div><div><div class="kicker">Story</div><h2 class="h2">{ab.get("title","About Us")}</h2><p style="color:{p};font-size:.95rem;border-left:2px solid {p};padding-left:1rem;margin-bottom:1.25rem;line-height:1.65">{ab.get("mission","")}</p><p style="color:#8888AA;line-height:1.85;font-size:.9rem;margin-bottom:1.5rem">{ab.get("story","")}</p><div style="margin-bottom:1.5rem">{vals_html}</div><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:50px;padding:.85rem 2rem;font-weight:700;font-size:.9rem;cursor:pointer;font-family:inherit;box-shadow:0 0 15px {p}50">Work With Us →</button></div></div></section><section style="background:#0D0D1F;padding:5rem 5%"><div class="wrap"><div class="kicker">Process</div><h2 class="h2" style="margin-bottom:3rem">How We Work</h2><div style="display:flex;align-items:flex-start;flex-wrap:wrap;justify-content:center;gap:0;max-width:900px;margin:0 auto">{proc_html}</div></div></section></div>

<div class="psec" id="sec-services"><section style="background:#0D0D1F;padding:5rem 5%"><div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:2.5rem">What We Build</h2><div class="g3">{svc_cards}</div></div></section></div>
<div class="psec" id="sec-reviews"><section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Reviews</div><h2 class="h2" style="margin-bottom:2.5rem">Client Stories</h2><div class="g3">{testi_html}</div></div></section></div>
<div class="psec" id="sec-blog"><section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Blog</div><h2 class="h2" style="margin-bottom:2.5rem">Latest Articles</h2><div class="g3">{blog_html}</div></div></section><section style="background:#0D0D1F;padding:4rem 5%"><div class="wrap"><div class="kicker">FAQ</div><h2 class="h2" style="margin-bottom:1.5rem">Questions</h2><div style="max-width:700px;margin:0 auto">{faq_html}</div></div></section></div>
<div class="psec" id="sec-contact"><section style="padding:5rem 5%"><div class="wrap g2" style="align-items:start;gap:4rem"><div><div class="kicker">Contact</div><h2 class="h2">Let's Build Together</h2><p class="sub" style="margin:1rem 0 2rem">We respond within 24 hours.</p><div style="display:flex;flex-direction:column;gap:.85rem"><div style="display:flex;gap:.75rem;align-items:center"><div style="width:38px;height:38px;border:1px solid {p}50;border-radius:8px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["support"]}</div><span style="font-size:.88rem;color:#AAAAC8">{ct.get("email","")}</span></div><div style="display:flex;gap:.75rem;align-items:center"><div style="width:38px;height:38px;border:1px solid {p}50;border-radius:8px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["fast"]}</div><span style="font-size:.88rem;color:#AAAAC8">{ct.get("phone","")}</span></div></div></div><div style="background:#12122A;border:1px solid #2A2A45;border-radius:16px;padding:2.5rem"><div style="margin-bottom:1rem"><label style="font-size:.78rem;font-weight:600;color:#8888AA;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.08em">Name</label><input type="text" style="width:100%;padding:.75rem;background:#0A0A14;border:1px solid #2A2A45;border-radius:8px;color:#E8E8F5;font-family:inherit;font-size:.88rem;outline:none" placeholder="Your name" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#2A2A45'"/></div><div style="margin-bottom:1rem"><label style="font-size:.78rem;font-weight:600;color:#8888AA;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.08em">Email</label><input type="email" style="width:100%;padding:.75rem;background:#0A0A14;border:1px solid #2A2A45;border-radius:8px;color:#E8E8F5;font-family:inherit;font-size:.88rem;outline:none" placeholder="your@email.com" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#2A2A45'"/></div><div style="margin-bottom:1rem"><label style="font-size:.78rem;font-weight:600;color:#8888AA;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.08em">Service</label><select style="width:100%;padding:.75rem;background:#0A0A14;border:1px solid #2A2A45;border-radius:8px;color:#E8E8F5;font-family:inherit;font-size:.88rem;outline:none"><option>Select</option>{svc_options}</select></div><div style="margin-bottom:1.5rem"><label style="font-size:.78rem;font-weight:600;color:#8888AA;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.08em">Message</label><textarea style="width:100%;padding:.75rem;background:#0A0A14;border:1px solid #2A2A45;border-radius:8px;color:#E8E8F5;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px" placeholder="Your project..." onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#2A2A45'"></textarea></div><button style="width:100%;padding:.9rem;background:{p};color:#fff;border:none;border-radius:50px;font-weight:700;cursor:pointer;font-family:inherit;font-size:.95rem;box-shadow:0 0 20px {p}50" onclick="alert('Submitted!')">Send Message →</button></div></div></section></div>

<footer><div style="max-width:1140px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem"><div style="font-size:1.2rem;font-weight:800;background:linear-gradient(135deg,{p},{a});-webkit-background-clip:text;-webkit-text-fill-color:transparent">{name}</div><span style="font-size:.75rem;color:rgba(255,255,255,.2)">© 2025 {name}. Generated by BizBuilder AI.</span></div></footer>
<style>@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}</style>
""" + _PAGE_JS + """</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 5 — PLAYFUL (warm, rounded, friendly, colorful)
# ══════════════════════════════════════════════════════════════════════════════
def _saas_playful(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    p  = "#FF6B35"
    s  = "#E64A19"
    a  = "#4CAF50"

    svc_cards = ""
    for i, sv in enumerate(svcs):
        colors = [p, a, "#2196F3", "#9C27B0", "#FF9800", "#00BCD4"]
        col = colors[i % len(colors)]
        ico = _svc_icon(sv.get("name",""))
        stars = "★" * int(sv.get("rating",4.8))
        svc_cards += f'<div style="background:#fff;border:2px solid #FFE0CC;border-radius:24px;padding:2rem;transition:all .3s" onmouseover="this.style.borderColor=\'{col}\';this.style.transform=\'translateY(-6px)\';this.style.boxShadow=\'0 16px 32px {col}25\'" onmouseout="this.style.borderColor=\'#FFE0CC\';this.style.transform=\'\';this.style.boxShadow=\'\'"><div style="width:52px;height:52px;background:{col};border-radius:16px;display:flex;align-items:center;justify-content:center;color:#fff;padding:11px;margin-bottom:1.1rem">{ico}</div><h3 style="font-size:1.05rem;font-weight:800;color:#2D1B00;margin-bottom:.5rem">{sv.get("name","")}</h3><p style="font-size:.84rem;color:#8B6914;line-height:1.65;margin-bottom:1rem;min-height:56px">{sv.get("description","")}</p><div style="font-size:.75rem;color:{col};margin-bottom:1rem">{stars} {sv.get("reviews",0)} reviews</div><button onclick="showSection(\'contact\')" style="width:100%;padding:.7rem;background:{col};color:#fff;border:none;border-radius:50px;font-weight:800;font-size:.85rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.opacity=\'.85\'" onmouseout="this.style.opacity=\'1\'">Let\'s Chat! →</button></div>'

    testi_html = ""
    for ti in testis:
        testi_html += f'<div style="background:#fff;border:2px solid #FFE0CC;border-radius:24px;padding:2rem;transition:all .2s" onmouseover="this.style.borderColor=\'{p}\';this.style.transform=\'translateY(-4px)\'" onmouseout="this.style.borderColor=\'#FFE0CC\';this.style.transform=\'\'"><div style="color:{p};font-size:1.5rem;margin-bottom:.75rem">★★★★★</div><p style="font-size:.92rem;color:#5D4037;line-height:1.75;margin-bottom:1.25rem">"{ti.get("text","")}"</p><div style="font-weight:800;color:#2D1B00">{ti.get("name","")}</div><div style="font-size:.75rem;color:#A1887F">{ti.get("location","")}</div></div>'

    blog_html = ""
    for i, post in enumerate(posts):
        bg_c = [f"linear-gradient(135deg,{p},{s})", f"linear-gradient(135deg,{a},#45A049)", f"linear-gradient(135deg,#2196F3,#1565C0)"]
        blog_html += f'<div style="background:#fff;border:2px solid #FFE0CC;border-radius:24px;overflow:hidden;cursor:pointer;transition:all .2s" onclick="alert(\'Coming soon!\')" onmouseover="this.style.transform=\'translateY(-4px)\';this.style.borderColor=\'{p}\'" onmouseout="this.style.transform=\'\';this.style.borderColor=\'#FFE0CC\'"><div style="height:120px;background:{bg_c[i%3]};display:flex;align-items:flex-end;padding:.85rem"><span style="background:rgba(255,255,255,.25);color:#fff;font-size:.68rem;font-weight:800;padding:.2rem .65rem;border-radius:50px;text-transform:uppercase">{post.get("category","")}</span></div><div style="padding:1.25rem"><div style="font-weight:800;font-size:.95rem;color:#2D1B00;margin-bottom:.4rem;line-height:1.35">{post.get("title","")}</div><div style="font-size:.78rem;color:#8B6914;line-height:1.5;margin-bottom:.6rem">{post.get("excerpt","")}</div><div style="font-size:.72rem;color:#BCAAA4">{post.get("date","")}</div></div></div>'

    stats_html = "".join(f'<div style="text-align:center;background:#fff;border:2px solid #FFE0CC;border-radius:24px;padding:2rem"><div style="font-size:3rem;font-weight:900;color:{p};line-height:1;letter-spacing:-.04em">{st.get("number","")}</div><div style="font-size:.82rem;color:#8B6914;margin-top:.4rem;font-weight:600">{st.get("label","")}</div></div>' for st in stats)

    ind_html = "".join(f'<div style="background:#fff;border:2px solid #FFE0CC;border-radius:20px;padding:1.5rem;text-align:center;cursor:pointer;transition:all .25s" onmouseover="this.style.borderColor=\'{p}\';this.style.transform=\'scale(1.04)\'" onmouseout="this.style.borderColor=\'#FFE0CC\';this.style.transform=\'scale(1)\'"><div style="width:48px;height:48px;background:{p}15;border-radius:14px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin:0 auto .65rem">{_ind_icon(cat.get("name",""))}</div><div style="font-weight:800;font-size:.88rem;color:#2D1B00;margin-bottom:.2rem">{cat.get("name","")}</div><div style="font-size:.74rem;color:#A1887F">{cat.get("count","")}</div></div>' for cat in cats)

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="background:#fff;border:2px solid #FFE0CC;border-radius:16px;margin-bottom:.75rem;overflow:hidden"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="padding:1.1rem 1.5rem;cursor:pointer;font-weight:700;font-size:.92rem;color:#2D1B00;display:flex;justify-content:space-between;user-select:none" onmouseover="this.style.background=\'#FFF3EE\'" onmouseout="this.style.background=\'\'"><span>{fq.get("question","")}</span><span style="color:{p};font-size:1.2rem">+</span></div><div style="display:none;padding:.75rem 1.5rem 1.1rem;font-size:.875rem;color:#8B6914;line-height:1.7">{fq.get("answer","")}</div></div>'

    feat_html = ""
    colors = [p, a, "#2196F3", "#9C27B0"]
    for i, f in enumerate(feats):
        col = colors[i % 4]
        ico = _feat_icon(f.get("title",""))
        feat_html += f'<div style="display:flex;gap:1rem;align-items:flex-start"><div style="width:48px;height:48px;background:{col};border-radius:14px;display:flex;align-items:center;justify-content:center;color:#fff;padding:11px;flex-shrink:0">{ico}</div><div><h4 style="font-weight:800;font-size:.95rem;color:#2D1B00;margin-bottom:.25rem">{f.get("title","")}</h4><p style="font-size:.84rem;color:#8B6914;line-height:1.6">{f.get("desc","")}</p></div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    vals_html = "".join(f'<span style="display:inline-block;background:{p};color:#fff;border-radius:50px;padding:.3rem .9rem;font-size:.8rem;font-weight:700;margin:.25rem">{v}</span>' for v in ab.get("values",[]))
    _proc_parts = []
    for i, pr in enumerate(procs):
        _conn = (f'<div style="flex:1;height:3px;background:{p}30;border-radius:50px;margin-top:28px;min-width:20px"></div>' if i < len(procs)-1 else "")
        _st = pr.get("step","01"); _ti = pr.get("title",""); _de = pr.get("desc","")
        _proc_parts.append(
            f'<div style="text-align:center;flex:1;min-width:150px">'
            f'<div style="width:56px;height:56px;background:{p};border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;color:#fff;font-size:1.1rem;margin:0 auto 1rem;box-shadow:0 8px 20px {p}40">{_st}</div>'
            f'<h4 style="font-weight:800;font-size:.95rem;color:#2D1B00;margin-bottom:.4rem">{_ti}</h4>'
            f'<p style="font-size:.82rem;color:#8B6914;line-height:1.6;max-width:160px;margin:0 auto">{_de}</p>'
            f'</div>{_conn}'
        )
    proc_html = "".join(_proc_parts)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name}</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Nunito',sans-serif;background:#FFF9F0;color:#2D1B00;line-height:1.6;-webkit-font-smoothing:antialiased}}
.ann{{background:{p};color:#fff;text-align:center;padding:.55rem;font-size:.82rem;font-weight:700}}
.nav{{background:#fff;border-bottom:2px solid #FFE0CC;height:70px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300;border-radius:0 0 20px 20px}}
.nav-brand{{font-size:1.3rem;font-weight:900;color:{p}}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.875rem;font-weight:700;color:#8B6914;cursor:pointer;text-decoration:none;transition:color .15s}}
.nav-links a:hover{{color:{p}}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1140px;margin:0 auto}}
.g3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1.5rem}}
.g4{{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:1rem}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:3rem;align-items:center}}
.kicker{{font-size:.78rem;font-weight:800;color:{p};text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem}}
.h2{{font-size:clamp(1.8rem,3vw,2.5rem);font-weight:900;color:#2D1B00;letter-spacing:-.02em;line-height:1.15;margin-bottom:.7rem}}
.sub{{color:#8B6914;font-size:.92rem;line-height:1.75;max-width:520px}}
img{{max-width:100%;object-fit:cover}}
footer{{background:#2D1B00;padding:3.5rem 5% 2rem}}
@media(max-width:768px){{.g2{{grid-template-columns:1fr}}.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand">{name} 🎯</div>
  <ul class="nav-links"><li><a onclick="showSection('home')">Home</a></li><li><a onclick="showSection('about')">About</a></li><li><a onclick="showSection('services')">Services</a></li><li><a onclick="showSection('blog')">Blog</a></li><li><a onclick="showSection('contact')">Contact</a></li></ul>
  <div style="display:flex;gap:.75rem">
    <button onclick="showSection('contact')" style="background:transparent;color:{p};border:2px solid {p};padding:.5rem 1.2rem;border-radius:50px;font-weight:800;font-size:.85rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.background='{p}';this.style.color='#fff'" onmouseout="this.style.background='transparent';this.style.color='{p}'">Say Hi!</button>
    <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.55rem 1.4rem;border-radius:50px;font-weight:800;font-size:.85rem;cursor:pointer;font-family:inherit;box-shadow:0 6px 16px {p}40">Get Started!</button>
  </div>
</nav>

<div class="psec visible" id="sec-home">
<section style="padding:6rem 5%;min-height:85vh;display:flex;align-items:center;gap:4rem">
  <div style="flex:1;max-width:580px">
    <div style="display:inline-flex;align-items:center;gap:.5rem;background:{p}15;border:2px solid {p}30;color:{p};padding:.4rem 1rem;border-radius:50px;font-size:.8rem;font-weight:800;margin-bottom:1.5rem">✨ {h.get("badge","Loved by 200+ clients")}</div>
    <h1 style="font-size:clamp(2.6rem,5vw,4rem);font-weight:900;line-height:1.1;letter-spacing:-.03em;color:#2D1B00;margin-bottom:1.25rem">{h.get("title",name)}</h1>
    <p style="font-size:1rem;color:#8B6914;margin-bottom:2.5rem;max-width:440px;line-height:1.8">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
      <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.9rem 2.2rem;border-radius:50px;font-weight:900;font-size:.95rem;cursor:pointer;font-family:inherit;box-shadow:0 8px 20px {p}40;transition:all .2s" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform=''">{h.get("cta_primary","Let's Go!")} →</button>
      <button onclick="showSection('services')" style="background:#fff;color:{p};border:2px solid {p};padding:.9rem 2.2rem;border-radius:50px;font-weight:800;font-size:.95rem;cursor:pointer;font-family:inherit;transition:all .2s">{h.get("cta_secondary","See Work")}</button>
    </div>
  </div>
  <div style="flex:1;max-width:400px">
    <img src="{hero_img or photos[0]}" style="width:100%;height:280px;border-radius:24px;border:3px solid {p}30" alt="Team"/>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-top:.75rem">{stats_html}</div>
  </div>
</section>
<section style="background:#fff;padding:5rem 5%;border-radius:32px;margin:0 2.5%"><div class="wrap"><div class="kicker">Our Services</div><h2 class="h2" style="margin-bottom:2.5rem">What We're Great At</h2><div class="g3">{svc_cards}</div></div></section>
<section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Who We Help</div><h2 class="h2" style="margin-bottom:2.5rem">Industries We Love</h2><div class="g4">{ind_html}</div></div></section>
<section style="background:{p};padding:5rem 5%;border-radius:32px;margin:0 2.5%"><div class="wrap g2"><div><h2 style="font-size:clamp(1.8rem,3vw,2.5rem);font-weight:900;color:#fff;letter-spacing:-.02em;margin-bottom:1rem">Why We're Different</h2><p style="color:rgba(255,255,255,.8);font-size:.92rem;line-height:1.75;margin-bottom:2rem">{ab.get("mission","")}</p><div style="display:flex;flex-direction:column;gap:1.25rem">{feat_html}</div></div><div><div style="background:#fff;border-radius:24px;padding:2rem;text-align:center"><h3 style="font-weight:900;font-size:1.1rem;color:#2D1B00;margin-bottom:.5rem">Ready to Start?</h3><p style="font-size:.85rem;color:#8B6914;margin-bottom:1.25rem">Free discovery call, zero pressure!</p><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:50px;padding:.85rem 2rem;font-weight:900;cursor:pointer;font-family:inherit;box-shadow:0 6px 16px {p}40">Book Free Call!</button></div></div></div></section>
<section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Happy Clients</div><h2 class="h2" style="margin-bottom:2.5rem">They Love Us!</h2><div class="g3">{testi_html}</div></div></section>
<section style="background:#fff;padding:5rem 5%;border-radius:32px;margin:0 2.5%"><div class="wrap"><div class="kicker">Our Process</div><h2 class="h2" style="margin-bottom:3rem">How We Work</h2><div style="display:flex;align-items:flex-start;flex-wrap:wrap;justify-content:center;gap:0;max-width:900px;margin:0 auto">{proc_html}</div></div></section>
<section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Blog</div><h2 class="h2" style="margin-bottom:2.5rem">Fresh Insights!</h2><div class="g3">{blog_html}</div></div></section>
</div>

<div class="psec" id="sec-about"><section style="padding:5rem 5%"><div class="wrap g2"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem"><img src="{photos[0]}" style="width:100%;height:200px;border-radius:20px" alt=""/><img src="{photos[1]}" style="width:100%;height:200px;border-radius:20px;margin-top:1.5rem" alt=""/><img src="{photos[2]}" style="width:100%;height:200px;border-radius:20px" alt=""/><img src="{photos[3]}" style="width:100%;height:200px;border-radius:20px;margin-top:-1.5rem" alt=""/></div><div><div class="kicker">Our Story</div><h2 class="h2">{ab.get("title","About Us")}</h2><p style="color:{p};font-weight:700;border-left:4px solid {p};padding-left:1rem;margin-bottom:1.25rem;line-height:1.65">{ab.get("mission","")}</p><p style="color:#8B6914;line-height:1.85;font-size:.9rem;margin-bottom:1.5rem">{ab.get("story","")}</p><div style="margin-bottom:1.5rem">{vals_html}</div><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:50px;padding:.85rem 2rem;font-weight:900;cursor:pointer;font-family:inherit;box-shadow:0 6px 16px {p}40">Work With Us!</button></div></div></section></div>

<div class="psec" id="sec-services"><section style="background:#fff;padding:5rem 5%;border-radius:32px;margin:1rem 2.5%"><div class="wrap"><div class="kicker">Services</div><h2 class="h2" style="margin-bottom:2.5rem">What We're Great At</h2><div class="g3">{svc_cards}</div></div></section></div>
<div class="psec" id="sec-reviews"><section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Reviews</div><h2 class="h2" style="margin-bottom:2.5rem">They Love Us!</h2><div class="g3">{testi_html}</div></div></section></div>
<div class="psec" id="sec-blog"><section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Blog</div><h2 class="h2" style="margin-bottom:2.5rem">Fresh Insights!</h2><div class="g3">{blog_html}</div></div></section><section style="background:#fff;padding:4rem 5%;border-radius:32px;margin:0 2.5%"><div class="wrap"><div class="kicker">FAQ</div><h2 class="h2" style="margin-bottom:1.5rem">Got Questions?</h2><div style="max-width:700px;margin:0 auto">{faq_html}</div></div></section></div>
<div class="psec" id="sec-contact"><section style="padding:5rem 5%"><div class="wrap"><div class="kicker">Say Hello</div><h2 class="h2" style="margin-bottom:.5rem">Let's Work Together!</h2><p class="sub" style="margin-bottom:3rem">We'd love to hear about your project!</p><div class="g2" style="align-items:start"><div><img src="{photos[1]}" style="width:100%;height:200px;border-radius:24px;margin-bottom:1.5rem" alt=""/><p style="font-weight:700;font-size:.9rem;margin-bottom:.5rem">{ct.get("email","")}</p><p style="font-weight:700;font-size:.9rem;margin-bottom:.5rem">{ct.get("phone","")}</p><p style="font-weight:700;font-size:.9rem">{ct.get("address","")}</p></div><div style="background:#fff;border:2px solid #FFE0CC;border-radius:24px;padding:2.5rem"><div style="margin-bottom:1rem"><label style="font-size:.8rem;font-weight:800;display:block;margin-bottom:.35rem;color:#2D1B00">Your Name</label><input type="text" style="width:100%;padding:.75rem;border:2px solid #FFE0CC;border-radius:14px;font-family:inherit;font-size:.88rem;outline:none;background:#FFF9F0" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#FFE0CC'"/></div><div style="margin-bottom:1rem"><label style="font-size:.8rem;font-weight:800;display:block;margin-bottom:.35rem;color:#2D1B00">Email</label><input type="email" style="width:100%;padding:.75rem;border:2px solid #FFE0CC;border-radius:14px;font-family:inherit;font-size:.88rem;outline:none;background:#FFF9F0" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#FFE0CC'"/></div><div style="margin-bottom:1rem"><label style="font-size:.8rem;font-weight:800;display:block;margin-bottom:.35rem;color:#2D1B00">I need help with</label><select style="width:100%;padding:.75rem;border:2px solid #FFE0CC;border-radius:14px;font-family:inherit;font-size:.88rem;outline:none;background:#FFF9F0"><option>Pick one!</option>{svc_options}</select></div><div style="margin-bottom:1.5rem"><label style="font-size:.8rem;font-weight:800;display:block;margin-bottom:.35rem;color:#2D1B00">Tell Us More!</label><textarea style="width:100%;padding:.75rem;border:2px solid #FFE0CC;border-radius:14px;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px;background:#FFF9F0" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#FFE0CC'"></textarea></div><button style="width:100%;padding:.9rem;background:{p};color:#fff;border:none;border-radius:50px;font-weight:900;cursor:pointer;font-family:inherit;font-size:.95rem;box-shadow:0 6px 16px {p}40" onclick="alert('Sent! We will reply super fast!')">Send it! 🎉</button></div></div></div></section></div>

<footer><div style="max-width:1140px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem"><div style="font-size:1.3rem;font-weight:900;color:{p}">{name}</div><span style="font-size:.75rem;color:rgba(255,255,255,.3)">© 2025 {name}. Generated by BizBuilder AI.</span></div></footer>
""" + _PAGE_JS + """</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STYLE 6 — CORPORATE (enterprise, navy/blue, professional, trustworthy)
# ══════════════════════════════════════════════════════════════════════════════
def _saas_corporate(name, c, h, ab, ct, tg, an, feats, stats, testis, svcs, cats, procs, posts, faqs, photos, hero_img=None):
    p  = "#1A3A6B"
    s  = "#0D2044"
    a  = "#2563EB"

    svc_cards = ""
    for sv in svcs:
        ico = _svc_icon(sv.get("name",""))
        badge = f'<span style="background:{a};color:#fff;font-size:.6rem;font-weight:700;padding:.15rem .55rem;border-radius:3px;text-transform:uppercase;float:right">{sv.get("badge","")}</span>' if sv.get("badge") else ""
        stars = "★" * int(sv.get("rating",4.8))
        svc_cards += f'<div style="background:#fff;border:1px solid #DDE3EE;border-radius:4px;padding:2rem;transition:all .2s;border-top:3px solid {p}" onmouseover="this.style.boxShadow=\'0 8px 24px rgba(26,58,107,.12)\';this.style.transform=\'translateY(-3px)\'" onmouseout="this.style.boxShadow=\'\';this.style.transform=\'\'">{badge}<div style="width:44px;height:44px;border:1px solid {a}30;border-radius:4px;display:flex;align-items:center;justify-content:center;color:{a};padding:10px;margin-bottom:1rem;clear:both">{ico}</div><h3 style="font-size:1rem;font-weight:700;color:{s};margin-bottom:.5rem">{sv.get("name","")}</h3><p style="font-size:.84rem;color:#4A5568;line-height:1.65;margin-bottom:1rem;min-height:56px">{sv.get("description","")}</p><div style="font-size:.74rem;color:#718096;margin-bottom:1rem">{stars} {sv.get("reviews",0)} reviews</div><button onclick="showSection(\'contact\')" style="width:100%;padding:.7rem;background:{p};color:#fff;border:none;border-radius:3px;font-weight:600;font-size:.84rem;cursor:pointer;font-family:inherit;letter-spacing:.02em;transition:background .2s" onmouseover="this.style.background=\'{a}\'" onmouseout="this.style.background=\'{p}\'">Request Information →</button></div>'

    testi_html = ""
    for ti in testis:
        stars = "★" * int(ti.get("rating",5))
        testi_html += f'<div style="background:#fff;border:1px solid #DDE3EE;border-radius:4px;padding:2rem;transition:all .2s;border-left:3px solid {p}" onmouseover="this.style.boxShadow=\'0 4px 16px rgba(26,58,107,.08)\'" onmouseout="this.style.boxShadow=\'\'"><div style="color:{a};font-size:.9rem;margin-bottom:.75rem">{stars}</div><p style="font-size:.9rem;color:#2D3748;line-height:1.8;margin-bottom:1.25rem">&ldquo;{ti.get("text","")}&rdquo;</p><div style="font-weight:700;font-size:.85rem;color:{s}">{ti.get("name","")}</div><div style="font-size:.74rem;color:#718096;text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem">{ti.get("location","")}</div></div>'

    feat_html = ""
    for f in feats:
        ico = _feat_icon(f.get("title",""))
        feat_html += f'<div style="display:flex;gap:1rem;padding:1.25rem;border:1px solid #DDE3EE;border-radius:4px;background:#fff;border-left:3px solid {a}"><div style="width:40px;height:40px;border:1px solid {a}30;border-radius:3px;display:flex;align-items:center;justify-content:center;color:{a};padding:9px;flex-shrink:0">{ico}</div><div><h4 style="font-weight:700;font-size:.92rem;color:{s};margin-bottom:.25rem">{f.get("title","")}</h4><p style="font-size:.83rem;color:#4A5568;line-height:1.65">{f.get("desc","")}</p></div></div>'

    blog_html = ""
    for i, post in enumerate(posts):
        _bg = f"linear-gradient(135deg,{p},{a})" if i%2==0 else f"linear-gradient(135deg,{a},{s})"
        _cat, _title, _exc, _date = post.get("category",""), post.get("title",""), post.get("excerpt",""), post.get("date","")
        blog_html += (f'<div style="background:#fff;border:1px solid #DDE3EE;border-radius:4px;overflow:hidden;cursor:pointer;transition:all .2s">'
            + f'<div style="height:110px;background:{_bg};display:flex;align-items:flex-end;padding:.85rem">'
            + f'<span style="background:rgba(255,255,255,.15);color:#fff;font-size:.65rem;font-weight:700;padding:.18rem .55rem;border-radius:2px;text-transform:uppercase;letter-spacing:.08em">{_cat}</span></div>'
            + f'<div style="padding:1.25rem"><div style="font-weight:700;font-size:.92rem;color:{s};margin-bottom:.4rem;line-height:1.35">{_title}</div>'
            + f'<div style="font-size:.78rem;color:#718096;line-height:1.55;margin-bottom:.6rem">{_exc}</div>'
            + f'<div style="font-size:.72rem;color:#A0AEC0;text-transform:uppercase;letter-spacing:.06em">{_date}</div></div></div>')

    stats_html = "".join(f'<div style="text-align:center;padding:2rem;border-right:1px solid rgba(255,255,255,.1)"><div style="font-size:2.8rem;font-weight:700;color:#fff;line-height:1;letter-spacing:-.02em">{st.get("number","")}</div><div style="font-size:.75rem;color:rgba(255,255,255,.55);margin-top:.4rem;text-transform:uppercase;letter-spacing:.12em">{st.get("label","")}</div></div>' for st in stats)

    ind_html = "".join(f'<div style="background:#fff;border:1px solid #DDE3EE;border-radius:4px;padding:1.5rem;text-align:center;cursor:pointer;transition:all .2s;border-top:2px solid transparent" onmouseover="this.style.borderTopColor=\'{p}\';this.style.boxShadow=\'0 4px 16px rgba(26,58,107,.08)\'" onmouseout="this.style.borderTopColor=\'transparent\';this.style.boxShadow=\'\'"><div style="width:44px;height:44px;border:1px solid {p}20;border-radius:4px;display:flex;align-items:center;justify-content:center;color:{p};padding:10px;margin:0 auto .65rem">{_ind_icon(cat.get("name",""))}</div><div style="font-weight:700;font-size:.88rem;color:{s};margin-bottom:.2rem">{cat.get("name","")}</div><div style="font-size:.74rem;color:#718096;text-transform:uppercase;letter-spacing:.04em">{cat.get("count","")}</div></div>' for cat in cats)

    faq_html = ""
    for fq in faqs:
        faq_html += f'<div style="border:1px solid #DDE3EE;border-radius:4px;margin-bottom:.75rem;overflow:hidden;background:#fff"><div onclick="var a=this.nextElementSibling;a.style.display=a.style.display===\'block\'?\'none\':\'block\'" style="padding:1.1rem 1.5rem;cursor:pointer;font-weight:600;font-size:.9rem;color:{s};display:flex;justify-content:space-between;user-select:none" onmouseover="this.style.background=\'#F4F6FA\'" onmouseout="this.style.background=\'\'"><span>{fq.get("question","")}</span><span style="color:{a};font-weight:400">&#43;</span></div><div style="display:none;padding:.75rem 1.5rem 1.1rem;font-size:.875rem;color:#4A5568;line-height:1.7;border-top:1px solid #DDE3EE">{fq.get("answer","")}</div></div>'

    svc_options = "".join(f'<option>{sv.get("name","")}</option>' for sv in svcs) + "<option>Other</option>"
    vals_html = "".join(f'<span style="display:inline-block;border:1px solid {p}30;color:{p};padding:.25rem .8rem;font-size:.8rem;font-weight:600;border-radius:3px;margin:.25rem;letter-spacing:.04em">{v}</span>' for v in ab.get("values",[]))
    _proc_parts = []
    for i, pr in enumerate(procs):
        _conn = ('<div style="flex:1;height:1px;background:#DDE3EE;margin-top:24px;min-width:20px"></div>' if i < len(procs)-1 else "")
        _st = pr.get("step","01"); _ti = pr.get("title",""); _de = pr.get("desc","")
        _proc_parts.append(
            f'<div style="flex:1;min-width:150px;text-align:center;padding:0 1rem">'
            f'<div style="width:48px;height:48px;background:{p};border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:700;color:#fff;margin:0 auto 1rem">{_st}</div>'
            f'<h4 style="font-weight:700;font-size:.92rem;color:{s};margin-bottom:.35rem">{_ti}</h4>'
            f'<p style="font-size:.82rem;color:#4A5568;line-height:1.6;max-width:160px;margin:0 auto">{_de}</p>'
            f'</div>{_conn}'
        )
    proc_html = "".join(_proc_parts)

    # Pre-build corporate footer
    _cs_li = []
    for sv in svcs[:5]:
        _cs_li.append(f'<li style="margin-bottom:.4rem"><a style="font-size:.8rem;color:rgba(255,255,255,.4);text-decoration:none;cursor:pointer">{sv.get("name","")}</a></li>')
    _corp_svc_html = "".join(_cs_li)
    _cp_li = []
    for _pg_id, _pg_nm in [("about","About Us"),("blog","Insights"),("reviews","Testimonials"),("contact","Contact")]:
        _cp_li.append(f'<li style="margin-bottom:.4rem"><a style="font-size:.8rem;color:rgba(255,255,255,.4);text-decoration:none;cursor:pointer">{_pg_nm}</a></li>')
    _corp_co_html = "".join(_cp_li)
    _corp_footer = (
        f'<footer><div style="max-width:1140px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem;margin-bottom:2.5rem">'
        f'<div><div style="font-size:1.1rem;font-weight:700;color:#fff;margin-bottom:.5rem;display:flex;align-items:center;gap:.5rem">'
        f'<div style="width:28px;height:28px;background:rgba(255,255,255,.1);border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800">{name[0]}</div>{name}</div>'
        f'<p style="font-size:.82rem;color:rgba(255,255,255,.35);line-height:1.7;max-width:220px">{tg}</p></div>'
        f'<div><h4 style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.3);margin-bottom:1rem">Services</h4>'
        f'<ul style="list-style:none">{_corp_svc_html}</ul></div>'
        f'<div><h4 style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.3);margin-bottom:1rem">Company</h4>'
        f'<ul style="list-style:none">{_corp_co_html}</ul></div>'
        f'<div><h4 style="font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.3);margin-bottom:1rem">Legal</h4>'
        '<ul style="list-style:none">'
        '<li style="margin-bottom:.4rem"><a style="font-size:.8rem;color:rgba(255,255,255,.4);text-decoration:none">Privacy Policy</a></li>'
        '<li style="margin-bottom:.4rem"><a style="font-size:.8rem;color:rgba(255,255,255,.4);text-decoration:none">Terms of Service</a></li>'
        '</ul></div></div>'
        f'<div style="max-width:1140px;margin:.5rem auto 0;border-top:1px solid rgba(255,255,255,.08);padding-top:1.5rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem">'
        f'<span style="font-size:.75rem;color:rgba(255,255,255,.2)">© 2025 {name}. Generated by BizBuilder AI.</span></div></footer>'
    )
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name} | Enterprise Solutions</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Inter',sans-serif;background:#F4F6FA;color:#1A2B4A;line-height:1.65;-webkit-font-smoothing:antialiased}}
.ann{{background:{s};color:rgba(255,255,255,.7);text-align:center;padding:.45rem;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase}}
.nav{{background:#fff;border-bottom:1px solid #DDE3EE;height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;position:sticky;top:0;z-index:300}}
.nav-brand{{display:flex;align-items:center;gap:.5rem}}
.nav-logo{{width:32px;height:32px;background:{p};border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:800;color:#fff}}
.nav-name{{font-size:1.1rem;font-weight:700;color:{s};letter-spacing:-.02em}}
.nav-links{{display:flex;gap:2rem;list-style:none}}
.nav-links a{{font-size:.85rem;font-weight:500;color:#4A5568;cursor:pointer;text-decoration:none;transition:color .15s}}
.nav-links a:hover{{color:{p}}}
.psec{{display:none}}.psec.visible{{display:block}}
section{{padding:5rem 5%}}.wrap{{max-width:1140px;margin:0 auto}}
.g3{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.25rem}}
.g4{{display:grid;grid-template-columns:repeat(auto-fill,minmax(195px,1fr));gap:1rem}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:3rem;align-items:center}}
.kicker{{font-size:.7rem;font-weight:700;color:{a};text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem}}
.h2{{font-size:clamp(1.7rem,2.8vw,2.3rem);font-weight:700;color:{s};letter-spacing:-.02em;margin-bottom:.6rem;line-height:1.2}}
.sub{{color:#718096;font-size:.9rem;line-height:1.75;max-width:520px}}
img{{max-width:100%;object-fit:cover}}
footer{{background:{s};padding:4rem 5% 2rem}}
@media(max-width:768px){{.g2{{grid-template-columns:1fr}}.nav-links{{display:none}}}}
</style></head><body>
<div class="ann">{an}</div>
<nav class="nav">
  <div class="nav-brand"><div class="nav-logo">{name[0]}</div><span class="nav-name">{name}</span></div>
  <ul class="nav-links"><li><a onclick="showSection('home')">Home</a></li><li><a onclick="showSection('about')">About</a></li><li><a onclick="showSection('services')">Services</a></li><li><a onclick="showSection('blog')">Insights</a></li><li><a onclick="showSection('contact')">Contact</a></li></ul>
  <div style="display:flex;gap:.75rem">
    <button onclick="showSection('contact')" style="background:transparent;color:{p};border:1px solid {p};padding:.5rem 1.2rem;border-radius:3px;font-weight:600;font-size:.84rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.background='{p}';this.style.color='#fff'" onmouseout="this.style.background='transparent';this.style.color='{p}'">Book a Meeting</button>
    <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.5rem 1.4rem;border-radius:3px;font-weight:600;font-size:.84rem;cursor:pointer;font-family:inherit;transition:background .2s" onmouseover="this.style.background='{a}'" onmouseout="this.style.background='{p}'">{h.get("cta_primary","Get Started")}</button>
  </div>
</nav>

<div class="psec visible" id="sec-home">
<!-- Topbar announcement -->
<div style="background:{p};padding:.75rem 5%;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">
  <span style="font-size:.82rem;color:rgba(255,255,255,.7);font-weight:500">{h.get("badge","Trusted by 200+ enterprises worldwide")}</span>
  <button onclick="showSection('contact')" style="background:#fff;color:{p};border:none;padding:.35rem 1rem;border-radius:3px;font-weight:700;font-size:.78rem;cursor:pointer;font-family:inherit">Request Demo →</button>
</div>
<section style="background:#fff;padding:5.5rem 5%;border-bottom:1px solid #DDE3EE;display:flex;align-items:center;gap:5rem">
  <div style="flex:1;max-width:560px">
    <div class="kicker">{tg}</div>
    <h1 style="font-size:clamp(2rem,4vw,3.2rem);font-weight:700;line-height:1.15;letter-spacing:-.03em;color:{s};margin-bottom:1.25rem">{h.get("title",name)}</h1>
    <p style="font-size:.95rem;color:#4A5568;margin-bottom:2.25rem;max-width:460px;line-height:1.8">{h.get("subtitle",tg)}</p>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
      <button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;padding:.85rem 2rem;border-radius:3px;font-weight:600;font-size:.9rem;cursor:pointer;font-family:inherit;transition:background .2s" onmouseover="this.style.background='{a}'" onmouseout="this.style.background='{p}'">{h.get("cta_primary","Request Demo")} →</button>
      <button onclick="showSection('services')" style="background:transparent;color:{p};border:1px solid #DDE3EE;padding:.85rem 2rem;border-radius:3px;font-weight:500;font-size:.9rem;cursor:pointer;font-family:inherit;transition:all .2s" onmouseover="this.style.borderColor='{p}'" onmouseout="this.style.borderColor='#DDE3EE'">{h.get("cta_secondary","View Solutions")}</button>
    </div>
    <div style="display:flex;gap:2.5rem;margin-top:2.5rem;padding-top:2rem;border-top:1px solid #DDE3EE">
      {"".join(f'<div><div style="font-size:1.8rem;font-weight:700;color:{p};letter-spacing:-.03em">{st.get("number","")}</div><div style="font-size:.75rem;color:#718096;text-transform:uppercase;letter-spacing:.08em;margin-top:.2rem">{st.get("label","")}</div></div>' for st in stats[:3])}
    </div>
  </div>
  <div style="flex:1;max-width:460px">
    <img src="{hero_img or photos[0]}" style="width:100%;height:300px;border-radius:4px;box-shadow:0 8px 32px rgba(26,58,107,.15)" alt="Enterprise"/>
  </div>
</section>
<section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap"><div class="kicker">Solutions</div><h2 class="h2" style="margin-bottom:3rem">Our Service Portfolio</h2><div class="g3">{svc_cards}</div></div></section>
<section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Industries</div><h2 class="h2" style="margin-bottom:2.5rem">Sectors We Serve</h2><div class="g4">{ind_html}</div></div></section>
<section style="background:{s};padding:4.5rem 5%"><div class="wrap" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:rgba(255,255,255,.08);border-radius:4px;overflow:hidden">{stats_html}</div></section>
<section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap g2"><div><div class="kicker">Why Partner With Us</div><h2 class="h2">{ab.get("mission","")}</h2><div style="display:flex;flex-direction:column;gap:1rem;margin-top:1.5rem">{feat_html}</div></div><div><img src="{photos[2]}" style="width:100%;height:280px;border-radius:4px;box-shadow:0 4px 20px rgba(26,58,107,.1)" alt=""/><div style="background:#fff;border:1px solid #DDE3EE;border-radius:4px;padding:1.5rem;margin-top:1rem;text-align:center;border-top:3px solid {p}"><div style="font-weight:700;color:{s};margin-bottom:.4rem">Schedule a Consultation</div><p style="font-size:.83rem;color:#718096;margin-bottom:1.1rem">Speak with our enterprise specialists.</p><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:3px;padding:.75rem 1.75rem;font-weight:600;font-size:.85rem;cursor:pointer;font-family:inherit;transition:background .2s" onmouseover="this.style.background='{a}'" onmouseout="this.style.background='{p}'">Book Meeting →</button></div></div></div></section>
<section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Client Testimonials</div><h2 class="h2" style="margin-bottom:2.5rem">What Our Clients Say</h2><div class="g3">{testi_html}</div></div></section>
<section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap"><div class="kicker">Insights</div><h2 class="h2" style="margin-bottom:2.5rem">Latest Research &amp; Articles</h2><div class="g3">{blog_html}</div></div></section>
</div>

<div class="psec" id="sec-about"><section style="background:#fff;padding:5rem 5%"><div class="wrap g2"><div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem"><img src="{photos[0]}" style="width:100%;height:210px;border-radius:4px" alt=""/><img src="{photos[1]}" style="width:100%;height:210px;border-radius:4px;margin-top:1.5rem" alt=""/><img src="{photos[2]}" style="width:100%;height:210px;border-radius:4px" alt=""/><img src="{photos[3]}" style="width:100%;height:210px;border-radius:4px;margin-top:-1.5rem" alt=""/></div><div><div class="kicker">Our Organization</div><h2 class="h2">{ab.get("title","About Us")}</h2><p style="font-size:.95rem;color:{a};font-weight:600;border-left:3px solid {p};padding-left:1rem;margin-bottom:1.25rem;line-height:1.65">{ab.get("mission","")}</p><p style="color:#4A5568;line-height:1.85;font-size:.88rem;margin-bottom:1.5rem">{ab.get("story","")}</p><div style="margin-bottom:1.75rem">{vals_html}</div><button onclick="showSection('contact')" style="background:{p};color:#fff;border:none;border-radius:3px;padding:.85rem 2rem;font-weight:600;cursor:pointer;font-family:inherit;transition:background .2s" onmouseover="this.style.background='{a}'" onmouseout="this.style.background='{p}'">Partner With Us →</button></div></div></section><section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap"><div class="kicker">Methodology</div><h2 class="h2" style="margin-bottom:3rem">Our Engagement Process</h2><div style="display:flex;align-items:flex-start;flex-wrap:wrap;justify-content:center;gap:0;max-width:900px;margin:0 auto">{proc_html}</div></div></section></div>

<div class="psec" id="sec-services"><section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap"><div class="kicker">Solutions</div><h2 class="h2" style="margin-bottom:3rem">Our Service Portfolio</h2><div class="g3">{svc_cards}</div></div></section></div>
<div class="psec" id="sec-reviews"><section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Testimonials</div><h2 class="h2" style="margin-bottom:2.5rem">Client Experiences</h2><div class="g3">{testi_html}</div></div></section></div>
<div class="psec" id="sec-blog"><section style="background:#F4F6FA;padding:5rem 5%"><div class="wrap"><div class="kicker">Insights</div><h2 class="h2" style="margin-bottom:2.5rem">Research &amp; Articles</h2><div class="g3">{blog_html}</div></div></section><section style="background:#fff;padding:4rem 5%"><div class="wrap"><div class="kicker">FAQ</div><h2 class="h2" style="margin-bottom:1.5rem">Frequently Asked Questions</h2><div style="max-width:720px;margin:0 auto">{faq_html}</div></div></section></div>
<div class="psec" id="sec-contact"><section style="background:#fff;padding:5rem 5%"><div class="wrap"><div class="kicker">Contact</div><h2 class="h2" style="margin-bottom:.5rem">Schedule a Consultation</h2><p class="sub" style="margin-bottom:3rem">Our team responds within one business day.</p><div class="g2" style="align-items:start;gap:4rem"><div><img src="{photos[1]}" style="width:100%;height:200px;border-radius:4px;margin-bottom:1.5rem" alt=""/><div style="display:flex;flex-direction:column;gap:.85rem"><div style="display:flex;gap:.75rem;align-items:center"><div style="width:38px;height:38px;border:1px solid #DDE3EE;border-radius:3px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["support"]}</div><div><strong style="font-size:.85rem;color:{s};display:block">{ct.get("email","")}</strong><span style="font-size:.78rem;color:#718096">Email us anytime</span></div></div><div style="display:flex;gap:.75rem;align-items:center"><div style="width:38px;height:38px;border:1px solid #DDE3EE;border-radius:3px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["fast"]}</div><div><strong style="font-size:.85rem;color:{s};display:block">{ct.get("phone","")}</strong><span style="font-size:.78rem;color:#718096">Mon-Fri 9am-6pm</span></div></div><div style="display:flex;gap:.75rem;align-items:center"><div style="width:38px;height:38px;border:1px solid #DDE3EE;border-radius:3px;display:flex;align-items:center;justify-content:center;color:{p};padding:9px;flex-shrink:0">{SVG_ICONS["default"]}</div><div><strong style="font-size:.85rem;color:{s};display:block">{ct.get("address","")}</strong></div></div></div></div><div style="background:#F4F6FA;border:1px solid #DDE3EE;border-radius:4px;padding:2.5rem"><h3 style="font-size:1rem;font-weight:700;color:{s};margin-bottom:1.5rem;border-bottom:1px solid #DDE3EE;padding-bottom:1rem">Enquiry Form</h3><div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem"><div><label style="font-size:.78rem;font-weight:600;color:#4A5568;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em">First Name</label><input type="text" style="width:100%;padding:.75rem;border:1px solid #DDE3EE;border-radius:3px;font-family:inherit;font-size:.88rem;outline:none;background:#fff" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#DDE3EE'"/></div><div><label style="font-size:.78rem;font-weight:600;color:#4A5568;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em">Last Name</label><input type="text" style="width:100%;padding:.75rem;border:1px solid #DDE3EE;border-radius:3px;font-family:inherit;font-size:.88rem;outline:none;background:#fff" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#DDE3EE'"/></div></div><div style="margin-bottom:1rem"><label style="font-size:.78rem;font-weight:600;color:#4A5568;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em">Business Email</label><input type="email" style="width:100%;padding:.75rem;border:1px solid #DDE3EE;border-radius:3px;font-family:inherit;font-size:.88rem;outline:none;background:#fff" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#DDE3EE'"/></div><div style="margin-bottom:1rem"><label style="font-size:.78rem;font-weight:600;color:#4A5568;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em">Service of Interest</label><select style="width:100%;padding:.75rem;border:1px solid #DDE3EE;border-radius:3px;font-family:inherit;font-size:.88rem;outline:none;background:#fff"><option value="">-- Select --</option>{svc_options}</select></div><div style="margin-bottom:1.5rem"><label style="font-size:.78rem;font-weight:600;color:#4A5568;display:block;margin-bottom:.35rem;text-transform:uppercase;letter-spacing:.06em">Project Details</label><textarea style="width:100%;padding:.75rem;border:1px solid #DDE3EE;border-radius:3px;font-family:inherit;font-size:.88rem;outline:none;resize:vertical;min-height:100px;background:#fff" onfocus="this.style.borderColor='{p}'" onblur="this.style.borderColor='#DDE3EE'"></textarea></div><button style="width:100%;padding:.9rem;background:{p};color:#fff;border:none;border-radius:3px;font-weight:600;font-size:.9rem;cursor:pointer;font-family:inherit;letter-spacing:.02em;transition:background .2s" onmouseover="this.style.background='{a}'" onmouseout="this.style.background='{p}'" onclick="alert('Submitted. We will contact you within one business day.')">Submit Enquiry →</button><p style="text-align:center;font-size:.74rem;color:#A0AEC0;margin-top:.75rem">We respond within 1 business day.</p></div></div></div></section></div>

{_corp_footer}
""" + _PAGE_JS + """</body></html>"""
