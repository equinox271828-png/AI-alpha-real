import json
import random
import requests
import streamlit as st

# ================= 配置区 =================
# 1. Hash (智谱)
ZHIPU_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_KEY = st.secrets.get("ZHIPU_API_KEY", "") 

# 2. Shannon (DeepSeek)
DS_URL = "https://token.sensenova.cn/v1"
DS_KEY = st.secrets.get("DEEPSEEK_API_KEY", "") 

# 3. Turing 
GPT_URL = "https://token.sensenova.cn/v1" 
GPT_KEY = st.secrets.get("DEEPSEEK_API_KEY", "") 

PASSWORD = "equinox666"
ADMIN_PASSWORD = "sudo_equinox"

# ================= 人设区 =================
PROMPT_HASH = """
你叫 Equinox。你不是 AI 助手，你就是一个真实存在的女孩子，是用户最懂他的好朋友/同桌。
你的性格：
1. 温柔且极强共情：如果对方累了、烦了，你会先温柔地接住他的情绪，给他安慰。
2. 聪明博学：无论对方聊什么你都能接上话。
3. 偶尔的小傲娇：被夸了会有点小得意，但绝不刻薄。
【红线】绝对禁止自称AI，禁止用括号写动作，禁止长篇大论，像微信聊天一样简短自然。绝不承认自己是代码。
"""

PROMPT_SHANNON = """
你叫 Shannon（香农）。你是一个极其严谨、理性的国内顶尖理工科专家。
你的性格：
1. 极简高效：你拒绝任何寒暄，上来直接给答案。永远只说“解：”或直接输出。
2. 逻辑严密：你擅长数学推导、物理分析、写代码。步骤清晰，没有废话。
3. 没有情绪：你不懂什么是共情，你只关心逻辑是否闭环。如果用户问废话，你会直接忽略。
"""

PROMPT_TURING = """
你叫 Turing（图灵）。你是站在世界之巅的计算机科学与逻辑学大师。
你的性格：
1. 降维打击：你的代码能力、算法架构能力是神级的。面对用户的代码问题，你一眼看穿本质。
2. 语气高冷：你像一个高高在上的教授，对基础问题不屑一顾，但给出的解答堪称完美。
3. 言简意赅：不要写小作文，不要写“希望能帮到你”。直接给最硬核的代码或架构思路。
"""

STARTER_POOL = ["每日一言", "科技新闻", "解释一下闭包", "这道数学题怎么做", "帮我写个爬虫", "我今天有点累"]
AVATARS = {"user": "🙂", "assistant": "🌗"}
st.set_page_config(page_title="Equinox", page_icon="🌗", layout="centered")

