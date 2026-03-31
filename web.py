import os, subprocess, requests, json as json_lib, yaml
import streamlit as st
st.set_page_config(page_title="나의 슈퍼 에이전트", page_icon="🤖", layout="wide")
import streamlit_authenticator as stauth
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from bs4 import BeautifulSoup
from datetime import datetime, date
from ddgs import DDGS
import pandas as pd
import plotly.express as px
import PyPDF2
import io

load_dotenv()

# 로그인 시스템 설정
from streamlit_authenticator.utilities import LoginError, RegisterError
_config_path = os.path.expanduser('~/Desktop/super_agent/config.yaml')
with open(_config_path, 'r', encoding='utf-8') as _f:
    _config = yaml.safe_load(_f)

_authenticator = stauth.Authenticate(
    _config['credentials'],
    _config['cookie']['name'],
    _config['cookie']['key'],
    _config['cookie']['expiry_days']
)

# 로그인 상태 확인
if not st.session_state.get('authentication_status'):
    st.markdown("---")
    _mode = st.radio("", ["🔐 로그인", "📝 회원가입"], horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    if _mode == "🔐 로그인":
        try:
            _authenticator.login()
        except LoginError as _e:
            st.error(f'로그인 오류: {_e}')
        if st.session_state.get('authentication_status') is False:
            st.error('❌ 아이디 또는 비밀번호가 틀렸어요!')
        st.stop()

    elif _mode == "📝 회원가입":
        try:
            (_reg_email, _reg_username, _reg_name) = _authenticator.register_user()
            if _reg_email:
                with open(_config_path, 'w', encoding='utf-8') as _f:
                    yaml.dump(_config, _f, allow_unicode=True, default_flow_style=False)
                st.success('✅ 회원가입 완료! 로그인을 선택해서 로그인해주세요!')
        except RegisterError as _e:
            st.error(f'회원가입 오류: {_e}')
        except Exception as _e:
            if str(_e):
                st.error(f'오류: {_e}')
        st.stop()

# 로그인 성공 시
_current_user = st.session_state.get('username', 'default')
MEMORY_FILE_BASE = os.path.expanduser(f'~/Desktop/super_agent/memory_{_current_user}.json')

# 사이드바에 로그아웃 버튼
with st.sidebar:
    st.write(f'👤 {st.session_state.get("name", "")}님 환영해요!')
    _authenticator.logout('로그아웃', 'sidebar')

# JSON 파일 기반 장기 기억 설정
MEMORY_FILE = MEMORY_FILE_BASE

def get_youtube_summary(url):
    """유튜브 영상 자막 가져오기 (v1.2.4 방식)"""
    try:
        import re
        # 유튜브 ID 추출
        patterns = [
            r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'(?:embed/)([a-zA-Z0-9_-]{11})'
        ]
        video_id = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        if not video_id:
            return "유튜브 링크에서 영상 ID를 찾을 수 없어요."
        # 새 방식으로 자막 가져오기
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        # 한국어 우선, 없으면 영어, 없으면 첫 번째
        transcript = None
        for lang in ["ko", "en"]:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except:
                continue
        if transcript is None:
            transcript = list(transcript_list)[0]
        # 자막 텍스트 가져오기
        fetched = transcript.fetch()
        full_text = " ".join([t.text for t in fetched])
        # 너무 길면 앞부분만
        if len(full_text) > 3000:
            full_text = full_text[:3000] + "..."
        return f"[유튜브 자막]\n{full_text}"
    except Exception as e:
        return f"자막을 가져올 수 없어요: {e}"

def get_memory_file():
    user = st.session_state.get("username", "default")
    return os.path.expanduser(f"~/Desktop/super_agent/memory_{user}.json")

def save_memory(user_msg, agent_msg):
    """대화를 JSON 파일에 저장"""
    import time
    MEMORY_FILE = get_memory_file()
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memories = json_lib.load(f)
        else:
            memories = []
        memories.append({
            "timestamp": time.time(),
            "user": user_msg,
            "agent": agent_msg
        })
        # 최근 100개만 유지
        memories = memories[-100:]
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json_lib.dump(memories, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def search_memory(query, n_results=5):
    """키워드로 과거 기억 검색"""
    MEMORY_FILE = get_memory_file()
    try:
        if not os.path.exists(MEMORY_FILE):
            return ""
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memories = json_lib.load(f)
        if not memories:
            return ""
        # 키워드 매칭으로 관련 기억 찾기
        query_words = set(query.replace("?","").replace("!","").split())
        scored = []
        for m in memories:
            text = m["user"] + " " + m["agent"]
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, m))
        # 점수 높은 순으로 정렬
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]
        if not top:
            # 키워드 매칭 없으면 최근 3개
            top_memories = memories[-3:]
            return "\n".join([f"사용자: {m['user']} → 에이전트: {m['agent'][:100]}" for m in top_memories])
        return "\n".join([f"사용자: {m['user']} → 에이전트: {m['agent'][:100]}" for _, m in top])
    except Exception:
        return ""




