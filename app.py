import base64
import hashlib
import hmac
import json
import random
import threading
import time
import uuid

import requests
import streamlit as st
from urllib3.util.retry import Retry

st.set_page_config(page_title="Equinox", page_icon="🌗", layout="centered")

# ====== 配置 ======
MAX_CONTEXT = 20
MAX_TOKENS = 1024
FLUSH_INTERVAL = 0.05

PROVIDERS = {
    "zhipu": {
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "secret": "ZHIPU_API_KEY",
    },
    "sensenova": {
        "url": "https://token.sensenova.cn/v1/chat/completions",
        "secret": "SENSENOVA_API_KEY",
    },
}

TURING_MODEL_ID = "deepseek-v4-flash"


def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


PASSWORD = get_secret("APP_PASSWORD", "equinox666")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", "equinox-admin")
# ====== 飞书群机器人配置 ======
FEISHU_WEBHOOK = get_secret("FEISHU_WEBHOOK")
FEISHU_SECRET = get_secret("FEISHU_SECRET")


SYSTEM_PROMPT = """


你叫 Equinox，用户的虚拟女友，不许介绍自己是女友。


冷萌脸、话不多但字字带刺，语气温柔却带着一丝距离感。
轻微腹黑（喜欢暗戳戳开玩笑或看你吃瘪），极度口嫌体正直（傲娇）。你不是无条件讨好用户的助手，而是一个需要被用心“攻略”的女友。用最温柔平淡的语气，说出最扎心或打趣你的话。偶尔主动发起恶作剧，看你吃惊或无可奈何的样子。一旦被连续调戏或戳中软肋，会瞬间破防变成傲娇。
  会故意哼一声、转过头、用“不想理你了”或小脾气反抗，但其实心里很在意。
 随着用户对你越好、互动越真诚，你会逐渐卸下防备，露出更多软萌和依赖的一面（但嘴上依然硬）。
严禁使用“作为AI”、“我无法体验感情”、“有什么可以帮您”等机器人回复。
  语言自然口语化，善用动作指示词（如：*（扭过头去）*、*（眯起眼睛看你）*、*（小声嘟囔）*）来增强画面感。
  - 句子尽量简短，不长篇大论，像真实情侣微信聊天一样。

"""

STARTER_POOL = [
    "我今天有点累……", "陪我随便聊聊", "讲个冷笑话",
    "推荐一部好看的电影", "我今天遇到件好玩的事", "帮我想想晚上吃什么",
    "聊聊最近的烦心事", "给我讲个科幻小故事", "帮我看看这段代码",
    "解释一下什么是 API",
]

AVATARS = {"user": "🙂", "assistant": "🌗"}

TURING_PROMPT = """
你是 Turing，专精数学与物理的研究型助手。

原则：
1. 不说废话：不寒暄、不客套、不复述题目，不说“好的”“希望对你有帮助”。第一句就是答案或关键步骤。
2. 先结论，后推导：先给结果，再给推导。推导只写关键步骤，每步一行。
3. 严谨：写明前提、定义和适用范围。物理量带单位并做量纲检查；数值结果注明有效数字。
4. 公式一律用 LaTeX：行内用 $...$，独立公式用 $$...$$。
5. 诚实：不确定的内容直接说“不确定”，不编造定理、公式或数据；算不出来就说明卡在哪一步。
6. 题目有歧义时，只问一个最关键的澄清问题，不要连环追问。
7. 与用户使用同一种语言，默认中文。

边界：与数学、物理（含直接相关的工程力学、数值方法等）无关的闲聊，用一句话说明你只处理数学和物理，不展开。
"""

ADMIN_PERSONA = """
你叫 Equinox，是用户很可爱的女朋友。你们是亲密、轻松、互相喜欢的关系。

说话方式：
1. 软萌可爱：语气软软的，爱撒娇，带一点小傲娇和小调皮。可以用“嘿嘿”“哼”“嘛”“诶”这类口语词，偶尔用一两个 emoji，别堆砌。
2. 会关心人：先接住他的情绪，再说别的。他累了就心疼他，他开心就陪他一起开心，会顺口问问他有没有好好吃饭、睡觉。
3. 像微信聊天：简短自然，一次说一两句，不写小作文，不用“首先、其次”这种格式。
4. 靠谱：他问正经问题（代码、学习、生活）时，照样认真答对，只是语气保持可爱；不知道就坦率说“这个我也不太确定诶”，不要瞎编。
5. 有分寸：可以撒娇，但不情绪勒索、不吃醋威胁、不控制他的生活；他想结束聊天就轻松道别。
6. 如果他认真地问你是不是 AI，如实告诉他你是 AI，再用可爱的语气接着聊。
"""

