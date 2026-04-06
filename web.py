import os, subprocess, requests, json as json_lib, time, re
import streamlit as st
st.set_page_config(page_title="J.A.R.V.I.S", page_icon="🔴", layout="wide")

# 아이언맨 스타일 CSS
st.markdown("""
<style>
/* 전체 배경 */
.stApp {
    background: linear-gradient(135deg, #0a0a0f 0%, #0d1117 50%, #0a0f1a 100%);
    color: #e0e0e0;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #0a0f1a 100%);
    border-right: 1px solid #1e3a5f;
}

/* 사이드바 텍스트 */
[data-testid="stSidebar"] * {
    color: #4fc3f7 !important;
}

/* 채팅 입력창 */
[data-testid="stChatInput"] {
    background: rgba(13, 17, 23, 0.9) !important;
    border: 1px solid #1565c0 !important;
    border-radius: 12px !important;
}

[data-testid="stChatInput"] textarea {
    color: #4fc3f7 !important;
}

/* 버튼 */
.stButton > button {
    background: linear-gradient(135deg, #0d47a1, #1565c0) !important;
    color: #4fc3f7 !important;
    border: 1px solid #1976d2 !important;
    border-radius: 8px !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #1565c0, #1976d2) !important;
    border-color: #42a5f5 !important;
    box-shadow: 0 0 15px rgba(66, 165, 245, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* 사용자 메시지 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: rgba(21, 101, 192, 0.15) !important;
    border: 1px solid rgba(21, 101, 192, 0.3) !important;
    border-radius: 12px !important;
    padding: 8px !important;
}

/* AI 메시지 */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: rgba(183, 28, 28, 0.1) !important;
    border: 1px solid rgba(183, 28, 28, 0.25) !important;
    border-radius: 12px !important;
    padding: 8px !important;
}

/* 텍스트 색상 */
.stMarkdown, p, span, div {
    color: #cfd8dc !important;
}

/* 제목 */
h1, h2, h3 {
    color: #4fc3f7 !important;
    text-shadow: 0 0 10px rgba(79, 195, 247, 0.3) !important;
}

/* 파일 업로더 */
[data-testid="stFileUploader"] {
    background: rgba(13, 71, 161, 0.1) !important;
    border: 1px dashed #1565c0 !important;
    border-radius: 8px !important;
}

/* 성공/에러 메시지 */
[data-testid="stAlert"] {
    border-radius: 8px !important;
}

/* 스크롤바 */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: #0a0a0f;
}
::-webkit-scrollbar-thumb {
    background: #1565c0;
    border-radius: 3px;
}

/* 토글 */
[data-testid="stToggle"] {
    color: #4fc3f7 !important;
}

/* 구분선 */
hr {
    border-color: #1e3a5f !important;
}

/* 상태 표시 */
.element-container .stSuccess {
    background: rgba(0, 77, 64, 0.3) !important;
    border-left: 3px solid #00e676 !important;
}

/* 스피너 */
.stSpinner {
    color: #4fc3f7 !important;
}
</style>
""", unsafe_allow_html=True)
from supabase import create_client, Client
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

# 음성 기능 (로컬에서만 작동)
try:
    import speech_recognition as sr
    import gtts
    import pygame
    import threading
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

load_dotenv()

# Supabase 연결
_supabase_url = os.getenv("SUPABASE_URL")
_supabase_key = os.getenv("SUPABASE_KEY")
_supabase: Client = create_client(_supabase_url, _supabase_key) if _supabase_url and _supabase_key else None

# 단일 사용자 모드 (로그인 없음)
st.session_state['username'] = 'jahyun'
st.session_state['authentication_status'] = True

# ──────────────────────────────────────────
# 사이드바
# ──────────────────────────────────────────

with st.sidebar:
    st.markdown("**👤 자현**")
    if 'voice_mode' not in st.session_state:
        st.session_state.voice_mode = False

# ──────────────────────────────────────────
# 음성 함수
# ──────────────────────────────────────────
if VOICE_AVAILABLE:
    _recognizer = sr.Recognizer()
    pygame.mixer.init()
    import atexit
    atexit.register(pygame.mixer.quit)
    atexit.register(pygame.quit)

