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
class SafeDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"

class OperationCancelledException(Exception):
    """Raised when user requests early termination of long-running news discovery/analysis."""
    def __init__(self, message: str = "Operation was cancelled by user.", partial_data: Any = None):
        super().__init__(message)
        self.partial_data = partial_data

class GeminiClient:
    def __init__(self):
        self.api_key = _get_gemini_setting("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables or Streamlit secrets.")
        
        # Configure the SDK
        genai.configure(api_key=self.api_key)
        
        # Model configurations
        raw_discovery = _get_gemini_setting("DISCOVERY_MODEL", "gemini-2.5-flash")
        raw_structure = _get_gemini_setting("STRUCTURE_MODEL", "gemini-2.5-flash")
        self.discovery_model_name = raw_discovery if raw_discovery and "perplexity" not in raw_discovery.lower() else "gemini-2.5-flash"
        self.structure_model_name = raw_structure if raw_structure and "perplexity" not in raw_structure.lower() else "gemini-2.5-flash"
        
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

    def _is_within_48h(self, pub_date_str: str, research_date_str: Optional[str] = None) -> bool:
        """Explicitly checks if published_date string is within 48 hours."""
        if not pub_date_str or not isinstance(pub_date_str, str):
            return True
        try:
            from datetime import datetime
            clean_pub = pub_date_str.split("T")[0].split(" ")[0].strip()
            pub_dt = datetime.strptime(clean_pub, "%Y-%m-%d")
            
            ref_dt = datetime.now()
            if research_date_str:
                try:
                    ref_dt = datetime.strptime(research_date_str.split("T")[0].split(" ")[0].strip(), "%Y-%m-%d")
                except Exception:
                    pass
            
            diff = (ref_dt - pub_dt).days
            return -1 <= diff <= 2
        except Exception:
            return True

    def run_discovery_stage(self, batch_params: Dict[str, Any], existing_domains: List[str]) -> str:
        """
        Stage 1: Google Search Grounded Discovery.
        Finds AI vendor candidates matching input parameters using Google Search tools.
        """
        logger.info("Starting Stage 1: Vendor Discovery with Google Search...")
        
        # Format list of existing domains for prompt
        domains_str = "\n".join([f"- {d}" for d in existing_domains]) if existing_domains else "None"
        
        # Format user prompt
        user_prompt = self.batch_prompt_template.format_map(SafeDict({
            "batch_id": batch_params.get("batch_id", ""),
            "region": batch_params.get("region", ""),
            "category": batch_params.get("category", ""),
            "industries": batch_params.get("industries", ""),
            "minimum_confidence_score": batch_params.get("minimum_confidence_score", 70),
            "hyperscale_policy": "Exclude major hyperscalers (Microsoft, Google, AWS, etc.)" if batch_params.get("exclude_hyperscalers", True) else "No restriction",
            "korea_presence_policy": batch_params.get("korea_presence_policy", "포함하되 표시"),
            "research_date": batch_params.get("research_date", ""),
            "existing_domains": domains_str,
            "preferred_sources": batch_params.get("preferred_sources", "None (Search generally)"),
            "target_count": batch_params.get("target_count", 5)
        }))
        
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
        user_prompt = self.partner_discovery_prompt_template.format_map(SafeDict({
            "batch_id": batch_params.get("batch_id", ""),
            "vendor_match": batch_params.get("vendor_match", "None (General search)"),
            "category": batch_params.get("category", ""),
            "industries": batch_params.get("industries", ""),
            "minimum_confidence_score": batch_params.get("minimum_confidence_score", 70),
            "research_date": batch_params.get("research_date", ""),
            "existing_domains": domains_str,
            "preferred_sources": batch_params.get("preferred_sources", "None (Search generally)"),
            "target_count": batch_params.get("target_count", 5),
            "max_discovery_candidates": batch_params.get("max_discovery_candidates", 15),
            "exclude_small_policy": "Exclude small boutique agencies. Prioritize mid-to-large SIs, MSPs, and established IT distributors." if batch_params.get("exclude_small_agencies", True) else "No restriction on partner scale."
        }))
        
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
        
        # Dynamically reload prompt template to ensure disk edits take effect immediately
        self.news_discovery_prompt_template = self._load_prompt("prompts/news_discovery.txt")
        
        urls_str = "\n".join([f"- {u}" for u in existing_urls]) if existing_urls else "None"
        
        user_prompt = self.news_discovery_prompt_template.format_map(SafeDict({
            "batch_id": batch_params.get("batch_id", ""),
            "primary_category": batch_params.get("primary_category", "All"),
            "news_topic": batch_params.get("news_topic", "All"),
            "language": batch_params.get("language", "All (EN + KO)"),
            "target_count": batch_params.get("target_count", 5),
            "research_date": batch_params.get("research_date", ""),
            "since_date": batch_params.get("since_date", "30 days ago"),
            "preferred_sources": batch_params.get("preferred_sources", "None"),
            "existing_urls": urls_str
        }))
        
        custom_directive = batch_params.get("custom_prompt_directive", "").strip()
        skill_preset = batch_params.get("skill_preset", "").strip()
        if custom_directive or skill_preset:
            user_prompt += f"\n\n[APPLIED SKILL & USER PROMPT DIRECTIVES]\n- Skill Rule: {skill_preset}\n- Custom User Directive: {custom_directive}\nStrictly prioritize and obey these directives during search and summarization."

        curr_year = batch_params.get("research_date", "2026")[:4]
        since_val = batch_params.get("since_date", "")
        recency_str = f"published ON OR AFTER {since_val}" if since_val else f"published in the CURRENT YEAR ({curr_year}) and recent 30 days"
        news_system_prompt = (
            "You are a professional AI industry journalist and news intelligence analyst for AIKA (AI Korea Access).\n"
            "Your objective is to find, verify, and summarize the latest high-impact AI technology and business news.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Ground all findings in real Google Search results.\n"
            f"2. STRICT RECENCY MANDATE: Search ONLY for fresh, breaking news {recency_str}. REJECT and DO NOT RETURN outdated articles published before this period.\n"
            "3. MULTI-SOURCE CONSENSUS: For every AI news event, find AT LEAST 3 DIFFERENT MEDIA OUTLETS (e.g. ZDNet Korea, ETNews, Digital Daily, Yonhap News, Naver News) covering the exact same event. List all 3+ URLs under 'Reference URLs'.\n"
            "4. SOURCE URL INTEGRITY: You MUST provide exact, live, working article URLs discovered from search. NEVER invent, guess, or hallucinate URLs.\n"
            "5. If an article is in English, always provide an accurate, natural Korean title translation alongside the original title.\n"
            "6. Provide high-quality Korean summaries and structured 10-line breakdown bullet points.\n"
            "7. SPECIALIZED AI PORTALS MANDATE: Strictly prioritize searching and selecting articles from specialized AI portals: AI Times (aitimes.com, aitimes.kr) for Korean news and AI News (artificialintelligence-news.com) for global news."
        )
        
        real_grounding_urls = []
        pipeline_mode = os.getenv("PIPELINE_MODE", "standard").strip().lower()

        if pipeline_mode == "reversed":
            logger.info("🔄 [REVERSED MODE] Running Stage 1 News Discovery with GPT-4o...")
            raw_text = self._fallback_openai_discovery(user_prompt, news_system_prompt)
            self._last_grounding_urls = []
            return raw_text

        try:
            search_tool = glm.Tool(google_search={})
            model = genai.GenerativeModel(
                model_name=self.discovery_model_name,
                system_instruction=news_system_prompt,
                tools=[search_tool]
            )
            response = model.generate_content(user_prompt)
            raw_text = ""
            if response.candidates and hasattr(response.candidates[0], "content") and response.candidates[0].content and hasattr(response.candidates[0].content, "parts"):
                raw_text = "\n".join([part.text for part in response.candidates[0].content.parts if hasattr(part, "text") and part.text])
            elif hasattr(response, "text") and response.text:
                raw_text = response.text

            if not raw_text.strip():
                raise ValueError("Stage 1 received an empty text response from Gemini API for news.")

            # Phase 1: Extract verified grounding metadata URIs directly from Google Search engine
            import requests
            if response.candidates and hasattr(response.candidates[0], "grounding_metadata"):
                gm = response.candidates[0].grounding_metadata
                if hasattr(gm, "grounding_chunks") and gm.grounding_chunks:
                    seen_uris = set()
                    for chunk in gm.grounding_chunks:
                        if hasattr(chunk, "web") and hasattr(chunk.web, "uri") and chunk.web.uri:
                            original_uri = chunk.web.uri
                            title = getattr(chunk.web, "title", "")
                            try:
                                # Resolve vertexaisearch redirect URLs
                                res = requests.get(original_uri, allow_redirects=True, timeout=5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                                if res.status_code == 200 and res.url not in seen_uris:
                                    seen_uris.add(res.url)
                                    real_grounding_urls.append({
                                        "uri": res.url,
                                        "title": title
                                    })
                            except Exception as e:
                                logger.warning(f"Failed to resolve redirect URL {original_uri}: {e}")
                else:
                    logger.warning("grounding_metadata is present, but grounding_chunks is empty or missing.")
            else:
                logger.warning("grounding_metadata is missing from the Gemini response.")
            
            logger.info(f"Extracted {len(real_grounding_urls)} verified real URIs from Gemini Search grounding_metadata.")
        except Exception as e:
            logger.warning(f"⚠️ [LLM FAILOVER TRIGGERED] Gemini Discovery API Exception: {e}. Falling back to OpenAI GPT Collector...")
            raw_text = self._fallback_openai_discovery(user_prompt, news_system_prompt)

        logger.info("Stage 1 News Discovery completed successfully.")
        # Store real grounding URLs on the instance for stage 2 mapping
        self._last_grounding_urls = real_grounding_urls
        return raw_text

    def _fallback_openai_discovery(self, user_prompt: str, news_system_prompt: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Gemini API failed and OPENAI_API_KEY is not set.")
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        logger.info("Running News Discovery via Fallback OpenAI GPT Collector (gpt-4o)...")
        response = client.chat.completions.create(
            model=os.getenv("GPT_AUDIT_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": news_system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content

    def run_news_structuring_stage(self, batch_id: str, discovery_report: str, target_count: int = 5) -> Dict[str, Any]:
        """
        Stage 2: Structuring news articles into JSON.
        URLs are extracted directly from the Stage 1 raw text via regex and
        forcibly override any URL the structuring LLM may produce, eliminating
        URL hallucination entirely.
        """
        logger.info("Starting Stage 2: News Report JSON Structuring...")
        
        import re
        ground_truth_urls: Dict[int, str] = {}

        # -----------------------------------------------------------------
        # Step B: Split into sections and let LLM structure the other fields
        # -----------------------------------------------------------------
        sections = re.split(r'---+\s*(?=### Article)', discovery_report)
        if len(sections) <= 1:
            sections = re.split(r'(?=### Article|###\s*Article|Article\s*\d+)', discovery_report)
        if len(sections) <= 1:
            sections = [s.strip() for s in re.split(r'\n\n(?=[#\-\*\d])', discovery_report) if len(s.strip()) > 50]
            
        cleaned_sections = []
        for sec in sections:
            sec_str = sec.strip()
            if len(sec_str) > 30:
                cleaned_sections.append(sec_str)
                
        logger.info(f"Split news report into {len(cleaned_sections)} articles for sequential structuring.")
        
        single_news_template = """Convert the supplied single AIKA AI news research result section into a valid JSON object.
Use only information contained in the supplied section.
Do not perform new web searches.
Do not add, infer, or invent information.
Do not include explanations outside the JSON.

IMPORTANT: Copy the Source URL field EXACTLY as written — character for character. Do not modify, shorten, or guess the URL.

Use this JSON structure:
{
  "title": "original title in article language",
  "korean_title": "Korean translation of the title (or same if already Korean)",
  "source_media": "string",
  "source_url": "copy the Source URL field exactly as written",
  "reference_urls": ["list of at least 3 distinct working candidate reference URLs from search"],
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
                logger.warning(f"Gemini Structuring failed for article {i+1}: {e}. Falling back to GPT-4o-mini...")
                try:
                    api_key = os.getenv("OPENAI_API_KEY")
                    if api_key:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key)
                        res = client.chat.completions.create(
                            model=os.getenv("GPT_AUDIT_MODEL", "gpt-4o"),
                            response_format={"type": "json_object"},
                            messages=[
                                {"role": "system", "content": "You are a JSON structuring assistant."},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.0
                        )
                        cand_data = json.loads(res.choices[0].message.content)
                        if isinstance(cand_data, dict):
                            parsed_articles.append(cand_data)
                except Exception as fallback_err:
                    logger.error(f"Failed both Gemini & GPT structuring for article {i+1}: {fallback_err}")
                    continue

        # -----------------------------------------------------------------
        # Step C: Override source_url with ground-truth URLs extracted in
        # Step A, or from self._last_grounding_urls, or fallback to Google search.
        # This completely neutralises Stage 2 URL hallucination.
        # -----------------------------------------------------------------
        import urllib.parse
        last_grounding = getattr(self, "_last_grounding_urls", []) or []

        final_articles = []
        for i, article in enumerate(parsed_articles[:target_count]):
            stage2_url = str(article.get("source_url") or "").strip()
            gt_url = ground_truth_urls.get(i, "")
            
            chosen_url = gt_url or stage2_url

            # If chosen_url is missing, empty, "None", "#", or generic domain, try grounding_metadata
            is_invalid = False
            if not chosen_url or chosen_url.lower() in ["none", "#", "null"]:
                is_invalid = True
            elif chosen_url.startswith("http://") or chosen_url.startswith("https://"):
                try:
                    p = urllib.parse.urlparse(chosen_url)
                    if not p.path or p.path in ["", "/"]:
                        is_invalid = True
                except Exception:
                    is_invalid = True
            else:
                is_invalid = True

            if is_invalid and i < len(last_grounding):
                chosen_url = last_grounding[i].get("uri", "")
                logger.info(f"Article [{i+1}] mapped URL from grounding_metadata: {chosen_url}")

            # Filter out non-news prompt instruction preamble blocks safely
            t_str = str(article.get("title") or "")
            m_str = str(article.get("source_media") or "")
            k_str = str(article.get("korean_title") or "")
            title_check = f"{t_str} {m_str} {k_str}".lower()
            if any(instr in title_check for instr in [
                "google search guide", "guide on how to", "instruction",
                "search guide", "search instruction", "prompt instruction"
            ]):
                logger.info(f"Article [{i+1}] skipped: Non-news prompt instruction block detected ({t_str})")
                continue

            article["source_url"] = chosen_url
            
            # Build list of candidate reference URLs for Stage 3 Auditor
            ref_candidates = []
            if chosen_url and chosen_url.startswith("http"):
                ref_candidates.append(chosen_url)
            if gt_url and gt_url.startswith("http") and gt_url not in ref_candidates:
                ref_candidates.append(gt_url)
            if stage2_url and stage2_url.startswith("http") and stage2_url not in ref_candidates:
                ref_candidates.append(stage2_url)
            for g_item in last_grounding:
                g_uri = g_item.get("uri", "")
                if g_uri and g_uri.startswith("http") and g_uri not in ref_candidates:
                    ref_candidates.append(g_uri)
            
            article["reference_urls"] = ref_candidates

            # Apply Jev (TypeSafe System One) News Classification & Filtering
            try:
                from services.typesafe_service import TypeSafeNewsClassifier
                jev_classifier = TypeSafeNewsClassifier()
                if jev_classifier.is_available():
                    title_for_jev = str(article.get("title") or article.get("korean_title") or "")
                    snippet_for_jev = str(article.get("detailed_summary") or article.get("korean_summary") or "")
                    jev_res = jev_classifier.evaluate_article(title_for_jev, snippet_for_jev, min_ai_prob_threshold=0.65)

                    article["jev_ai_prob"] = jev_res.get("ai_probability")
                    article["jev_impact_score"] = jev_res.get("impact_score")
                    article["target_bucket"] = jev_res.get("target_bucket", "국내 AI 소식")
                    article["article_region"] = jev_res.get("article_region", "국내")
                    article["article_type"] = jev_res.get("article_type", "소식")

                    if jev_res.get("status") == "success":
                        article["primary_ai_category"] = jev_res.get("primary_category")
                        article["korea_market_relevance"] = jev_res.get("korea_relevance")

                    # Python 48-Hour Explicit Date Filter Check
                    pub_date = str(article.get("published_date", ""))
                    is_date_recent = self._is_within_48h(pub_date)

                    if not jev_res.get("is_ai_news", True) or not is_date_recent:
                        reason = jev_res.get('filter_reason') if jev_res.get('filter_reason') else f"Published date ({pub_date}) older than 48 hours"
                        logger.info(f"Article [{i+1}] EXCLUDED (Non-AI / Outdated) by Jev: {reason}")
                        article["review_status"] = "Filtered (Non-AI)"
                        continue  # Skip non-AI articles entirely
            except Exception as jev_err:
                logger.warning(f"Jev classification skipped due to error: {jev_err}")

            final_articles.append(article)

                
        combined_result = {
            "batch_id": batch_id,
            "requested_count": target_count,
            "verified_count": len(final_articles),
            "candidates": final_articles
        }
        
        logger.info(f"Stage 2 completed successfully. Structured {len(final_articles)} news articles.")
        return combined_result

    def run_tri_engine_discovery(self, batch_params: Dict[str, Any], existing_urls: List[str], status_callback: Optional[Any] = None) -> Dict[str, Any]:
        """
        Tri-Engine News Discovery:
        1. Gemini Google Search Grounding.
        2. Perplexity AI Real-Time Search (if PERPLEXITY_API_KEY present).
        3. Naver News Real-Time Search (API / HTML Scraper).
        Merges candidates and pools all reference URLs so every headline has >=3 reference URLs.
        """
        topic = batch_params.get("news_topic", "")
        res_date = batch_params.get("research_date", "")

        def _collect_current_urls(candidates, g_urls):
            pooled = []
            seen = set()
            for g in g_urls:
                u = g.get("uri") if isinstance(g, dict) else str(g)
                if u and u.startswith("http") and u not in seen:
                    seen.add(u)
                    t = g.get("title") if isinstance(g, dict) else u
                    pooled.append({"uri": u, "title": t or u})
            for c in candidates:
                s_url = c.get("source_url", "")
                c_title = c.get("title") or c.get("korean_title") or "Article Link"
                c_media = c.get("source_media", "News")
                if s_url and s_url.startswith("http") and s_url not in seen:
                    seen.add(s_url)
                    pooled.append({"uri": s_url, "title": f"[{c_media}] {c_title}"})
                for ref in c.get("reference_urls", []):
                    if ref and ref.startswith("http") and ref not in seen:
                        seen.add(ref)
                        pooled.append({"uri": ref, "title": ref})
            return pooled

        # 1. Gemini Grounding Discovery with Over-fetching
        target_count = batch_params.get("target_count", 5)
        from services.validator import calculate_overfetch_count
        discovery_count = calculate_overfetch_count(target_count)

        batch_params_overfetch = dict(batch_params)
        batch_params_overfetch["target_count"] = discovery_count

        enable_gemini = batch_params.get("enable_gemini", True)
        base_candidates = []

        active_disc_model = os.getenv("DISCOVERY_MODEL", "gemini-2.5-flash").strip()

        if "perplexity" in active_disc_model:
            px_m_name = "sonar-pro" if "pro" in active_disc_model else "sonar"
            if status_callback:
                status_callback(f"⚡ [메인 기사 검색 모델] Perplexity AI ({px_m_name}) 탐색 중... ({discovery_count}개 후보 수집)")
            from services.perplexity_client import PerplexityNewsClient
            px_client = PerplexityNewsClient()
            if px_client.is_available():
                px_cands = px_client.search_news_candidates(topic, res_date, max_results=discovery_count, model_name=px_m_name)
                base_candidates.extend(px_cands)
            gemini_result = {"batch_id": batch_params.get("batch_id", ""), "candidates": base_candidates}
        elif enable_gemini:
            if status_callback:
                status_callback(f"🌐 [메인 기사 검색 모델] Gemini Search Grounding ({active_disc_model}) 탐색 중... ({discovery_count}개 후보 수집)")
            gemini_raw_report = self.run_news_discovery_stage(batch_params_overfetch, existing_urls)
            gemini_result = self.run_news_structuring_stage(
                batch_params.get("batch_id", ""),
                gemini_raw_report,
                target_count=discovery_count
            )
            base_candidates = gemini_result.get("candidates", [])
        else:
            gemini_result = {"batch_id": batch_params.get("batch_id", ""), "candidates": []}

        # 1.5. RSS Channels (Google News RSS & Direct RSS)
        try:
            from services.rss_client import fetch_google_news_rss, fetch_direct_media_rss
            from datetime import datetime, date

            since_str = batch_params.get("since_date", "")
            days = 7
            cutoff_d = None
            if since_str:
                try:
                    cutoff_d = datetime.strptime(since_str, "%Y-%m-%d").date()
                    days = max(1, (date.today() - cutoff_d).days)
                except Exception:
                    days = 7

            if batch_params.get("enable_google_news_rss", True):
                if status_callback:
                    status_callback(f"📰 Google News RSS ({days}일 이내) 탐색 중...")
                q = f"{batch_params.get('primary_category', 'AI')} {batch_params.get('news_topic', 'News')}"
                g_rss = fetch_google_news_rss(query=q, days=days, max_results=5)
                base_candidates.extend(g_rss)

            if batch_params.get("enable_direct_rss", True):
                if status_callback:
                    status_callback("📡 주요 언론사 직접 RSS 피드 수집 중...")
                d_rss = fetch_direct_media_rss(cutoff_date=cutoff_d, max_per_feed=2)
                base_candidates.extend(d_rss)
        except Exception as rss_err:
            logger.warning(f"RSS Discovery integration error: {rss_err}")
        
        current_g_urls = getattr(self, "_last_grounding_urls", [])
        urls_step1 = _collect_current_urls(base_candidates, current_g_urls)
        if status_callback:
            status_callback(f"🌐 1차 후보 탐색 완료 ({len(base_candidates)}개 후보 기사 수집)", urls=urls_step1)

        # 2. Perplexity AI Real-Time Search
        try:
            from services.perplexity_client import PerplexityNewsClient
            px_client = PerplexityNewsClient()
            if px_client.is_available():
                px_model = batch_params.get("perplexity_model", "sonar")
                if status_callback:
                    status_callback(f"⚡ 2/3 Perplexity AI ({px_model}) 실시간 검색 중...")
                px_candidates = px_client.search_news_candidates(topic, res_date, max_results=3, model_name=px_model)
                for px in px_candidates:
                    base_candidates.append(px)
                urls_step2 = _collect_current_urls(base_candidates, current_g_urls)
                if status_callback:
                    status_callback(f"⚡ 2/3 Perplexity AI ({px_model}) 탐색 완료 ({len(urls_step2)}개 참고 URL 발견)", urls=urls_step2)
        except Exception as px_err:
            logger.warning(f"Perplexity integration error: {px_err}")

        # 3. Naver News Real-Time Search
        try:
            if status_callback:
                status_callback("🇰🇷 3/3 네이버 실시간 뉴스 수집 중...")
            from services.naver_search import get_naver_news_candidates
            naver_candidates = get_naver_news_candidates(topic, display=5)
            for nv in naver_candidates:
                base_candidates.append(nv)
            urls_step3 = _collect_current_urls(base_candidates, current_g_urls)
            if status_callback:
                status_callback(f"🇰🇷 3/3 네이버 뉴스 수집 완료 ({len(urls_step3)}개 참고 URL 발견)", urls=urls_step3)
        except Exception as nv_err:
            logger.warning(f"Naver News integration error: {nv_err}")

        # Final Pooling and deduplicating reference URLs across candidates and engines
        all_grounding_uris = [g.get("uri") for g in getattr(self, "_last_grounding_urls", []) if isinstance(g, dict) and g.get("uri")]
        pooled_urls = _collect_current_urls(base_candidates, getattr(self, "_last_grounding_urls", []))

        for cand in base_candidates:
            refs = cand.get("reference_urls", [])
            if not isinstance(refs, list):
                refs = []
            s_url = cand.get("source_url", "")
            if s_url and s_url.startswith("http") and s_url not in refs:
                refs.append(s_url)
            for g_uri in all_grounding_uris:
                if g_uri and g_uri not in refs:
                    refs.append(g_uri)
            cand["reference_urls"] = refs

        # -----------------------------------------------------------------
        # Stage 1.5: AI-Relevance Pre-Filter (Title Keyword Check)
        # Removes obviously non-AI articles from RSS/Naver/Perplexity before
        # expensive URL resolution.
        # -----------------------------------------------------------------
        AI_KEYWORDS = [
            "ai", "인공지능", "llm", "gpt", "생성형", "딥러닝", "머신러닝",
            "machine learning", "deep learning", "generative", "openai",
            "claude", "gemini", "copilot", "chatbot", "챗봇", "자율주행",
            "로봇", "robot", "neural", "transformer", "데이터", "클라우드",
            "cloud", "사이버", "보안", "security", "자동화", "automation",
            "algorithm", "알고리즘", "스타트업", "startup", "반도체", "chip",
            "gpu", "npu", "semiconductor", "model", "모델", "api",
            "saas", "플랫폼", "platform", "tech", "테크", "소프트웨어",
            "software", "디지털", "digital", "빅테크", "it", "skt", "네이버",
            "카카오", "삼성", "lg", "microsoft", "google", "apple", "meta",
            "amazon", "nvidia", "anthropic", "hugging", "컴퓨팅", "computing"
        ]

        def _has_ai_relevance(cand_dict):
            """Quick keyword check on title + summary to filter obviously non-AI content."""
            title_text = str(cand_dict.get("title") or cand_dict.get("korean_title") or "").lower()
            summary_text = str(cand_dict.get("rss_description") or cand_dict.get("korean_summary") or "").lower()
            combined = f"{title_text} {summary_text}"
            return any(kw in combined for kw in AI_KEYWORDS)

        pre_filter_count = len(base_candidates)
        base_candidates = [c for c in base_candidates if _has_ai_relevance(c)]
        filtered_out = pre_filter_count - len(base_candidates)
        if filtered_out > 0:
            logger.info(f"AI-relevance pre-filter removed {filtered_out} non-AI candidates (keyword check).")

        # -----------------------------------------------------------------
        # Stage 2: 3-Stage Cross Verification & Direct Deep-Link Resolution
        # -----------------------------------------------------------------
        if status_callback:
            status_callback(f"🛡️ [2차 교차검증] 후보 {len(base_candidates)}개 기사 3단계 팩트 검증 중...")

        from services.url_resolver import resolve_exact_news_url
        verified_candidates = []
        for cand in base_candidates:
            if len(verified_candidates) >= target_count:
                break
            title_q = cand.get("title") or cand.get("korean_title") or "AI News"
            media_q = cand.get("source_media", "")
            url_q = cand.get("source_url", "")
            title_kr_q = cand.get("korean_title", "")
            refs_q = cand.get("reference_urls", [])

            resolved_url = resolve_exact_news_url(title_q, media_q, url_q, title_kr=title_kr_q, reference_urls=refs_q)
            if resolved_url:
                cand["source_url"] = resolved_url
                if resolved_url.lower() not in [u.lower() for u in existing_urls]:
                    verified_candidates.append(cand)
            else:
                logger.warning(f"Rejected unverified article during Stage 2: '{title_q}' ({url_q})")

        base_candidates = verified_candidates[:target_count]
        logger.info(f"tri_engine_discovery: 2nd stage verified & trimmed to {len(base_candidates)} candidates (target_count={target_count})")

        # -----------------------------------------------------------------
        # Stage 3: Auto-Structuring & Korean Summarization for Raw Candidates (RSS/Perplexity/Naver)
        # -----------------------------------------------------------------
        for cand in base_candidates:
            if not cand.get("korean_summary") or not cand.get("detailed_summary"):
                title_t = cand.get("title") or cand.get("korean_title") or "AI News"
                media_t = cand.get("source_media", "News")
                url_t = cand.get("source_url", "")
                rss_t = cand.get("rss_description", "")
                
                content_to_analyze = f"Title: {title_t}\nMedia: {media_t}\nURL: {url_t}\nSummary Snippet: {rss_t}"
                try:
                    logger.info(f"Auto-enriching missing summary for candidate: '{title_t}'")
                    analyzed = self.analyze_manual_article(
                        content=content_to_analyze,
                        url=url_t,
                        media_name=media_t,
                        title=title_t,
                        primary_category=batch_params.get("primary_category", "All"),
                        news_topic=batch_params.get("news_topic", "All")
                    )
                    cand["korean_title"] = analyzed.get("korean_title") or title_t
                    cand["language"] = analyzed.get("language") or "EN"
                    cand["primary_ai_category"] = analyzed.get("primary_ai_category") or batch_params.get("primary_category", "All")
                    cand["news_topic"] = analyzed.get("news_topic") or batch_params.get("news_topic", "All")
                    cand["korean_summary"] = analyzed.get("korean_summary", "")
                    cand["detailed_summary"] = analyzed.get("detailed_summary", "")
                    cand["key_keywords"] = analyzed.get("key_keywords", "")
                    cand["related_companies"] = analyzed.get("related_companies", "")
                    cand["korea_market_relevance"] = analyzed.get("korea_market_relevance", "Medium")
                except Exception as enrich_err:
                    logger.warning(f"Failed to auto-enrich candidate summary: {enrich_err}")

        self._last_grounding_urls = pooled_urls
        gemini_result["candidates"] = base_candidates
        return gemini_result

    def analyze_manual_article(
        self,
        content: str,
        url: str = "",
        media_name: str = "",
        title: str = "",
        primary_category: str = "All",
        news_topic: str = "AI Product Launch"
    ) -> Dict[str, Any]:
        """
        Analyzes manually provided news article content/text and structures it into
        the standardized AIKA news candidate format using Gemini JSON generation.
        """
        logger.info("Analyzing manually submitted news article with Gemini...")
        
        prompt = f"""You are an expert AI news auditor and business intelligence analyst.
Analyze the following user-provided news article text/content and extract/structure it into a valid JSON object matching the standard AIKA news schema.

[INPUT DETAILS]
- Provided Title: {title if title else "(Extract from content)"}
- Provided Media/Source: {media_name if media_name else "(Infer from content or default to 'User Selected Media')"}
- Provided Source URL: {url if url else ""}
- Primary AI Category: {primary_category}
- News Topic: {news_topic}

[ARTICLE CONTENT / TEXT]
{content}

[REQUIRED JSON SCHEMA]
Return a SINGLE JSON object with the following fields:
{{
  "title": "Original English or main title of the article",
  "korean_title": "Clear, concise Korean translation of the title",
  "source_media": "Name of the publishing media/outlet (e.g., TechCrunch, ZDNet Korea, Official Blog, etc.)",
  "source_url": "{url if url else ''}",
  "published_date": "YYYY-MM-DD (extract if present in text, otherwise use today's date)",
  "language": "EN or KO (language of original text)",
  "primary_ai_category": "{primary_category}",
  "news_topic": "{news_topic}",
  "korean_summary": "1-line concise executive summary in Korean for quick briefing",
  "detailed_summary": "10-line detailed structured summary in Korean covering background, technical/product specs, market impact, and future implications with clear line breaks (\\n)",
  "key_keywords": "5-8 key Korean keywords separated by commas",
  "related_companies": "Relevant company names mentioned in the text, separated by commas",
  "korea_market_relevance": "High or Medium or Low",
  "reference_urls": {json.dumps([url] if url else [])},
  "audit_status": "Approved (Manual Entry)",
  "discovery_channel": "manual"
}}

Respond ONLY with valid JSON. Do not include markdown code block syntax unless required by JSON output format.
"""
        try:
            model = genai.GenerativeModel(model_name=self.structure_model_name)
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json"
                }
            )
            
            if response.text:
                data = json.loads(response.text)
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                
                if isinstance(data, dict):
                    if not data.get("source_url") and url:
                        data["source_url"] = url
                    if not data.get("reference_urls") and url:
                        data["reference_urls"] = [url]

                    # Apply Jev (TypeSafe System One) News Classification & Filtering
                    try:
                        from services.typesafe_service import TypeSafeNewsClassifier
                        jev_classifier = TypeSafeNewsClassifier()
                        if jev_classifier.is_available():
                            title_for_jev = str(data.get("title") or data.get("korean_title") or "")
                            snippet_for_jev = str(data.get("detailed_summary") or data.get("korean_summary") or content or "")
                            jev_res = jev_classifier.evaluate_article(title_for_jev, snippet_for_jev)

                            data["jev_ai_prob"] = jev_res.get("ai_probability")
                            data["jev_impact_score"] = jev_res.get("impact_score")

                            if jev_res.get("status") == "success":
                                data["primary_ai_category"] = jev_res.get("primary_category")
                                data["korea_market_relevance"] = jev_res.get("korea_relevance")

                            if not jev_res.get("is_ai_news", True):
                                logger.info(f"Article marked as Filtered (Non-AI) by Jev: {jev_res.get('filter_reason')}")
                                data["review_status"] = "Filtered (Non-AI)"
                    except Exception as jev_err:
                        logger.warning(f"Jev classification skipped in analyze_single_news_article: {jev_err}")

                    return data


            raise ValueError("Gemini returned empty or invalid response for manual article analysis.")
        except Exception as e:
            logger.error(f"Failed to analyze manual article with Gemini: {e}")
            raise e

    def analyze_multiple_manual_articles(
        self,
        raw_text_bundle: str,
        primary_category: str = "All",
        news_topic: str = "AI Product Launch",
        status_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes a raw text bundle containing 1 to N news articles (without explicit dividers, separated by line spaces/paragraphs),
        detects individual articles & URLs, fetches web content with fallback, and structures each into the standard AIKA template.
        """
        logger.info("Analyzing multiple manual articles bundle with Gemini...")
        from services.url_resolver import fetch_article_text_with_fallback, follow_and_get_final_url

        if status_callback:
            status_callback("🔍 1단계: 입력된 텍스트 뭉치에서 1개~N개 기사 단락 및 URL 감지/분할 중...")

        # Step 1: Segmentation prompt
        segmentation_prompt = f"""You are a news text parser.
The user provided a text bundle containing 1 or multiple news articles (separated by blank lines, headers, or URLs).
Identify and separate each distinct news article. Also extract any source URL (http:// or https://) if present inside each article text.

[TEXT BUNDLE]
{raw_text_bundle}

[REQUIRED JSON OUTPUT]
Return a JSON array of objects:
[
  {{
    "article_index": 1,
    "raw_content": "Full extracted text of article 1",
    "detected_title": "Extracted or inferred title",
    "detected_url": "Source URL if found in text, otherwise empty string",
    "detected_media": "Source media name if mentioned, otherwise empty string"
  }}
]
Respond ONLY with valid JSON array.
"""
        model = genai.GenerativeModel(model_name=self.structure_model_name)
        segments = []
        try:
            resp = model.generate_content(
                segmentation_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            if resp.text:
                parsed = json.loads(resp.text)
                if isinstance(parsed, list):
                    segments = parsed
                elif isinstance(parsed, dict) and "articles" in parsed:
                    segments = parsed["articles"]
        except Exception as seg_err:
            logger.warning(f"Failed automatic segmentation, falling back to single article: {seg_err}")
            segments = [{
                "article_index": 1,
                "raw_content": raw_text_bundle,
                "detected_title": "",
                "detected_url": "",
                "detected_media": ""
            }]

        if not segments:
            segments = [{
                "article_index": 1,
                "raw_content": raw_text_bundle,
                "detected_title": "",
                "detected_url": "",
                "detected_media": ""
            }]

        if status_callback:
            status_callback(f"✓ 총 {len(segments)}개의 기사 단락을 감지했습니다. 2단계 URL 웹 원문 탐색 및 우회 요약 진행 중...")

        # Step 2 & 3: For each segment, attempt web fetch, then summarize into standard schema
        results = []
        for i, seg in enumerate(segments, 1):
            if status_callback:
                try:
                    status_callback(f"[{i}/{len(segments)}] 기사 단락 {i} 분석 준비 중...")
                except OperationCancelledException as cancel_err:
                    cancel_err.partial_data = results
                    raise cancel_err

            raw_content = seg.get("raw_content", "").strip()
            if not raw_content and len(raw_text_bundle.strip()) > 0:
                raw_content = raw_text_bundle.strip()

            url = seg.get("detected_url", "").strip()
            if not url:
                # Regex fallback for URL in text
                urls_found = re.findall(r'https?://[^\s\)]+', raw_content)
                if urls_found:
                    url = urls_found[0].rstrip(".,;\"'")

            title = seg.get("detected_title", "").strip()
            media = seg.get("detected_media", "").strip()

            # Attempt Web Page Fetch if URL present
            web_text = None
            if url:
                if status_callback:
                    try:
                        status_callback(f"[{i}/{len(segments)}] URL '{url}' 웹페이지 원문 탐색 중...")
                    except OperationCancelledException as cancel_err:
                        cancel_err.partial_data = results
                        raise cancel_err
                web_text = fetch_article_text_with_fallback(url)
                if web_text:
                    if status_callback:
                        try:
                            status_callback(f"  ✅ 웹페이지 원문 획득 성공 ({len(web_text)} 자)")
                        except OperationCancelledException as cancel_err:
                            cancel_err.partial_data = results
                            raise cancel_err
                else:
                    if status_callback:
                        try:
                            if len(raw_content) > 100:
                                status_callback(f"  ℹ️ 입력된 텍스트 본문 기반으로 정밀 분석 진행 완료 ({len(raw_content)}자 활용)")
                            else:
                                status_callback(f"  ⚠️ URL 웹 원문 접근 차단(방화벽) → 텍스트 본문을 함께 입력하시면 100% 정밀 요약이 가능합니다.")
                        except OperationCancelledException as cancel_err:
                            cancel_err.partial_data = results
                            raise cancel_err

            combined_content = raw_content
            if web_text:
                combined_content = f"{raw_content}\n\n[FETCHED FULL WEB CONTENT]\n{web_text}"

            if status_callback:
                try:
                    status_callback(f"[{i}/{len(segments)}] Gemini 템플릿(한글 제목, 1줄/10줄 상세 요약 등) 분석 중...")
                except OperationCancelledException as cancel_err:
                    cancel_err.partial_data = results
                    raise cancel_err

            try:
                analyzed = self.analyze_manual_article(
                    content=combined_content,
                    url=url,
                    media_name=media,
                    title=title,
                    primary_category=primary_category,
                    news_topic=news_topic
                )
                results.append(analyzed)
            except OperationCancelledException as cancel_err:
                cancel_err.partial_data = results
                raise cancel_err
            except Exception as a_err:
                logger.error(f"Error analyzing segment {i}: {a_err}")

        return results

    def test_connection(self) -> bool:
        """
        Tests if the Gemini API key is valid by running a lightweight call.
        Safely uses a valid Gemini model name even if discovery_model is set to Perplexity.
        """
        try:
            target_model = self.structure_model_name if self.structure_model_name and "perplexity" not in self.structure_model_name else "gemini-2.5-flash"
            if "perplexity" in target_model:
                target_model = "gemini-2.5-flash"
            model = genai.GenerativeModel(target_model)
            response = model.generate_content("hello")
            self.last_error = None
            return response.text is not None and len(response.text) > 0
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False


