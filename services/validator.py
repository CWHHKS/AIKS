import re
import validators
from services.domain_utils import normalize_domain

# Standard AI Categories as per SOW
ALLOWED_CATEGORIES = {
    "All",
    "AI Agents",
    "Generative AI",
    "Enterprise Automation",
    "AI Security",
    "AI Governance",
    "Data and AI Platform",
    "AI Observability",
    "Private AI",
    "Computer Vision",
    "Conversational AI",
    "Manufacturing AI",
    "Financial AI",
    "Healthcare AI",
    "Retail AI",
    "Marketing AI",
    "HR AI",
    "Developer Tools",
    "Other"
}

def sanitize_value_for_sheets(val: any) -> any:
    """
    Prevents CSV / Google Sheets Formula Injection.
    Prepends a single quote "'" to string values starting with '=', '+', '-', or '@'.
    Handles lists by converting them to '|' joined strings first or sanitizing elements.
    """
    if isinstance(val, list):
        # Join list items with ' | ' and sanitize the combined string
        joined_str = " | ".join([str(item).strip() for item in val if item is not None])
        return sanitize_value_for_sheets(joined_str)
        
    if isinstance(val, str):
        val_str = val.strip()
        # Prevent formula execution in Google Sheets
        if val_str and val_str[0] in ('=', '+', '-', '@'):
            return f"'{val_str}"
        return val_str
        
    if val is None:
        return ""
        
    return val

def validate_url(url: str) -> bool:
    """
    Checks if a URL is valid.
    """
    if not url:
        return False
    return bool(validators.url(url.strip()))

def validate_candidate(candidate: dict, min_confidence: int = 70) -> dict:
    """
    Validates a single AI Vendor candidate.
    Returns a dict containing:
        - "is_valid": bool
        - "errors": list of error message strings
        - "sanitized_data": dict of sanitized/formatted candidate data
    """
    errors = []
    sanitized = {}
    
    # 1. Company Name (Required)
    name = candidate.get("company_name", "").strip()
    if not name:
        errors.append("Company Name is required.")
    sanitized["company_name"] = sanitize_value_for_sheets(name)
    
    # 2. Official Website (Required & Valid URL)
    website = candidate.get("official_website", "").strip()
    if not website:
        errors.append("Official Website is required.")
    elif not validate_url(website):
        errors.append(f"Invalid Official Website URL: {website}")
    sanitized["official_website"] = website
    
    # 3. Normalized Domain (Auto-generated/verified)
    normalized = normalize_domain(website) if website else ""
    if not normalized:
        errors.append("Failed to generate normalized domain.")
    sanitized["normalized_domain"] = normalized
    
    # 4. Primary AI Category (Check against allowed list)
    category = candidate.get("primary_ai_category", "").strip()
    if not category:
        errors.append("Primary AI Category is required.")
    elif category not in ALLOWED_CATEGORIES:
        # Fallback to 'Other' if not matching, but log a warning
        errors.append(f"Category '{category}' is not standard. Fallback to 'Other' if necessary.")
        # If it doesn't match, we map to Other or allow it as is but warn
        
    sanitized["primary_ai_category"] = category
    
    # 5. Confidence Score (Must be >= min_confidence)
    try:
        score = int(candidate.get("confidence_score", 0))
    except (ValueError, TypeError):
        score = 0
    if score < min_confidence:
        errors.append(f"Confidence score {score} is below the minimum threshold ({min_confidence}).")
    sanitized["confidence_score"] = score
    
    # 6. Recommendation Check
    rec = candidate.get("aika_recommendation", "").strip()
    if rec not in ("Strong Candidate", "Candidate"):
        errors.append(f"Recommendation status '{rec}' is not acceptable for sheet storage.")
    sanitized["aika_recommendation"] = rec
    
    # 7. URL checks for evidence
    evidence = candidate.get("primary_evidence_url", "").strip()
    if evidence and not validate_url(evidence):
        errors.append(f"Invalid Primary Evidence URL: {evidence}")
    sanitized["primary_evidence_url"] = evidence
    
    # Sanitize remaining string / list fields
    sanitized["headquarters_country"] = sanitize_value_for_sheets(candidate.get("headquarters_country"))
    sanitized["main_ai_product"] = sanitize_value_for_sheets(candidate.get("main_ai_product"))
    sanitized["secondary_ai_categories"] = sanitize_value_for_sheets(candidate.get("secondary_ai_categories", []))
    sanitized["company_summary"] = sanitize_value_for_sheets(candidate.get("company_summary"))
    sanitized["target_customers"] = sanitize_value_for_sheets(candidate.get("target_customers", []))
    sanitized["target_industries"] = sanitize_value_for_sheets(candidate.get("target_industries", []))
    sanitized["main_use_cases"] = sanitize_value_for_sheets(candidate.get("main_use_cases", []))
    sanitized["deployment_type"] = sanitize_value_for_sheets(candidate.get("deployment_type", []))
    
    sanitized["official_product_page"] = candidate.get("official_product_page", "")
    sanitized["official_about_page"] = candidate.get("official_about_page", "")
    sanitized["official_contact_page"] = candidate.get("official_contact_page", "")
    
    sanitized["korea_presence_found"] = sanitize_value_for_sheets(candidate.get("korea_presence_found", "No evidence found"))
    sanitized["potential_korean_partner_type"] = sanitize_value_for_sheets(candidate.get("potential_korean_partner_type", []))
    sanitized["korea_market_relevance"] = sanitize_value_for_sheets(candidate.get("korea_market_relevance", ""))
    
    sanitized["b2b_product_confirmed"] = sanitize_value_for_sheets(candidate.get("b2b_product_confirmed", "Not publicly confirmed"))
    sanitized["proprietary_product_confirmed"] = sanitize_value_for_sheets(candidate.get("proprietary_product_confirmed", "Not publicly confirmed"))
    
    sanitized["additional_source_urls"] = sanitize_value_for_sheets(candidate.get("additional_source_urls", []))
    sanitized["review_status"] = candidate.get("review_status", "New")
    sanitized["processing_status"] = candidate.get("processing_status", "Completed")
    sanitized["research_notes"] = sanitize_value_for_sheets(candidate.get("research_notes", ""))
    sanitized["batch_id"] = candidate.get("batch_id", "")
    sanitized["research_date"] = candidate.get("research_date", "")
    
    # Verify optional pages if present
    for page_key in ("official_product_page", "official_about_page", "official_contact_page"):
        page_val = sanitized[page_key]
        if page_val and not validate_url(page_val):
            errors.append(f"Invalid URL for {page_key}: {page_val}")
            
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "sanitized_data": sanitized
    }