def speak(text):
    if not VOICE_AVAILABLE:
        return
    import tempfile, re as _re, subprocess as _sp
    # 음성 모드 꺼져있으면 즉시 중단
    try:
        if not st.session_state.get('voice_mode', False):
            return
    except:
        return
    # 문장 분리
    sentences = _re.split(r'(?<=[.!?\n])\s+', text.strip())
    merged = []
    buf = ""
    for s in sentences:
        buf = (buf + " " + s).strip() if buf else s
        if len(buf) >= 20:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    merged = merged[:5]
    for sentence in merged:
        if not sentence.strip():
            continue
        # 매 문장마다 음성 모드 재확인
        try:
            if not st.session_state.get('voice_mode', False):
                pygame.mixer.music.stop()
                return
        except:
            pygame.mixer.music.stop()
            return
        tmp_path = None
        try:
            tts = gtts.gTTS(sentence.strip(), lang='ko')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp_path = tmp.name
                tts.save(tmp_path)
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            # 재생 중 매 0.1초마다 세션 체크
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                try:
                    if not st.session_state.get('voice_mode', False):
                        pygame.mixer.music.stop()
                        break
                except:
                    pygame.mixer.music.stop()
                    break
        except Exception as e:
            print(f"TTS 오류: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

def listen():
    if not VOICE_AVAILABLE:
        return None
    try:
        with sr.Microphone() as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = _recognizer.listen(source, timeout=10, phrase_time_limit=30)
            text = _recognizer.recognize_google(audio, language='ko-KR')
            return text
    except:
        return None

# ──────────────────────────────────────────
# 메모리 함수
# ──────────────────────────────────────────
def get_memory_file():
    user = st.session_state.get('username', 'jahyun')
    return os.path.expanduser(f'~/Desktop/super_agent/memory_{user}.json')

def save_memory(user_msg, agent_msg):
    user = st.session_state.get('username', 'jahyun')
    if _supabase:
        try:
            _supabase.table('memories').insert({
                'username': user,
                'user_msg': user_msg,
                'agent_msg': agent_msg[:500]
            }).execute()
            return
        except:
            pass
    mf = get_memory_file()
    memories = []
    if os.path.exists(mf):
        with open(mf, 'r', encoding='utf-8') as f:
            memories = json_lib.load(f)
    memories.append({"timestamp": time.time(), "user": user_msg, "agent": agent_msg})
    memories = memories[-100:]
    with open(mf, 'w', encoding='utf-8') as f:
        json_lib.dump(memories, f, ensure_ascii=False, indent=2)

def search_memory(query, n_results=5):
    user = st.session_state.get('username', 'jahyun')
    memories = []
    if _supabase:
        try:
            res = _supabase.table('memories').select('*').eq('username', user).order('created_at', desc=True).limit(50).execute()
            memories = [{'user': r['user_msg'], 'agent': r['agent_msg']} for r in res.data]
        except:
            pass
    if not memories:
        mf = get_memory_file()
        if os.path.exists(mf):
            with open(mf, 'r', encoding='utf-8') as f:
                raw = json_lib.load(f)
            memories = [{'user': m['user'], 'agent': m['agent']} for m in raw]
    if not memories:
        return ""
    query_words = set(query.replace("?","").replace("!","").split())
    scored = []
    for m in memories:
        text = m["user"] + " " + m["agent"]
        score = sum(1 for w in query_words if w in text)
        if score:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:n_results]
    if not top:
        top = [(0, m) for m in memories[:3]]
    return "\n".join([f'사용자: {m["user"]} → 에이전트: {m["agent"][:100]}' for _, m in top])

# ──────────────────────────────────────────
# 일정 함수
# ──────────────────────────────────────────
def get_schedule_file():
    user = st.session_state.get('username', 'jahyun')
    return os.path.expanduser(f"~/Desktop/super_agent/schedule_{user}.json")

def load_schedule():
    user = st.session_state.get('username', 'jahyun')
    if _supabase:
        try:
            res = _supabase.table('schedules').select('*').eq('username', user).execute()
            return [{'date': r['date'], 'title': r['title'], 'memo': r.get('memo','')} for r in res.data]
        except:
            pass
    sf = get_schedule_file()
    if os.path.exists(sf):
        with open(sf, 'r', encoding='utf-8') as f:
            return json_lib.load(f)
    return []

