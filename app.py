import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import logging
import random

# Services
import importlib
import services.gemini_client
import services.sheets_client
import services.url_resolver
import services.audit_agent
import services.validator

importlib.reload(services.gemini_client)
importlib.reload(services.sheets_client)
importlib.reload(services.url_resolver)
importlib.reload(services.audit_agent)
importlib.reload(services.validator)

from services.gemini_client import GeminiClient
from services.sheets_client import SheetsClient
from services.batch_service import BatchService, CATEGORY_CODES
from services.validator import validate_article, ALLOWED_CATEGORIES
from services.scheduler_service import SchedulerService

# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Render Timer UI Helper
def render_timer_ui(task_name: str, task_title: str):
    st.markdown("---")
    st.markdown(f"#### ⏱️ {task_title} 자동 예약 수집 및 결과 알림 설정 (Scheduled Auto-Discovery)")
    scheduler = SchedulerService()
    cfg = scheduler.config.get(task_name, {})
    info = scheduler.get_job_info(task_name)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        enabled = st.toggle(
            f"자동 예약 수집 활성화 ({task_title})",
            value=cfg.get("enabled", False),
            key=f"timer_enabled_{task_name}"
        )
        mode = st.selectbox(
            "실행 방식 (Mode)",
            ["interval", "daily"],
            format_func=lambda x: "주기적 반복 (매 N시간마다)" if x == "interval" else "매일 특정 시각 수집 (Daily Multi-Time)",
            index=0 if cfg.get("mode") == "interval" else 1,
            key=f"timer_mode_{task_name}"
        )

    with col_t2:
        if mode == "interval":
            interval_h = st.number_input(
                "반복 주기 (시간 단위)",
                min_value=1,
                max_value=168,
                value=int(cfg.get("interval_hours", 24)),
                key=f"timer_hours_{task_name}"
            )
            daily_count = cfg.get("daily_count", 1)
            daily_times_str = cfg.get("daily_times", cfg.get("daily_time", "09:00"))
        else:
            interval_h = cfg.get("interval_hours", 24)
            daily_count = st.number_input(
                "하루 수집 횟수 (1~6회/일)",
                min_value=1,
                max_value=6,
                value=int(cfg.get("daily_count", 1)),
                key=f"timer_daily_count_{task_name}",
                help="하루에 몇 번 지정한 시각에 수집을 실행할지 지정합니다."
            )
            
            # Default preset generator based on count if user hasn't specified
            default_times_map = {
                1: "09:00",
                2: "08:00, 18:00",
                3: "08:00, 13:00, 19:00",
                4: "08:00, 12:00, 16:00, 20:00",
                5: "08:00, 11:00, 14:00, 17:00, 20:00",
                6: "06:00, 09:00, 12:00, 15:00, 18:00, 21:00"
            }
            preset_val = cfg.get("daily_times") or cfg.get("daily_time") or default_times_map.get(daily_count, "09:00")
            
            daily_times_str = st.text_input(
                "매일 실행 시각 지정 (콤마로 구분, 24시간제 HH:MM)",
                value=preset_val,
                key=f"timer_daily_times_{task_name}",
                help="예시: 08:00, 18:00 (설정한 수집 횟수만큼 24시간제 시각을 콤마로 구분하여 입력하세요)"
            )

    # 📧 Email Notification Settings Section
    st.markdown("##### 📧 수집 결과 이메일 알림 및 발송 시각 설정")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        email_enabled = st.checkbox(
            "실행 결과 브리핑 메일 자동 발송 활성화",
            value=cfg.get("email_enabled", False),
            key=f"timer_email_enabled_{task_name}"
        )
        email_send_mode = st.selectbox(
            "메일 발송 타이밍 (Sending Timing)",
            ["immediate", "scheduled"],
            format_func=lambda x: "⚡ 수집 완료 직후 즉시 발송" if x == "immediate" else "⏰ 지정한 특정 시각에 발송",
            index=0 if cfg.get("email_send_mode", "immediate") == "immediate" else 1,
            key=f"timer_email_send_mode_{task_name}"
        )
    with col_e2:
        recipient_email = st.text_input(
            "수신 이메일 주소 (복수 입력 가능, 콤마로 구분)",
            value=cfg.get("recipient_email", "changwan.lim@agichang.ai"),
            key=f"timer_recipient_email_{task_name}",
            placeholder="user1@example.com, user2@example.com",
            help="여러 메일 주소로 동시 발송하려면 콤마(,)로 구분하여 입력하세요. 예: user1@ai.com, user2@ai.com"
        )
        if email_send_mode == "scheduled":
            email_dispatch_time = st.text_input(
                "메일 발송 지정 시각 (HH:MM 24시간제, 콤마 구분)",
                value=cfg.get("email_dispatch_time", "08:30, 18:30"),
                key=f"timer_email_dispatch_time_{task_name}",
                help="예시: 08:30, 18:30 (원하는 24시간제 시각을 콤마로 구분하여 입력하세요)"
            )
        else:
            email_dispatch_time = cfg.get("email_dispatch_time", "08:30, 18:30")

        if st.button("🧪 테스트 메일 발송", key=f"test_email_btn_{task_name}", use_container_width=True):
            with st.spinner("테스트 이메일 발송 중..."):
                res = scheduler.send_test_email(task_name, recipient_email)
                if res.get("success"):
                    st.success(f"✅ 테스트 이메일이 {recipient_email}로 성공적으로 발송되었습니다.")
                else:
                    st.error(f"❌ 이메일 발송 실패: {res.get('error')}")

    from services.email_service import EmailService
    if not EmailService().is_configured():
        with st.expander("ℹ️ 발송용 이메일 계정(SMTP) 설정 방법", expanded=False):
            st.markdown("""
            자동 이메일 발송을 위해서는 프로젝트의 **`.env`** 파일(또는 Streamlit secrets)에 발송용 이메일 계정 정보가 설정되어 있어야 합니다:
            
            ```env
            # Gmail SMTP 설정 예시 (.env 파일 하단에 추가)
            EMAIL_SENDER=your_email@gmail.com
            EMAIL_PASSWORD=your_16_digit_app_password
            EMAIL_RECEIVER=changwan.lim@agichang.ai
            EMAIL_SMTP_SERVER=smtp.gmail.com
            EMAIL_SMTP_PORT=465
            ```
            
            > 💡 **Gmail 계정 사용 시 필수 사항**:  
            > 일반 로그인 비밀번호가 아닌, **Google 계정 설정 > 보안 > 2단계 인증 > [앱 비밀번호]**에서 16자리 앱 비밀번호(App Password)를 발급받아 `EMAIL_PASSWORD`에 입력하셔야 합니다.
            """)

    # Detect change & save
    current_daily_time = daily_times_str.split(",")[0].strip() if daily_times_str else "09:00"
    if (enabled != cfg.get("enabled") or 
        mode != cfg.get("mode") or 
        interval_h != cfg.get("interval_hours") or 
        daily_count != cfg.get("daily_count") or
        daily_times_str != cfg.get("daily_times") or
        email_enabled != cfg.get("email_enabled") or
        email_send_mode != cfg.get("email_send_mode") or
        email_dispatch_time != cfg.get("email_dispatch_time") or
        recipient_email != cfg.get("recipient_email")):
        
        new_task_cfg = {
            "enabled": enabled,
            "mode": mode,
            "interval_hours": interval_h,
            "daily_count": daily_count,
            "daily_times": daily_times_str,
            "daily_time": current_daily_time,
            "email_enabled": email_enabled,
            "email_send_mode": email_send_mode,
            "email_dispatch_time": email_dispatch_time,
            "recipient_email": recipient_email
        }
        scheduler.update_task_config(task_name, new_task_cfg)
        st.success(f"⏱️ {task_title} 예약 타이머 및 메일 발송 설정이 저장되었습니다.")
        st.rerun()

    status_icon = "🟢 예약 작동 중 (Auto-Collected로 구글 시트 자동 저장)" if info["enabled"] else "🔴 비활성화"
    if cfg.get("email_enabled"):
        timing_info = f"즉시 발송" if cfg.get("email_send_mode", "immediate") == "immediate" else f"지정 시각({cfg.get('email_dispatch_time', '')}) 발송"
        email_status = f"📧 메일 알림 켜짐 ({cfg.get('recipient_email', '')} / {timing_info})"
    else:
        email_status = "🔕 메일 알림 꺼짐"
    st.info(f"**현재 상태**: {status_icon} | {email_status}\n\n- **마지막 실행**: `{info['last_run']}` (`{info['last_status']}`)\n- **다음 예정**: `{info['next_run']}`")

# ----------------- DOMAIN PERSISTENCE HELPERS -----------------
DOMAIN_CONFIG_PATH = os.path.join(os.getcwd(), "data", "domain_config.json")
DEFAULT_DOMAINS = {
    "vendor_domains": "ycombinator.com, crunchbase.com, producthunt.com, techcrunch.com",
    "partner_domains": "zdnet.co.kr, ddaily.co.kr, etnews.com",
    "news_domains": "zdnet.co.kr, etnews.com, techcrunch.com, venturebeat.com, reuters.com"
}

