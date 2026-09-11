import os
import json
import logging
from typing import Dict, Any, List, Optional
import google.generativeai as genai
import google.ai.generativelanguage_v1beta as glm
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def _get_gemini_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default

class GeminiClient:
    def __init__(self):
        self.api_key = _get_gemini_setting("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables or Streamlit secrets.")
        
        # Configure the SDK
        genai.configure(api_key=self.api_key)
        
        # Model configurations
        self.discovery_model_name = _get_gemini_setting("DISCOVERY_MODEL", "gemini-2.0-flash")
        self.structure_model_name = _get_gemini_setting("STRUCTURE_MODEL", "gemini-2.0-flash")
        
        # Load prompt files
        self.system_prompt = self._load_prompt("prompts/vendor_discovery_system.txt")
        self.batch_prompt_template = self._load_prompt("prompts/vendor_discovery_batch.txt")
        self.structure_prompt_template = self._load_prompt("prompts/vendor_structure.txt")
        self.partner_discovery_prompt_template = self._load_prompt("prompts/partner_discovery.txt")
        self.partner_structure_prompt_template = self._load_prompt("prompts/partner_structure.txt")
        self.news_discovery_prompt_template = self._load_prompt("prompts/news_discovery.txt")

    def _load_prompt(self, file_path: str) -> str:
        full_path = os.path.join(os.getcwd(), file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Required prompt file not found: {file_path}")
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def run_discovery_stage(self, batch_params: Dict[str, Any], existing_domains: List[str]) -> str:
        """
        Stage 1: Google Search Grounded Discovery.
        Finds AI vendor candidates matching input parameters using Google Search tools.
        """
        logger.info("Starting Stage 1: Vendor Discovery with Google Search...")
        
        # Format list of existing domains for prompt
        domains_str = "\n".join([f"- {d}" for d in existing_domains]) if existing_domains else "None"
        
        # Format user prompt
        user_prompt = self.batch_prompt_template.format(
            batch_id=batch_params.get("batch_id"),
            region=batch_params.get("region"),
            category=batch_params.get("category"),
            industries=batch_params.get("industries"),
            minimum_confidence_score=batch_params.get("minimum_confidence_score", 70),
            hyperscale_policy="Exclude major hyperscalers (Microsoft, Google, AWS, etc.)" if batch_params.get("exclude_hyperscalers", True) else "No restriction",
            korea_presence_policy=batch_params.get("korea_presence_policy", "포함하되 표시"),
            research_date=batch_params.get("research_date"),
            existing_domains=domains_str,
            preferred_sources=batch_params.get("preferred_sources", "None (Search generally)"),
            target_count=batch_params.get("target_count", 5)
        )
        
        # Define model with System Instruction and Search Grounding tool
        search_tool = glm.Tool(google_search={})
        model = genai.GenerativeModel(
            model_name=self.discovery_model_name,
            system_instruction=self.system_prompt,
            tools=[search_tool]
        )
        
        # Generate content
        response = model.generate_content(user_prompt)
        
        if not response.text:
            raise ValueError("Stage 1 received an empty response from Gemini API.")
            
        logger.info("Stage 1 completed successfully.")
        return response.text

    def run_structuring_stage(self, batch_id: str, discovery_report: str, target_count: int = 5) -> Dict[str, Any]:
        """
        Stage 2: Structuring into JSON.
        Splits the discovery report into individual candidate sections and
        structures each sequentially to prevent token limit truncation.
        """
        logger.info("Starting Stage 2: Report JSON Structuring (Sequential Candidate Parsing)...")
        
        import re
        # Split the discovery report by candidates
        sections = re.split(r'---+\s*(?=### Candidate)', discovery_report)
        if len(sections) <= 1:
            sections = re.split(r'(?=### Candidate)', discovery_report)
            
        cleaned_sections = []
        for sec in sections:
            sec_str = sec.strip()
            if "Company Name" in sec_str or "company_name" in sec_str.lower():
                cleaned_sections.append(sec_str)
                
        logger.info(f"Split discovery report into {len(cleaned_sections)} candidates for sequential structuring.")
        
        # Single candidate structuring template prompt
        single_candidate_template = """Convert the supplied single AIKA vendor research result section into a valid JSON object.
Use only information contained in the supplied section.
Do not perform new web searches.
Do not add, infer, or invent information.
Do not include explanations outside the JSON.

Use this JSON structure:
{
  "company_name": "string",
  "official_website": "string",
  "normalized_domain": "string",
  "headquarters_country": "string or null",
  "main_ai_product": "string or null",
  "primary_ai_category": "allowed category",
  "secondary_ai_categories": [],
  "company_summary": "string",
  "target_customers": [],
  "target_industries": [],
  "main_use_cases": [],
  "deployment_type": [],
  "official_product_page": "string or null",
  "official_about_page": "string or null",
  "official_contact_page": "string or null",
  "korea_presence_found": "Yes | No evidence found | Review Required",
  "potential_korean_partner_type": [],
  "korea_market_relevance": "string",
  "b2b_product_confirmed": "Yes | No | Not publicly confirmed",
  "proprietary_product_confirmed": "Yes | No | Not publicly confirmed",
  "confidence_score": 0,
  "aika_recommendation": "Strong Candidate | Candidate",
  "primary_evidence_url": "string",
  "additional_source_urls": [],
  "review_status": "New",
  "processing_status": "Completed",
  "research_notes": "string or null"
}

Separate multiple values as JSON arrays.
Use null for unavailable single-value fields.
Use an empty array for unavailable multiple-value fields.

CRITICAL FORMATTING FOR SPREADSHEETS:
For "company_summary" and "korea_market_relevance", format the text with logical line breaks (using \\n) to separate key points into short, highly readable paragraphs (e.g. max 2-3 sentences per paragraph, or bullet points separated by \\n). This is required for visual formatting in sheets.
"""

        parsed_candidates = []
        model = genai.GenerativeModel(model_name=self.structure_model_name)
        
        for i, section_text in enumerate(cleaned_sections):
            logger.info(f"Structuring candidate {i+1} of {len(cleaned_sections)}...")
            user_prompt = f"{single_candidate_template}\n\nRESEARCH REPORT SECTION TO STRUCTURE:\n{section_text}"
            
            try:
                response = model.generate_content(
                    user_prompt,
                    generation_config={
                        "response_mime_type": "application/json"
                    }
                )
                
                if response.text:
                    cand_data = json.loads(response.text)
                    if isinstance(cand_data, list):
                        for item in cand_data:
                            if isinstance(item, dict):
                                parsed_candidates.append(item)
                                logger.info(f"Successfully structured candidate {i+1}: {item.get('company_name', 'Unknown')}")
                    elif isinstance(cand_data, dict):
                        parsed_candidates.append(cand_data)
                        logger.info(f"Successfully structured candidate {i+1}: {cand_data.get('company_name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Failed to structure candidate {i+1}: {str(e)}")
                continue
                
        # Limit to target_count if needed
        final_candidates = parsed_candidates[:target_count]
        
        combined_result = {
            "batch_id": batch_id,
            "requested_count": target_count,
            "verified_count": len(final_candidates),
            "candidates": final_candidates
        }
        
        logger.info(f"Stage 2 completed successfully. Structured {len(final_candidates)} candidates.")
        return combined_result

    def run_partner_discovery_stage(self, batch_params: Dict[str, Any], existing_domains: List[str]) -> str:
        """
        Stage 1: Google Search Grounded Partner Discovery.
        Finds domestic partners/resellers for the given vendor or category.
        """
        logger.info("Starting Stage 1: Partner Discovery with Google Search...")
        
        # Format list of existing domains for prompt
        domains_str = "\n".join([f"- {d}" for d in existing_domains]) if existing_domains else "None"
        
        # Format user prompt
        user_prompt = self.partner_discovery_prompt_template.format(
            batch_id=batch_params.get("batch_id"),
            vendor_match=batch_params.get("vendor_match", "None (General search)"),
            category=batch_params.get("category"),
            industries=batch_params.get("industries"),
            minimum_confidence_score=batch_params.get("minimum_confidence_score", 70),
            research_date=batch_params.get("research_date"),
            existing_domains=domains_str,
            preferred_sources=batch_params.get("preferred_sources", "None (Search generally)"),
            target_count=batch_params.get("target_count", 5),
            max_discovery_candidates=batch_params.get("max_discovery_candidates", 15),
            exclude_small_policy="Exclude small boutique agencies. Prioritize mid-to-large SIs, MSPs, and established IT distributors." if batch_params.get("exclude_small_agencies", True) else "No restriction on partner scale."
        )
        
        # Define model with System Instruction and Search Grounding tool
        search_tool = glm.Tool(google_search={})
        model = genai.GenerativeModel(
            model_name=self.discovery_model_name,
            system_instruction=self.system_prompt,
            tools=[search_tool]
        )
        
        # Generate content
        response = model.generate_content(user_prompt)
        
        if not response.text:
            raise ValueError("Stage 1 received an empty response from Gemini API for partners.")
            
        logger.info("Stage 1 Partner Discovery completed successfully.")
        return response.text

    def run_partner_structuring_stage(self, batch_id: str, discovery_report: str, target_count: int = 5) -> Dict[str, Any]:
        """
        Stage 2: Structuring partners into JSON.
        """
        logger.info("Starting Stage 2: Partner Report JSON Structuring (Sequential Candidate Parsing)...")
        
        import re
        sections = re.split(r'---+\s*(?=### Candidate)', discovery_report)
        if len(sections) <= 1:
            sections = re.split(r'(?=### Candidate)', discovery_report)
            
        cleaned_sections = []
        for sec in sections:
            sec_str = sec.strip()
            if "Company Name" in sec_str or "company_name" in sec_str.lower():
                cleaned_sections.append(sec_str)
                
        logger.info(f"Split partner discovery report into {len(cleaned_sections)} candidates for sequential structuring.")
        
        # Single partner structuring template prompt
        single_partner_template = """Convert the supplied single AIKA Korean partner/reseller research result section into a valid JSON object.
Use only information contained in the supplied section.
Do not perform new web searches.
Do not add, infer, or invent information.
Do not include explanations outside the JSON.

Use this JSON structure:
{
  "company_name": "string",
  "official_website": "string",
  "normalized_domain": "string",
  "headquarters_country": "South Korea",
  "main_ai_product": "string or null",
  "primary_ai_category": "allowed category",
  "secondary_ai_categories": [],
  "company_summary": "string",
  "target_customers": [],
  "target_industries": [],
  "main_use_cases": [],
  "deployment_type": [],
  "official_product_page": "string or null",
  "official_about_page": "string or null",
  "official_contact_page": "string or null",
  "korea_presence_found": "Yes",
  "potential_korean_partner_type": [],
  "korea_market_relevance": "string",
  "b2b_product_confirmed": "Yes",
  "proprietary_product_confirmed": "Yes",
  "confidence_score": 0,
  "aika_recommendation": "Strong Partner | Partner",
  "primary_evidence_url": "string",
  "additional_source_urls": [],
  "review_status": "New",
  "processing_status": "Completed",
  "research_notes": "string or null"
}

Separate multiple values as JSON arrays.
Use null for unavailable single-value fields.
Use an empty array for unavailable multiple-value fields.

CRITICAL FORMATTING FOR SPREADSHEETS:
For "company_summary" and "korea_market_relevance", format the text with logical line breaks (using \\n) to separate key points into short, highly readable paragraphs (e.g. max 2-3 sentences per paragraph, or bullet points separated by \\n). This is required for visual formatting in sheets.
"""

        parsed_partners = []
        model = genai.GenerativeModel(model_name=self.structure_model_name)
        
        for i, section_text in enumerate(cleaned_sections):
            logger.info(f"Structuring partner {i+1} of {len(cleaned_sections)}...")
            user_prompt = f"{single_partner_template}\n\nRESEARCH REPORT SECTION TO STRUCTURE:\n{section_text}"
            
            try:
                response = model.generate_content(
                    user_prompt,
                    generation_config={
                        "response_mime_type": "application/json"
                    }
                )
                
                if response.text:
                    cand_data = json.loads(response.text)
                    if isinstance(cand_data, list):
                        for item in cand_data:
                            if isinstance(item, dict):
                                parsed_partners.append(item)
                                logger.info(f"Successfully structured partner {i+1}: {item.get('company_name', 'Unknown')}")
                    elif isinstance(cand_data, dict):
                        parsed_partners.append(cand_data)
                        logger.info(f"Successfully structured partner {i+1}: {cand_data.get('company_name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Failed to structure partner {i+1}: {str(e)}")
                continue
                
        final_partners = parsed_partners[:target_count]
        
        combined_result = {
            "batch_id": batch_id,
            "requested_count": target_count,
            "verified_count": len(final_partners),
            "candidates": final_partners
        }
        
        logger.info(f"Stage 2 completed successfully. Structured {len(final_partners)} partners.")
        return combined_result

    def run_news_discovery_stage(self, batch_params: Dict[str, Any], existing_urls: List[str]) -> str:
        """
        Stage 1: Google Search Grounded News Discovery.
        Finds AI news articles matching input parameters.
        """
        logger.info("Starting Stage 1: News Discovery with Google Search...")
        
        urls_str = "\n".join([f"- {u}" for u in existing_urls]) if existing_urls else "None"
        
        user_prompt = self.news_discovery_prompt_template.format(
            batch_id=batch_params.get("batch_id"),
            primary_category=batch_params.get("primary_category", "All"),
            news_topic=batch_params.get("news_topic", "All"),
            language=batch_params.get("language", "All (EN + KO)"),
            target_count=batch_params.get("target_count", 5),
            research_date=batch_params.get("research_date"),
            preferred_sources=batch_params.get("preferred_sources", "None"),
            existing_urls=urls_str
        )
        
        search_tool = glm.Tool(google_search={})
        model = genai.GenerativeModel(
            model_name=self.discovery_model_name,
            system_instruction=self.system_prompt,
            tools=[search_tool]
        )
        
        response = model.generate_content(user_prompt)
        
        if not response.text:
            raise ValueError("Stage 1 received an empty response from Gemini API for news.")
            
        logger.info("Stage 1 News Discovery completed successfully.")
        return response.text

    def run_news_structuring_stage(self, batch_id: str, discovery_report: str, target_count: int = 5) -> Dict[str, Any]:
        """
        Stage 2: Structuring news articles into JSON.
        """
        logger.info("Starting Stage 2: News Report JSON Structuring...")
        
        import re
        sections = re.split(r'---+\s*(?=### Article)', discovery_report)
        if len(sections) <= 1:
            sections = re.split(r'(?=### Article)', discovery_report)
            
        cleaned_sections = []
        for sec in sections:
            sec_str = sec.strip()
            if "Title" in sec_str or "title" in sec_str.lower():
                cleaned_sections.append(sec_str)
                
        logger.info(f"Split news report into {len(cleaned_sections)} articles for sequential structuring.")
        
        single_news_template = """Convert the supplied single AIKA AI news research result section into a valid JSON object.
Use only information contained in the supplied section.
Do not perform new web searches.
Do not add, infer, or invent information.
Do not include explanations outside the JSON.

Use this JSON structure:
{
  "title": "original title in article language",
  "korean_title": "Korean translation of the title (or same if already Korean)",
  "source_media": "string",
  "source_url": "string",
  "published_date": "YYYY-MM-DD",
  "language": "EN or KO",
  "primary_ai_category": "allowed category",
  "news_topic": "news topic",
  "related_companies": "string",
  "korean_summary": "1-2 sentence concise summary in Korean",
  "detailed_summary": "10 structured bullet points summary in Korean detailing facts, tech, impact, and takeaways",
  "key_keywords": "string in Korean",
  "korea_market_relevance": "High | Medium | Low",
  "review_status": "New",
  "research_notes": "Korean notes or null"
}


"""

        parsed_articles = []
        model = genai.GenerativeModel(model_name=self.structure_model_name)
        
        for i, section_text in enumerate(cleaned_sections):
            logger.info(f"Structuring news article {i+1} of {len(cleaned_sections)}...")
            user_prompt = f"{single_news_template}\n\nRESEARCH REPORT SECTION TO STRUCTURE:\n{section_text}"
            
            try:
                response = model.generate_content(
                    user_prompt,
                    generation_config={
                        "response_mime_type": "application/json"
                    }
                )
                
                if response.text:
                    cand_data = json.loads(response.text)
                    if isinstance(cand_data, list):
                        for item in cand_data:
                            if isinstance(item, dict):
                                parsed_articles.append(item)
                    elif isinstance(cand_data, dict):
                        parsed_articles.append(cand_data)
            except Exception as e:
                logger.error(f"Failed to structure news article {i+1}: {str(e)}")
                continue
                
        final_articles = parsed_articles[:target_count]
        
        combined_result = {
            "batch_id": batch_id,
            "requested_count": target_count,
            "verified_count": len(final_articles),
            "candidates": final_articles
        }
        
        logger.info(f"Stage 2 completed successfully. Structured {len(final_articles)} news articles.")
        return combined_result

    def test_connection(self) -> bool:
        """
        Tests if the Gemini API key is valid by running a lightweight call.
        """
        try:
            model = genai.GenerativeModel(self.discovery_model_name)
            response = model.generate_content("hello")
            return response.text is not None and len(response.text) > 0
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False