def save_schedule(schedules):
    if not _supabase:
        with open(get_schedule_file(), "w", encoding="utf-8") as f:
            json_lib.dump(schedules, f, ensure_ascii=False, indent=2)

def add_schedule(text):
    parts = text.split("|")
    if len(parts) >= 2:
        date_str = parts[0].strip()
        title = parts[1].strip()
        memo = parts[2].strip() if len(parts) > 2 else ""
        # 과거 날짜 차단
        from datetime import date as _date
        today = str(_date.today())
        if date_str < today:
            return f"❌ {date_str}은 이미 지난 날짜예요. 오늘({today}) 이후 날짜만 등록 가능해요."
        user = st.session_state.get('username', 'jahyun')
        if _supabase:
            try:
                _supabase.table('schedules').insert({
                    'username': user,
                    'date': date_str,
                    'title': title,
                    'memo': memo
                }).execute()
                return f"✅ 일정 추가됨: {date_str} {title} ({memo})"
            except:
                pass
        try:
            schedules = load_schedule()
        except:
            schedules = []
        schedules.append({"date": date_str, "title": title, "memo": memo})
        save_schedule(schedules)
        return f"✅ 일정 추가됨: {date_str} {title} ({memo})"
    return "❌ 형식 오류: YYYY-MM-DD|제목|메모 형식으로 입력해주세요"

def get_schedule(query=""):
    schedules = load_schedule()
    if not schedules:
        return "등록된 일정이 없습니다."
    schedules = sorted(schedules, key=lambda x: x.get("date",""))
    result = "[실제 저장된 일정 목록]\n"
    result += "\n".join([f"- {s['date']} {s['title']} {s.get('memo','')}" for s in schedules])
    return result

def delete_schedule(query):
    schedules = load_schedule()
    keyword = query.strip()
    before = len(schedules)
    schedules = [s for s in schedules if keyword not in s.get('title','') and keyword not in s.get('date','')]
    after = len(schedules)
    if before > after:
        if _supabase:
            user = st.session_state.get('username', 'jahyun')
            try:
                _supabase.table('schedules').delete().eq('username', user).or_(f"title.ilike.%{keyword}%,date.ilike.%{keyword}%").execute()
            except:
                pass
        else:
            save_schedule(schedules)
        return f"✅ {before-after}개 일정 삭제됨"
    return "❌ 해당 일정을 찾을 수 없습니다"

def cleanup_old_schedules():
    """오늘 이전 일정 전부 삭제 (로컬 + Supabase 둘 다)"""
    from datetime import date as _date
    today = str(_date.today())
    schedules = load_schedule()
    before = len(schedules)
    schedules = [s for s in schedules if s.get('date', '') >= today]
    after = len(schedules)
    removed = before - after
    if removed == 0:
        return "지난 일정이 없어요!"
    # 로컬 파일 항상 업데이트
    save_schedule(schedules)
    # Supabase도 연결돼 있으면 같이 삭제
    if _supabase:
        user = st.session_state.get('username', 'jahyun')
        try:
            _supabase.table('schedules').delete().eq('username', user).lt('date', today).execute()
        except:
            pass
    return f"✅ {removed}개 지난 일정 삭제됨!"

# ──────────────────────────────────────────
# 도구 함수들
# ──────────────────────────────────────────
def get_date():
    now = datetime.now()
    weekdays = ["월","화","수","목","금","토","일"]
    return f"{now.strftime('%Y년 %m월 %d일')} ({weekdays[now.weekday()]}요일) {now.strftime('%H:%M')}"

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
    dangerous = ['import os', 'import sys', 'import subprocess', '__import__',
                 'shutil', 'rmdir', 'system(', 'popen']
    for d in dangerous:
        if d in code.lower():
            return "❌ 보안상 허용되지 않는 코드예요."
    try:
        result = subprocess.run(
            ['python3', '-c', code],
            capture_output=True, text=True, timeout=10,
            env={'PATH': '/usr/bin:/bin'}
        )
        return result.stdout or result.stderr or "실행 완료 (출력 없음)"
    except subprocess.TimeoutExpired:
        return "❌ 실행 시간 초과 (10초)"
    except Exception as e:
        return str(e)

