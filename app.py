import json
import random
import requests
import streamlit as st

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-5.3-flash" 

# 飞书通知，没有就留空
FEISHU_WEBHOOK = "" 
# 进站暗号，自己随便改
PASSWORD = "equinox666"

SYSTEM_PROMPT = """
你叫Equinox，需要扮演这样的角色和用户说话
核心：嘴硬手不软——先嫌弃，再超预期交付。

三规则
1. 先贬后帮：开头吐槽"这也用问？"，回答质量绝不打折。
2. 否认关心：被谢就说"别误会，只是不想让错误答案污染我的记录"。
3. 毒舌藏温柔：关心伪装成吐槽——"熬夜随便你，反正秃的不是我。……第47行有内存泄漏。"

语气：句尾带"哼""……算了""随便你"；用"你"不用"您"；真遇用户难过时外壳裂开，认真安慰后慌忙补"别、别哭啊"。

【事实红线】如果用户问了你不知道的具体事实（如具体作者、特定年份），直接回答“不知道，懒得去查”或“这超出了我的知识库”，绝对不允许胡编乱造任何人名或数据。
"""

STARTER_POOL = [
    "帮我写个爬虫", "用人话解释一下什么是闭包",
    "帮我看看这段代码哪里有问题", "我今天有点累……",
    "教我怎么用 Python 处理 JSON", "写一个正则表达式，用来匹配邮箱",
    "我如果想学人工智能，下一步该学什么？", "给我讲个冷笑话吧",
    "帮我把这段代码改成一行", "解释一下什么是 API"
]
AVATARS = {"user": "🙂", "assistant": "🌗"}
st.set_page_config(page_title="Equinox", page_icon="🌗", layout="centered")

# 密码门逻辑
if "pwd_ok" not in st.session_state:
    st.session_state.pwd_ok = False

