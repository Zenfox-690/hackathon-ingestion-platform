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
    },
    {
        "provider": "Google Cloud",
        "name": "Google Cloud Credits",
        "category": "Cloud Credits",
        "keywords": [r"\bgoogle cloud\b", r"\bgcp\b", r"\bvertex ai\b", r"\bgemini api\b"],
        "default_desc": "Google Cloud Platform compute and Vertex AI / Gemini API credits for participating teams.",
    },
    {
        "provider": "Microsoft Azure",
        "name": "Microsoft Azure Credits",
        "category": "Cloud Credits",
        "keywords": [r"\bazure\b", r"\bmicrosoft azure\b", r"\bmicrosoft for startups\b", r"\bazure openai\b"],
        "default_desc": "Microsoft Azure cloud computing and OpenAI service credits.",
    },
    {
        "provider": "OpenAI",
        "name": "OpenAI API Credits",
        "category": "API Credits",
        "keywords": [r"\bopenai\b", r"\bchatgpt api\b", r"\bgpt-4o\b"],
        "default_desc": "Developer API credits for integrating OpenAI models and assistants into hackathon projects.",
    },
    {
        "provider": "Twilio",
        "name": "Twilio API Credits",
        "category": "API Credits",
        "keywords": [r"\btwilio\b", r"\bsendgrid\b"],
        "default_desc": "Communication API credits (SMS, Voice, Messaging) from Twilio.",
    },
    {
        "provider": "MongoDB",
        "name": "MongoDB Atlas Credits",
        "category": "Developer Tools",
        "keywords": [r"\bmongodb\b", r"\bmongodb atlas\b"],
        "default_desc": "Database hosting credits and vector search developer perks on MongoDB Atlas.",
    },
    {
        "provider": "GitHub",
        "name": "GitHub Developer Perks",
        "category": "Developer Tools",
        "keywords": [r"\bgithub\b", r"\bgithub copilot\b", r"\bgithub student\b"],
        "default_desc": "Developer tools, GitHub Copilot access, and student developer pack benefits.",
    },
]

PERK_TERMS = re.compile(
    r"\b(credits?|vouchers?|perks?|tokens?|compute|api\s+access|developer\s+pack|free\s+tier|activate)\b",
    re.IGNORECASE,
)


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
    Extracts participant benefits, cloud credits, and developer tools only when
    supported by explicit source evidence.

    Guarantees:
    - Never marks a benefit verified merely because a provider name appears in the title, tags, or sponsor list.
    - Requires an actual credit/perk claim supported by source text.
    - Preserves unknown eligibility/deadlines as None instead of fabricating boilerplate.
    - Does not cross-attribute credit amounts or separate credit forms to unrelated providers.
    - Never interprets early-bird or hackathon registration deadlines as benefit deadlines.
    """
    if hackathon_data is None:
        hackathon_data = {}

    benefits: List[BenefitDict] = []
    seen_providers = set()

    description = str(hackathon_data.get("description") or "")
    src_url = str(source_url or hackathon_data.get("link") or hackathon_data.get("url") or "")

    # Primary content body where benefit claims are made
    body_text = f"{text or ''} {description}".strip()
    body_text_lower = body_text.lower()

    if not body_text:
        return []

    # Search for separate credit application cues (linked to credits or benefits, not generic registration)
    has_separate_app = bool(
        re.search(
            r"\b(credit\s+request\s+form|apply\s+for\s+(?:your\s+)?credits?|voucher\s+form|claim\s+credits|request\s+credits|redeem\s+(?:credits?|voucher))\b",
            body_text_lower,
        )
    )

    if re.search(
        r"\b(no\s+separate\s+application|without\s+separate\s+application|not\s+require(?:d)?\s+(?:a\s+)?separate\s+application)\b",
        body_text_lower,
    ):
        has_separate_app = False

    # Search for dedicated credit/benefit form URL (must be associated with credits/perks, not general event registration)
    application_url = None
    form_matches = re.finditer(
        r"https?://(?:forms\.gle|docs\.google\.com/forms|airtable\.com|typeform\.com|tally\.so)/[^\s\"'>]+",
        body_text,
    )
    for fm in form_matches:
        url = fm.group(0).rstrip(".")
        # Check window around URL (100 chars before and after) for credit/perk context
        start = max(0, fm.start() - 100)
        end = min(len(body_text), fm.end() + 100)
        context = body_text[start:end].lower()
        if any(w in context for w in ["credit", "voucher", "perk", "claim", "aws", "gcp", "azure", "openai"]):
            application_url = url
            has_separate_app = True
            break

    # Search specifically for a credit/benefit-specific deadline (NOT early-bird or registration deadline!)
    benefit_deadline_match = re.search(
        r"\b(?:credit|credits|voucher|perk)\s+(?:application\s+)?deadline\s*(?:is\s*)?[:\-]?\s*([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2})",
        body_text,
        re.IGNORECASE,
    )
    application_deadline = None
    if benefit_deadline_match:
        raw_deadline_str = benefit_deadline_match.group(1)
        application_deadline = normalize_date(raw_deadline_str)

    # Extract source-supported eligibility if present, otherwise leave None
    eligibility_match = re.search(
        r"\b(?:eligibility|eligible\s+teams|open\s+to)\s*:\s*([^.\n]+)",
        body_text,
        re.IGNORECASE,
    )
    extracted_eligibility = eligibility_match.group(1).strip() if eligibility_match else None

    # Match known providers with explicit perk/credit context
    for p in KNOWN_PROVIDERS:
        matched = False
        matched_kw = None
        for kw in p["keywords"]:
            if re.search(kw, body_text_lower):
                matched = True
                matched_kw = kw
                break

        if not matched or p["provider"] in seen_providers:
            continue

        # Critical: Verify that the provider is mentioned in the context of credits/perks/tools
        # A bare mention of a sponsor name or title does NOT constitute a participant benefit!
        perk_in_context = False
        for sentence in re.split(r"[.\n;]", body_text):
            if matched_kw and re.search(matched_kw, sentence, re.IGNORECASE):
                if PERK_TERMS.search(sentence):
                    perk_in_context = True
                    break

        if not perk_in_context:
            continue

        seen_providers.add(p["provider"])

        # Check if a specific dollar amount is linked directly to this provider
        # Avoid stealing amounts belonging to other providers
        amount_match = re.search(
            rf"(?<!\w)(\$\d+(?:,\d+)?|\d+\s*(?:k|usd))\s*(?:in\s*)?{p['provider']}",
            body_text,
            re.IGNORECASE,
        )
        if not amount_match:
            amount_match = re.search(
                rf"{p['provider']}\s*(?:[a-zA-Z\s]{{0,30}})?(\$\d+(?:,\d+)?|\d+\s*(?:k|usd))\s*(?:in\s*)?credits?",
                body_text,
                re.IGNORECASE,
            )

        if amount_match:
            desc = f"{amount_match.group(1)} in {p['name']} for participating developers."
            confidence = "verified"
        else:
            desc = p["default_desc"]
            confidence = "verified" if has_separate_app or application_url or perk_in_context else "unverified"

        benefit_item = {
            "id": f"{hackathon_data.get('fingerprint', 'hack')[:8]}-{p['provider'].lower()}",
            "name": p["name"],
            "category": p["category"],
            "description": desc,
            "requires_separate_application": has_separate_app,
            "application_deadline": application_deadline,
            "application_url": application_url,
            "source_url": src_url,
            "eligibility": extracted_eligibility,
            "confidence": confidence,
        }
        benefits.append(BenefitDict(benefit_item))

    return benefits