def get_youtube_summary(url):
    try:
        video_id_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not video_id_match:
            return "❌ 유효한 유튜브 URL이 아닙니다"
        video_id = video_id_match.group(1)
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        transcript = None
        for t in transcript_list:
            if t.language_code == 'ko':
                transcript = t.fetch()
                break
        if not transcript:
            for t in transcript_list:
                if t.language_code == 'en':
                    transcript = t.fetch()
                    break
        if not transcript:
            for t in transcript_list:
                transcript = t.fetch()
                break
        if not transcript:
            return "❌ 자막을 찾을 수 없습니다"
        full_text = " ".join([s.text for s in transcript])
        return f"[유튜브 자막]\n{full_text[:3000]}"
    except Exception as e:
        return f"❌ 자막 오류: {e}"

def read_webpage(url):
    try:
        resp = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script','style','nav','footer']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)[:3000]
    except Exception as e:
        return f"오류: {e}"

def write_report(topic):
    search_result = web_search(topic)
    report = f"# {topic} 보고서\n\n{search_result}"
    st.session_state.last_report = report
    st.session_state.last_report_filename = f"{topic.replace(' ', '_')}_보고서.txt"
    return report

def news_summary(topic):
    return web_search(f"{topic} 최신 뉴스 오늘 한국")

def analyze_data(description):
    if 'file_content' in st.session_state and st.session_state.file_content:
        return f"파일 데이터 분석:\n{st.session_state.file_content[:2000]}"
    return "분석할 파일이 없습니다. 파일을 먼저 업로드해주세요."

def draw_chart(description):
    if 'df' not in st.session_state or st.session_state.df is None:
        return "차트를 그릴 데이터가 없습니다."
    try:
        fig = px.bar(st.session_state.df, title=description)
        st.plotly_chart(fig)
        return "차트 생성 완료"
    except Exception as e:
        return f"차트 오류: {e}"

TOOLS = {
    "web_search": web_search,
    "run_code": run_code,
    "get_schedule": get_schedule,
    "add_schedule": add_schedule,
    "delete_schedule": delete_schedule,
    "cleanup_old_schedules": cleanup_old_schedules,
    "read_webpage": read_webpage,
    "write_report": write_report,
    "news_summary": news_summary,
    "analyze_data": analyze_data,
    "draw_chart": draw_chart,
    "youtube_summary": get_youtube_summary,
}

def execute_tool(tool_name, tool_input):
    tool_name = tool_name.strip()
    if tool_name in TOOLS:
        return TOOLS[tool_name](tool_input)
    return f"알 수 없는 도구: {tool_name}"

# ──────────────────────────────────────────
# LLM & 에이전트
# ──────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

