import os, subprocess, requests, json
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from bs4 import BeautifulSoup
from datetime import datetime, date
from duckduckgo_search import DDGS
import pandas as pd
import plotly.express as px
import PyPDF2
import io

load_dotenv()

st.set_page_config(page_title="나의 슈퍼 에이전트", page_icon="🤖", layout="wide")

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

SCHEDULE_FILE = os.path.expanduser("~/Desktop/super_agent/schedule.json")
CHAT_DIR = os.path.expanduser("~/Desktop/super_agent/chats")
os.makedirs(CHAT_DIR, exist_ok=True)

def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_schedule(schedules):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

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
        return f"일정 추가됨: {item['date']} - {item['title']}"
    except Exception as e:
        return f"일정 오류: {e}"

def get_schedule(query=""):
    schedules = load_schedule()
    if not schedules:
        return "등록된 일정이 없어요"
    if query:
        schedules = [s for s in schedules if query in s.get("date","") or query in s.get("title","")]
    result = "\n".join([f"📅 {s['date']} - {s['title']} {s.get('memo','')}" for s in schedules])
    return result or "해당 일정 없음"

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
        json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
    return f"대화 저장됨: {filename}.json"

def load_chat(name):
    filepath = os.path.join(CHAT_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        filepath = os.path.join(CHAT_DIR, name)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
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
        return "\n".join([f"- {r['title']}: {r['body']}" for r in results]) or "결과 없음"
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
    history_text = ""
    if chat_history:
        history_text = "\n[이전 대화]\n"
        for h in chat_history[-6:]:
            role = "사용자" if h["role"]=="user" else "에이전트"
            history_text += f"{role}: {h['content']}\n"

    file_text = ""
    if "file_content" in st.session_state and st.session_state.file_content:
        file_text = f"\n[업로드 파일]\n{st.session_state.file_content[:2000]}\n"

    system = f"""너는 친절한 한국어 슈퍼 에이전트야.
현재 시각: {get_date()}
{history_text}{file_text}

[언어 규칙 - 절대 준수]
- 오직 한국어(한글)만 사용할 것
- 한자 절대 금지
- 중국어, 일본어 절대 금지

사용 가능한 도구:
- web_search    : 인터넷 검색
- run_code      : 파이썬 코드 실행
- read_webpage  : 웹페이지 읽기
- analyze_data  : 데이터 분석
- draw_chart    : 차트 그리기
- add_schedule  : 일정 추가 (입력: 날짜|제목|메모)
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

규칙:
1. 최신 정보는 web_search 사용
2. 날짜/시간은 도구 없이 바로 답변
3. 도구는 딱 한 번만 사용
4. 항상 한국어로 친절하게 답변
5. 이전 대화 기억하고 활용"""

    messages = [SystemMessage(content=system), HumanMessage(content=user_input)]
    reply = llm.invoke(messages).content

    if "TOOL:" in reply and "INPUT:" in reply:
        lines = reply.strip().split("\n")
        tool_name, tool_input = "", ""
        for line in lines:
            if line.strip().startswith("TOOL:"): tool_name = line.replace("TOOL:","").strip()
            if line.strip().startswith("INPUT:"): tool_input = line.replace("INPUT:","").strip()
        if tool_name and tool_input:
            tool_result = execute_tool(tool_name, tool_input)
            messages2 = [
                SystemMessage(content=system),
                HumanMessage(content=user_input),
                HumanMessage(content=f"도구 결과:\n{tool_result}\n\n한국어로 친절하게 답변해줘.")
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