def load_domain_config() -> dict:
    os.makedirs(os.path.dirname(DOMAIN_CONFIG_PATH), exist_ok=True)
    if os.path.exists(DOMAIN_CONFIG_PATH):
        try:
            with open(DOMAIN_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                merged = DEFAULT_DOMAINS.copy()
                merged.update(cfg)
                return merged
        except Exception as e:
            logger.error(f"Error loading domain_config.json: {e}")
    return DEFAULT_DOMAINS.copy()

def save_domain_config(key: str, val: str):
    cfg = load_domain_config()
    cfg[key] = val
    try:
        with open(DOMAIN_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving domain_config.json: {e}")

def parse_domains(raw_str: str) -> list:
    import re
    return [d.strip() for d in re.split(r'[,\n]', raw_str) if d.strip()]



# Helper to clear checkbox widget state from session_state
def clear_checkbox_keys():
    for key in list(st.session_state.keys()):
        if key.startswith("chk_save_") or key.startswith("chk_partner_save_") or key.startswith("chk_news_save_"):
            del st.session_state[key]

# Callback to safely select a candidate and check its save checkbox
def select_candidate_callback(idx):
    st.session_state.selected_candidate_idx = idx
    st.session_state[f"chk_save_{idx}"] = True

# Callback to safely select a partner candidate and check its save checkbox
def select_partner_callback(idx):
    st.session_state.selected_partner_idx = idx
    st.session_state[f"chk_partner_save_{idx}"] = True

# Callback to safely select a news candidate and check its save checkbox
def select_news_callback(idx):
    st.session_state.selected_news_idx = idx
    st.session_state[f"chk_news_save_{idx}"] = True

# Page configuration
st.set_page_config(
    page_title="AIKA Global AI Vendor Research Tool",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply some custom CSS for styling (glassmorphism look, clean buttons, state indicator badges)
st.markdown("""
<style>
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85em;
        display: inline-block;
    }
    .status-connected {
        background-color: #d4edda;
        color: #155724;
    }
    .status-disconnected {
        background-color: #f8d7da;
        color: #721c24;
    }
    .main-header {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        background: linear-gradient(45deg, #1A365D, #2B6CB0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .stButton>button {
        border-radius: 6px;
    }
    .vendor-card {
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        background-color: #f7fafc;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- AUTHENTICATION MODULE -----------------
def check_authentication():
    """Renders login form and blocks access until authenticated."""
    disable_auth = os.getenv("DISABLE_AUTH", "false").strip().lower() in ["true", "1", "yes"]
    if disable_auth or st.session_state.get("authenticated", False):
        st.session_state["authenticated"] = True
        return True

    # Hide sidebar during login screen
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #1A365D;'>🤖 AIKA Platform Access</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #4A5568;'>보안 로그인이 필요합니다. 계정 정보를 입력하세요.</p>", unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("아이디 (ID)", key="input_username")
            password = st.text_input("비밀번호 (Password)", type="password", key="input_password")
            submit = st.form_submit_button("🔑 로그인 (Login)", use_container_width=True)

            if submit:
                target_user = os.getenv("APP_USERNAME", "aika")
                target_pass = os.getenv("APP_PASSWORD", "$aSmith2115$")
                
                # Check secrets if available
                try:
                    if "APP_USERNAME" in st.secrets:
                        target_user = str(st.secrets["APP_USERNAME"])
                    if "APP_PASSWORD" in st.secrets:
                        target_pass = str(st.secrets["APP_PASSWORD"])
                except Exception:
                    pass

                if username.strip() == target_user and password.strip() == target_pass:
                    st.session_state["authenticated"] = True
                    st.success("✅ 로그인되었습니다!")
                    st.rerun()
                else:
                    st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")

    st.stop()

check_authentication()

# Force reinit of services on code change (version stamp)
_GEMINI_VERSION = "v2.2-since-date-fix"
if "gemini" not in st.session_state or st.session_state.get("_gemini_version") != _GEMINI_VERSION:
    try:
        st.session_state.gemini = GeminiClient()
        st.session_state._gemini_version = _GEMINI_VERSION
    except Exception as e:
        logger.warning(f"Could not load Gemini Client: {e}")
        st.session_state.gemini = None

_SHEETS_VERSION = "v2.1-list-fix"
if "sheets" not in st.session_state or st.session_state.get("_sheets_version") != _SHEETS_VERSION:
    st.session_state.sheets = SheetsClient()
    st.session_state._sheets_version = _SHEETS_VERSION

if "batch_service" not in st.session_state:
    st.session_state.batch_service = BatchService()

if "candidates" not in st.session_state:
    st.session_state.candidates = []

if "selected_candidate_idx" not in st.session_state:
    st.session_state.selected_candidate_idx = 0

if "target_count" not in st.session_state:
    st.session_state.target_count = 5

if "batch_id" not in st.session_state:
    st.session_state.batch_id = ""

if "partner_candidates" not in st.session_state:
    st.session_state.partner_candidates = []

if "selected_partner_idx" not in st.session_state:
    st.session_state.selected_partner_idx = 0

if "partner_batch_id" not in st.session_state:
    st.session_state.partner_batch_id = ""

if "news_candidates" not in st.session_state:
    st.session_state.news_candidates = []

if "selected_news_idx" not in st.session_state:
    st.session_state.selected_news_idx = 0

if "news_batch_id" not in st.session_state:
    st.session_state.news_batch_id = ""

if "saved_status" not in st.session_state:
    st.session_state.saved_status = None

# Helper to refresh Google Sheets status
def refresh_connections():
    st.session_state.sheets = SheetsClient()
    try:
        st.session_state.gemini = GeminiClient()
    except Exception:
        st.session_state.gemini = None

# ----------------- SIDEBAR: API Status & Info -----------------
with st.sidebar:
    st.markdown("### 🤖 AIKA Connections")

    # 1. API Status Badges
    gemini_ok = False
    if st.session_state.gemini:
        with st.spinner("Testing Gemini..."):
            gemini_ok = st.session_state.gemini.test_connection()

    gemini_badge = "🟢 Gemini OK" if gemini_ok else "🔴 Gemini Off"
    sheets_ok = st.session_state.sheets.is_connected()
    sheets_badge = "🟢 Sheets OK" if sheets_ok else "🔴 Sheets Off"

    # 1.5 Auditor Connection Badge
    from services.audit_agent import GPTNewsAuditor
    gpt_auditor = GPTNewsAuditor()
    gpt_ok = gpt_auditor.is_available()
    provider_name = gpt_auditor.audit_provider.upper() if hasattr(gpt_auditor, 'audit_provider') else 'AUDITOR'
    gpt_badge = f"🟢 {provider_name} Standby OK" if gpt_ok else "🔴 Auditor Off"

    st.markdown(f'<small>{gemini_badge} | {sheets_badge} | {gpt_badge}</small>', unsafe_allow_html=True)
    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
    
    # 0. Pipeline Mode Selector Widget (Standard vs Reversed)
    curr_pipeline_mode = os.getenv("PIPELINE_MODE", "standard").strip().lower()
    pipeline_mode_options = ["standard", "reversed"]
    p_curr_idx = 1 if curr_pipeline_mode == "reversed" else 0

    selected_pipeline_mode = st.radio(
        "🔀 파이프라인 모델 역할 스위처",
        pipeline_mode_options,
        index=p_curr_idx,
        format_func=lambda x: "🔵 기본 모드 (메인: Gemini | 검증: 선택 검증 모델)" if x == "standard" else "🔄 역전 모드 (메인: GPT-4o | 검증: Gemini)",
        key="sb_pipeline_mode_selector",
        help="메인 웹 탐색 모델과 3단계 교차 검증 모델의 역할을 서로 맞바꾸어 실행합니다."
    )

    if selected_pipeline_mode != curr_pipeline_mode:
        os.environ["PIPELINE_MODE"] = selected_pipeline_mode
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            if "PIPELINE_MODE=" in content:
                content = re.sub(r'PIPELINE_MODE=.*', f'PIPELINE_MODE={selected_pipeline_mode}', content)
            else:
                content += f"\nPIPELINE_MODE={selected_pipeline_mode}\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        st.success(f"파이프라인 역할 모드가 `{'기본 (Gemini 수집 / 선택 검증)' if selected_pipeline_mode == 'standard' else '역전 (GPT 수집 / Gemini 검증)'}`(으)로 전환되었습니다.")
        st.rerun()

    # 1. Gemini Primary Model Switcher Widget in Sidebar
    curr_gemini_model = os.getenv("DISCOVERY_MODEL", "gemini-3.5-flash").strip()
    gemini_options = ["gemini-3.5-flash", "gemini-2.5-flash"]
    g_curr_idx = gemini_options.index(curr_gemini_model) if curr_gemini_model in gemini_options else 0

    selected_gemini_model = st.selectbox(
        "🔍 기사 검색 모델 선택",
        gemini_options,
        index=g_curr_idx,
        format_func=lambda x: "⚡ Gemini 3.5 Flash (최신 모델)" if x == "gemini-3.5-flash" else "🟢 Gemini 2.5 Flash (안정 모델)",
        key="sb_gemini_model_selector",
        help="1차 실시간 웹 탐색 및 수집에 사용할 메인 Gemini AI 모델 버전을 선택합니다."
    )

    if selected_gemini_model != curr_gemini_model:
        os.environ["DISCOVERY_MODEL"] = selected_gemini_model
        os.environ["STRUCTURE_MODEL"] = selected_gemini_model
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            if "DISCOVERY_MODEL=" in content:
                content = re.sub(r'DISCOVERY_MODEL=.*', f'DISCOVERY_MODEL={selected_gemini_model}', content)
            else:
                content += f"\nDISCOVERY_MODEL={selected_gemini_model}\n"
            if "STRUCTURE_MODEL=" in content:
                content = re.sub(r'STRUCTURE_MODEL=.*', f'STRUCTURE_MODEL={selected_gemini_model}', content)
            else:
                content += f"\nSTRUCTURE_MODEL={selected_gemini_model}\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        if st.session_state.gemini:
            st.session_state.gemini.discovery_model_name = selected_gemini_model
            st.session_state.gemini.structure_model_name = selected_gemini_model
        st.success(f"Gemini 모델이 `{selected_gemini_model}`(으)로 변경되었습니다.")
        st.rerun()

    # 2. Auditor Model Switcher Widget in Sidebar (Claude vs GPT vs Gemini)
    model_options = ["claude-sonnet-4-6", "gpt-4o", "gpt-4o-mini", "gemini-2.5-flash"]
    curr_provider = os.getenv("AUDIT_PROVIDER", "").strip().lower()
    
    if curr_provider == "claude":
        curr_audit_model = os.getenv("CLAUDE_AUDIT_MODEL", "claude-sonnet-4-6").strip()
    elif curr_provider == "gpt":
        curr_audit_model = os.getenv("GPT_AUDIT_MODEL", "gpt-4o").strip()
    elif curr_provider == "gemini":
        curr_audit_model = "gemini-2.5-flash"
    else:
        if os.getenv("ANTHROPIC_API_KEY"):
            curr_audit_model = os.getenv("CLAUDE_AUDIT_MODEL", "claude-sonnet-4-6").strip()
        elif os.getenv("OPENAI_API_KEY"):
            curr_audit_model = os.getenv("GPT_AUDIT_MODEL", "gpt-4o").strip()
        else:
            curr_audit_model = "gemini-2.5-flash"

    curr_idx = model_options.index(curr_audit_model) if curr_audit_model in model_options else 0

    def format_audit_model(x):
        if x == "claude-sonnet-4-6":
            return "🟠 Claude Sonnet 4.6 (Anthropic)"
        elif x == "gpt-4o":
            return "⚡ GPT-4o (OpenAI)"
        elif x == "gpt-4o-mini":
            return "🎈 GPT-4o-mini (OpenAI)"
        elif x == "gemini-2.5-flash":
            return "🟢 Gemini 2.5 Flash (Google)"
        return x

    selected_audit_model = st.selectbox(
        "🛡️ 검증 (Auditor) 모델 선택",
        model_options,
        index=curr_idx,
        format_func=format_audit_model,
        key="sb_audit_model_selector",
        help="팩트 및 출처 3단계 교차 검증에 사용할 AI 모델(Claude / GPT-4o / Gemini)을 선택합니다."
    )

    if selected_audit_model != curr_audit_model:
        env_path = os.path.join(os.getcwd(), ".env")
        import re
        if selected_audit_model.startswith("claude"):
            os.environ["AUDIT_PROVIDER"] = "claude"
            os.environ["CLAUDE_AUDIT_MODEL"] = selected_audit_model
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r'AUDIT_PROVIDER=.*', 'AUDIT_PROVIDER=claude', content) if "AUDIT_PROVIDER=" in content else content + "\nAUDIT_PROVIDER=claude\n"
                content = re.sub(r'CLAUDE_AUDIT_MODEL=.*', f'CLAUDE_AUDIT_MODEL={selected_audit_model}', content) if "CLAUDE_AUDIT_MODEL=" in content else content + f"\nCLAUDE_AUDIT_MODEL={selected_audit_model}\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        elif selected_audit_model.startswith("gpt"):
            os.environ["AUDIT_PROVIDER"] = "gpt"
            os.environ["GPT_AUDIT_MODEL"] = selected_audit_model
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r'AUDIT_PROVIDER=.*', 'AUDIT_PROVIDER=gpt', content) if "AUDIT_PROVIDER=" in content else content + "\nAUDIT_PROVIDER=gpt\n"
                content = re.sub(r'GPT_AUDIT_MODEL=.*', f'GPT_AUDIT_MODEL={selected_audit_model}', content) if "GPT_AUDIT_MODEL=" in content else content + f"\nGPT_AUDIT_MODEL={selected_audit_model}\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        elif selected_audit_model.startswith("gemini"):
            os.environ["AUDIT_PROVIDER"] = "gemini"
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = re.sub(r'AUDIT_PROVIDER=.*', 'AUDIT_PROVIDER=gemini', content) if "AUDIT_PROVIDER=" in content else content + "\nAUDIT_PROVIDER=gemini\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)

        st.success(f"검증 모델이 `{selected_audit_model}`(으)로 변경되었습니다.")
        st.rerun()

    if selected_pipeline_mode == "reversed":
        st.caption(f"🔍 Main Discovery: `GPT ({selected_audit_model})`")
        st.caption(f"🛡️ Auditor & Cross-Verifier: `Gemini ({selected_gemini_model})`")
    else:
        auditor_label = f"Claude ({getattr(gpt_auditor, 'claude_model_name', 'claude-sonnet-4-6')})" if getattr(gpt_auditor, "claude_client", None) else (f"GPT ({getattr(gpt_auditor, 'gpt_model_name', 'gpt-4o')})" if getattr(gpt_auditor, "client", None) else f"Gemini ({getattr(gpt_auditor, 'gemini_model_name', 'gemini-2.5-flash')})")
        st.caption(f"🔍 Main Discovery: `Gemini ({selected_gemini_model})`")
        st.caption(f"🛡️ Auditor & Cross-Verifier: `{auditor_label}`")

    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)


    # 2. Stats Board
    if sheets_ok:
        vendor_count = st.session_state.sheets.get_registered_vendor_count()
        partner_count = st.session_state.sheets.get_registered_partner_count()
        news_count = st.session_state.sheets.get_registered_news_count()

        scheduler = SchedulerService()
        v_info = scheduler.get_job_info("vendor")
        p_info = scheduler.get_job_info("partner")
        n_info = scheduler.get_job_info("news")

        p_target = st.session_state.get("p_target_count", 5)
        n_target = st.session_state.get("n_target_count", 5)

        vt = "🟢" if v_info["enabled"] else "⚪"
        pt = "🟢" if p_info["enabled"] else "⚪"
        nt = "🟢" if n_info["enabled"] else "⚪"

        st.markdown(f"""
        <div style='background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.08)); color: var(--text-color, inherit); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 10px; font-size: 0.85rem; line-height: 1.6;'>
            <div>🌐 <b>해외 벤더</b>: <b>{vendor_count}개</b> (목표 {st.session_state.target_count}개) {vt}</div>
            <div>🤝 <b>국내 파트너</b>: <b>{partner_count}개</b> (목표 {p_target}개) {pt}</div>
            <div>📰 <b>AI 뉴스</b>: <b>{news_count}개</b> (목표 {n_target}개) {nt}</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("<small>🟢: 자동 예약 수집 작동 중 | ⚪: 비활성</small>", unsafe_allow_html=True)
    else:
        st.error("Google Sheets Disconnected")
        if hasattr(st.session_state.sheets, "last_error") and st.session_state.sheets.last_error:
            st.caption(f"⚠️ `{st.session_state.sheets.last_error}`")

    # 3. Google Sheets Quick Links
    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
    st.markdown("##### 🔗 구글 시트 바로가기")
    
    def _get_link_id(k):
        return os.getenv(k) or (st.secrets.get(k, "") if hasattr(st, "secrets") else "")

    v_sheet_id = _get_link_id("GOOGLE_SPREADSHEET_ID")
    p_sheet_id = _get_link_id("KOREAN_PARTNERS_SPREADSHEET_ID")
    n_sheet_id = _get_link_id("NEWS_SPREADSHEET_ID")

    v_sheet_url = f"https://docs.google.com/spreadsheets/d/{v_sheet_id}" if v_sheet_id else "#"
    p_sheet_url = f"https://docs.google.com/spreadsheets/d/{p_sheet_id}" if p_sheet_id else "#"
    n_sheet_url = f"https://docs.google.com/spreadsheets/d/{n_sheet_id}" if n_sheet_id else "#"

    st.link_button("🌐 해외 벤더 시트 열기 ↗", v_sheet_url, use_container_width=True)
    st.link_button("🤝 국내 파트너 시트 열기 ↗", p_sheet_url, use_container_width=True)
    st.link_button("📰 AI 뉴스 시트 열기 ↗", n_sheet_url, use_container_width=True)

    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Connections", use_container_width=True):
        refresh_connections()
        st.rerun()

    if st.button("🔒 로그아웃 (Logout)", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()



# ----------------- MAIN TITLE & ANNOUNCEMENT -----------------
st.markdown('<h1 class="main-header">AIKA Global AI Vendor Research Tool</h1>', unsafe_allow_html=True)
st.markdown("Discover, review, and save global AI vendors for the AIKA database.")

# Flash message
if st.session_state.saved_status:
    st.success(st.session_state.saved_status)
    if st.button("Clear Message (메시지 지우기)"):
        st.session_state.saved_status = None
        st.rerun()

# ----------------- TAB LAYOUT -----------------
tab1, tab_partner, tab_news, tab2 = st.tabs([
    "🔎 AI Vendor Discovery (해외 벤더 발굴)", 
    "🤝 Korean Partner Discovery (국내 파트너 발굴)", 
    "📰 AI News Intelligence (AI 뉴스 인텔리전스)",
    "📂 Recent Batches / Backups (실행 이력)"
])

with tab1:
    # ----------------- 1. RESEARCH PARAMETERS -----------------
    st.subheader("① Search Parameters")
    
    # Grid structure for input form
    col1, col2 = st.columns(2)
    
    with col1:
        region = st.selectbox(
            "Target Country or Region",
            ["Global", "North America", "United States", "Canada", "Europe", "United Kingdom", "Germany", "France", "Israel", "Singapore", "Japan", "Australia", "Other"]
        )
        
        categories_list = sorted(list(ALLOWED_CATEGORIES))
        if "All" in categories_list:
            categories_list.remove("All")
            categories_list = ["All"] + categories_list
            
        category = st.selectbox(
            "AI Category",
            categories_list
        )
        
    with col2:
        industries_list = st.multiselect(
            "Target Industries (Multi-select)",
            ["Financial Services", "Manufacturing", "Healthcare", "Retail", "Public Sector", "Telecommunications", "Logistics", "Education", "Energy", "General Enterprise", "Other"],
            default=["General Enterprise"]
        )
        
        korea_presence = st.selectbox(
            "Korea Market Presence Policy",
            ["포함하되 표시", "이미 한국 진출기업은 제외", "제한 없음"]
        )

    # Secondary Parameters Row
    col_row2_1, col_row2_2 = st.columns(2)
    with col_row2_1:
        target_count = st.selectbox(
            "Target Candidate Count (목표 수집 기업 수)",
            [5, 6, 7, 8, 9, 10],
            key="target_count"
        )

    # Advanced Settings Expander
    with st.expander("⚙️ Advanced Settings"):
        col_adv1, col_adv2 = st.columns(2)
        with col_adv1:
            min_confidence = st.slider("Minimum Confidence Score", 0, 100, 70, 5)
            max_discovery = st.slider("Max Search Candidates to Scan (스캔할 최대 후보 수)", 5, 30, 15, 1)
            exclude_hyperscale = st.toggle("Exclude Major Hyperscalers (e.g. MS, Google)", value=True)
        with col_adv2:
            exclude_existing = st.toggle("Auto-exclude Previously Saved Domains", value=True)
            custom_batch_id = st.text_input("Custom Batch ID (Leave empty for auto-generation)")
            
            # Load persistent default domains
            domain_cfg = load_domain_config()
            saved_vendor_domains = domain_cfg.get("vendor_domains", "ycombinator.com, crunchbase.com, producthunt.com, techcrunch.com")

            default_sources = st.text_area(
                "Default Preferred Domains (항시 우선 검색 도메인 - 자동 영구 저장)",
                value=saved_vendor_domains,
                height=80,
                key="v_def_domains",
                help="입력한 도메인은 새로고침 후에도 자동 보존됩니다. 쉼표(,)나 줄바꿈 작성 시 아래로 자동 확장됩니다."
            )
            if default_sources != saved_vendor_domains:
                save_domain_config("vendor_domains", default_sources)

            temporary_sources = st.text_area(
                "Temporary Extra Domains (이번 회차 임시 추가 도메인)",
                placeholder="e.g. sifted.eu, fintechweekly.com",
                height=60,
                key="v_temp_domains",
                help="이번 실행에만 임시로 추가할 도메인입니다."
            )


        render_timer_ui("vendor", "해외 벤더")

            
    # Trigger Search Button
    st.markdown("---")
    search_clicked = st.button(f"🚀 Search {target_count} AI Vendors", use_container_width=True)

    # ----------------- 2. PROCESSING STATE -----------------
    if search_clicked:
        if not gemini_ok:
            st.error("Cannot run research. Gemini API is disconnected. Please check your keys.")
        else:
            # Clear previous run state
            st.session_state.candidates = []
            st.session_state.saved_status = None
            st.session_state.selected_candidate_idx = 0
            clear_checkbox_keys()
            
            # Step 1: Generate Batch ID
            batch_service = st.session_state.batch_service
            if custom_batch_id.strip():
                batch_id = custom_batch_id.strip()
            else:
                batch_id = batch_service.generate_batch_id(category)
            st.session_state.batch_id = batch_id
            
            # Build search progress UI
            with st.status("Executing Research Pipeline...", expanded=True) as status_box:
                st.write("1. Retrieving existing domains from Google Sheet...")
                # Execute Step 1
                existing_domains = []
                if exclude_existing and sheets_ok:
                    try:
                        existing_domains = st.session_state.sheets.get_existing_domains()
                    except Exception as e:
                        logger.error(f"Error fetching domains: {e}")
                
                st.write("2. Querying Gemini API (Google Search Grounding)...")
                # Execute Step 2
                # Combine default and temporary preferred sources
                combined_sources = parse_domains(default_sources) + parse_domains(temporary_sources)

                
                preferred_sources_str = ", ".join(combined_sources) if combined_sources else "None (Search generally)"
                
                batch_params = {
                    "batch_id": batch_id,
                    "region": region,
                    "category": category,
                    "industries": " | ".join(industries_list),
                    "minimum_confidence_score": min_confidence,
                    "exclude_hyperscalers": exclude_hyperscale,
                    "korea_presence_policy": korea_presence,
                    "research_date": datetime.now().strftime("%Y-%m-%d"),
                    "preferred_sources": preferred_sources_str,
                    "target_count": target_count
                }
                
                discovery_report = ""
                try:
                    discovery_report = st.session_state.gemini.run_discovery_stage(batch_params, existing_domains)
                except Exception as e:
                    status_box.update(label="Research failed in discovery stage!", state="error")
                    st.error(f"Error in discovery stage: {e}")
                    if sheets_ok:
                        st.session_state.sheets.write_error_log(batch_id, str(e), "Gemini Discovery", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    st.stop()
                    
                st.write("3. Parsing and structuring JSON schema...")
                # Execute Step 3
                structured_data = {}
                try:
                    structured_data = st.session_state.gemini.run_structuring_stage(batch_id, discovery_report, target_count)
                except Exception as e:
                    status_box.update(label="Research failed in structuring stage!", state="error")
                    st.error(f"Error in structuring stage: {e}")
                    if sheets_ok:
                        st.session_state.sheets.write_error_log(batch_id, str(e), "Gemini Structuring", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    st.stop()
                    
                st.write("4. Running python validations & deduplication...")
                # Execute Step 4
                candidates = structured_data.get("candidates", [])
                valid_candidates = []
                validation_errors = []
                
                for c in candidates:
                    # Force batch ID and research date
                    c["batch_id"] = batch_id
                    c["research_date"] = batch_params["research_date"]
                    
                    # Run validator
                    val_res = validate_candidate(c, min_confidence)
                    if val_res["is_valid"]:
                        valid_candidates.append(val_res["sanitized_data"])
                    else:
                        validation_errors.append(f"{c.get('company_name', 'Unknown')}: {', '.join(val_res['errors'])}")
                
                status_box.update(label="Research pipeline completed!", state="complete")
            
            # Save candidates to session
            st.session_state.candidates = valid_candidates
            
            if validation_errors:
                st.warning("Some found companies were skipped due to validation rules:")
                for err in validation_errors:
                    st.write(f"- {err}")
            
            # Backup locally
            try:
                backup_payload = {
                    "batch_id": batch_id,
                    "research_date": batch_params["research_date"],
                    "region": region,
                    "category": category,
                    "industries": " | ".join(industries_list),
                    "candidates": valid_candidates,
                    "status": "Awaiting Review"
                }
                batch_service.save_local_backup(batch_id, backup_payload)
            except Exception as e:
                st.warning(f"Failed to create local JSON backup: {e}")
                
            if not valid_candidates:
                st.info("No candidates passed the criteria or confidence threshold. Try adjusting parameters.")
            else:
                st.success(f"Discovered **{len(valid_candidates)}** candidates matching criteria!")

    # ----------------- 3. RESULTS EDITOR & PREVIEW -----------------
    if st.session_state.candidates:
        st.markdown("---")
        st.subheader("② Review & Edit Candidates")
        
        # We split the screen: Left side candidate list/table, Right side details form editor
        col_list, col_edit = st.columns([1, 2])
        
        # Load current candidates to list
        cands = st.session_state.candidates
        
        # Initialize checkbox states in st.session_state if not present
        for idx, c in enumerate(cands):
            key = f"chk_save_{idx}"
            if key not in st.session_state:
                st.session_state[key] = c.get("save_to_sheet", True) # Default all to True initially
        
        # Callback for Select All checkbox
        def on_select_all_change():
            val = st.session_state.select_all
            for idx in range(len(cands)):
                st.session_state[f"chk_save_{idx}"] = val
        
        with col_list:
            st.write("Candidates List (후보 목록)")
            
            # Select All checkbox
            st.checkbox(
                "Select All (전체 선택/해제)",
                value=True,
                key="select_all",
                on_change=on_select_all_change
            )
            st.markdown("---")
            
            # Render candidates cards
            for idx, c in enumerate(cands):
                is_active = (idx == st.session_state.selected_candidate_idx)
                
                # Visual Highlight Header
                if is_active:
                    st.markdown(f'<div style="background-color: #EBF8FF; border-left: 5px solid #2B6CB0; padding: 6px 12px; border-radius: 4px; margin-top: 10px; font-weight: bold; color: #2B6CB0; font-size: 0.9em;">👀 Currently Reviewing (검토 중)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="background-color: #F7FAFC; border-left: 5px solid #CBD5E0; padding: 6px 12px; border-radius: 4px; margin-top: 10px; color: #718096; font-size: 0.9em;">📄 Candidate (대기 후보)</div>', unsafe_allow_html=True)
                
                key = f"chk_save_{idx}"
                is_selected = st.checkbox(
                    f"Save: {c['company_name']} ({c['confidence_score']} pts)",
                    key=key
                )
                c["save_to_sheet"] = is_selected
                
                # Radio button like selection to pick who to edit
                st.button(
                    f"🔎 Edit Profile: {c['company_name']}",
                    key=f"btn_edit_{idx}",
                    use_container_width=True,
                    on_click=select_candidate_callback,
                    args=(idx,)
                )
            
            st.markdown(f"Selected Candidate: **{cands[st.session_state.selected_candidate_idx]['company_name']}**")
            
        with col_edit:
            idx = st.session_state.selected_candidate_idx
            if idx < len(cands):
                curr = cands[idx]
                st.write(f"📝 Editing Profile: **{curr['company_name']}** (프로필 상세 수정)")
                
                # Details input form
                curr["company_name"] = st.text_input("Company Name (회사명)", curr.get("company_name", ""), key=f"name_{idx}")
                curr["official_website"] = st.text_input("Official Website (공식 홈페이지 URL)", curr.get("official_website", ""), key=f"web_{idx}")
                curr["normalized_domain"] = st.text_input("Normalized Domain (정규화 도메인 - 읽기전용)", curr.get("normalized_domain", ""), key=f"norm_{idx}", disabled=True)
                curr["headquarters_country"] = st.text_input("Headquarters Country (본사 소재 국가)", curr.get("headquarters_country", ""), key=f"country_{idx}")
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    # Retrieve standard category list with "All" prioritized
                    categories_list = sorted(list(ALLOWED_CATEGORIES))
                    if "All" in categories_list:
                        categories_list.remove("All")
                        categories_list = ["All"] + categories_list
                    curr["primary_ai_category"] = st.selectbox("Primary AI Category (대표 AI 카테고리)", categories_list, index=categories_list.index(curr.get("primary_ai_category", "Other")) if curr.get("primary_ai_category") in categories_list else 0, key=f"cat1_{idx}")
                with col_c2:
                    curr["secondary_ai_categories"] = st.text_input("Secondary Categories (상세 카테고리 - | 로 구분)", curr.get("secondary_ai_categories", ""), key=f"cat2_{idx}")
                    
                curr["main_ai_product"] = st.text_input("Main AI Product/Platform (대표 AI 제품/플랫폼)", curr.get("main_ai_product", ""), key=f"prod_{idx}")
                curr["company_summary"] = st.text_area("Company Summary (기업 요약 - 35~60단어)", curr.get("company_summary", ""), height=100, key=f"sum_{idx}")
                
                curr["target_customers"] = st.text_input("Target Customers (주요 고객층)", curr.get("target_customers", ""), key=f"tc_{idx}")
                curr["target_industries"] = st.text_input("Target Industries (적용 가능 산업군)", curr.get("target_industries", ""), key=f"ti_{idx}")
                curr["main_use_cases"] = st.text_input("Main Use Cases (주요 유즈케이스)", curr.get("main_use_cases", ""), key=f"uc_{idx}")
                curr["deployment_type"] = st.text_input("Deployment Type (배포 방식)", curr.get("deployment_type", ""), key=f"dep_{idx}")
                
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    curr["official_product_page"] = st.text_input("Product Page URL (공식 제품 페이지 URL)", curr.get("official_product_page", ""), key=f"up_{idx}")
                with col_u2:
                    curr["official_contact_page"] = st.text_input("Contact Page URL (공식 문의 페이지 URL)", curr.get("official_contact_page", ""), key=f"ucont_{idx}")
                    
                col_k1, col_k2 = st.columns(2)
                with col_k1:
                    curr["korea_presence_found"] = st.selectbox("Korea Presence Found (한국 진출 여부)", ["Yes", "No evidence found", "Review Required"], index=["Yes", "No evidence found", "Review Required"].index(curr.get("korea_presence_found", "No evidence found")) if curr.get("korea_presence_found") in ["Yes", "No evidence found", "Review Required"] else 1, key=f"kpres_{idx}")
                with col_k2:
                    curr["potential_korean_partner_type"] = st.text_input("Potential Korean Partner Type (잠재적 한국 파트너 유형)", curr.get("potential_korean_partner_type", ""), key=f"kpart_{idx}")
                    
                curr["korea_market_relevance"] = st.text_area("Korea Market Relevance Notes (한국 시장 연관성 분석)", curr.get("korea_market_relevance", ""), height=80, key=f"krel_{idx}")
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    curr["aika_recommendation"] = st.selectbox("Recommendation Status (추천 등급)", ["Strong Candidate", "Candidate"], index=["Strong Candidate", "Candidate"].index(curr.get("aika_recommendation", "Candidate")) if curr.get("aika_recommendation") in ["Strong Candidate", "Candidate"] else 1, key=f"rec_{idx}")
                with col_r2:
                    curr["review_status"] = st.selectbox("Review Status (검토 상태)", ["New", "Ready for Website Analysis", "Hold", "Rejected"], index=["New", "Ready for Website Analysis", "Hold", "Rejected"].index(curr.get("review_status", "New")) if curr.get("review_status") in ["New", "Ready for Website Analysis", "Hold", "Rejected"] else 0, key=f"rev_{idx}")
                    
                curr["primary_evidence_url"] = st.text_input("Primary Evidence Source URL (주요 근거 출처 URL)", curr.get("primary_evidence_url", ""), key=f"evid_{idx}")
                curr["research_notes"] = st.text_area("Research / Validation Notes (연구 및 검증 노트)", curr.get("research_notes", ""), height=80, key=f"notes_{idx}")

        # ----------------- 4. SAVE TO GOOGLE SHEET -----------------
        st.markdown("---")
        st.subheader("③ Export to Google Sheets Staging")
        
        save_target = [c for c in cands if c.get("save_to_sheet", True)]
        
        st.write(f"Preparing to save **{len(save_target)} of {len(cands)}** companies to Google Sheets.")
        
        save_button = st.button("💾 Save Selected Vendors to Google Sheets", use_container_width=True)
        
        if save_button:
            if not save_target:
                st.warning("Please select at least one vendor to save.")
            elif not sheets_ok:
                st.error("Google Sheets API is not connected. Saving local JSON backup instead.")
                # We save session as failed sheet run
                try:
                    backup_payload = {
                        "batch_id": st.session_state.batch_id,
                        "research_date": datetime.now().strftime("%Y-%m-%d"),
                        "candidates": cands,
                        "saved_candidates": save_target,
                        "status": "Google Sheet Save Failed"
                    }
                    path = st.session_state.batch_service.save_local_backup(st.session_state.batch_id, backup_payload)
                    st.info(f"Local backup stored in: `{path}`. You can recover and retry this batch from Tab 2.")
                except Exception as ex:
                    st.error(f"Failed to write local backup: {ex}")
            else:
                with st.spinner("Saving records to Google Spreadsheet..."):
                    # Double check duplicate domains before writing
                    sheets_client = st.session_state.sheets
                    existing_domains = sheets_client.get_existing_domains()
                    
                    final_to_save = []
                    duplicates = []
                    
                    for v in save_target:
                        domain = v.get("normalized_domain", "").lower()
                        if domain in existing_domains:
                            duplicates.append(f"{v['company_name']} ({domain})")
                        else:
                            final_to_save.append(v)
                            
                    if duplicates:
                        st.warning(f"Skipped {len(duplicates)} duplicates already in spreadsheet:\n" + "\n".join([f"- {d}" for d in duplicates]))
                        
                    if final_to_save:
                        res = sheets_client.append_vendors(final_to_save)
                        if res["success"]:
                            # Log batch
                            batch_info = {
                                "batch_id": st.session_state.batch_id,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "region": region,
                                "category": category,
                                "industries": " | ".join(industries_list),
                                "candidate_count": len(cands),
                                "saved_count": len(final_to_save),
                                "status": "Completed"
                            }
                            sheets_client.write_batch_log(batch_info)
                            
                            # Log to local backup as success
                            try:
                                backup_payload = {
                                    "batch_id": st.session_state.batch_id,
                                    "research_date": batch_info["timestamp"],
                                    "region": region,
                                    "category": category,
                                    "industries": batch_info["industries"],
                                    "candidates": cands,
                                    "saved_candidates": final_to_save,
                                    "status": "Saved to Sheets"
                                }
                                st.session_state.batch_service.save_local_backup(st.session_state.batch_id, backup_payload)
                            except Exception:
                                pass
                                
                            st.session_state.saved_status = f"Successfully saved **{len(final_to_save)}** vendors to Google Sheet. (선택한 {len(final_to_save)}개 기업을 구글 시트에 성공적으로 저장했습니다.)"
                            
                            # Clean state
                            st.session_state.candidates = []
                            st.session_state.selected_candidate_idx = 0
                            
                            # Automatically rerun to refresh registered count
                            st.rerun()
                        else:
                            st.error(f"Failed to write to Google Sheets: {res['error']}")
                            sheets_client.write_error_log(st.session_state.batch_id, res["error"], "Sheets Write", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

with tab_partner:
    # ----------------- 1. RESEARCH PARAMETERS -----------------
    st.subheader("① 국내 파트너사 리서치 매개변수")
    
    # Grid structure for input form
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        partner_category = st.selectbox(
            "대표 AI 카테고리 (Primary AI Category)",
            categories_list,
            index=0,
            key="p_category"
        )
        
        # Split search inputs for partner
        st.markdown("##### ⚙️ 국내 리서치 추가 도메인 설정")
        saved_partner_domains = domain_cfg.get("partner_domains", "zdnet.co.kr, ddaily.co.kr, datanet.co.kr, itdaily.kr, aitimes.com, etnews.com")
        p_default_domains = st.text_area(
            "항시 우선 검색 도메인 (자동 영구 저장)",
            value=saved_partner_domains,
            height=80,
            key="p_def_domains",
            help="입력한 도메인은 새로고침 후에도 자동 보존됩니다. 쉼표(,)나 줄바꿈 작성 시 아래로 자동 확장됩니다."
        )
        if p_default_domains != saved_partner_domains:
            save_domain_config("partner_domains", p_default_domains)

        p_temp_domains = st.text_area(
            "이번 회차 임시 추가 도메인",
            value="",
            height=60,
            key="p_temp_domains",
            help="이번 실행에만 임시로 추가할 도메인입니다."
        )

        
    with col_p2:
        partner_industries_list = st.multiselect(
            "선호 대상 산업군 (복수 선택 가능)",
            ["Financial Services", "Healthcare & Life Sciences", "Retail & E-commerce", "Manufacturing & Automotive", "Technology & Telecom", "Professional Services", "Public Sector & Education", "Media & Entertainment", "Logistics & Supply Chain", "Other"],
            default=["Financial Services", "Technology & Telecom"],
            key="p_industries"
        )
        
        partner_target_count = st.selectbox(
            "목표 수집 파트너 수",
            [1, 2, 3, 5, 8, 10],
            index=3,
            key="p_target_count"
        )
        
    # Advanced settings for partners
    with st.expander("⚙️ 고급 설정 (Advanced Settings)", expanded=False):
        col_p_adv1, col_p_adv2 = st.columns(2)
        with col_p_adv1:
            partner_min_score = st.slider(
                "최소 파트너십 적합도 점수 기준",
                50, 90, 70,
                key="p_min_score"
            )
            partner_exclude_small = st.toggle(
                "소규모 대행사 제외 및 중견/대기업 MSP/SI 위주 발굴",
                value=True,
                key="p_exclude_small"
            )
            partner_exclude_existing = st.toggle(
                "이미 등록된 파트너 도메인 제외",
                value=True,
                key="p_exclude_existing"
            )
        with col_p_adv2:
            partner_max_candidates = st.slider(
                "스캔할 최대 후보 수 (Max scan candidates)",
                5, 30, 15, 1,
                key="p_max_cand"
            )
            partner_custom_batch_id = st.text_input(
                "커스텀 배치 ID (미입력 시 자동생성)",
                key="p_custom_batch"
            )

        render_timer_ui("partner", "국내 파트너")

        
    # Generate search prompt combined domains
    p_combined_domains_list = parse_domains(p_default_domains) + parse_domains(p_temp_domains)
    p_combined_domains = ", ".join(p_combined_domains_list)

    
    st.markdown("---")
    
    # Execution button
    p_btn_label = f"국내 파트너사 {partner_target_count}개 리서치 시작"
    p_search_button = st.button(p_btn_label, use_container_width=True, key="p_search_btn")
    
    if p_search_button:
        if not gemini_ok:
            st.error("Gemini API Key가 누락되었거나 연결에 실패했습니다. 설정 및 API 키를 확인하세요.")
        else:
            # Clear previous partner run state
            st.session_state.partner_candidates = []
            st.session_state.saved_status = None
            st.session_state.selected_partner_idx = 0
            
            # Helper to clear checkbox keys for partner
            for key in list(st.session_state.keys()):
                if key.startswith("chk_partner_save_"):
                    del st.session_state[key]
            
            # Step 1: Generate Partner Batch ID
            batch_service = st.session_state.batch_service
            if partner_custom_batch_id.strip():
                p_batch_id = partner_custom_batch_id.strip()
            else:
                p_cat_code = CATEGORY_CODES.get(partner_category, "ALL")
                p_batch_id = f"KP-{p_cat_code}-{datetime.now().strftime('%Y%m%d')}-{random.randint(10,99)}"
            st.session_state.partner_batch_id = p_batch_id
            
            # Step 2: Fetch existing partner domains for deduplication
            p_existing_domains = []
            if partner_exclude_existing and sheets_ok:
                with st.spinner("구글 시트에서 기존 파트너 도메인 조회 중..."):
                    p_existing_domains = st.session_state.sheets.get_existing_partner_domains()
            
            p_batch_params = {
                "batch_id": p_batch_id,
                "vendor_match": "None (General search)",
                "category": partner_category,
                "industries": " | ".join(partner_industries_list),
                "target_count": partner_target_count,
                "minimum_confidence_score": partner_min_score,
                "research_date": datetime.now().strftime("%Y-%m-%d"),
                "preferred_sources": p_combined_domains,
                "max_discovery_candidates": partner_max_candidates,
                "exclude_small_agencies": partner_exclude_small
            }
            
            # Stage 1: Search and text report
            stage1_report = ""
            with st.status("🔍 1단계: 국내 파트너 웹 리서치 진행 중...", expanded=True) as status:
                try:
                    stage1_report = st.session_state.gemini.run_partner_discovery_stage(p_batch_params, p_existing_domains)
                    status.update(label="✓ 1단계: 국내 파트너 웹 리서치 완료!", state="complete")
                except Exception as e:
                    status.update(label=f"✗ 1단계 리서치 실패: {e}", state="error")
                    st.error(f"Error details: {e}")
                    
            if stage1_report:
                # Stage 2: JSON sequential candidate structuring
                with st.status("🏗️ 2단계: 개별 파트너 정보 구조화 진행 중...", expanded=True) as status_json:
                    try:
                        structured_res = st.session_state.gemini.run_partner_structuring_stage(
                            p_batch_id, stage1_report, partner_target_count
                        )
                        raw_cands = structured_res.get("candidates", [])
                        status_json.update(label=f"✓ 2단계: 파트너 구조화 완료 ({len(raw_cands)}개 파싱됨)", state="complete")
                    except Exception as e:
                        status_json.update(label=f"✗ 2단계 구조화 실패: {e}", state="error")
                        raw_cands = []
                        st.error(f"Error details: {e}")
                        
                # Stage 3: Python validation and final filtering
                valid_partners = []
                for c in raw_cands:
                    # Basic sanitization
                    if partner_exclude_existing:
                        domain = c.get("normalized_domain", "").strip().lower()
                        if domain in p_existing_domains:
                            logger.info(f"Duplicate domain excluded in validation: {domain}")
                            continue
                            
                    # Always force headquarters_country to South Korea
                    c["headquarters_country"] = "South Korea"
                    c["korea_presence_found"] = "Yes"
                    c["b2b_product_confirmed"] = "Yes"
                    c["proprietary_product_confirmed"] = "Yes"
                    c["review_status"] = "New"
                    c["processing_status"] = "Completed"
                    c["research_date"] = p_batch_params["research_date"]
                    c["batch_id"] = p_batch_id
                    
                    valid_partners.append(c)
                    
                # Save locally
                try:
                    p_backup_payload = {
                        "batch_id": p_batch_id,
                        "research_date": p_batch_params["research_date"],
                        "vendor_match": "None",
                        "category": partner_category,
                        "industries": " | ".join(partner_industries_list),
                        "candidates": valid_partners,
                        "status": "Awaiting Review"
                    }
                    st.session_state.batch_service.save_local_backup(p_batch_id, p_backup_payload)
                except Exception as e:
                    st.warning(f"로컬 백업 생성 실패: {e}")
                    
                if not valid_partners:
                    st.info("검증 조건이나 점수 기준을 통과한 파트너사 후보가 없습니다. 검색 조건을 조정해 보세요.")
                else:
                    st.success(f"조건에 맞는 **{len(valid_partners)}**개의 국내 파트너사를 성공적으로 찾았습니다!")
                    st.session_state.partner_candidates = valid_partners
                    st.session_state.selected_partner_idx = 0
                    
    # ----------------- 3. PARTNERS EDITOR & PREVIEW -----------------
    if st.session_state.partner_candidates:
        st.markdown("---")
        st.subheader("② 국내 파트너 정보 검토 및 수정 (Review & Edit)")
        
        col_p_list, col_p_edit = st.columns([1, 2])
        partner_cands = st.session_state.partner_candidates
        
        # Initialize checkbox states
        for idx, c in enumerate(partner_cands):
            p_key = f"chk_partner_save_{idx}"
            if p_key not in st.session_state:
                st.session_state[p_key] = c.get("save_to_sheet", True)
                
        def on_partner_select_all_change():
            val = st.session_state.partner_select_all
            for idx in range(len(partner_cands)):
                st.session_state[f"chk_partner_save_{idx}"] = val
                
        with col_p_list:
            st.write("후보 목록 (Candidates List)")
            
            st.checkbox(
                "전체 선택/해제 (Select All)",
                value=True,
                key="partner_select_all",
                on_change=on_partner_select_all_change
            )
            st.markdown("---")
            
            for idx, c in enumerate(partner_cands):
                is_active = (idx == st.session_state.selected_partner_idx)
                
                if is_active:
                    st.markdown(f'<div style="background-color: #EBF8FF; border-left: 5px solid #2B6CB0; padding: 6px 12px; border-radius: 4px; margin-top: 10px; font-weight: bold; color: #2B6CB0; font-size: 0.9em;">👀 현재 검토 중</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="background-color: #F7FAFC; border-left: 5px solid #CBD5E0; padding: 6px 12px; border-radius: 4px; margin-top: 10px; color: #718096; font-size: 0.9em;">📄 대기 후보</div>', unsafe_allow_html=True)
                    
                p_key = f"chk_partner_save_{idx}"
                is_selected = st.checkbox(
                    f"저장: {c['company_name']} ({c['confidence_score']} 점)",
                    key=p_key
                )
                c["save_to_sheet"] = is_selected
                
                st.button(
                    f"🔎 프로필 수정: {c['company_name']}",
                    key=f"btn_partner_edit_{idx}",
                    use_container_width=True,
                    on_click=select_partner_callback,
                    args=(idx,)
                )
                
            st.markdown(f"선택된 파트너: **{partner_cands[st.session_state.selected_partner_idx]['company_name']}**")
            
        with col_p_edit:
            idx = st.session_state.selected_partner_idx
            if idx < len(partner_cands):
                curr = partner_cands[idx]
                st.write(f"📝 상세 수정: **{curr['company_name']}**")
                
                curr["company_name"] = st.text_input("국내 파트너사명", curr.get("company_name", ""), key=f"p_name_{idx}")
                curr["official_website"] = st.text_input("공식 홈페이지 URL", curr.get("official_website", ""), key=f"p_web_{idx}")
                curr["normalized_domain"] = st.text_input("정규화 도메인 (읽기 전용)", curr.get("normalized_domain", ""), key=f"p_norm_{idx}", disabled=True)
                curr["headquarters_country"] = st.text_input("본사 소재국 (읽기 전용)", curr.get("headquarters_country", "South Korea"), key=f"p_country_{idx}", disabled=True)
                
                col_pc1, col_pc2 = st.columns(2)
                with col_pc1:
                    categories_list = sorted(list(ALLOWED_CATEGORIES))
                    if "All" in categories_list:
                        categories_list.remove("All")
                        categories_list = ["All"] + categories_list
                    curr["primary_ai_category"] = st.selectbox("대표 AI 카테고리", categories_list, index=categories_list.index(curr.get("primary_ai_category", "Other")) if curr.get("primary_ai_category") in categories_list else 0, key=f"p_cat1_{idx}")
                with col_pc2:
                    curr["secondary_ai_categories"] = st.text_input("상세 카테고리 ( | 로 구분)", curr.get("secondary_ai_categories", ""), key=f"p_cat2_{idx}")
                    
                curr["main_ai_product"] = st.text_input("매칭/유통 대상 해외 벤더사명 및 솔루션", curr.get("main_ai_product", ""), key=f"p_prod_{idx}")
                curr["company_summary"] = st.text_area("회사 요약 (기업 소개)", curr.get("company_summary", ""), height=100, key=f"p_sum_{idx}")
                
                curr["target_customers"] = st.text_input("주요 고객층", curr.get("target_customers", ""), key=f"p_tc_{idx}")
                curr["target_industries"] = st.text_input("적용 가능 산업군", curr.get("target_industries", ""), key=f"p_ti_{idx}")
                curr["main_use_cases"] = st.text_input("주요 유즈케이스", curr.get("main_use_cases", ""), key=f"p_uc_{idx}")
                curr["deployment_type"] = st.text_input("배포 환경", curr.get("deployment_type", ""), key=f"p_dep_{idx}")
                
                col_pu1, col_pu2 = st.columns(2)
                with col_pu1:
                    curr["official_product_page"] = st.text_input("공식 제품 페이지 URL", curr.get("official_product_page", ""), key=f"p_up_{idx}")
                with col_pu2:
                    curr["official_contact_page"] = st.text_input("공식 문의 페이지 URL", curr.get("official_contact_page", ""), key=f"p_ucont_{idx}")
                    
                col_pk1, col_pk2 = st.columns(2)
                with col_pk1:
                    curr["potential_korean_partner_type"] = st.text_input("국내 파트너십 형태 및 등급 (예: 공식 총판, 리셀러)", curr.get("potential_korean_partner_type", ""), key=f"p_kpart_{idx}")
                with col_pk2:
                    curr["confidence_score"] = st.number_input("파트너십 적합도 및 역량 점수 (70~100점)", min_value=50, max_value=100, value=int(curr.get("confidence_score", 70)), key=f"p_score_num_{idx}")
                    
                curr["korea_market_relevance"] = st.text_area("국내 시장 내 입지 및 파트너십 영향력 특징", curr.get("korea_market_relevance", ""), height=80, key=f"p_krel_{idx}")
                
                col_pr1, col_pr2 = st.columns(2)
                with col_pr1:
                    curr["aika_recommendation"] = st.selectbox("AIKA 추천 등급", ["Strong Partner", "Partner"], index=["Strong Partner", "Partner"].index(curr.get("aika_recommendation", "Partner")) if curr.get("aika_recommendation") in ["Strong Partner", "Partner"] else 1, key=f"p_rec_{idx}")
                with col_pr2:
                    curr["review_status"] = st.selectbox("검토 상태", ["New", "Approved", "Hold", "Rejected"], index=["New", "Approved", "Hold", "Rejected"].index(curr.get("review_status", "New")) if curr.get("review_status") in ["New", "Approved", "Hold", "Rejected"] else 0, key=f"p_rev_{idx}")
                    
                curr["primary_evidence_url"] = st.text_input("매칭/파트너십 근거 출처 URL", curr.get("primary_evidence_url", ""), key=f"p_evid_{idx}")
                curr["research_notes"] = st.text_area("리서치 관련 추가 설명 및 산출 근거", curr.get("research_notes", ""), height=80, key=f"p_notes_{idx}")
                
        # ----------------- 4. SAVE TO GOOGLE SHEET -----------------
        st.markdown("---")
        st.subheader("③ 구글 스프레드시트에 저장")
        
        p_save_target = [c for c in partner_cands if c.get("save_to_sheet", True)]
        st.write(f"현재 선택된 **{len(p_save_target)} / {len(partner_cands)}**개의 파트너사를 저장할 준비가 되었습니다.")
        
        p_save_button = st.button("💾 선택한 파트너 구글 스프레드시트에 저장", use_container_width=True, key="p_save_btn")
        
        if p_save_button:
            if not p_save_target:
                st.warning("저장할 파트너사를 최소 1개 이상 선택해 주세요.")
            elif not sheets_ok:
                st.error("Google Sheets API 연결이 끊겼습니다. 로컬 JSON 백업만 진행합니다.")
                try:
                    p_backup_payload = {
                        "batch_id": st.session_state.partner_batch_id,
                        "research_date": datetime.now().strftime("%Y-%m-%d"),
                        "candidates": partner_cands,
                        "saved_candidates": p_save_target,
                        "status": "Google Sheet Save Failed"
                    }
                    path = st.session_state.batch_service.save_local_backup(st.session_state.partner_batch_id, p_backup_payload)
                    st.info(f"로컬 백업 경로: `{path}`. 히스토리 탭에서 나중에 복구할 수 있습니다.")
                except Exception as ex:
                    st.error(f"로컬 백업 저장 실패: {ex}")
            else:
                with st.spinner("구글 스프레드시트에 저장 중..."):
                    sheets_client = st.session_state.sheets
                    p_existing_domains = sheets_client.get_existing_partner_domains()
                    
                    final_p_to_save = []
                    p_duplicates = []
                    
                    for v in p_save_target:
                        domain = v.get("normalized_domain", "").lower()
                        if domain in p_existing_domains:
                            p_duplicates.append(f"{v['company_name']} ({domain})")
                        else:
                            final_p_to_save.append(v)
                            
                    if p_duplicates:
                        st.warning(f"이미 구글 시트에 존재하는 중복 파트너사 {len(p_duplicates)}개를 제외하고 저장합니다:\n" + "\n".join([f"- {d}" for d in p_duplicates]))
                        
                    if final_p_to_save:
                        res = sheets_client.append_partners(final_p_to_save)
                        if res["success"]:
                            # Log batch
                            batch_info = {
                                "batch_id": st.session_state.partner_batch_id,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "region": "South Korea",
                                "category": partner_category,
                                "industries": " | ".join(partner_industries_list),
                                "candidate_count": len(partner_cands),
                                "saved_count": len(final_p_to_save),
                                "status": "Completed"
                            }
                            sheets_client.write_batch_log(batch_info)
                            
                            try:
                                p_backup_payload = {
                                    "batch_id": st.session_state.partner_batch_id,
                                    "research_date": batch_info["timestamp"],
                                    "vendor_match": "None",
                                    "category": partner_category,
                                    "industries": batch_info["industries"],
                                    "candidates": partner_cands,
                                    "saved_candidates": final_p_to_save,
                                    "status": "Saved to Sheets"
                                }
                                st.session_state.batch_service.save_local_backup(st.session_state.partner_batch_id, p_backup_payload)
                            except Exception:
                                pass
                                
                            st.session_state.saved_status = f"성공적으로 {len(final_p_to_save)}개의 파트너사를 구글 시트에 저장했습니다! (시트 저장 완료)"
                            st.session_state.partner_candidates = []
                            st.session_state.selected_partner_idx = 0
                            st.rerun()
                        else:
                            st.error(f"구글 시트 저장 실패: {res['error']}")
                            sheets_client.write_error_log(st.session_state.partner_batch_id, res["error"], "Sheets Write (Partner)", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

with tab_news:
    # ----------------- 1. RESEARCH PARAMETERS -----------------
    st.subheader("① AI 뉴스 인텔리전스 리서치 매개변수")
    
    col_n1, col_n2 = st.columns(2)
    
    news_topics_list = [
        "All", 
        "AI Investment & M&A", 
        "AI Policy & Regulation", 
        "Korea AI Market", 
        "Big Tech AI", 
        "AI Research & Breakthroughs", 
        "AI Product Launch", 
        "AI Industry Trends", 
        "Other News"
    ]
    
    with col_n1:
        news_primary_cat = st.selectbox(
            "대표 AI 카테고리 (Primary AI Category - 벤더/파트너 DB 매칭 키)",
            categories_list,
            index=0,
            key="n_primary_cat"
        )
        
        news_topic = st.selectbox(
            "뉴스 세부 주제 (News Topic)",
            news_topics_list,
            index=0,
            key="n_topic"
        )
        
        st.markdown("##### ⚙️ 뉴스 리서치 출처 도메인 설정")
        saved_news_domains = domain_cfg.get("news_domains", "zdnet.co.kr, etnews.com, techcrunch.com, venturebeat.com, reuters.com")
        
        include_vendor_official = st.checkbox(
            "🏢 AI 벤더 공식 뉴스룸/블로그 자동 포함 (OpenAI, Gemini, Claude, Hugging Face, OpenRouter, Meta, MS)",
            value=True,
            key="n_inc_vendor_official",
            help="OpenAI, Google AI/DeepMind, Anthropic, Hugging Face, OpenRouter, Meta AI, Microsoft AI 공식 블로그/뉴스룸 도메인을 우선 수집 도메인에 자동 포함합니다."
        )
        vendor_official_domains = "openai.com, blog.google, deepmind.google, anthropic.com, huggingface.co, openrouter.ai, ai.meta.com, blogs.microsoft.com"
        
        n_default_domains = st.text_area(
            "항시 우선 검색 도메인 (자동 영구 저장)",
            value=saved_news_domains,
            height=80,
            key="n_def_domains",
            help="입력한 도메인은 새로고침 후에도 자동 보존됩니다. 쉼표(,)나 줄바꿈 작성 시 아래로 자동 확장됩니다."
        )
        if n_default_domains != saved_news_domains:
            save_domain_config("news_domains", n_default_domains)

        n_temp_domains_raw = st.text_area(
            "이번 회차 임시 추가 도메인",
            value="",
            height=60,
            key="n_temp_domains",
            help="이번 실행에만 임시로 추가할 도메인입니다."
        )
        n_temp_domains = (n_temp_domains_raw + (", " + vendor_official_domains if include_vendor_official else "")).strip(", ")

        
    with col_n2:
        news_language = st.selectbox(
            "기사 언어 선호도 (Language)",
            ["All (EN + KO)", "Korean (KO)", "English (EN)"],
            index=0,
            key="n_language"
        )
        
        news_target_count = st.number_input(
            "검색 상한 (1 ~ 50개)",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="n_target_count",
            help="탐색 시 시도할 최대 기사 수(상한선)입니다. 실제 검증 통과분만 시트에 저장됩니다."
        )
        
        from datetime import timedelta, date
        default_since = date.today() - timedelta(days=30)
        news_since_date = st.date_input(
            "📅 기사 게재일 기준 (이 날짜 이후 기사만 수집)",
            value=default_since,
            key="n_since_date",
            help="선택한 날짜 이후(Since Date)에 게재된 최신 AI 뉴스만 엄선하여 수집합니다."
        )

        
    with st.expander("⚙️ 고급 설정 (Advanced Settings)", expanded=False):
        col_n_adv1, col_n_adv2 = st.columns(2)
        with col_n_adv1:
            news_exclude_existing = st.toggle(
                "이미 수집된 기사 URL 자동 제외",
                value=True,
                key="n_exclude_existing"
            )
        with col_n_adv2:
            news_custom_batch_id = st.text_input(
                "커스텀 배치 ID (미입력 시 자동생성)",
                key="n_custom_batch"
            )

        st.markdown("##### 📡 뉴스 탐색 채널 선택 (Discovery Channels)")
        col_ch1, col_ch2, col_ch3 = st.columns(3)
        with col_ch1:
            enable_gemini_ch = st.checkbox("Gemini Grounding", value=True, key="chk_gemini_ch")
        with col_ch2:
            enable_gnews_rss_ch = st.checkbox("Google News RSS (when:Nd)", value=True, key="chk_gnews_rss_ch")
        with col_ch3:
            enable_direct_rss_ch = st.checkbox("주요 매체 직접 RSS", value=True, key="chk_direct_rss_ch")

        render_timer_ui("news", "AI 뉴스")

            
    n_combined_domains_list = parse_domains(n_default_domains) + parse_domains(n_temp_domains)
    n_combined_domains = ", ".join(n_combined_domains_list)

    
    st.markdown("---")
    
    since_str = news_since_date.strftime('%Y-%m-%d')
    n_btn_label = f"📰 AI 뉴스 {news_target_count}개 수집 및 분석 시작 ({since_str} 이후)"
    n_search_button = st.button(n_btn_label, use_container_width=True, key="n_search_btn")
    
    if n_search_button:
        if not gemini_ok:
            st.error("Gemini API Key가 누락되었거나 연결에 실패했습니다. 설정 및 API 키를 확인하세요.")
        else:
            st.session_state.news_candidates = []
            st.session_state.saved_status = None
            st.session_state.selected_news_idx = 0
            
            for key in list(st.session_state.keys()):
                if key.startswith("chk_news_save_"):
                    del st.session_state[key]
                    
            if news_custom_batch_id.strip():
                n_batch_id = news_custom_batch_id.strip()
            else:
                n_cat_code = CATEGORY_CODES.get(news_primary_cat, "ALL")
                n_batch_id = f"NEWS-{n_cat_code}-{datetime.now().strftime('%Y%m%d')}-{random.randint(10,99)}"
            st.session_state.news_batch_id = n_batch_id
            
            n_existing_urls = []
            if news_exclude_existing and sheets_ok:
                with st.spinner("구글 시트에서 기존 기사 URL 조회 중..."):
                    n_existing_urls = st.session_state.sheets.get_existing_news_urls()
                    
            n_batch_params = {
                "batch_id": n_batch_id,
                "primary_category": news_primary_cat,
                "news_topic": news_topic,
                "language": news_language,
                "target_count": news_target_count,
                "research_date": datetime.now().strftime("%Y-%m-%d"),
                "since_date": since_str,
                "preferred_sources": n_combined_domains,
                "enable_gemini": enable_gemini_ch,
                "enable_google_news_rss": enable_gnews_rss_ch,
                "enable_direct_rss": enable_direct_rss_ch,
            }
            
            col_run_left, col_run_right = st.columns([3, 2])
            right_box = col_run_right.empty()

            def update_realtime_urls(urls_list, current_msg=""):
                with right_box.container():
                    st.markdown("##### 🌐 1차 탐색 수집 참고 URL 전체 리스트")
                    if current_msg:
                        st.caption(f"🔄 {current_msg}")
                    if urls_list:
                        st.caption(f"총 **{len(urls_list)}개**의 실시간 수집 출처 URL 보관됨:")
                        for g_idx, g_item in enumerate(urls_list, 1):
                            t_title = g_item.get('title') if isinstance(g_item, dict) else str(g_item)
                            g_uri = g_item.get('uri') if isinstance(g_item, dict) else str(g_item)
                            st.markdown(f"**{g_idx}. [{t_title[:45]}...]({g_uri})**")
                            st.caption(g_uri)
                    else:
                        st.info("실시간 검색 진행 중... 발견된 URL이 이곳 우측 패널에 즉시 나타납니다.")

            # Render initial state on right panel
            update_realtime_urls(st.session_state.get("news_grounding_urls", []), "")

            raw_news = []
            with col_run_left:
                with st.status("🔍 1단계: 뉴스 후보 기사 오버패칭 실시간 탐색 중...", expanded=True) as status:
                    try:
                        def update_status(msg, urls=None):
                            status.write(msg)
                            if urls:
                                st.session_state["news_grounding_urls"] = urls
                                update_realtime_urls(urls, msg)

                        tri_res = st.session_state.gemini.run_tri_engine_discovery(
                            n_batch_params, n_existing_urls, status_callback=update_status
                        )
                        raw_news = tri_res.get("candidates", [])
                        g_urls_discovered = getattr(st.session_state.gemini, "_last_grounding_urls", [])
                        st.session_state["news_grounding_urls"] = g_urls_discovered
                        update_realtime_urls(g_urls_discovered, "1차 후보 수집 완료")
                        status.update(label=f"✓ 1단계: 실시간 후보 탐색 및 2차 교차검증 완료 ({len(raw_news)}개 기사 승인 / {len(g_urls_discovered)}개 참고 URL 확보)", state="complete")
                    except Exception as e:
                        status.update(label=f"✗ 1단계 탐색 및 검증 실패: {e}", state="error")
                        st.error(f"Error details: {e}")
                        
                audited_news = []
                if raw_news:
                    with st.status("🛡️ 2-3단계: URL 정합성 및 최종 검증 (validator.py) 확인 중...", expanded=True) as status_audit:
                        try:
                            from services.validator import validate_article
                            rejected_items = []

                            for idx, a in enumerate(raw_news, 1):
                                title = a.get("title", "")
                                title_kr = a.get("korean_title", title)
                                media = a.get("source_media", "News")
                                raw_url = a.get("source_url", "")

                                status_audit.write(f"[{idx}/{len(raw_news)}] '{title_kr[:25]}...' URL & 게재일 검증 중...")

                                v_res = validate_article(
                                    url=raw_url,
                                    source_media=media,
                                    cutoff_date=news_since_date if isinstance(news_since_date, date) else None,
                                    existing_urls=set(n_existing_urls)
                                )

                                if v_res["passed"]:
                                    a["source_url"] = v_res["final_url"]
                                    if v_res["published_at"]:
                                        a["published_date"] = v_res["published_at"]
                                    a["audit_status"] = "Approved (Validator Passed)"
                                    audited_news.append(a)
                                    status_audit.write(f"  ✅ 통과: 게재일={v_res['published_at']}, URL={v_res['final_url']}")
                                else:
                                    reason = v_res["reason"]
                                    a["audit_status"] = f"Rejected ({reason})"
                                    rejected_items.append({
                                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "batch_id": n_batch_id,
                                        "reason": reason,
                                        "url": raw_url,
                                        "title": title,
                                        "discovery_channel": a.get("discovery_channel", "gemini")
                                    })
                                    status_audit.write(f"  ❌ 탈락 사유: {reason}")

                            # Write rejected items to _rejected tab in Google Sheets
                            if rejected_items and sheets_ok:
                                try:
                                    st.session_state.sheets.append_rejected_news(rejected_items)
                                except Exception as r_err:
                                    logger.warning(f"Failed to record rejected items to sheet: {r_err}")

                            # Save local audit log file for Tab 4 analysis
                            try:
                                all_log_records = rejected_items + [
                                    {
                                        "title": a.get("title"),
                                        "url": a.get("source_url"),
                                        "media": a.get("source_media"),
                                        "reason": a.get("audit_status", "Approved"),
                                        "passed": True
                                    } for a in audited_news
                                ]
                                st.session_state.batch_service.save_audit_log(n_batch_id, all_log_records)
                            except Exception as log_err:
                                logger.warning(f"Failed to save local audit log: {log_err}")

                            reason_counts = {}
                            for r in rejected_items:
                                rs = r["reason"]
                                reason_counts[rs] = reason_counts.get(rs, 0) + 1

                            rej_summary = " / ".join([f"{k} {v}건" for k, v in reason_counts.items()]) if reason_counts else "없음"
                            status_audit.update(
                                label=f"✓ 최종 검증 완료: 시도 {len(raw_news)}건 → 통과 {len(audited_news)}건 (탈락: {rej_summary})",
                                state="complete"
                            )
                        except Exception as audit_err:
                            status_audit.update(label=f"⚠️ 최종 검증 중 경고: {audit_err}", state="complete")
                            audited_news = raw_news

            with col_run_right:
                # Keep final state rendered
                update_realtime_urls(st.session_state.get("news_grounding_urls", []), "최종 수집 완료")

                valid_news = []
                for a in audited_news:
                    if "Approved" not in a.get("audit_status", ""):
                        continue
                    if news_exclude_existing:
                        url = a.get("source_url", "").strip().lower()
                        if url in n_existing_urls:
                            continue
                    a["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    a["review_status"] = "New"
                    a["batch_id"] = n_batch_id
                    valid_news.append(a)
                    
                try:
                    n_backup_payload = {
                        "batch_id": n_batch_id,
                        "research_date": n_batch_params["research_date"],
                        "primary_category": news_primary_cat,
                        "news_topic": news_topic,
                        "candidates": valid_news,
                        "status": "Awaiting Review"
                    }
                    st.session_state.batch_service.save_local_backup(n_batch_id, n_backup_payload)
                except Exception as e:
                    st.warning(f"로컬 백업 생성 실패: {e}")
                    
                if not valid_news:
                    st.info("검색 조건에 맞는 새 기사를 찾지 못했습니다. 검색 단어를 조정해 보세요.")
                else:
                    st.success(f"3단계 교차 검증을 거친 **{len(valid_news)}**개의 AI 기사를 성공적으로 수집했습니다!")
                    st.session_state.news_candidates = valid_news
                    st.session_state.selected_news_idx = 0

    # ----------------- 2. NEWS EDITOR & PREVIEW -----------------
    if st.session_state.news_candidates:
        st.markdown("---")
        st.subheader("② 수집된 기사 검토 및 수정 (Review & Edit)")
        
        g_urls_summary = st.session_state.get("news_grounding_urls", []) or getattr(st.session_state.gemini, "_last_grounding_urls", [])
        if g_urls_summary:
            with st.expander(f"🌐 1차 탐색 수집 참고 URL 전체 리스트 ({len(g_urls_summary)}개 구글 탐색 출처 보관됨)", expanded=True):
                for g_idx, g_item in enumerate(g_urls_summary, 1):
                    t_title = g_item.get('title') or g_item.get('uri') if isinstance(g_item, dict) else str(g_item)
                    g_uri = g_item.get('uri', '') if isinstance(g_item, dict) else str(g_item)
                    st.markdown(f"**{g_idx}. [{t_title[:45]}...]({g_uri})**")
                    st.caption(g_uri)

        col_n_list, col_n_edit = st.columns([1, 2])
        news_cands = st.session_state.news_candidates
        
        for idx, a in enumerate(news_cands):
            n_key = f"chk_news_save_{idx}"
            if n_key not in st.session_state:
                st.session_state[n_key] = a.get("save_to_sheet", True)
                
        def on_news_select_all_change():
            new_val = st.session_state["chk_news_save_all"]
            for idx in range(len(news_cands)):
                st.session_state[f"chk_news_save_{idx}"] = new_val
                news_cands[idx]["save_to_sheet"] = new_val

        st.checkbox("전체 선택 / 해제", value=True, key="chk_news_save_all", on_change=on_news_select_all_change)
        
        with col_n_list:
            st.markdown(f"**수집된 기사 목록 ({len(news_cands)}개)**")
            for idx, a in enumerate(news_cands):
                title = a.get("title", f"Article {idx+1}")
                title_kr = a.get("korean_title", "")
                source = a.get("source_media", "Unknown Source")
                topic = a.get("news_topic", "General")
                
                n_key = f"chk_news_save_{idx}"
                display_label = f"{idx+1}. [{source}] {title[:30]}..."
                if title_kr and title_kr != title:
                    display_label += f" ({title_kr[:20]}...)"
                    
                checked = st.checkbox(
                    display_label,
                    value=st.session_state.get(n_key, True),
                    key=n_key
                )
                a["save_to_sheet"] = checked
                
                is_selected = (idx == st.session_state.selected_news_idx)
                btn_type = "primary" if is_selected else "secondary"
                
                st.button(
                    f"🔍 상세 편집 #{idx+1}",
                    key=f"btn_sel_news_{idx}",
                    type=btn_type,
                    on_click=select_news_callback,
                    args=(idx,)
                )
                st.markdown(f"<small>🏷️ {topic} | 📅 {a.get('published_date', '')}</small>", unsafe_allow_html=True)
                st.markdown("---")

        with col_n_edit:
            sel_idx = st.session_state.selected_news_idx
            if 0 <= sel_idx < len(news_cands):
                curr = news_cands[sel_idx]
                st.markdown(f"### ✏️ 기사 #{sel_idx+1} 상세 정보 수정")
                
                col_title1, col_title2 = st.columns(2)
                with col_title1:
                    curr["title"] = st.text_input("원문 기사 제목 (Original Title)", curr.get("title", ""), key=f"n_title_{sel_idx}")
                with col_title2:
                    curr["korean_title"] = st.text_input("한글 제목 번역 (Korean Title)", curr.get("korean_title", curr.get("title", "")), key=f"n_title_kr_{sel_idx}")
                
                col_ne1, col_ne2 = st.columns(2)
                with col_ne1:
                    curr["source_media"] = st.text_input("출처 미디어명 (e.g. TechCrunch, ZDNet)", curr.get("source_media", ""), key=f"n_media_{sel_idx}")
                    curr["published_date"] = st.text_input("기사 게재일 (YYYY-MM-DD)", curr.get("published_date", ""), key=f"n_date_{sel_idx}")
                    curr["primary_ai_category"] = st.selectbox(
                        "Primary AI Category (벤더/파트너 매칭 키)",
                        categories_list,
                        index=categories_list.index(curr.get("primary_ai_category", "All")) if curr.get("primary_ai_category") in categories_list else 0,
                        key=f"n_pcat_{sel_idx}"
                    )
                with col_ne2:
                    curr_url = curr.get("source_url", "")
                    curr["source_url"] = st.text_input("출처 URL (Source URL)", curr_url, key=f"n_url_{sel_idx}")
                    
                    if curr_url and curr_url.startswith("http"):
                        st.markdown(f"🔗 **[원문 기사 웹사이트 바로가기 ↗]({curr_url})**")
                        st.caption("📋 **URL 1초 복사 전용 스니펫** (아래 박스 우측 상단 📋 버튼 클릭):")
                        st.code(curr_url, language=None)
                    else:
                        st.error("⚠️ 출처 URL이 유효하지 않거나 Not Found 상태입니다. 아래 '3단계 교차 검증 재실행' 버튼을 누르세요.")

                    refs = curr.get("reference_urls", [])
                    g_urls = st.session_state.get("news_grounding_urls", []) or getattr(st.session_state.gemini, "_last_grounding_urls", [])
                    if isinstance(refs, list):
                        ref_list = [str(u) for u in refs if u]
                    else:
                        ref_list = [str(refs)] if refs else []

                    # Fallback: pre-fill with all Stage 1 grounding URLs if ref_list is empty
                    if not ref_list and g_urls:
                        for g in g_urls:
                            u_val = g.get("uri", "") if isinstance(g, dict) else str(g)
                            if u_val and u_val not in ref_list:
                                ref_list.append(u_val)

                    ref_txt = "\n".join(ref_list)
                    new_ref_txt = st.text_area("🌐 3개 이상 이종 언론사 교차 검증 참조 URL 목록 (Min 3 Reference URLs - 1줄에 1개씩)", ref_txt, height=110, key=f"n_ref_txt_{sel_idx}")
                    curr["reference_urls"] = [line.strip() for line in new_ref_txt.splitlines() if line.strip()]

                    if curr["reference_urls"]:
                        with st.expander(f"🔗 참조 URL 바로가기 목록 ({len(curr['reference_urls'])}개 후보)", expanded=True):
                            for r_i, r_url in enumerate(curr["reference_urls"], 1):
                                st.markdown(f"{r_i}. [{r_url}]({r_url})")
                    
                    audit_st = curr.get("audit_status", "Approved (Verified 200 OK & GPT Approved)")
                    if "Approved" in audit_st:
                        st.success(f"🛡️ **3단계 교차 검증 상태**: {audit_st}")
                    else:
                        st.warning(f"⚠️ **3단계 교차 검증 상태**: {audit_st}")

                    if st.button("🔄 이 기사 3단계 교차 검증 & URL 재해소 실행", key=f"btn_reverify_{sel_idx}"):
                        with st.spinner("🔍 3단계 교차 검증 (HTTP 200 / WAF / GPT Auditor) 진행 중..."):
                            from services.url_resolver import resolve_exact_news_url
                            r_title = curr.get("title", "")
                            r_title_kr = curr.get("korean_title", "")
                            r_media = curr.get("source_media", "News")
                            r_refs = curr.get("reference_urls", [])
                            r_url = resolve_exact_news_url(r_title, r_media, curr_url, title_kr=r_title_kr, reference_urls=r_refs)
                            if r_url:
                                curr["source_url"] = r_url
                                curr["audit_status"] = "Approved (Verified 200 OK & GPT Approved)"
                                st.success(f"✅ 검증 완료된 직링크 URL을 찾았습니다: {r_url}")
                            else:
                                curr["audit_status"] = "WAF Block / Review Needed"
                                st.error("⚠️ 유효한 직링크를 구하지 못했습니다. 수동 검토가 필요합니다.")
                            st.rerun()

                    curr["language"] = st.selectbox("언어", ["EN", "KO"], index=0 if curr.get("language")=="EN" else 1, key=f"n_lang_{sel_idx}")
                    curr["news_topic"] = st.selectbox(
                        "News Topic (뉴스 세부 주제)",
                        news_topics_list[1:], # Exclude "All" for single item classification
                        index=news_topics_list[1:].index(curr.get("news_topic")) if curr.get("news_topic") in news_topics_list[1:] else 0,
                        key=f"n_top_{sel_idx}"
                    )
                    
                curr["related_companies"] = st.text_input("관련 기업명 (쉼표 구분)", curr.get("related_companies", ""), key=f"n_comps_{sel_idx}")
                curr["korean_summary"] = st.text_area("한줄 요약 (1-Line Summary - 빠른 브리핑용)", curr.get("korean_summary", ""), height=70, key=f"n_sum_{sel_idx}")
                curr["detailed_summary"] = st.text_area("10줄 상세 요약 (10-Line Detailed Summary - 배경, 스펙, 시장 파급력, 시사점)", curr.get("detailed_summary", ""), height=180, key=f"n_det_sum_{sel_idx}")
                curr["key_keywords"] = st.text_input("핵심 키워드 (한국어, 쉼표 구분)", curr.get("key_keywords", ""), key=f"n_kw_{sel_idx}")

                
                col_nr1, col_nr2 = st.columns(2)
                with col_nr1:
                    curr["korea_market_relevance"] = st.selectbox("한국 시장 관련성", ["High", "Medium", "Low"], index=["High", "Medium", "Low"].index(curr.get("korea_market_relevance", "Medium")) if curr.get("korea_market_relevance") in ["High", "Medium", "Low"] else 1, key=f"n_krel_{sel_idx}")
                with col_nr2:
                    curr["review_status"] = st.selectbox("검토 상태", ["New", "Approved", "Hold"], index=0, key=f"n_rev_{sel_idx}")
                    
                curr["research_notes"] = st.text_area("추가 분석 메모 (한국어)", curr.get("research_notes", ""), height=60, key=f"n_notes_{sel_idx}")


        # ----------------- 3. SAVE TO GOOGLE SHEET -----------------
        st.markdown("---")
        st.subheader("③ 구글 스프레드시트에 저장")
        
        n_save_target = [a for a in news_cands if a.get("save_to_sheet", True)]
        st.write(f"현재 선택된 **{len(n_save_target)} / {len(news_cands)}**개의 기사를 뉴스 스프레드시트에 저장할 준비가 되었습니다.")
        
        n_save_button = st.button("💾 선택한 뉴스 기사 구글 스프레드시트에 저장", use_container_width=True, key="n_save_btn")
        
        if n_save_button:
            if not n_save_target:
                st.warning("저장할 기사를 최소 1개 이상 선택해 주세요.")
            elif not sheets_ok:
                st.error("Google Sheets API 연결이 끊겼습니다.")
            else:
                with st.spinner("뉴스 구글 스프레드시트에 저장 중..."):
                    sheets_client = st.session_state.sheets
                    n_existing_urls = sheets_client.get_existing_news_urls()
                    
                    final_n_to_save = []
                    n_duplicates = []
                    
                    for a in n_save_target:
                        url = a.get("source_url", "").lower()
                        if url in n_existing_urls:
                            n_duplicates.append(f"{a.get('title', 'Article')} ({url})")
                        else:
                            final_n_to_save.append(a)
                            
                    if n_duplicates:
                        st.warning(f"이미 저장된 중복 기사 {len(n_duplicates)}개를 제외하고 저장합니다.")
                        
                    if final_n_to_save:
                        res = sheets_client.append_news(final_n_to_save)
                        if res["success"]:
                            batch_info = {
                                "batch_id": st.session_state.news_batch_id,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "region": "Global/Korea",
                                "category": news_primary_cat,
                                "industries": news_topic,
                                "candidate_count": len(news_cands),
                                "saved_count": len(final_n_to_save),
                                "status": "Completed"
                            }
                            sheets_client.write_batch_log(batch_info)
                            
                            try:
                                n_backup_payload = {
                                    "batch_id": st.session_state.news_batch_id,
                                    "research_date": batch_info["timestamp"],
                                    "primary_category": news_primary_cat,
                                    "news_topic": news_topic,
                                    "candidates": news_cands,
                                    "saved_candidates": final_n_to_save,
                                    "status": "Saved to News Sheets"
                                }
                                st.session_state.batch_service.save_local_backup(st.session_state.news_batch_id, n_backup_payload)
                            except Exception:
                                pass
                                
                            st.session_state.saved_status = f"성공적으로 {len(final_n_to_save)}개의 AI 뉴스 기사를 구글 시트에 저장했습니다!"
                            st.session_state.news_candidates = []
                            st.session_state.selected_news_idx = 0
                            st.rerun()
                        else:
                            st.error(f"구글 시트 저장 실패: {res['error']}")

with tab2:
    st.subheader("📂 Batch History and Local Recoveries")

    # ── Filter buttons ──────────────────────────────────────────────
    batch_filter = st.radio(
        "이력 유형 필터",
        ["전체", "🌐 해외 벤더 발굴", "🤝 국내 파트너 발굴", "📰 AI 뉴스 인텔리전스"],
        horizontal=True,
        key="batch_filter_radio"
    )


    col_hist1, col_hist2 = st.columns(2)

    with col_hist1:
        st.write("### Recent Batches (from Google Sheets)")
        if sheets_ok:
            recent_batches = st.session_state.sheets.get_recent_batches(limit=30)
            if recent_batches:
                df = pd.DataFrame(
                    recent_batches,
                    columns=["No.", "Batch ID", "Run Timestamp", "Region", "Category", "Target Industries", "Candidates Found", "Saved Count", "Status"]
                )
                # Apply filter based on Batch ID prefix
                if batch_filter == "🌐 해외 벤더 발굴":
                    df = df[~df["Batch ID"].str.startswith("KP-", na=False) & ~df["Batch ID"].str.startswith("NEWS-", na=False)]
                elif batch_filter == "🤝 국내 파트너 발굴":
                    df = df[df["Batch ID"].str.startswith("KP-", na=False)]
                elif batch_filter == "📰 AI 뉴스 인텔리전스":
                    df = df[df["Batch ID"].str.startswith("NEWS-", na=False)]

                if df.empty:
                    st.info("해당 유형의 배치 이력이 없습니다.")
                else:
                    st.dataframe(df, use_container_width=True)
            else:
                st.info("No batch history records found in spreadsheet.")
        else:
            st.warning("Cannot load spreadsheet history. Google Sheets is disconnected.")

    with col_hist2:
        st.write("### Local Backups & Failed Runs")
        local_backups = st.session_state.batch_service.get_backup_list()

        if local_backups:
            # Apply filter to local backups too
            if batch_filter == "🌐 해외 벤더 발굴":
                filtered_backups = [b for b in local_backups if not b["batch_id"].startswith("KP-") and not b["batch_id"].startswith("NEWS-")]
            elif batch_filter == "🤝 국내 파트너 발굴":
                filtered_backups = [b for b in local_backups if b["batch_id"].startswith("KP-")]
            elif batch_filter == "📰 AI 뉴스 인텔리전스":
                filtered_backups = [b for b in local_backups if b["batch_id"].startswith("NEWS-")]
            else:
                filtered_backups = local_backups

            if filtered_backups:
                df_local = pd.DataFrame(filtered_backups)
                st.dataframe(df_local, use_container_width=True)

                # Form to restore a local batch
                st.markdown("#### Recover Session")
                restore_id = st.selectbox("Select Batch ID to reload into editor", [b["batch_id"] for b in filtered_backups])

                if st.button("🔌 Reload Selected Batch"):
                    try:
                        loaded = st.session_state.batch_service.load_local_backup(restore_id)
                        if restore_id.startswith("NEWS-"):
                            st.session_state.news_candidates = loaded.get("candidates", [])
                            st.session_state.news_batch_id = loaded.get("batch_id", "")
                            st.session_state.selected_news_idx = 0
                            clear_checkbox_keys()
                            st.success(f"뉴스 배치 **{restore_id}** 복구 완료. '📰 AI News Intelligence' 탭에서 확인하세요.")
                        elif restore_id.startswith("KP-"):
                            st.session_state.partner_candidates = loaded.get("candidates", [])
                            st.session_state.partner_batch_id = loaded.get("batch_id", "")
                            st.session_state.selected_partner_idx = 0
                            clear_checkbox_keys()
                            st.success(f"파트너 배치 **{restore_id}** 복구 완료. '🤝 Korean Partner Discovery' 탭에서 확인하세요.")
                        else:
                            st.session_state.candidates = loaded.get("candidates", [])
                            st.session_state.batch_id = loaded.get("batch_id", "")
                            st.session_state.selected_candidate_idx = 0
                            clear_checkbox_keys()
                            st.success(f"벤더 배치 **{restore_id}** 복구 완료. '🔎 AI Vendor Discovery' 탭에서 확인하세요.")
                    except Exception as e:
                        st.error(f"Failed to reload: {e}")

            else:
                st.info("해당 유형의 로컬 백업이 없습니다.")
        else:
            st.info("No local backups found in `data/local_backup/`.")

    # ── 🔍 2단계 교차검증 및 탈락 분석 로그 섹션 ────────────────────
    st.markdown("---")
    st.markdown("### 🛡️ 2단계 교차검증 및 탈락 상세 분석 로그 (Detailed Audit & Rejections Log)")

    all_audit_logs = st.session_state.batch_service.get_all_audit_logs()
    if all_audit_logs:
        audit_options = [f"{log.get('batch_id')} ({log.get('timestamp')}) - 총 {log.get('total_records', 0)}건 검증 기록" for log in all_audit_logs]
        selected_log_idx = st.selectbox(
            "분석 및 복구할 수집 회차(배치 ID) 선택",
            range(len(audit_options)),
            format_func=lambda i: audit_options[i],
            key="sb_audit_log_selector"
        )
        
        sel_log = all_audit_logs[selected_log_idx]
        st.markdown(f"🤖 **검증엔진**: `{sel_log.get('audit_provider', 'claude').upper()}` (`{sel_log.get('claude_model', 'claude-sonnet-4-6')}`) | 🕒 **실행시각**: `{sel_log.get('timestamp')}`")
        
        records = sel_log.get("records", [])
        if records:
            df_rec = pd.DataFrame(records)
            st.dataframe(df_rec, use_container_width=True)
            
            # JSON Download button
            json_str = json.dumps(sel_log, ensure_ascii=False, indent=2)
            st.download_button(
                label=f"📥 `{sel_log.get('batch_id')}` 검증 상세 로그 JSON 다운로드",
                data=json_str,
                file_name=f"{sel_log.get('batch_id')}_audit_log.json",
                mime="application/json",
                key="btn_download_audit_json"
            )
    else:
        st.info("💡 아직 저장된 상세 검증 분석 로그가 없습니다. 뉴스 탐색 실행 시 검증 결과 및 탈락 사유 로그가 이곳 `data/audit_logs/` 폴더에 자동으로 보관되어 언제든지 재분석할 수 있습니다.")