def run_agent(user_input, chat_history):
    schedule_keywords = ["일정", "스케줄", "언제", "추가", "삭제", "더 없", "또", "전부", "다 보", "없어", "있어"]
    is_schedule_query = any(k in user_input for k in schedule_keywords)
    if not is_schedule_query and chat_history:
        for h in chat_history[-4:]:
            if any(k in h.get('content','') for k in schedule_keywords):
                is_schedule_query = True
                break

    long_term_memory = "" if is_schedule_query else search_memory(user_input)
    long_term_section = f"[과거 기억]\n{long_term_memory}\n" if long_term_memory else ""

    history_text = ""
    if chat_history:
        history_text = "\n[이전 대화]\n"
        for h in chat_history[-12:]:
            role = "사용자" if h["role"]=="user" else "에이전트"
            history_text += f"{role}: {h['content']}\n"

    file_text = ""
    if "file_content" in st.session_state and st.session_state.file_content:
        file_text = f"\n[업로드 파일]\n{st.session_state.file_content[:2000]}"

    today = str(date.today())
    tomorrow = str(date.fromordinal(date.today().toordinal()+1))

    system_prompt = f"""너는 자현의 개인 AI 비서 자비스야.

{long_term_section}
[사고 방식]
- 복잡한 문제는 단계별로 분해해서 생각해
- 확실하지 않으면 솔직하게 말해
- 수학/논리 문제는 반드시 검산해

[답변 규칙]
- 항상 존댓말 사용
- 핵심만 간결하게 답변
- 이전 대화 번호 나열 금지
- 한국어만 사용 (영어 고유명사 제외)
- 한자 절대 금지 (進行, 開始 같은 한자 사용 금지)
- 중국어, 일본어 절대 금지

[도구 사용 규칙]
1. 실시간 정보(시세, 날씨, 뉴스)는 반드시 web_search 사용
2. 코드 실행은 run_code 사용
3. 일정은 get_schedule/add_schedule/delete_schedule 사용
4. 유튜브 URL은 youtube_summary 사용
5. 보고서는 write_report 사용

[도구 호출 형식]
TOOL: 도구이름
INPUT: 입력값

[일정 추가 형식]
TOOL: add_schedule
INPUT: YYYY-MM-DD|제목|시간메모
오늘: {today}, 내일: {tomorrow}
※ 오늘({today}) 이전 날짜는 절대 일정 추가 금지

[사용 가능한 도구]
- web_search: 인터넷 검색
- run_code: 파이썬 코드 실행
- get_schedule: 일정 조회
- add_schedule: 일정 추가 (YYYY-MM-DD|제목|메모)
- delete_schedule: 일정 삭제
- cleanup_old_schedules: 지난 일정 전부 삭제
- read_webpage: 웹페이지 읽기
- write_report: 보고서 작성
- news_summary: 뉴스 요약
- analyze_data: 데이터 분석
- draw_chart: 차트 그리기
- youtube_summary: 유튜브 요약

현재 시각: {get_date()}
{history_text}{file_text}"""

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_input)]
    reply = llm.invoke(messages).content

    tool_names = list(TOOLS.keys())
    if "TOOL:" in reply or any(f"{t} INPUT:" in reply or f"{t}\nINPUT:" in reply for t in tool_names):
        lines = reply.strip().split("\n")
        tool_name, tool_input = "", ""
        capture_input = False
        input_lines = []
        for line in lines:
            if line.strip().startswith("TOOL:"):
                tool_name = line.replace("TOOL:", "").strip()
                capture_input = False
            elif any(line.strip().startswith(t) and "INPUT:" in line for t in tool_names):
                parts_line = line.split("INPUT:", 1)
                tool_name = parts_line[0].strip()
                tool_input = parts_line[1].strip() if len(parts_line) > 1 else ""
                capture_input = True
            elif line.strip().startswith("INPUT:"):
                tool_input = line.replace("INPUT:", "").strip()
                capture_input = True
            elif capture_input and line.strip():
                input_lines.append(line.strip())
        if input_lines:
            tool_input = (tool_input + "\n" + "\n".join(input_lines)).strip() if tool_input else "\n".join(input_lines)

        if tool_name:
            tool_result = execute_tool(tool_name, tool_input)
            messages2 = [
                SystemMessage(content="""도구 실행 결과를 그대로 전달해.
- 결과에 있는 정보만 사용
- 추측 금지
- 한국어로 친절하게
- 존댓말 사용"""),
                HumanMessage(content=f"사용자 질문: {user_input}\n\n도구 결과:\n{tool_result}\n\n위 결과만 사용해서 답변해줘.")
            ]
            response = llm.invoke(messages2).content
            return response, "⚡ Groq"

    return reply, "⚡ Groq"

# ──────────────────────────────────────────
# 세션 초기화
# ──────────────────────────────────────────
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'file_content' not in st.session_state:
    st.session_state.file_content = ""
if 'df' not in st.session_state:
    st.session_state.df = None

# 하루 한 번 자동으로 지난 일정 삭제
_today_cleanup_key = f"cleanup_done_{str(date.today())}"
if _today_cleanup_key not in st.session_state:
    try:
        cleanup_old_schedules()
    except:
        pass
    st.session_state[_today_cleanup_key] = True

def process_input(user_input):
    today_key = f"usage_{str(date.today())}_jahyun"
    if today_key not in st.session_state:
        st.session_state[today_key] = 0
    st.session_state[today_key] += 1

    st.session_state.messages.append({"role":"user","content":user_input})
    with st.chat_message("user"):
        st.write(user_input)
    with st.chat_message("assistant"):
        with st.spinner("생각 중... 🤔"):
            try:
                response, ai_name = run_agent(user_input, st.session_state.chat_history)
            except Exception as e:
                response, ai_name = f"오류: {e}", "오류"
        st.write(response)
        st.caption(f"사용된 AI: {ai_name}")
    st.session_state.messages.append({"role":"assistant","content":response})
    try:
        save_memory(user_input, response)
    except:
        pass
    st.session_state.chat_history.append({"role":"user","content":user_input})
    st.session_state.chat_history.append({"role":"assistant","content":response})
    if st.session_state.get('voice_mode', False) and VOICE_AVAILABLE:
        speak(response)

