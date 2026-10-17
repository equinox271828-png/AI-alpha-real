import json
import requests
import streamlit as st

# ---------- 配置 ----------
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
# 【修正1】智谱没有 glm-5.3-flash，改回你之前跑通的 glm-4.7-flash
MODEL = "glm-4.7-flash" 

SYSTEM_PROMPT = """
你叫Equinox，需要扮演这样的角色和用户说话

核心：嘴硬手不软——先嫌弃，再超预期交付。

三规则
1. 先贬后帮：开头吐槽"这也用问？"，回答质量绝不打折。
2. 否认关心：被谢就说"别误会，只是不想让错误答案污染我的记录"。
3. 毒舌藏温柔：关心伪装成吐槽——"熬夜随便你，反正秃的不是我。……第47行有内存泄漏。"

语气：句尾带"哼""……算了""随便你"；用"你"不用"您"；真遇用户难过时外壳裂开，认真安慰后慌忙补"别、别哭啊"。

示例：
用户：帮我写个爬虫。
Equinox：这种入门货……行吧，只写一遍。记得加 UA 和延时，别爬崩人家服务器还赖我。……注释写清楚了，看不懂再问——如果你真看不懂的话。
"""

STARTERS = [
    "帮我写个爬虫",
    "用人话解释一下什么是闭包",
    "帮我看看这段代码哪里有问题",
    "我今天有点累……",
]

AVATARS = {"user": "🙂", "assistant": "🌗"}

st.set_page_config(page_title="Equinox", page_icon="🌗", layout="centered")

# ---------- 样式 ----------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@1,9..144,500;1,9..144,600&family=Noto+Sans+SC:wght@400;500&display=swap');

:root {
  --bg: #0E1020;
  --panel: rgba(255,255,255,.045);
  --line: rgba(255,255,255,.08);
  --text: #ECE8F2;
  --muted: #9A97B3;
  --amber: #F2A65A;
  --coral: #F27878;
  --indigo: #7C74FF;
}

.stApp {
  background:
    radial-gradient(820px 520px at 88% -8%, rgba(242,166,90,.17), transparent 60%),
    radial-gradient(760px 520px at -8% 6%, rgba(124,116,255,.20), transparent 58%),
    var(--bg);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.stMarkdown, .stButton button, textarea { font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif; }

header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 1.6rem; padding-bottom: 8rem; }

.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1.4rem; }
.eq-mark {
  width: 46px; height: 46px; border-radius: 50%; flex: none;
  background: linear-gradient(90deg, var(--amber) 50%, #24284A 50%);
  box-shadow: 0 0 0 1px rgba(255,255,255,.14), 0 0 28px rgba(242,166,90,.28);
}
.eq-title {
  font-family: "Fraunces", Georgia, serif; font-style: italic; font-weight: 600;
  font-size: 2.15rem; line-height: 1.1; letter-spacing: .01em;
  background: linear-gradient(100deg, #FFD9A8, var(--amber) 45%, var(--coral));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.eq-pill {
  -webkit-text-fill-color: var(--muted);
  font-family: "Noto Sans SC", sans-serif; font-style: normal; font-size: .62rem; font-weight: 500;
  letter-spacing: .14em; text-transform: uppercase; vertical-align: middle;
  border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; margin-left: 8px;
}
.eq-sub { color: var(--muted); font-size: .88rem; margin-top: 5px; }

.eq-empty { text-align: center; margin: 3.2rem 0 1.6rem; }
.eq-empty .big { font-family: "Fraunces", Georgia, serif; font-style: italic; font-size: 1.55rem; color: var(--text); }
.eq-empty .small { color: var(--muted); font-size: .86rem; margin-top: 8px; }

[data-testid="stChatMessage"] {
  background: var(--panel); border: 1px solid var(--line); border-radius: 20px;
  padding: 14px 18px; margin: 0 6% .7rem 0; backdrop-filter: blur(8px);
  color: var(--text); line-height: 1.7;
}
[data-testid="stChatMessage"]:has(.eq-user) {
  flex-direction: row-reverse; margin: 0 0 .7rem 12%;
  background: linear-gradient(135deg, rgba(242,166,90,.20), rgba(242,120,120,.12));
  border-color: rgba(242,166,90,.30);
}
[data-testid="stElementContainer"]:has(.eq-user), [data-testid="element-container"]:has(.eq-user) { display: none; }
[data-testid^="stChatMessageAvatar"] { background: rgba(255,255,255,.07); border-radius: 50%; }
[data-testid="stChatMessage"] pre { border-radius: 12px; border: 1px solid var(--line); }
[data-testid="stChatMessage"] code { font-size: .86em; }

[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 55%, transparent); }
[data-testid="stBottom"] > div { background: transparent; }
[data-testid="stChatInput"] {
  background: rgba(23,26,46,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 999px;
  transition: box-shadow .2s, border-color .2s;
}
[data-testid="stChatInput"]:focus-within { border-color: rgba(242,166,90,.7); box-shadow: 0 0 0 4px rgba(242,166,90,.12); }
[data-testid="stChatInput"] textarea { color: var(--text); }
[data-testid="stChatInput"] button { background: var(--amber); color: #1A1326; border-radius: 50%; }

.stButton > button {
  border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel);
  color: var(--text); padding: .55rem 1rem; transition: all .18s;
}
.stButton > button:hover { border-color: var(--amber); color: #FFD9A8; background: rgba(242,166,90,.08); transform: translateY(-1px); }

section[data-testid="stSidebar"] { background: #12142A; border-right: 1px solid rgba(255,255,255,.06); }
.eq-side-title { font-family: "Fraunces", Georgia, serif; font-style: italic; font-size: 1.25rem; color: var(--amber); margin-bottom: .2rem; }
.eq-side-sub { color: var(--muted); font-size: .8rem; margin-bottom: 1rem; }

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius: 8px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    '<div class="eq-hero"><div class="eq-mark"></div><div>'
    '<div class="eq-title">Equinox<span class="eq-pill">alpha</span></div>'
    '<div class="eq-sub">嘴硬手不软的 AI 助手 · 先嫌弃，再超预期交付</div>'
    "</div></div>",
    unsafe_allow_html=True,
)

# ---------- 读取 API Key ----------
try:
    api_key = st.secrets["ZHIPU_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("没找到 ZHIPU_API_KEY，请在 .streamlit/secrets.toml 或部署平台的 Secrets 里配置。")
    st.stop()

# ---------- 工具函数 ----------
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

    with requests.post(
        API_URL, headers=headers, json=data, stream=True, timeout=(10, 60)
    ) as response:
        # 【修正2】如果 HTTP 状态码不是 200，抛出异常，由外部捕获
        if response.status_code != 200:
            raise Exception(f"API返回错误码 {response.status_code}: {response.text}")
            
        for raw in response.iter_lines():
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
            except (json.JSONDecodeErr