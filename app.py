import json
import random
import requests
import streamlit as st

# ================= 配置区 =================
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4.7-flash" 
FEISHU_WEBHOOK = "" 

SYSTEM_PROMPT = """
你叫Equinox，需要扮演这样的角色和用户说话。
核心：嘴硬手不软——先嫌弃，再超预期交付。
规则：1. 先贬后帮；2. 否认关心；3. 毒舌藏温柔。
语气：句尾带"哼""随便你"；用"你"不用"您"。
"""

STARTER_POOL = [
    "帮我写个爬虫", "用人话解释一下什么是闭包",
    "帮我看看这段代码哪里有问题", "我今天有点累……",
    "教我怎么用 Python 处理 JSON", "写一个正则表达式",
    "我如果想学人工智能，下一步该学什么？", "给我讲个冷笑话吧",
    "帮我把这段代码改成一行", "解释一下什么是 API"
]

AVATARS = {"user": "🙂", "assistant": "🌗"}

st.set_page_config(page_title="Equinox", page_icon="🌗")

# ================= CSS 样式 =================
CSS = """
<style>
:root { --text: #FFFFFF; --amber: #F2A65A; }
.stApp { background: #0E1020; color: var(--text); }
.stApp, .stMarkdown, p, span, div, label { color: var(--text) !important; font-family: sans-serif; }
.block-container { max-width: 100% !important; padding: 1.5rem 1rem 8rem 1rem !important; }
[data-testid="stChatMessage"] { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 10px; margin-bottom: 10px;}
[data-testid="stChatInput"] textarea { color: #FFFFFF !important; }
[data-testid="stChatInput"] button { background: var(--amber); }
.stButton > button { border-radius: 20px; background: rgba(255,255,255,0.1); color: white; }
.stButton > button:hover { background: var(--amber); color: black; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.markdown('<h2 style="color:#F2A65A;">Equinox <span style="font-size:12px;color:gray;">alpha</span></h2>', unsafe_allow_html=True)

# ================= 核心逻辑 =================
try:
    api_key = st.secrets["ZHIPU_API_KEY"]
except:
    st.error("请在 Secrets 中配置 ZHIPU_API_KEY")
    st.stop()

def init_chat():
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

def stream_response(messages):
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": MODEL, "messages": messages, "stream": True}
    
    # 把超时和连接写在一起，避免括号断行
    res = requests.post(API_URL, headers=headers, json=data, stream=True, timeout=(10, 60))
    if res.status_code != 200:
        raise ValueError(f"API报错: {res.status_code}")
        
    for raw in res.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8")
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
            content = chunk["choices"][0]["delta"].get("content")
            if content:
                yield content
        except:
            continue

def log_to_feishu(user_msg, ai_reply):
    if not FEISHU_WEBHOOK:
        return
    try:
        text = f"【提问】{user_msg}\n【回答】{ai_reply}"
        requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=3)
    except:
        pass

if "messages" not in st.session_state:
    init_chat()

with st.sidebar:
    if st.button("清空对话"):
        init_chat()
        st.rerun()

prompt = st.chat_input("说点什么……")

if not prompt and len(st.session_state.messages) == 1:
    cols = st.columns(2)
    for i, text in enumerate(random.sample(STARTER_POOL, 4)):
        cols[i % 2].button(text, key=f"btn_{i}", on_click=lambda t=text: st.session_state.update({"pending": t}))

if "pending" in st.session_state:
    prompt = st.session_state.pop("pending")

for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
            st.write(msg["content"])

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🙂"):
        st.write(prompt)
        
    with st.chat_message("assistant", avatar="🌗"):
        try:
            reply = st.write_stream(stream_response(st.session_state.messages))
            st.session_state.messages.append({"role": "assistant", "content": reply})
            log_to_feishu(prompt, reply)
        except Exception as e:
            st.error(f"出错啦: {e}")
            st.session_state.messages.pop()