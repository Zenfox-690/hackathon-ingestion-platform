import re
from typing import Any, Dict, List, Optional

from utils.dates import normalize_date

KNOWN_PROVIDERS = [
    {
        "provider": "AWS",
        "name": "AWS Cloud Credits",
        "category": "Cloud Credits",
        "keywords": [r"\baws\b", r"\bamazon web services\b", r"\bamazon bedrock\b", r"\baws activate\b"],
        "default_desc": "Cloud compute and AI services credits provided by Amazon Web Services for hackathon projects.",
        "default_eligibility": "Registered participants building on AWS cloud infrastructure.",
    },
    {
        "provider": "Google Cloud",
        "name": "Google Cloud Credits",
        "category": "Cloud Credits",
        "keywords": [r"\bgoogle cloud\b", r"\bgcp\b", r"\bvertex ai\b", r"\bgemini api\b"],
        "default_desc": "Google Cloud Platform compute and Vertex AI / Gemini API credits for participating teams.",
        "default_eligibility": "Registered teams deploying solutions on Google Cloud Platform.",
    },
    {
        "provider": "Microsoft Azure",
        "name": "Microsoft Azure Credits",
        "category": "Cloud Credits",
        "keywords": [r"\bazure\b", r"\bmicrosoft azure\b", r"\bmicrosoft for startups\b", r"\bazure openai\b"],
        "default_desc": "Microsoft Azure cloud computing and OpenAI service credits.",
        "default_eligibility": "Active participants deploying project prototypes to Microsoft Azure.",
    },
    {
        "provider": "OpenAI",
        "name": "OpenAI API Credits",
        "category": "API Credits",
        "keywords": [r"\bopenai\b", r"\bchatgpt api\b", r"\bgpt-4o\b"],
        "default_desc": "Developer API credits for integrating OpenAI models and assistants into hackathon projects.",
        "default_eligibility": "Participants integrating OpenAI API endpoints into their hackathon build.",
    },
    {
        "provider": "Twilio",
        "name": "Twilio API Credits",
        "category": "API Credits",
        "keywords": [r"\btwilio\b", r"\bsendgrid\b"],
        "default_desc": "Communication API credits (SMS, Voice, Messaging) from Twilio.",
        "default_eligibility": "Projects incorporating Twilio or SendGrid communication services.",
    },
    {
        "provider": "MongoDB",
        "name": "MongoDB Atlas Credits",
        "category": "Developer Tools",
        "keywords": [r"\bmongodb\b", r"\bmongodb atlas\b"],
        "default_desc": "Database hosting credits and vector search developer perks on MongoDB Atlas.",
        "default_eligibility": "Participants using MongoDB Atlas as their database layer.",
    },
    {
        "provider": "GitHub",
        "name": "GitHub Developer Perks",
        "category": "Developer Tools",
        "keywords": [r"\bgithub\b", r"\bgithub copilot\b", r"\bgithub student\b"],
        "default_desc": "Developer tools, GitHub Copilot access, and student developer pack benefits.",
        "default_eligibility": "Registered student developers with active GitHub accounts.",
    },
]


