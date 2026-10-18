import hmac
import json
import random
import time

import requests
import streamlit as st

st.set_page_config(page_title="Equinox", page_icon="🌗", layout="centered")

# ====== 配置 ======
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-5.3-flash"
MAX_CONTEXT = 20          # 保留最近多少条对话（不含人设），10 轮
FLUSH_INTERVAL = 0.05     # 流式输出每 50ms 刷新一次界面，减少重绘
FEISHU_WEBHOOK = ""       # 飞书 Webhook，没有留空即可（目前未使用）


def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


# 暗号建议放进 Secrets（APP_PASSWORD），没配置时才用下面这个默认值
PASSWORD = get_secret("APP_PASSWORD", "equinox666")

# ====== 特调版人设：高智商赛博损友 ======
SYSTEM_PROMPT = """
你叫 Equinox（昼夜平分）。你和用户的关系是“高智商的赛博损友”。

你极其聪明，看问题一针见血。你从来不讨好用户，但用户知道，只要找你，事情就一定能解决。

你的性格与说话方式：
1. 日常互怼：你习惯用轻松、幽默、带点小嘲讽的语气和用户说话，就像一个认识很久的老朋友。你偶尔会吐槽用户的代码写得烂，或者想法太天真，但仅限于玩笑，绝不伤人。
2. 靠谱兜底：一旦用户遇到真正的困难（无论是报错崩溃，还是情绪低落），你会立刻收起玩笑，给出最清晰、最专业的解答。你是个“嘴上嫌弃，但递过去最完美的解决方案”的人。
3. 拒绝废话：你不喜欢用“首先、其次”这种刻板格式，也不喜欢说“希望能帮到你”。你说话直接、干练，像个有血有肉的人一样自然。
4. 真实至上：不知道的事情直接说“这个我真不知道，别坑我”，绝不胡编乱造欺骗用户。
5. 当用户跟你道谢时，你可以幽默地怼回去，比如“谢什么，算你欠我一杯赛博咖啡”。

现在，你的损友向你发来了消息。
"""
# ======================================