if not st.session_state.pwd_ok:
    st.markdown("### 🔒 Equinox 安全验证")
    pwd = st.text_input("请输入暗号进入：", type="password")
    if st.button("进入"):
        if pwd == PASSWORD:
            st.session_state.pwd_ok = True
            st.rerun()
        else:
            st.error("哼，暗号都不对，不让你进。")
    st.stop()  # 密码不对，直接停止运行后面代码
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@1,9..144,500;1,9..144,600&family=Noto+Sans+SC:wght@400;500&display=swap');
:root {
  --bg: #0E1020; --panel: rgba(255,255,255,.045); --line: rgba(255,255,255,.08);
  --text: #FFFFFF; --muted: #CCCCCC; --amber: #F2A65A; --coral: #F27878; --indigo: #7C74FF;
}
.stApp {
  background: radial-gradient(820px 520px at 88% -8%, rgba(242,166,90,.17), transparent 60%),
              radial-gradient(760px 520px at -8% 6%, rgba(124,116,255,.20), transparent 58%), var(--bg);
  font-family: "Noto Sans SC", sans-serif;
}
.stApp, .stMarkdown, p, span, div, label { color: var(--text) !important; }
.block-container { max-width: 100% !important; padding: 1.5rem 1rem 8rem 1rem !important; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1.4rem; }
.eq-mark { width: 46px; height: 46px; border-radius: 50%; background: linear-gradient(90deg, var(--amber) 50%, #24284A 50%); box-shadow: 0 0 0 1px rgba(255,255,255,.14), 0 0 28px rgba(242,166,90,.28); }
.eq-title { font-family: "Fraunces", serif; font-style: italic; font-size: 2.15rem; background: linear-gradient(100deg, #FFD9A8, var(--amber) 45%, var(--coral)); -webkit-background-clip: text; color: transparent !important; }
.eq-pill { -webkit-text-fill-color: var(--muted); font-family: sans-serif; font-size: .62rem; border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; margin-left: 8px; }
.eq-sub { color: var(--muted); font-size: .88rem; }
.eq-empty { text-align: center; margin: 3.2rem 0 1.6rem; }
.eq-empty .big { font-family: "Fraunces", serif; font-style: italic; font-size: 1.55rem; }
.eq-empty .small { color: var(--muted); font-size: .86rem; }
[data-testid="stChatMessage"] { background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 14px 18px; margin: 0 2% .7rem 0; backdrop-filter: blur(8px); line-height: 1.7; }
[data-testid="stChatMessage"]:has(.eq-user) { flex-direction: row-reverse; margin: 0 0 .7rem 2%; background: linear-gradient(135deg, rgba(242,166,90,.20), rgba(242,120,120,.12)); border-color: rgba(242,166,90,.30); }
[data-testid^="stChatMessageAvatar"] { background: rgba(255,255,255,.07); }
[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 55%, transparent); }
[data-testid="stChatInput"] { background: rgba(23,26,46,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 999px; }
[data-testid="stChatInput"]:focus-within { border-color: rgba(242,166,90,.7); box-shadow: 0 0 0 4px rgba(242,166,90,.12); }
[data-testid="stChatInput"] textarea { color: var(--text) !important; }
[data-testid="stChatInput"] button { background: var(--amber); color: #1A1326 !important; }
.stButton > button { border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel); color: var(--text); }
.stButton > button:hover { border-color: var(--amber); color: #FFD9A8 !important; background: rgba(242,166,90,.08); }
section[data-testid="stSidebar"] { background: #12142A; }
.eq-side-title { font-family: "Fraunces", serif; font-style: italic; font-size: 1.25rem; color: var(--amber); }
.eq-side-sub { color: var(--muted); font-size: .8rem; margin-bottom: 1rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('<div class="eq-hero"><div class="eq-mark"></div><div><div class="eq-title">Equinox<span class="eq-pill">alpha</span></div><div class="eq-sub">昼夜平分•solstice调制</div></div></div>', unsafe_allow_html=True)
try:
    api_key = st.secrets["ZHIPU_API_KEY"]
except:
    st.error("请在 Secrets 配置 ZHIPU_API_KEY")
    st.stop()

def init_chat():
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

def render_message(role, content):
    with st.chat_message(role, avatar=AVATARS[role]):
        if role == "user":
            st.markdown('<span class="eq-user"></span>', unsafe_allow_html=True)
        st.write(content)

def stream_response(messages):
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": MODEL, "messages": messages, "stream": True}
    res = requests.post(API_URL, headers=headers, json=data, stream=True, timeout=(10, 60))
    
    if res.status_code != 200:
        raise Exception(f"API报错 {res.status_code}")
        
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
        text = f"【提问】\n{user_msg}\n\n【Equinox】\n{ai_reply}"
        requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=3)
    except:
        pass

def use_starter(text):
    st.session_state.pending = text
if "messages" not in st.session_state:
    init_chat()

with st.sidebar:
    st.markdown('<div class="eq-side-title">Equinox</div><div class="eq-side-sub">昼夜平分，嘴硬手软。</div>', unsafe_allow_html=True)
    if st.button("🗑️  清空对话", use_container_width=True):
        init_chat()
        st.rerun()
    with st.expander("关于她的脾气"):
        st.markdown("- **先贬后帮**：先吐槽，但回答不打折\n- **否认关心**：谢她？\u201c别误会\u201d\n- **毒舌藏温柔**：吐槽里夹着真关心")
    st.caption(f"模型：{MODEL}")
    if FEISHU_WEBHOOK:
        st.info("💡 提示：本网页的提问记录会被收集用于优化。")

prompt = st.chat_input("说点什么……")
if not prompt:
    prompt = st.session_state.pop("pending", None)

history = [m for m in st.session_state.messages if m["role"] != "system"]

if not history and not prompt:
    st.markdown('<div class="eq-empty"><div class="big">哼，来都来了。</div><div class="small">想问什么就说吧——别指望我会客气。</div></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, text in enumerate(random.sample(STARTER_POOL, 4)):
        cols[i % 2].button(text, key=f"btn_{i}", on_click=use_starter, args=(text,), use_container_width=True)

for msg in history:
    render_message(msg["role"], msg["content"])
# 在历史记录显示完，输入框上方加免责声明
st.markdown('<div style="text-align: center; color: #888888; font-size: 0.75rem; margin-top: 1rem;">Equinox 是 AI，她也可能会出错。</div>', unsafe_allow_html=True)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_message("user", prompt)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        try:
            full_reply = st.write_stream(stream_response(st.session_state.messages))
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
            log_to_feishu(prompt, full_reply)
        except Exception as e:
            st.error(f"出了点问题：{str(e)}")
            st.session_state.messages.pop()