class BenefitDict(dict):
    """Dictionary supporting both item and attribute access for backward compatibility."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'BenefitDict' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value


def extract_special_benefits(
    hackathon_data: Optional[Dict[str, Any]] = None,
    text: Optional[str] = None,
    event_name: Optional[str] = None,
    source_url: Optional[str] = None,
    hackathon_deadline: Optional[str] = None,
    **kwargs,
) -> List[BenefitDict]:
    """
    Extracts explicitly advertised participant benefits, cloud credits, and developer tools.

    Guarantees:
    - Never copies the hackathon registration deadline into benefit application deadline.
    - If a separate deadline is not explicitly advertised, application_deadline is None (unknown).
    - Preserves official source/evidence URL for verification.
    - Distinguishes verified terms from unverified mentions.
    """
    if hackathon_data is None:
        hackathon_data = {}

    benefits: List[BenefitDict] = []
    seen_providers = set()

    # Aggregate all available text fields
    name = str(event_name or hackathon_data.get("name") or hackathon_data.get("title") or "")
    description = str(hackathon_data.get("description") or "")
    prize = str(hackathon_data.get("prize") or "")
    src_url = str(source_url or hackathon_data.get("link") or hackathon_data.get("url") or "")
    tags = hackathon_data.get("tags") or []
    tags_str = " ".join(str(t) for t in tags)

    full_text = f"{text or ''} {name} {description} {prize} {tags_str}".strip()
    full_text_lower = full_text.lower()

    # Search for separate application cues
    has_separate_app = bool(
        re.search(
            r"\b(separate application|apply separately|fill (?:out )?the form|credit request form|apply for credits|claim form|application form|request credits before|redeem via)\b",
            full_text_lower,
        )
    )

    # Exclude explicit negative cues: "no separate application", "without separate application"
    if re.search(
        r"\b(no separate application|without separate application|not require(?:d)? (?:a )?separate application)\b",
        full_text_lower,
    ):
        has_separate_app = False

    # Search for external form URLs if any
    form_url_match = re.search(
        r"https?://(?:forms\.gle|docs\.google\.com/forms|airtable\.com|typeform\.com|tally\.so)/[^\s\"'>]+",
        full_text,
    )
    application_url = form_url_match.group(0).rstrip(".") if form_url_match else None
    if application_url:
        has_separate_app = True

    # Search specifically for a credit/benefit-specific deadline (NOT the hackathon registration deadline!)
    benefit_deadline_match = re.search(
        r"\b(?:credit|credits|benefit|benefits|grant|perk|early[\s-]bird)\s+(?:application\s+)?deadline\s*(?:is\s*)?[:\-]?\s*([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2})",
        full_text,
        re.IGNORECASE,
    )
    application_deadline = None
    if benefit_deadline_match:
        raw_deadline_str = benefit_deadline_match.group(1)
        application_deadline = normalize_date(raw_deadline_str)

    # Match known providers
    for p in KNOWN_PROVIDERS:
        matched = False
        for kw in p["keywords"]:
            if re.search(kw, full_text_lower):
                matched = True
                break

        if matched and p["provider"] not in seen_providers:
            seen_providers.add(p["provider"])

            # Check if dollar amount of credits is explicitly mentioned
            amount_match = re.search(
                rf"(?<!\w)(\$\d+(?:,\d+)?|\d+\s*(?:k|usd))\s*(?:in\s*)?{p['provider']}",
                full_text,
                re.IGNORECASE,
            )
            if not amount_match:
                amount_match = re.search(
                    r"(?<!\w)(\$\d+(?:,\d+)?\s*(?:in\s*)?(?:cloud|api|compute)?\s*credits?)\b",
                    full_text,
                    re.IGNORECASE,
                )

            desc = p["default_desc"]
            confidence = "unverified"

            if amount_match:
                desc = f"{amount_match.group(1)} in {p['name']} for participating developers."
                confidence = "verified"
            elif any(k in description.lower() or k in prize.lower() for k in [p["provider"].lower()]):
                confidence = "verified"

            benefit_item = {
                "id": f"{hackathon_data.get('fingerprint', 'hack')[:8]}-{p['provider'].lower()}",
                "name": p["name"],
                "category": p["category"],
                "description": desc,
                "requires_separate_application": has_separate_app,
                "application_deadline": application_deadline,
                "application_url": application_url,
                "source_url": src_url,
                "eligibility": p["default_eligibility"],
                "confidence": confidence,
            }
            benefits.append(BenefitDict(benefit_item))

    # Generic credit discovery if no known provider matched but credits explicitly advertised
    if not benefits:
        generic_credit_match = re.search(
            r"\b(\$\d+(?:,\d+)?\s*(?:in\s*)?(?:cloud|api|compute|developer)?\s*credits?)\b",
            full_text,
            re.IGNORECASE,
        )
        if generic_credit_match:
            credit_phrase = generic_credit_match.group(1)
            benefits.append(
                BenefitDict(
                    {
                        "id": f"{hackathon_data.get('fingerprint', 'hack')[:8]}-credits",
                        "name": "Participant Developer Credits",
                        "category": "Cloud Credits",
                        "description": f"{credit_phrase} advertised for participants.",
                        "requires_separate_application": has_separate_app,
                        "application_deadline": application_deadline,
                        "application_url": application_url,
                        "source_url": src_url,
                        "eligibility": "Registered participants according to hackathon rules.",
                        "confidence": "verified" if has_separate_app or application_url else "unverified",
                    }
                )
            )

    return benefits