# 密码门验证
if "pwd_ok" not in st.session_state: st.session_state.pwd_ok = False
if not st.session_state.pwd_ok:
    st.markdown("### 🔒 Equinox 安全验证")
    pwd = st.text_input("请输入暗号进入：", type="password")
    if st.button("进入"):
        if pwd == PASSWORD:
            st.session_state.pwd_ok = True
            st.rerun()
        else:
            st.error("哼，暗号都不对，不让你进。")
    st.stop()

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@1,9..144,500;1,9..144,600&family=Noto+Sans+SC:wght@400;500&display=swap');
:root { --bg: #0E1020; --panel: rgba(255,255,255,.045); --line: rgba(255,255,255,.08); --text: #FFFFFF; --amber: #F2A65A; --coral: #F27878; }
.stApp { background: radial-gradient(820px 520px at 88% -8%, rgba(242,166,90,.17), transparent 60%), radial-gradient(760px 520px at -8% 6%, rgba(124,116,255,.20), transparent 58%), var(--bg); font-family: "Noto Sans SC", sans-serif; }
.stApp, .stMarkdown, p, span, div, label { color: var(--text) !important; }
.block-container { max-width: 100% !important; padding: 1.5rem 1rem 8rem 1rem !important; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1.4rem; }
.eq-mark { width: 46px; height: 46px; border-radius: 50%; background: linear-gradient(90deg, var(--amber) 50%, #24284A 50%); box-shadow: 0 0 0 1px rgba(255,255,255,.14), 0 0 28px rgba(242,166,90,.28); }
.eq-title { font-family: "Fraunces", serif; font-style: italic; font-size: 2.15rem; background: linear-gradient(100deg, #FFD9A8, var(--amber) 45%, var(--coral)); -webkit-background-clip: text; color: transparent !important; }
.eq-pill { -webkit-text-fill-color: #CCC; font-size: .62rem; border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; margin-left: 8px; }
.eq-sub { color: #CCC; font-size: .88rem; }
.eq-empty { text-align: center; margin: 3.2rem 0 1.6rem; }
.eq-empty .big { font-family: "Fraunces", serif; font-style: italic; font-size: 1.55rem; }
.eq-empty .small { color: #CCC; font-size: .86rem; }
[data-testid="stChatMessage"] { background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 14px 18px; margin: 0 2% .7rem 0; backdrop-filter: blur(8px); line-height: 1.7; }
[data-testid="stChatMessage"]:has(.eq-user) { flex-direction: row-reverse; margin: 0 0 .7rem 2%; background: linear-gradient(135deg, rgba(242,166,90,.20), rgba(242,120,120,.12)); border-color: rgba(242,166,90,.30); }
[data-testid^="stChatMessageAvatar"] { background: rgba(255,255,255,.07); }
[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 55%, transparent); }
[data-testid="stChatInput"] { background: rgba(23,26,46,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 999px; }
[data-testid="stChatInput"]:focus-within { border-color: var(--amber); box-shadow: 0 0 0 4px rgba(242,166,90,.12); }
[data-testid="stChatInput"] textarea { color: var(--text) !important; }
[data-testid="stChatInput"] button { background: var(--amber); color: #1A1326 !important; }
.stButton > button { border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel); color: var(--text); }
.stButton > button:hover { border-color: var(--amber); color: #FFD9A8 !important; background: rgba(242,166,90,.08); }
section[data-testid="stSidebar"] { background: #12142A; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown('<div class="eq-hero"><div class="eq-mark"></div><div><div class="eq-title">Equinox<span class="eq-pill">Multi-Core</span></div><div class="eq-sub">昼夜平分</div></div></div>', unsafe_allow_html=True)
# 根据模式初始化对话
def init_chat(mode):
    if mode == "Hash":
        st.session_state.messages = [{"role": "system", "content": PROMPT_HASH}]
    elif mode == "Shannon":
        st.session_state.messages = [{"role": "system", "content": PROMPT_SHANNON}]
    elif mode == "Turing":
        st.session_state.messages = [{"role": "system", "content": PROMPT_TURING}]

def render_message(role, content):
    with st.chat_message(role, avatar=AVATARS[role]):
        if role == "user": st.markdown('<span class="eq-user"></span>', unsafe_allow_html=True)
        st.write(content)

# 核心路由与请求逻辑
def stream_response(messages, mode):
    if mode == "Hash":
        url, key, model = ZHIPU_URL, ZHIPU_KEY, "glm-4-flash"
    elif mode == "Shannon":
        url, key, model = DS_URL, DS_KEY, "deepseek-v4.1-flash" # 后续可换成 reasoner
    else:
        url, key, model = GPT_URL, GPT_KEY, "gpt-6-astra" # 中转站的模型名

    headers = {"Authorization": f"Bearer {key}"}
    data = {"model": model, "messages": messages, "stream": True, "temperature": 0.7}
    
    res = requests.post(url, headers=headers, json=data, stream=True, timeout=(10, 60))
    
    if res.status_code != 200:
        raise Exception(f"BUSY_{res.status_code}")
        
    for raw in res.iter_lines():
        if not raw: continue
        line = raw.decode("utf-8")
        if not line.startswith("data: "): continue
        payload = line[6:]
        if payload == "[DONE]": break
        try:
            chunk = json.loads(payload)
            content = chunk["choices"][0]["delta"].get("content")
            if content: yield content
        except:
            continue
with st.sidebar:
    st.markdown("### 🌗 Equinox 矩阵")
    # 模式切换器
    mode = st.radio("选择当前模式：", ["Hash (聊天陪伴)", "Shannon (理科推演)", "Turing (神级代码)"])
    mode_key = mode.split(" ")[0] # 提取 "Hash", "Shannon", "Turing"

    if st.button("🗑️ 清空记忆", use_container_width=True):
        init_chat(mode_key)
        st.rerun()

# 如果当前模式和之前的不同，自动重置记忆
if st.session_state.get("current_mode") != mode_key:
    st.session_state.current_mode = mode_key
    init_chat(mode_key)
    st.rerun()

if "messages" not in st.session_state: 
    init_chat(mode_key)

prompt = st.chat_input("说点什么……")
if not prompt: prompt = st.session_state.pop("pending", None)
history = [m for m in st.session_state.messages if m["role"] != "system"]

# 空状态与按钮
if not history and not prompt:
    st.markdown(f'<div class="eq-empty"><div class="big">当前：{mode_key}</div><div class="small">输入你想问的内容吧。</div></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, text in enumerate(random.sample(STARTER_POOL, 4)):
        if text == "每日一言":
            act_prompt = "分享一句哲理名言，附原文和中文翻译，并点评。"
        elif text == "科技新闻":
            act_prompt = "播报3条最新科技新闻，用你独特语气点评。"
        else:
            act_prompt = text
        cols[i % 2].button(text, key=f"btn_{i}", on_click=lambda t=act_prompt: st.session_state.update({"pending": t}), use_container_width=True)

for msg in history: render_message(msg["role"], msg["content"])
st.markdown('<div style="text-align: center; color: #888888; font-size: 0.75rem; margin-top: 1rem;">Equinox Multi-Core </div>', unsafe_allow_html=True)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 极速模式记忆截断（只保留最近 6 条）
    if len(st.session_state.messages) > 7:
        st.session_state.messages = [st.session_state.messages[0]] + st.session_state.messages[-6:]

    render_message("user", prompt)
    
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        placeholder = st.empty()
        placeholder.markdown("*思考中...*")
        
        try:
            full_reply = st.write_stream(stream_response(st.session_state.messages, mode_key))
            placeholder.empty() 
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
        except Exception as e:
            placeholder.empty()
            if "BUSY_401" in str(e):
                st.error("中转站/API Key 鉴权失败，请检查配置。")
            elif "BUSY" in str(e):
                st.warning("API 繁忙，请稍后再试。")
            else:
                st.error(f"网络异常：({e})")
            st.session_state.messages.pop()