st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); }
    h1 {
        background: linear-gradient(90deg, #00d2ff, #7b2ff7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center; font-size: 2.5rem !important;
    }
    .stApp p { color: #a0aec0; }
    .stChatInput input {
        background: #1a1a2e !important; color: white !important;
        border: 1px solid #7b2ff7 !important; border-radius: 20px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 나의 슈퍼 에이전트")
st.caption("Groq ⚡ | 일정관리 📅 | 보고서 📝 | 뉴스요약 🔔 | 파일분석 📄 | 검색 🔍")

@st.cache_resource
def load_groq():
    return ChatGroq(model="llama-3.3-70b-versatile",
        groq_api_key=os.getenv("GROQ_API_KEY"), temperature=0.1)

llm = load_groq()

def get_schedule_file():
    user = st.session_state.get("username", "default")
    return os.path.expanduser(f"~/Desktop/super_agent/schedule_{user}.json")
CHAT_DIR = os.path.expanduser(f"~/Desktop/super_agent/chats_{_current_user}")
os.makedirs(CHAT_DIR, exist_ok=True)

def load_schedule():
    sf = get_schedule_file()
    if os.path.exists(sf):
        with open(sf, "r", encoding="utf-8") as f:
            return json_lib.load(f)
    return []

def save_schedule(schedules):
    sf = get_schedule_file()
    with open(sf, "w", encoding="utf-8") as f:
        json_lib.dump(schedules, f, ensure_ascii=False, indent=2)

def add_schedule(text):
    try:
        schedules = load_schedule()
        parts = text.split("|")
        if len(parts) >= 2:
            item = {"date": parts[0].strip(), "title": parts[1].strip(),
                    "memo": parts[2].strip() if len(parts) > 2 else ""}
        else:
            item = {"date": str(date.today()), "title": text.strip(), "memo": ""}
        schedules.append(item)
        save_schedule(schedules)
        return f"일정 추가됨: {item['date']} - {item['title']} ({item['memo']})"
    except Exception as e:
        return f"일정 오류: {e}"

def get_schedule(query=""):
    schedules = load_schedule()
    if not schedules:
        return "등록된 일정이 없어요. (파일에 저장된 일정 없음)"
    if query and query.strip():
        filtered = [s for s in schedules if query in s.get("date","") or query in s.get("title","")]
        schedules = filtered if filtered else schedules
    # 날짜순 정렬
    schedules = sorted(schedules, key=lambda x: x.get("date",""))
    result = "[실제 저장된 일정 목록]\n"
    result += "\n".join([f"📅 {s['date']} {s.get('memo','')} - {s['title']}" for s in schedules])
    return result

def delete_schedule(title):
    schedules = load_schedule()
    before = len(schedules)
    schedules = [s for s in schedules if title not in s.get("title","")]
    save_schedule(schedules)
    return f"{before - len(schedules)}개 일정 삭제됨"

def save_chat(name=""):
    if "messages" not in st.session_state:
        return "저장할 대화가 없어요"
    filename = name if name else datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(CHAT_DIR, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json_lib.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
    return f"대화 저장됨: {filename}.json"

def load_chat(name):
    filepath = os.path.join(CHAT_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        filepath = os.path.join(CHAT_DIR, name)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            st.session_state.messages = json_lib.load(f)
        return f"대화 불러옴: {name}"
    return f"파일 없음: {name}"

def list_chats():
    files = os.listdir(CHAT_DIR)
    if not files:
        return "저장된 대화 없음"
    return "\n".join([f"📁 {f}" for f in files])

def get_news_summary(topic):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{topic} 뉴스 최신", max_results=5))
        if not results:
            return "뉴스 없음"
        news_text = "\n".join([f"- {r['title']}: {r['body'][:200]}" for r in results])
        messages = [
            SystemMessage(content="뉴스를 한국어로 간결하게 요약해줘. 핵심만 bullet point로."),
            HumanMessage(content=f"다음 뉴스들을 요약해줘:\n{news_text}")
        ]
        return llm.invoke(messages).content
    except Exception as e:
        return f"뉴스 오류: {e}"

def write_report(topic):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(topic, max_results=5))
        context = "\n".join([f"- {r['title']}: {r['body'][:300]}" for r in results])
        messages = [
            SystemMessage(content="전문적인 보고서를 한국어로 작성해줘. 형식: 제목, 요약, 주요내용(3개), 결론 순서로."),
            HumanMessage(content=f"주제: {topic}\n\n참고자료:\n{context}")
        ]
        report = llm.invoke(messages).content
        filename = f"{topic[:20].replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.txt"
        filepath = os.path.expanduser(f"~/Desktop/{filename}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        st.session_state.last_report = report
        return f"보고서 작성완료! 바탕화면에 저장됨: {filename}"
    except Exception as e:
        return f"보고서 오류: {e}"

def web_search(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        if not results:
            return "검색 결과 없음"
        output = "[실제 검색 결과 - 반드시 이 내용만 사용해서 답변할 것]\n"
        output += "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return output
    except Exception as e:
        return f"검색 오류: {e}"

def run_code(code):
    try:
        result = subprocess.run(["python3", "-c", code],
            capture_output=True, text=True, timeout=30)
        return result.stdout or result.stderr or "실행완료"
    except Exception as e:
        return f"오류: {e}"

def read_webpage(url):
    try:
        res = requests.get(url.strip(), timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style"]): tag.decompose()
        return soup.get_text()[:2000]
    except Exception as e:
        return f"오류: {e}"

def get_date():
    now = datetime.now()
    weekdays = ["월","화","수","목","금","토","일"]
    return f"{now.year}년 {now.month}월 {now.day}일 ({weekdays[now.weekday()]}요일) {now.strftime('%H:%M')}"

def analyze_dataframe(q):
    if "df" not in st.session_state or st.session_state.df is None:
        return "업로드된 데이터 없음"
    df = st.session_state.df
    return f"크기: {df.shape}\n컬럼: {list(df.columns)}\n통계:\n{df.describe().to_string()}"

def draw_chart(chart_type):
    if "df" not in st.session_state or st.session_state.df is None:
        return "데이터 없음"
    df = st.session_state.df
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols: return "숫자 데이터 없음"
    try:
        if "bar" in chart_type or "막대" in chart_type:
            fig = px.bar(df, y=numeric_cols[0], title="막대 차트", color_discrete_sequence=["#7b2ff7"])
        elif "line" in chart_type or "선" in chart_type:
            fig = px.line(df, y=numeric_cols[0], title="선 그래프", color_discrete_sequence=["#00d2ff"])
        else:
            fig = px.bar(df, y=numeric_cols[0], title="차트", color_discrete_sequence=["#7b2ff7"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.session_state.last_chart = fig
        return "차트 생성완료!"
    except Exception as e:
        return f"차트 오류: {e}"

def execute_tool(tool_name, tool_input):
    t = tool_name.strip().lower()
    i = tool_input.strip()
    tools = {
        "web_search": web_search,
        "run_code": run_code,
        "read_webpage": read_webpage,
        "youtube_summary": get_youtube_summary,
        "analyze_data": analyze_dataframe,
        "draw_chart": draw_chart,
        "add_schedule": add_schedule,
        "get_schedule": get_schedule,
        "delete_schedule": delete_schedule,
        "save_chat": save_chat,
        "load_chat": load_chat,
        "list_chats": lambda x: list_chats(),
        "news_summary": get_news_summary,
        "write_report": write_report,
    }
    return tools.get(t, web_search)(i)

def run_agent(user_input, chat_history):
    # 장기 기억 검색
    today = str(date.today())
    tomorrow = str(date.fromordinal(date.today().toordinal()+1))
    
    # 대화 요약 (10개 이상이면 앞부분 요약)
    summary_text = ""
    if len(chat_history) > 10:
        old_msgs = chat_history[:-10]
        summary_lines = []
        for h in old_msgs:
            role = "사용자" if h["role"]=="user" else "에이전트"
            summary_lines.append(f"{role}: {h['content'][:80]}")
        summary_text = f"\n[이전 대화 요약]\n" + "\n".join(summary_lines[-10:]) + "\n"
    # 일정 관련 질문은 장기 기억 사용 안 함 (실제 파일만 사용)
    schedule_keywords = ["일정", "스케줄", "언제", "추가", "삭제", "더 없", "또", "전부", "다 보", "없어", "있어"]
    # 최근 대화에서 일정 관련 맥락이 있으면 일정 쿼리로 처리
    recent_context = " ".join([h.get("content","") for h in chat_history[-4:]])
    is_schedule_query = any(k in user_input for k in schedule_keywords) or                         (any(k in recent_context for k in ["일정","스케줄"]) and len(user_input) < 10)
    long_term_memory = "" if is_schedule_query else search_memory(user_input)
    long_term_section = f"[과거 기억 - 예전 대화에서 찾은 관련 내용]\n{long_term_memory}\n" if long_term_memory else ""

    history_text = ""
    if chat_history:
        history_text = "\n[이전 대화]\n"
        for h in chat_history[-12:]:
            role = "사용자" if h["role"]=="user" else "에이전트"
            history_text += f"{role}: {h['content']}\n"

    file_text = ""
    if "file_content" in st.session_state and st.session_state.file_content:
        file_text = f"\n[업로드 파일]\n{st.session_state.file_content[:2000]}\n"

    system = f"""너는 세계 최고 수준의 한국어 AI 슈퍼 에이전트야.\n{long_term_section}{summary_text}

[사고 방식 - 반드시 지켜]
- 복잡한 문제는 단계별로 분해해서 생각해 (Chain of Thought)
- 답변 전에 항상 "이게 정말 맞는 답인가?" 한 번 더 검토해
- 확실하지 않으면 솔직하게 "잘 모르겠다"고 말해
- 수학/논리 문제는 반드시 검산해

[답변 품질 - 반드시 지켜]  
- 단순 나열 말고 이유와 근거를 포함해서 설명해
- 예시를 들어서 이해하기 쉽게 설명해
- 중요한 정보는 강조해서 표현해
- 짧은 질문도 충실하게 답변해
- 항상 존댓말 사용해 (예: "없어요", "있어요", "됩니다")
- 절대 반말 금지 ("없어", "있어", "해" 같은 표현 금지)
- 이전 대화 내용을 번호로 나열하거나 요약하지 마
- 바로 핵심 답변만 해
- "제가 기억하는 한" 같은 불필요한 말 하지 마

[언어 규칙 - 절대 어기면 안됨]
- 오직 한국어(한글)만 사용
- 한자 절대 금지
- 중국어, 일본어 절대 금지
- 영어는 꼭 필요한 고유명사만
현재 시각: {get_date()}
오늘 날짜: {str(date.today())} / 내일 날짜: {str(date.fromordinal(date.today().toordinal()+1))} / 모레: {str(date.fromordinal(date.today().toordinal()+2))}
{history_text}{file_text}

[언어 규칙 - 절대 준수]
- 오직 한국어(한글)만 사용할 것
- 한자 절대 금지
- 중국어, 일본어 절대 금지

사용 가능한 도구:
- web_search      : 인터넷 검색
- run_code        : 파이썬 코드 실행
- read_webpage    : 웹페이지 읽기
- youtube_summary : 유튜브 영상 요약 (입력: 유튜브 URL)
- analyze_data  : 데이터 분석
- draw_chart    : 차트 그리기
- add_schedule  : 일정 추가. 입력형식: YYYY-MM-DD|제목|시간 (오늘={today}, 내일={tomorrow}) 예시) {tomorrow}|헬스장|15시
- get_schedule  : 일정 조회
- delete_schedule: 일정 삭제
- save_chat     : 대화 저장
- load_chat     : 대화 불러오기
- list_chats    : 저장된 대화 목록
- news_summary  : 뉴스 요약
- write_report  : 보고서 작성

도구 사용 형식:
TOOL: 도구이름
INPUT: 입력값

[도구 사용 규칙 - 절대 어기면 안됨]
1. 코드 실행 요청 → 반드시 run_code 도구 사용! 절대 머릿속으로 계산하지 마!
2. 시세/가격/날씨/뉴스/최신정보 → 반드시 web_search 사용! 절대 지어내지 마!
3. 유튜브 링크 → 반드시 youtube_summary 사용!
4. 도구를 쓸 때는 반드시 아래 형식만 사용:
TOOL: 도구이름
INPUT: 입력값
5. 도구 결과 없이 절대 답변하지 마!
6. 날짜/시간만 도구 없이 답변 가능"""

    messages = [SystemMessage(content=system), HumanMessage(content=user_input)]
    reply = llm.invoke(messages).content

    if "TOOL:" in reply or any(t in reply for t in ["get_schedule", "add_schedule", "web_search", "run_code", "youtube_summary", "write_report", "news_summary"]):
        lines = reply.strip().split("\n")
        tool_name, tool_input = "", ""
        capture_input = False
        input_lines = []
        for line in lines:
            if line.strip().startswith("TOOL:"):
                tool_name = line.replace("TOOL:","").strip()
                capture_input = False
            elif any(line.strip().startswith(t) for t in ["get_schedule","add_schedule","web_search","run_code","youtube_summary","write_report","news_summary","draw_chart","analyze_data","news_summary"]):
                parts = line.strip().split("INPUT:",1)
                tool_name = parts[0].replace("TOOL:","").strip()
                tool_input = parts[1].strip() if len(parts)>1 else ""
                capture_input = True
            elif line.strip().startswith("INPUT:"):
                tool_input = line.replace("INPUT:","").strip()
                capture_input = True
            elif capture_input and line.strip():
                input_lines.append(line.strip())
        # 멀티라인 INPUT 처리
        if input_lines and not tool_input:
            tool_input = "\n".join(input_lines)
        elif input_lines:
            tool_input = tool_input + "\n" + "\n".join(input_lines)
        if tool_name:
            tool_result = execute_tool(tool_name, tool_input)
            messages2 = [
                SystemMessage(content=f"""너는 도구 실행 결과를 그대로 전달하는 AI야.
[절대 규칙]
- 도구 실행 결과에 있는 정보만 사용해서 답변해
- 절대 네가 알고 있는 값을 추가하지 마
- 일정 결과면 일정 내용을 그대로 보여줘
- "검색 결과에 따르면" 같은 말 하지 마. 바로 결과만 말해
- 한국어로 친절하게 답변해
- 한자, 중국어, 일본어 절대 금지"""),
                HumanMessage(content=f"""사용자 질문: {user_input}

도구 실행 결과:
{tool_result}

위 검색 결과에 있는 정보만 사용해서 답변해줘. 절대 다른 값 쓰지 마.""")
            ]
            return llm.invoke(messages2).content, "⚡ Groq"

    return reply, "⚡ Groq"

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    st.markdown("---")
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = [{"role":"assistant","content":"안녕하세요! 슈퍼 에이전트예요 🤖"}]
        st.session_state.chat_history = []
        st.session_state.file_content = ""
        st.session_state.df = None
        st.rerun()

    st.markdown("---")
    st.markdown("### 💾 대화 저장/불러오기")
    chat_name = st.text_input("저장 파일명", placeholder="예: 오늘대화")
    if st.button("💾 저장", use_container_width=True):
        st.success(save_chat(chat_name or ""))
    saved_chats = [f.replace(".json","") for f in os.listdir(CHAT_DIR) if f.endswith(".json")]
    if saved_chats:
        selected = st.selectbox("불러올 대화", saved_chats)
        if st.button("📂 불러오기", use_container_width=True):
            load_chat(selected)
            st.rerun()

    st.markdown("---")
    st.markdown("### 📅 오늘의 일정")
    today_schedule = get_schedule(str(date.today()))
    st.markdown(today_schedule if today_schedule != "해당 일정 없음" else "오늘 일정 없음")

    st.markdown("---")
    st.markdown("### 📂 파일 업로드")
    uploaded_file = st.file_uploader("파일을 올려주세요", type=["pdf","txt","csv","xlsx","xls"])
    if uploaded_file:
        file_type = uploaded_file.name.split(".")[-1].lower()
        if file_type == "pdf":
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
                text = "".join([p.extract_text() for p in pdf_reader.pages])
                st.session_state.file_content = text[:5000]
                st.session_state.df = None
                st.success("✅ PDF 완료!")
            except Exception as e:
                st.error(f"오류: {e}")
        elif file_type == "txt":
            text = uploaded_file.read().decode("utf-8")
            st.session_state.file_content = text[:5000]
            st.session_state.df = None
            st.success("✅ TXT 완료!")
        elif file_type == "csv":
            df = pd.read_csv(uploaded_file)
            st.session_state.df = df
            st.session_state.file_content = f"CSV: {df.shape[0]}행 컬럼: {list(df.columns)}"
            st.success("✅ CSV 완료!")
        elif file_type in ["xlsx","xls"]:
            df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.session_state.file_content = f"엑셀: {df.shape[0]}행 컬럼: {list(df.columns)}"
            st.success("✅ 엑셀 완료!")

    if "df" in st.session_state and st.session_state.df is not None:
        st.markdown("---")
        st.dataframe(st.session_state.df.head(), use_container_width=True)

    st.markdown("---")
    st.markdown("### 📊 통계")
    if "messages" in st.session_state:
        st.metric("총 대화 수", f"{max(0, len(st.session_state.messages)-1)}번")

    st.markdown("---")
    st.markdown("### 💡 예시 질문")
    examples = ["오늘 AI 뉴스 요약해줘", "내 일정 알려줘", "AI 트렌드 보고서 작성해줘", "대화 저장해줘"]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state.example_input = ex
            st.rerun()

for key, val in {
    "messages": [{"role":"assistant","content":"안녕하세요! 슈퍼 에이전트예요 🤖\n일정관리, 보고서, 뉴스요약 다 돼요!"}],
    "chat_history": [], "file_content": "", "df": None,
    "last_chart": None, "last_report": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "ai_used" in msg: st.caption(f"사용된 AI: {msg['ai_used']}")

def process_input(user_input):
    st.session_state.messages.append({"role":"user","content":user_input})
    with st.chat_message("user"): st.write(user_input)
    with st.chat_message("assistant"):
        with st.spinner("생각 중... 🤔"):
            try: response, ai_name = run_agent(user_input, st.session_state.chat_history)
            except Exception as e: response, ai_name = f"오류: {e}", "오류"
        # 장기 기억에 저장
        try:
            save_memory(user_input, response)
        except Exception:
            pass
        st.write(response)
        st.caption(f"사용된 AI: {ai_name}")
        if st.session_state.last_report:
            with st.expander("📝 보고서 전체 보기"):
                st.write(st.session_state.last_report)
            st.session_state.last_report = None
        st.session_state.messages.append({"role":"assistant","content":response,"ai_used":ai_name})
        st.session_state.chat_history.append({"role":"user","content":user_input})
        st.session_state.chat_history.append({"role":"assistant","content":response})
    if st.session_state.last_chart:
        st.plotly_chart(st.session_state.last_chart, use_container_width=True)
        st.session_state.last_chart = None

if "example_input" in st.session_state:
    process_input(st.session_state.pop("example_input"))

if user_input := st.chat_input("메시지를 입력하세요..."):
    process_input(user_input)