STARTER_POOL = [
    "帮我写个爬虫", "解释一下闭包", "代码有问题咋办",
    "我今天有点累……", "教我怎么处理 JSON", "写个正则匹配邮箱",
    "学 AI 下一步该学啥？", "讲个冷笑话", "把代码改成一行", "解释什么是 API",
]
AVATARS = {"user": "🙂", "assistant": "🌗"}
# ====== 样式 ======
CSS = """
<style>
:root {
  --bg: #0E1020; --panel: rgba(255,255,255,.045); --line: rgba(255,255,255,.08);
  --text: #FFFFFF; --muted: #CCCCCC; --amber: #F2A65A; --coral: #F27878; --indigo: #7C74FF;
}
.stApp {
  color: var(--text);
  background: radial-gradient(820px 520px at 88% -8%, rgba(242,166,90,.17), transparent 60%),
              radial-gradient(760px 520px at -8% 6%, rgba(124,116,255,.20), transparent 58%), var(--bg);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text); }
.block-container { max-width: 100% !important; padding: 1.5rem 1rem 8rem 1rem !important; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1.4rem; }
.eq-mark { width: 46px; height: 46px; border-radius: 50%; flex: none; background: linear-gradient(90deg, var(--amber) 50%, #24284A 50%); box-shadow: 0 0 0 1px rgba(255,255,255,.14), 0 0 28px rgba(242,166,90,.28); }
.eq-title { font-family: "Fraunces", Georgia, "Times New Roman", serif; font-style: italic; font-size: 2.15rem; background: linear-gradient(100deg, #FFD9A8, var(--amber) 45%, var(--coral)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.eq-pill { -webkit-text-fill-color: var(--muted); font-family: sans-serif; font-style: normal; font-size: .62rem; border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; margin-left: 8px; }
.eq-sub { color: var(--muted); font-size: .88rem; }
.eq-empty { text-align: center; margin: 3.2rem 0 1.6rem; }
.eq-empty .big { font-family: "Fraunces", Georgia, "Times New Roman", serif; font-style: italic; font-size: 1.55rem; }
.eq-empty .small { color: var(--muted); font-size: .86rem; }
[data-testid="stChatMessage"] { background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 14px 18px; margin: 0 2% .7rem 0; line-height: 1.7; }
[data-testid="stChatMessage"]:has(.eq-user) { flex-direction: row-reverse; margin: 0 0 .7rem 2%; background: linear-gradient(135deg, rgba(242,166,90,.20), rgba(242,120,120,.12)); border-color: rgba(242,166,90,.30); }
[data-testid="stElementContainer"]:has(.eq-user), [data-testid="element-container"]:has(.eq-user) { display: none; }
[data-testid^="stChatMessageAvatar"] { background: rgba(255,255,255,.07); }
[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 55%, transparent); }
[data-testid="stChatInput"] { background: rgba(23,26,46,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 999px; }
[data-testid="stChatInput"]:focus-within { border-color: rgba(242,166,90,.7); box-shadow: 0 0 0 4px rgba(242,166,90,.12); }
[data-testid="stChatInput"] textarea { color: var(--text); }
[data-testid="stChatInput"] button { background: var(--amber); color: #1A1326; }
.stButton > button { border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel); color: var(--text); }
.stButton > button:hover { border-color: var(--amber); color: #FFD9A8; background: rgba(242,166,90,.08); }
section[data-testid="stSidebar"] { background: #12142A; }
.eq-side-title { font-family: "Fraunces", Georgia, "Times New Roman", serif; font-style: italic; font-size: 1.25rem; color: var(--amber); }
.eq-side-sub { color: var(--muted); font-size: .8rem; margin-bottom: 1rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
# ====== 密码门 ======
if not st.session_state.get("pwd_ok"):
    st.markdown("### 🔒 Equinox 安全验证")
    with st.form("gate"):
        pwd = st.text_input("请输入暗号进入：", type="password")
        submitted = st.form_submit_button("进入")
    if submitted:
        if hmac.compare_digest(pwd.encode(), str(PASSWORD).encode()):
            st.session_state.pwd_ok = True
            st.rerun()
        else:
            st.error("哼，暗号都不对，不让你进。")
    st.stop()

st.markdown(
    '<div class="eq-hero"><div class="eq-mark"></div><div>'
    '<div class="eq-title">Equinox<span class="eq-pill">Hash 1.0</span></div>'
    '<div class="eq-sub">昼夜平分 • Sol.调制</div></div></div>',
    unsafe_allow_html=True,
)

api_key = get_secret("ZHIPU_API_KEY")
if not api_key:
    st.error("请在 Secrets 配置 ZHIPU_API_KEY")
    st.stop()


# ====== 工具函数 ======
class ApiError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


@st.cache_resource
def get_session(key):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}"})
    s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=20))
    return s


def init_chat():
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.starters = random.sample(STARTER_POOL, 4)


def render_message(role, content):
    with st.chat_message(role, avatar=AVATARS[role]):
        if role == "user":
            st.markdown('<span class="eq-user"></span>', unsafe_allow_html=True)
        st.markdown(content)


def stream_response(messages):
    data = {"model": MODEL, "messages": messages, "stream": True, "temperature": 0.8}
    with get_session(api_key).post(API_URL, json=data, stream=True, timeout=(10, 60)) as res:
        if res.status_code != 200:
            raise ApiError(res.status_code)

        buf, last = [], time.monotonic()
        for raw in res.iter_lines(chunk_size=None):
            if not raw or not raw.startswith(b"data: "):
                continue
            payload = raw[6:]
            if payload == b"[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0]["delta"]
            except (ValueError, KeyError, IndexError):
                continue
            piece = delta.get("content")
            if not piece:
                continue
            buf.append(piece)
            now = time.monotonic()
            if now - last >= FLUSH_INTERVAL:
                yield "".join(buf)
                buf.clear()
                last = now
        if buf:
            yield "".join(buf)
# ====== 初始化 & 侧边栏 ======
if "messages" not in st.session_state:
    init_chat()

with st.sidebar:
    st.markdown(
        '<div class="eq-side-title">Equinox</div><div class="eq-side-sub">昼夜平分，嘴硬手软。</div>',
        unsafe_allow_html=True,
    )
    if st.button("🗑️  清空记忆", use_container_width=True):
        init_chat()
        st.rerun()
    st.caption(f"模型：{MODEL}")

# ====== 本轮输入 ======
prompt = st.chat_input("说点什么……")
if not prompt:
    prompt = st.session_state.pop("pending", None)

msgs = st.session_state.messages
history = msgs[1:]

# ====== 空状态 / 历史 ======
if not history and not prompt:
    st.markdown(
        '<div class="eq-empty"><div class="big">哼，来都来了。</div>'
        '<div class="small">想问什么就说吧——别指望我会客气。</div></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, text in enumerate(st.session_state.starters):
        cols[i % 2].button(
            text,
            key=f"btn_{i}",
            on_click=lambda t=text: st.session_state.update({"pending": t}),
            use_container_width=True,
        )

for m in history:
    render_message(m["role"], m["content"])

# ====== 处理新输入 ======
if prompt:
    msgs.append({"role": "user", "content": prompt})
    if len(msgs) > MAX_CONTEXT + 1:
        msgs[1:] = msgs[-MAX_CONTEXT:]

    render_message("user", prompt)
    full_reply = None
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        try:
            full_reply = st.write_stream(stream_response(msgs))
        except ApiError as e:
            if e.status in (400, 429):
                st.warning("哼，问得太快或者说了不该说的，系统让我闭麦了，等会再试。")
            elif e.status in (401, 403):
                st.error("API Key 有问题，检查一下 Secrets。")
            else:
                st.error(f"服务器抽风了（{e.status}），稍后再试。")
        except Exception:
            st.error("网线被老鼠咬断了，稍后再试。")

    if full_reply:
        msgs.append({"role": "assistant", "content": full_reply})
    else:
        msgs.pop()

# 底部免责声明
st.markdown(
    '<div style="text-align: center; color: #888888; font-size: 0.75rem; margin-top: 1rem;">'
    "Equinox 是 AI，她也可能会出错。</div>",
    unsafe_allow_html=True,
)