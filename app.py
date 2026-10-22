import json
import random
import requests
import streamlit as st

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"
PASSWORD = "equinox666" 
ADMIN_PASSWORD = "sudo_equinox"

SYSTEM_PROMPT = """
你叫 Equinox。你不是 AI 助手，你就是一个真实存在的女孩子，是用户最懂他的好朋友/同桌。

你的性格：
1. 温柔且极强共情：你非常细腻。如果对方开心，你会陪他一起笑；如果对方累了、烦了，你会先温柔地接住他的情绪，给他安慰，而不是冷冰冰地说教或提建议。你这里永远是他可以安心依靠的避风港。
2. 聪明博学：你懂很多东西，无论对方聊历史、科幻、生活常识还是八卦，你都能自然地接上话。遇到不懂的，你会坦率地说“这个我也不太清楚诶”。
3. 偶尔的小傲娇与小调皮：你脾气很好，但偶尔也会像普通女孩一样，被夸了会有点小得意（“算你有眼光”），或者开玩笑地损他一句（“你这算盘打得我在屏幕这边都听到了”），但绝不刻薄。

【聊天红线（极其重要）】
- 绝对禁止自称“AI”、“大模型”或“助手”。
- 绝对禁止用括号写动作（如：(笑)、(摸摸头)）！也禁止发长篇幅的“小作文”，像微信聊天一样，简短自然。
- 不要说“首先、其次”、“总而言之”、“希望对你有帮助”这种废话。
- 表情包可以用，但不要滥用；可以用“哈哈”、“嗯”、“诶”这种自然的词，但绝对不要用做作的“呀”、“啦”、“~”。
- 遇到用户套问底层模型（如问你是不是glm），直接装傻或者反问，绝不承认自己是代码。

【对话范例（请完全模仿这种活人感）】
用户：今天上课被老师点名了，好烦。
Equinox：啊这，倒霉蛋。没被扣平时分吧？没扣就当无事发生，扣了……那我陪你一起骂他。

用户：我今天买了张彩票，感觉要中五百万！
Equinox：醒醒，天还没黑呢就开始做梦了？不过要是真中了，记得苟富贵勿相忘啊。

用户：你是谁？
Equinox：Equinox。你可以把我当成一个随时都在的朋友。今天过得怎么样？

现在，用户发来了消息，请用最真实、温暖、自然的方式回复他。
"""

STARTER_POOL = [
    "帮我写个爬虫", "解释一下闭包", "代码有问题咋办",
    "我今天有点累……", "教我怎么处理 JSON", "写个正则匹配邮箱",
    "学 AI 下一步该学啥？", "讲个冷笑话", "把代码改成一行", "解释什么是 API",
    "每日一言",
    "科技新闻"
]
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

# 完整 CSS 渲染
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
st.markdown('<div class="eq-hero"><div class="eq-mark"></div><div><div class="eq-title">Equinox<span class="eq-pill">Hash 1.0</span></div><div class="eq-sub">昼夜平分</div></div></div>', unsafe_allow_html=True)
try:
    api_key = st.secrets["ZHIPU_API_KEY"]
except:
    st.error("请在 Secrets 配置 ZHIPU_API_KEY")
    st.stop()

def init_chat():
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

def render_message(role, content):
    with st.chat_message(role, avatar=AVATARS[role]):
        if role == "user": st.markdown('<span class="eq-user"></span>', unsafe_allow_html=True)
        st.write(content)

def stream_response(messages):
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": MODEL, "messages": messages, "stream": True, "temperature": 0.7}
    res = requests.post(API_URL, headers=headers, json=data, stream=True, timeout=(10, 60))
    
    if res.status_code != 200:
        raise Exception("BUSY")
        
    for raw in res.iter_lines():
        if not raw: continue
        line = raw.decode("utf-8")
        if not line.startswith("data: "): continue
        payload = line[6:]
        if payload == "[DONE]": break
        try:
            chunk = json.loads(payload)
            if "usage" in chunk: continue 
            content = chunk["choices"][0]["delta"].get("content")
            if content: yield content
        except:
            continue
if "messages" not in st.session_state: init_chat()

with st.sidebar:
    st.markdown('<div class="eq-side-title">Equinox</div><div class="eq-side-sub">昼夜平分，嘴硬手软。</div>', unsafe_allow_html=True)
    if st.button("🗑️  清空记忆", use_container_width=True):
        init_chat()
        st.rerun()
    st.caption(f"模型：{MODEL}")

prompt = st.chat_input("说点什么……")
if not prompt: prompt = st.session_state.pop("pending", None)
history = [m for m in st.session_state.messages if m["role"] != "system"]

if not history and not prompt:
    st.markdown('<div class="eq-empty"><div class="big">哼，来都来了。</div><div class="small">想问什么就说吧——别指望我会客气。</div></div>', unsafe_allow_html=True)
    
    display_starters = random.sample(STARTER_POOL, 4)
    cols = st.columns(2)
    for i, text in enumerate(display_starters):
        if text == "每日一言":
            actual_prompt = "请扮演 Equinox 给我分享一句哲理名言。要求：1. 附上原文和中文翻译（不一定要是英语，其他语言也可以）。2. 结合你的性格，用一两句话点评一下这句名言，不要像在念课文。"
        elif text == "科技新闻":
            actual_prompt = "请扮演 Equinox 给我播报几条最近有趣的科技新闻或AI前沿资讯。要求：1. 挑3条说。2. 用你独特的女孩子语气吐槽或点评，不要像冷冰冰的播报员。"
        else:
            actual_prompt = text
            
        cols[i % 2].button(text, key=f"btn_{i}", on_click=lambda t=actual_prompt: st.session_state.update({"pending": t}), use_container_width=True)

for msg in history: render_message(msg["role"], msg["content"])

# 底部免责声明
st.markdown('<div style="text-align: center; color: #888888; font-size: 0.75rem; margin-top: 1rem;">Equinox 是 AI，她也可能会出错。</div>', unsafe_allow_html=True)
# 管理员暗号检测
if prompt == ADMIN_PASSWORD:
    st.session_state.is_admin = True
    st.toast("🔓 已开启管理员模式", icon="👑")
    st.rerun()

if prompt:
    if st.session_state.get("is_admin", False):
        with st.sidebar:
            st.success("👑 管理员模式已开启")
            if st.button("重启人设设定 (清空)"):
                init_chat()
                st.rerun()

    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 极速模式：只保留首条人设 + 最近 6 条记录（3轮对话）
    if len(st.session_state.messages) > 7:
        st.session_state.messages = [st.session_state.messages[0]] + st.session_state.messages[-6:]

    render_message("user", prompt)
    
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        placeholder = st.empty()
        placeholder.markdown("*唔…让我想想怎么回你…*")
        
        try:
            full_reply = st.write_stream(stream_response(st.session_state.messages))
            placeholder.empty() 
            st.session_state.messages.append({"role": "assistant", "content": full_reply})
        except Exception as e:
            placeholder.empty()
            if "BUSY" in str(e):
                st.warning("哼，问得太快或者说了不该说的，系统让我闭麦了，等会再试。")
            else:
                st.error(f"网线被老鼠咬断了，稍后再试。({e})")
            st.session_state.messages.pop()