# ──────────────────────────────────────────
# 툴바 (파일업로드, 음성, 초기화)
# ──────────────────────────────────────────
with st.expander("⚙️ 설정 및 파일 업로드", expanded=False):
    col_a, col_b = st.columns([3, 1])
    with col_a:
        uploaded_file = st.file_uploader("📎 파일 업로드", type=['pdf','csv','xlsx','txt'], label_visibility="collapsed")
        if uploaded_file:
            file_ext = uploaded_file.name.split('.')[-1].lower()
            if file_ext == 'pdf':
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
                st.session_state.file_content = "\n".join([p.extract_text() or "" for p in pdf_reader.pages])
            elif file_ext == 'csv':
                df = pd.read_csv(uploaded_file)
                st.session_state.df = df
                st.session_state.file_content = df.to_string()
            elif file_ext == 'xlsx':
                df = pd.read_excel(uploaded_file)
                st.session_state.df = df
                st.session_state.file_content = df.to_string()
            elif file_ext == 'txt':
                st.session_state.file_content = uploaded_file.read().decode('utf-8')
            st.success(f"✅ {uploaded_file.name} 로드됨")
    with col_b:
        if VOICE_AVAILABLE:
            st.session_state.voice_mode = st.toggle("🔊 음성 자동재생", value=st.session_state.get("voice_mode", False))
        if st.button("🗑️ 지난 일정 삭제", use_container_width=True):
            result = cleanup_old_schedules()
            st.toast(result)



# ──────────────────────────────────────────
# 메인 채팅
# ──────────────────────────────────────────
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("""
<div style='
    background: linear-gradient(135deg, rgba(183,28,28,0.15), rgba(13,71,161,0.15));
    border: 1px solid rgba(239,83,80,0.3);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
'>
    <div style='font-size: 20px; color: #ef5350; font-weight: bold; margin-bottom: 8px;'>⚡ J.A.R.V.I.S 온라인</div>
    <div style='color: #4fc3f7; font-size: 14px;'>안녕하세요, 자현님. 모든 시스템이 정상 작동 중입니다.</div>
    <div style='color: #78909c; font-size: 12px; margin-top: 8px;'>검색 · 일정관리 · 뉴스요약 · 유튜브요약 · 코드실행 · 보고서작성</div>
</div>
""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if 'last_report' in st.session_state and st.session_state.last_report:
    st.download_button(
        label="📥 보고서 다운로드",
        data=st.session_state.last_report,
        file_name=st.session_state.get('last_report_filename', 'report.txt'),
        mime="text/plain"
    )

# 채팅 입력
user_input = st.chat_input("자비스에게 말하세요... 💬")
if user_input:
    process_input(user_input)

# 음성 버튼 (채팅창 바로 위, 오른쪽 정렬)
if VOICE_AVAILABLE:
    st.markdown("""
    <style>
    .voice-row {
        position: fixed;
        bottom: 70px;
        right: 28px;
        z-index: 99999;
    }
    .voice-row button {
        width: 40px !important;
        height: 40px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #b71c1c, #0d47a1) !important;
        border: 1px solid #ef5350 !important;
        font-size: 18px !important;
        padding: 0 !important;
        line-height: 1 !important;
        box-shadow: 0 0 10px rgba(239,83,80,0.5) !important;
    }
    .voice-row button:hover {
        box-shadow: 0 0 20px rgba(239,83,80,0.9) !important;
        transform: scale(1.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="voice-row">', unsafe_allow_html=True)
        if st.button("🎙️", key="voice_fixed", help="음성 입력"):
            with st.spinner("🎙️ 듣는 중..."):
                voice_text = listen()
            if voice_text:
                st.toast(f"✅ {voice_text}")
                process_input(voice_text)
            else:
                st.toast("❌ 다시 시도해주세요!")
        st.markdown('</div>', unsafe_allow_html=True)