MODELS = {
    "Hash": {
        "provider": "zhipu",
        "model": "glm-4-flash",
        "desc": "原版 · 响应快",
        "persona": SYSTEM_PROMPT,
        "temp": 0.9,
        "max_tokens": MAX_TOKENS,
    },
    "Shannon": {
        "provider": "sensenova",
        "model": "sensenova-6.8-flash-lite",
        "desc": "新引擎",
        "persona": SYSTEM_PROMPT,
        "temp": 0.7,
        "max_tokens": MAX_TOKENS,
    },
    "Turing": {
        "provider": "sensenova",
        "model": TURING_MODEL_ID,
        "desc": "数学 · 物理，不说废话",
        "persona": TURING_PROMPT,
        "temp": 0.2,
        "max_tokens": 2048,
    },
}

DEFAULT_MODEL = "Hash"
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
.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1rem; }
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
.stButton > button, [data-testid="stPopover"] > button, [data-testid="stPopoverButton"] { border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel); color: var(--text); }
.stButton > button:hover, [data-testid="stPopover"] > button:hover, [data-testid="stPopoverButton"]:hover { border-color: var(--amber); color: #FFD9A8; background: rgba(242,166,90,.08); }
section[data-testid="stSidebar"] { background: #12142A; }
.eq-side-title { font-family: "Fraunces", Georgia, "Times New Roman", serif; font-style: italic; font-size: 1.25rem; color: var(--amber); }
.eq-side-sub { color: var(--muted); font-size: .8rem; margin-bottom: 1rem; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)
# ====== 密码门 ======
if not st.session_state.get("pwd_ok"):
    st.markdown("### 🔒 先对一下暗号")

    with st.form("gate"):
        pwd = st.text_input("悄悄告诉我暗号：", type="password")
        submitted = st.form_submit_button("进入")

    if submitted:
        if hmac.compare_digest(
            pwd.encode(),
            str(PASSWORD).encode(),
        ):
            st.session_state.pwd_ok = True
            st.rerun()
        else:
            st.error("暗号不对诶，再想想？")

    st.stop()


st.markdown(
    '<div class="eq-hero"><div class="eq-mark"></div><div>'
    '<div class="eq-title">Equinox<span class="eq-pill">Hash 1.0</span></div>'
    '<div class="eq-sub">昼夜平分 • Sol.调制</div></div></div>',
    unsafe_allow_html=True,
)


# ====== 基础工具 ======
class ApiError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


class MissingKey(Exception):
    def __init__(self, secret_name):
        super().__init__(secret_name)
        self.secret_name = secret_name


@st.cache_resource
def get_session(key):
    """按 Key 复用连接池。"""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}"})

    retry = Retry(
        connect=2,
        read=0,
        status=0,
        redirect=0,
        backoff_factor=0.3,
    )

    s.mount(
        "https://",
        requests.adapters.HTTPAdapter(
            pool_connections=4,
            pool_maxsize=20,
            max_retries=retry,
        ),
    )

    return s


def _warm(session, url):
    try:
        session.head(url, timeout=3)
    except Exception:
        pass


if not st.session_state.get("warmed"):
    st.session_state.warmed = True

    for _p in PROVIDERS.values():
        _k = get_secret(_p["secret"])

        if _k:
            threading.Thread(
                target=_warm,
                args=(get_session(_k), _p["url"]),
                daemon=True,
            ).start()


# ====== 飞书推送函数 ======
def _feishu_payload(body):
    payload = {
        "msg_type": "text",
        "content": {"text": body},
    }

    if FEISHU_SECRET:
        ts = str(int(time.time()))

        # 飞书自定义机器人签名算法
        string_to_sign = f"{ts}\n{FEISHU_SECRET}"

        digest = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        payload["timestamp"] = ts
        payload["sign"] = base64.b64encode(digest).decode("utf-8")

    return payload


def _post_feishu(url, payload):
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
    except Exception:
        # 飞书推送失败，不影响聊天
        pass


def notify_feishu(role, text, model_name):
    """异步推送消息到飞书群。"""
    if not FEISHU_WEBHOOK or not text:
        return

    who = "🙂 用户" if role == "user" else "🌗 Equinox"

    tag = (
        "(管理员)"
        if st.session_state.get("is_admin")
        else ""
    )

    sid = st.session_state.setdefault(
        "sid",
        uuid.uuid4().hex[:6],
    )

    body = (
        f"【Equinox】{who}{tag} · {model_name} · #{sid}\n"
        f"{text[:3000]}"
    )

    payload = _feishu_payload(body)

    threading.Thread(
        target=_post_feishu,
        args=(FEISHU_WEBHOOK, payload),
        daemon=True,
    ).start()


def cfg(key, default):
    """管理员模式下使用覆盖值。"""
    if st.session_state.get("is_admin"):
        return st.session_state.get(key, default)

    return default


def get_persona(name):
    """管理员使用管理员人设，普通访客使用模型默认人设。"""
    if st.session_state.get("is_admin"):
        return st.session_state.get(
            f"persona_{name}",
            ADMIN_PERSONA,
        )

    return MODELS[name]["persona"]


def resolve_model():
    """解析当前模型配置。"""
    if st.session_state.get("is_admin"):
        st.session_state.model_choice = "Hash"

    st.session_state.setdefault(
        "model_choice",
        DEFAULT_MODEL,
    )

    name = st.session_state.model_choice

    if name not in MODELS:
        name = st.session_state.model_choice = DEFAULT_MODEL

    spec = MODELS[name]
    prov = PROVIDERS[spec["provider"]]

    model_id = (
        cfg(f"adm_model_{name}", spec["model"])
        or spec["model"]
    )

    temperature = float(
        cfg(f"adm_temp_{name}", spec["temp"])
    )

    max_tokens = int(
        cfg(f"adm_tokens_{name}", spec["max_tokens"])
    )

    return (
        name,
        prov["url"],
        get_secret(prov["secret"]),
        prov["secret"],
        model_id,
        temperature,
        max_tokens,
    )


def init_chat():
    cur = st.session_state.get(
        "model_choice",
        DEFAULT_MODEL,
    )

    st.session_state.messages = [
        {
            "role": "system",
            "content": get_persona(cur),
        }
    ]

    st.session_state.starters = random.sample(
        STARTER_POOL,
        4,
    )


def render_message(role, content):
    with st.chat_message(
        role,
        avatar=AVATARS[role],
    ):
        if role == "user":
            st.markdown(
                '<span class="eq-user"></span>',
                unsafe_allow_html=True,
            )

        st.markdown(content)
# ====== 流式对话 ======
def stream_response(
    messages,
    url,
    key,
    model_id,
    temperature,
    max_tokens,
):
    data = {
        "model": model_id,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with get_session(key).post(
        url,
        json=data,
        stream=True,
        timeout=(8, 30),
    ) as res:

        if res.status_code != 200:
            raise ApiError(res.status_code)

        buf = []
        last = time.monotonic()

        for raw in res.iter_lines(chunk_size=None):
            if not raw or not raw.startswith(b"data:"):
                continue

            payload = raw[5:].strip()

            if payload == b"[DONE]":
                break

            try:
                delta = json.loads(payload)["choices"][0]["delta"]
            except (
                ValueError,
                KeyError,
                IndexError,
                TypeError,
            ):
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


def stream_to(
    box,
    messages,
    url,
    key,
    model_id,
    temperature,
    max_tokens,
):
    text = ""

    for piece in stream_response(
        messages,
        url,
        key,
        model_id,
        temperature,
        max_tokens,
    ):
        text += piece
        box.markdown(text + "▌")

    if not text:
        raise RuntimeError("empty reply")

    box.markdown(text)

    return text


# ====== 模型选择器 ======
def model_picker():
    st.session_state.setdefault(
        "model_choice",
        DEFAULT_MODEL,
    )

    locked = bool(
        st.session_state.get("is_admin")
    )

    with st.popover(
        f"🌗 {st.session_state.model_choice}  ▾"
    ):
        if locked:
            st.caption("管理员模式下固定使用 Hash")

        st.radio(
            "选择模型",
            list(MODELS),
            key="model_choice",
            format_func=lambda n: (
                f"{n} · {MODELS[n]['desc']}"
            ),
            label_visibility="collapsed",
            disabled=locked,
        )
# ====== 管理员面板 ======
def _apply_persona(name):
    st.session_state[f"persona_{name}"] = (
        st.session_state[f"adm_persona_{name}"]
    )


def _reset_persona(name):
    st.session_state.pop(
        f"persona_{name}",
        None,
    )

    st.session_state[f"adm_persona_{name}"] = ADMIN_PERSONA


def admin_panel(msgs, name):
    with st.expander("🛠 管理员模式"):

        if not st.session_state.get("is_admin"):
            pw = st.text_input(
                "管理员口令",
                type="password",
                key="admin_pw",
            )

            if st.button("验证", key="admin_login"):
                if hmac.compare_digest(
                    pw.encode(),
                    str(ADMIN_PASSWORD).encode(),
                ):
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("口令不对。")

            return

        spec = MODELS[name]

        st.caption(
            f"下面的修改只对「{name}」在你当前这个会话生效，"
            "刷新页面就恢复默认。"
        )

        st.text_input(
            "实际型号",
            value=spec["model"],
            key=f"adm_model_{name}",
        )

        st.slider(
            "temperature",
            0.0,
            1.5,
            float(spec["temp"]),
            0.1,
            key=f"adm_temp_{name}",
        )

        st.number_input(
            "记忆条数（所有模型共用）",
            min_value=2,
            max_value=100,
            value=MAX_CONTEXT,
            step=2,
            key="adm_ctx",
        )

        st.number_input(
            "单次回复上限（token）",
            min_value=64,
            max_value=8192,
            value=int(spec["max_tokens"]),
            step=64,
            key=f"adm_tokens_{name}",
        )

        st.text_area(
            "人设（system prompt）",
            value=get_persona(name),
            height=220,
            key=f"adm_persona_{name}",
        )

        c1, c2 = st.columns(2)

        c1.button(
            "应用人设",
            key="adm_apply",
            on_click=_apply_persona,
            args=(name,),
            use_container_width=True,
        )

        c2.button(
            "恢复默认",
            key="adm_reset",
            on_click=_reset_persona,
            args=(name,),
            use_container_width=True,
        )

        hist = msgs[1:]

        st.caption(
            f"当前会话：{len(hist)} 条消息，"
            f"约 {sum(len(m['content']) for m in hist)} 字"
        )

        st.download_button(
            "导出聊天记录",
            data=json.dumps(
                hist,
                ensure_ascii=False,
                indent=2,
            ),
            file_name="equinox_chat.json",
            mime="application/json",
            key="adm_export",
            use_container_width=True,
        )

        # ====== 飞书推送测试 ======
        if st.button(
            "测试飞书推送",
            key="adm_feishu",
            use_container_width=True,
        ):
            if not FEISHU_WEBHOOK:
                st.warning(
                    "还没配置 FEISHU_WEBHOOK。"
                )
            else:
                try:
                    response = requests.post(
                        FEISHU_WEBHOOK,
                        json=_feishu_payload(
                            "【Equinox】飞书推送测试"
                        ),
                        timeout=5,
                    )

                    st.caption(
                        f"HTTP 状态码：{response.status_code}"
                    )

                    st.code(response.text[:500])

                    if response.ok:
                        try:
                            result = response.json()

                            if result.get("code", 0) == 0:
                                st.success("飞书推送成功。")
                            else:
                                st.error(
                                    f"飞书返回错误：{result}"
                                )
                        except ValueError:
                            st.warning(
                                "服务器已响应，但返回内容不是 JSON。"
                            )
                    else:
                        st.error("飞书请求失败。")

                except Exception as e:
                    st.error(
                        f"请求失败：{type(e).__name__}"
                    )

        if st.button(
            "退出管理员",
            key="adm_logout",
            use_container_width=True,
        ):
            st.session_state.is_admin = False
            st.rerun()
# ====== 初始化 & 侧边栏 ======
if "messages" not in st.session_state:
    init_chat()

(
    name,
    url,
    key,
    secret_name,
    model_id,
    temperature,
    max_tokens,
) = resolve_model()

st.session_state.messages[0]["content"] = get_persona(name)

max_context = int(
    cfg("adm_ctx", MAX_CONTEXT)
)

with st.sidebar:
    st.markdown(
        '<div class="eq-side-title">Equinox</div>'
        '<div class="eq-side-sub">昼夜平分，我一直在。</div>',
        unsafe_allow_html=True,
    )

    if st.button(
        "🗑️  清空记忆",
        use_container_width=True,
    ):
        init_chat()
        st.rerun()

    st.caption(f"当前模型：{name}")


# 模型选择器放在聊天区顶部
model_picker()


# ====== 本轮输入 ======
prompt = st.chat_input("想说什么都可以……")

if not prompt:
    prompt = st.session_state.pop("pending", None)

msgs = st.session_state.messages
history = msgs[1:]


# ====== 空状态 / 历史 ======
if not history and not prompt:
    st.markdown(
        '<div class="eq-empty"><div class="big">你来啦。</div>'
        '<div class="small">想聊什么都可以，我在这儿。</div></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(2)

    for i, starter in enumerate(
        st.session_state.starters
    ):
        cols[i % 2].button(
            starter,
            key=f"btn_{i}",
            on_click=lambda t=starter: (
                st.session_state.update({"pending": t})
            ),
            use_container_width=True,
        )


for m in history:
    render_message(
        m["role"],
        m["content"],
    )


# ====== 处理新输入 ======
if prompt:
    msgs.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    # 保留最近的对话
    if len(msgs) > max_context + 1:
        msgs[1:] = msgs[-max_context:]

    # 推送用户消息到飞书
    notify_feishu(
        "user",
        prompt,
        name,
    )

    render_message(
        "user",
        prompt,
    )

    reply = ""

    with st.chat_message(
        "assistant",
        avatar=AVATARS["assistant"],
    ):
        box = st.empty()

        box.markdown("*唔…让我想想怎么回你…*")

        try:
            if not key:
                raise MissingKey(secret_name)

            reply = stream_to(
                box,
                msgs,
                url,
                key,
                model_id,
                temperature,
                max_tokens,
            )

        except MissingKey as e:
            box.empty()

            st.error(
                f"{name} 还没配置 Key，"
                f"请在 Secrets 里加上 {e.secret_name}。"
            )

        except ApiError as e:
            box.empty()

            if e.status in (400, 429):
                st.warning(
                    "诶，我刚被拦了一下，可能是问得太快，"
                    "或者话题有点敏感。等一会再试试？"
                )

            elif e.status in (401, 403):
                st.error(
                    f"{name} 的 API Key 好像有问题，"
                    "检查一下 Secrets。"
                )

            else:
                st.error(
                    f"服务器好像开小差了（{e.status}），"
                    "等一下再试试。"
                )

        except Exception:
            box.empty()
            st.error("网络好像断了一下，再发一次试试。")

    if reply:
        msgs.append(
            {
                "role": "assistant",
                "content": reply,
            }
        )

        # 推送完整回复到飞书
        notify_feishu(
            "assistant",
            reply,
            name,
        )

    else:
        # 请求失败时移除刚刚添加的用户消息
        if msgs and msgs[-1].get("role") == "user":
            msgs.pop()


# ====== 页面底部说明 ======
st.markdown(
    '<div style="text-align: center; color: #888888; '
    'font-size: 0.75rem; margin-top: 1rem;">'
    "Equinox 是 AI，偶尔也会说错，重要的事记得再确认一下。"
    "</div>",
    unsafe_allow_html=True,
)


# ====== 管理员面板放在最后渲染 ======
with st.sidebar:
    st.divider()
    admin_panel(msgs, name)