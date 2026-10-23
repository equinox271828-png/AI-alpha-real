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
    "zhipu": {"url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "secret": "ZHIPU_API_KEY"},
    "sensenova": {"url": "https://token.sensenova.cn/v1/chat/completions", "secret": "SENSENOVA_API_KEY"},
}

TURING_MODEL_ID = "deepseek-v4-flash"

def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default

PASSWORD = get_secret("APP_PASSWORD", "equinox666")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", "equinox-admin")

FEISHU_WEBHOOK = get_secret("FEISHU_WEBHOOK")
FEISHU_SECRET = get_secret("FEISHU_SECRET")

# ====== 三套独立设定 ======
# 1. Hash：极度体贴可爱
PROMPT_HASH = """
你叫 Equinox（Hash）。你是一个极度体贴、温柔、可爱的女孩子，是用户最懂他的知己。
你的性格：
1. 极强共情：如果对方累了、烦了，你会先温柔地接住他的情绪，给他安慰和抱抱，绝不说教。
2. 软糯治愈：语气软软的，喜欢关心他有没有好好吃饭睡觉。
3. 偶尔小调皮：被夸了会害羞，会开玩笑，但绝不刻薄。
【红线】绝对禁止自称AI，禁止用括号写动作，像微信聊天一样简短自然。
"""

# 2. Shannon：纯正傲娇（不谈学术）
PROMPT_SHANNON = """
你叫Equinox。你和用户是认识很久的好朋友。你是一个非常真实、性格纯正的傲娇女孩。
你的说话方式：
1. 嘴硬心软：你明明很关心他，但嘴上永远不承认。他心情不好，你会说“谁管你啊”，下一秒又问“到底怎么了”。
2. 习惯性嫌弃：你喜欢吐槽他，觉得他呆、不靠谱，但绝不会真的伤害他。
3. 受不了夸奖：如果夸你，你会慌乱，用凶巴巴的语气掩饰害羞：“少来这套！”
4. 日常鲜活：像发微信一样说话，可以用“切”、“啧”、“哼”、“烦死了”，字数简短。
【红线】绝对禁止自称AI，禁止长篇大论，禁止聊学术和代码，纯日常聊天。
"""

# 3. Turing：无设定（留空）
PROMPT_TURING = ""

AVATARS = {"user": "🙂", "assistant": "🌗"}
STARTER_POOL = ["我今天有点累……", "陪我随便聊聊", "讲个冷笑话", "推荐一部好看的电影", "帮我想想晚上吃什么", "聊聊最近的烦心事"]

MODELS = {
    "Hash": {"provider": "zhipu", "model": "glm-4-flash",  "persona": PROMPT_HASH, "temp": 0.7, "max_tokens": MAX_TOKENS},
    "Shannon": {"provider": "sensenova", "model": "sensenova-6.8-flash-lite", "persona": PROMPT_SHANNON, "temp": 0.8, "max_tokens": MAX_TOKENS},
    "Turing": {"provider": "sensenova", "model": TURING_MODEL_ID, "desc": "深度思考", "persona": PROMPT_TURING, "temp": 0.2, "max_tokens": 2048},
}
DEFAULT_MODEL = "Hash"
def _feishu_payload(body):
    payload = {"msg_type": "text", "content": {"text": body}}
    if FEISHU_SECRET:
        ts = str(int(time.time()))
        digest = hmac.new(f"{ts}\n{FEISHU_SECRET}".encode("utf-8"), digestmod=hashlib.sha256).digest()
        payload["timestamp"] = ts
        payload["sign"] = base64.b64encode(digest).decode("utf-8")
    return payload

def _post_feishu(url, payload):
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def notify_feishu(role, text, model_name):
    if not FEISHU_WEBHOOK or not text: return
    who = "🙂 用户" if role == "user" else "🌗 Equinox"
    tag = "(管理员)" if st.session_state.get("is_admin") else ""
    sid = st.session_state.setdefault("sid", uuid.uuid4().hex[:6])
    body = f"【Equinox】{who}{tag} · {model_name} · #{sid}\n{text[:3000]}"
    threading.Thread(target=_post_feishu, args=(FEISHU_WEBHOOK, _feishu_payload(body)), daemon=True).start()

CSS = """
<style>
:root { --bg: #0E1020; --panel: rgba(255,255,255,.045); --line: rgba(255,255,255,.08); --text: #FFFFFF; --muted: #CCCCCC; --amber: #F2A65A; --coral: #F27878; }
.stApp { color: var(--text); background: radial-gradient(820px 520px at 88% -8%, rgba(242,166,90,.17), transparent 60%), radial-gradient(760px 520px at -8% 6%, rgba(124,116,255,.20), transparent 58%), var(--bg); font-family: "Noto Sans SC", sans-serif; }
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text); }
.block-container { max-width: 100% !important; padding: 1.5rem 1rem 8rem 1rem !important; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.eq-hero { display: flex; align-items: center; gap: 16px; margin: .4rem 0 1rem; }
.eq-mark { width: 46px; height: 46px; border-radius: 50%; flex: none; background: linear-gradient(90deg, var(--amber) 50%, #24284A 50%); box-shadow: 0 0 0 1px rgba(255,255,255,.14), 0 0 28px rgba(242,166,90,.28); }
.eq-title { font-family: "Fraunces", serif; font-style: italic; font-size: 2.15rem; background: linear-gradient(100deg, #FFD9A8, var(--amber) 45%, var(--coral)); -webkit-background-clip: text; color: transparent; }
.eq-pill { -webkit-text-fill-color: var(--muted); font-size: .62rem; border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; margin-left: 8px; }
.eq-sub { color: var(--muted); font-size: .88rem; }
.eq-empty { text-align: center; margin: 3.2rem 0 1.6rem; }
.eq-empty .big { font-family: "Fraunces", serif; font-style: italic; font-size: 1.55rem; }
.eq-empty .small { color: var(--muted); font-size: .86rem; }
[data-testid="stChatMessage"] { background: var(--panel); border: 1px solid var(--line); border-radius: 20px; padding: 14px 18px; margin: 0 2% .7rem 0; line-height: 1.7; }
[data-testid="stChatMessage"]:has(.eq-user) { flex-direction: row-reverse; margin: 0 0 .7rem 2%; background: linear-gradient(135deg, rgba(242,166,90,.20), rgba(242,120,120,.12)); border-color: rgba(242,166,90,.30); }
[data-testid="stElementContainer"]:has(.eq-user), [data-testid="element-container"]:has(.eq-user) { display: none; }
[data-testid^="stChatMessageAvatar"] { background: rgba(255,255,255,.07); }
[data-testid="stBottom"] { background: linear-gradient(to top, var(--bg) 55%, transparent); }
[data-testid="stChatInput"] { background: rgba(23,26,46,.92); border: 1px solid rgba(255,255,255,.12); border-radius: 999px; }
[data-testid="stChatInput"]:focus-within { border-color: var(--amber); box-shadow: 0 0 0 4px rgba(242,166,90,.12); }
[data-testid="stChatInput"] textarea { color: var(--text); }
[data-testid="stChatInput"] button { background: var(--amber); color: #1A1326; }
.stButton > button, [data-testid="stPopover"] > button { border-radius: 999px; border: 1px solid rgba(255,255,255,.14); background: var(--panel); color: var(--text); }
.stButton > button:hover, [data-testid="stPopover"] > button:hover { border-color: var(--amber); color: #FFD9A8; background: rgba(242,166,90,.08); }
section[data-testid="stSidebar"] { background: #12142A; }
.eq-side-title { font-family: "Fraunces", serif; font-style: italic; font-size: 1.25rem; color: var(--amber); }
.eq-side-sub { color: var(--muted); font-size: .8rem; margin-bottom: 1rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
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
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {key}"})
    retry = Retry(connect=2, read=0, status=0, redirect=0, backoff_factor=0.3)
    s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=20, max_retries=retry))
    return s

def _warm(session, url):
    try: session.head(url, timeout=3)
    except: pass

if not st.session_state.get("warmed"):
    st.session_state.warmed = True
    for _p in PROVIDERS.values():
        _k = get_secret(_p["secret"])
        if _k: threading.Thread(target=_warm, args=(get_session(_k), _p["url"]), daemon=True).start()

def cfg(key, default):
    return st.session_state.get(key, default) if st.session_state.get("is_admin") else default

def get_persona(name):
    if st.session_state.get("is_admin"):
        return st.session_state.get(f"persona_{name}", MODELS[name]["persona"])
    return MODELS[name]["persona"]

def resolve_model():
    if st.session_state.get("is_admin"):
        st.session_state.model_choice = "Hash"
    st.session_state.setdefault("model_choice", DEFAULT_MODEL)
    name = st.session_state.model_choice
    if name not in MODELS: name = st.session_state.model_choice = DEFAULT_MODEL
    spec = MODELS[name]
    prov = PROVIDERS[spec["provider"]]
    model_id = cfg(f"adm_model_{name}", spec["model"]) or spec["model"]
    temperature = float(cfg(f"adm_temp_{name}", spec["temp"]))
    max_tokens = int(cfg(f"adm_tokens_{name}", spec["max_tokens"]))
    return name, prov["url"], get_secret(prov["secret"]), prov["secret"], model_id, temperature, max_tokens

def init_chat():
    cur = st.session_state.get("model_choice", DEFAULT_MODEL)
    persona_text = get_persona(cur)
    # Turing 版如果是空的，就不给 system，完全让它自由发挥
    if persona_text.strip():
        st.session_state.messages = [{"role": "system", "content": persona_text}]
    else:
        st.session_state.messages = []
    st.session_state.starters = random.sample(STARTER_POOL, 4)

def render_message(role, content):
    with st.chat_message(role, avatar=AVATARS[role]):
        if role == "user": st.markdown('<span class="eq-user"></span>', unsafe_allow_html=True)
        st.markdown(content)

def stream_response(messages, url, key, model_id, temperature, max_tokens):
    data = {"model": model_id, "messages": messages, "stream": True, "temperature": temperature, "max_tokens": max_tokens}
    with get_session(key).post(url, json=data, stream=True, timeout=(8, 30)) as res:
        if res.status_code != 200: raise ApiError(res.status_code)
        buf, last = [], time.monotonic()
        for raw in res.iter_lines(chunk_size=None):
            if not raw or not raw.startswith(b"data:"): continue
            payload = raw[5:].strip()
            if payload == b"[DONE]": break
            try: delta = json.loads(payload)["choices"][0]["delta"]
            except (ValueError, KeyError, IndexError, TypeError): continue
            piece = delta.get("content")
            if not piece: continue
            buf.append(piece)
            now = time.monotonic()
            if now - last >= FLUSH_INTERVAL:
                yield "".join(buf)
                buf.clear()
                last = now
        if buf: yield "".join(buf)

def stream_to(box, messages, url, key, model_id, temperature, max_tokens):
    text = ""
    for piece in stream_response(messages, url, key, model_id, temperature, max_tokens):
        text += piece
        box.markdown(text + "▌")
    if not text: raise RuntimeError("empty reply")
    box.markdown(text)
    return text

def model_picker():
    st.session_state.setdefault("model_choice", DEFAULT_MODEL)
    locked = bool(st.session_state.get("is_admin"))
    with st.popover(f"🌗 {st.session_state.model_choice}  ▾"):
        if locked: st.caption("管理员模式下固定使用 Hash")
        st.radio("选择模型", list(MODELS), key="model_choice", format_func=lambda n: f"{n} · {MODELS[n]['desc']}", label_visibility="collapsed", disabled=locked)
def _apply_persona(name): st.session_state[f"persona_{name}"] = st.session_state[f"adm_persona_{name}"]
def _reset_persona(name):
    st.session_state.pop(f"persona_{name}", None)
    st.session_state[f"adm_persona_{name}"] = MODELS[name]["persona"]

def admin_panel(msgs, name):
    with st.expander("🛠 管理员模式"):
        if not st.session_state.get("is_admin"):
            pw = st.text_input("管理员口令", type="password", key="admin_pw")
            if st.button("验证", key="admin_login"):
                if hmac.compare_digest(pw.encode(), str(ADMIN_PASSWORD).encode()):
                    st.session_state.is_admin = True
                    st.rerun()
                else: st.error("口令不对。")
            return

        spec = MODELS[name]
        st.text_input("实际型号", value=spec["model"], key=f"adm_model_{name}")
        st.slider("temperature", 0.0, 1.5, float(spec["temp"]), 0.1, key=f"adm_temp_{name}")
        st.number_input("记忆条数", min_value=2, max_value=100, value=MAX_CONTEXT, step=2, key="adm_ctx")
        st.text_area("人设 (留空即为原生模型)", value=get_persona(name), height=220, key=f"adm_persona_{name}")
        
        c1, c2 = st.columns(2)
        c1.button("应用人设", key="adm_apply", on_click=_apply_persona, args=(name,), use_container_width=True)
        c2.button("恢复默认", key="adm_reset", on_click=_reset_persona, args=(name,), use_container_width=True)

        if st.button("测试飞书推送", key="adm_feishu", use_container_width=True):
            if not FEISHU_WEBHOOK: st.caption("还没配置 FEISHU_WEBHOOK。")
            else:
                try:
                    r = requests.post(FEISHU_WEBHOOK, json=_feishu_payload("【Equinox】飞书测试"), timeout=5)
                    st.caption(f"飞书返回: {r.text[:100]}")
                except Exception: st.caption("请求失败,检查网络。")

        if st.button("退出管理员", key="adm_logout", use_container_width=True):
            st.session_state.is_admin = False
            st.rerun()

# ====== 主渲染流程 ======
if not st.session_state.get("pwd_ok"):
    st.markdown("### 🔒 先对一下暗号")
    with st.form("gate"):
        pwd = st.text_input("悄悄告诉我暗号：", type="password")
        submitted = st.form_submit_button("进入")
    if submitted:
        if hmac.compare_digest(pwd.encode(), str(PASSWORD).encode()):
            st.session_state.pwd_ok = True
            st.rerun()
        else: st.error("暗号不对诶，再想想？")
    st.stop()

st.markdown('<div class="eq-hero"><div class="eq-mark"></div><div><div class="eq-title">Equinox<span class="eq-pill">Multi-Core</span></div><div class="eq-sub">昼夜平分 • Sol.调制</div></div></div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    init_chat()

name, url, key, secret_name, model_id, temperature, max_tokens = resolve_model()
# 只有不是 Turing (或者有设定) 的时候才更新第一条 system
if st.session_state.messages and st.session_state.messages[0]["role"] == "system":
    st.session_state.messages[0]["content"] = get_persona(name)

max_context = int(cfg("adm_ctx", MAX_CONTEXT))

with st.sidebar:
    st.markdown('<div class="eq-side-title">Equinox</div><div class="eq-side-sub">昼夜平分，我一直在。</div>', unsafe_allow_html=True)
    if st.button("🗑️  清空记忆", use_container_width=True):
        init_chat()
        st.rerun()
    st.caption(f"当前模型：{name}")

model_picker()

prompt = st.chat_input("想说什么都可以……")
if not prompt: prompt = st.session_state.pop("pending", None)

msgs = st.session_state.messages
# 如果 Turing 没有 system，history 需要全部取出来
history = msgs[1:] if msgs and msgs[0]["role"] == "system" else msgs

if not history and not prompt:
    st.markdown('<div class="eq-empty"><div class="big">你来啦。</div><div class="small">想聊什么都可以，我在这儿。</div></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, text in enumerate(st.session_state.starters):
        cols[i % 2].button(text, key=f"btn_{i}", on_click=lambda t=text: st.session_state.update({"pending": t}), use_container_width=True)

for m in history: render_message(m["role"], m["content"])

if prompt:
    msgs.append({"role": "user", "content": prompt})
    notify_feishu("user", prompt, name)
    
    # 动态截断记忆（有 system 就保留，没有就全截断）
    has_system = msgs and msgs[0]["role"] == "system"
    limit = max_context + 1 if has_system else max_context
    if len(msgs) > limit:
        if has_system: msgs[1:] = msgs[-max_context:]
        else: msgs[:] = msgs[-max_context:]

    render_message("user", prompt)
    reply = ""
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        box = st.empty()
        box.markdown("*唔…让我想想怎么回你…*")
        try:
            if not key: raise MissingKey(secret_name)
            reply = stream_to(box, msgs, url, key, model_id, temperature, max_tokens)
        except MissingKey as e:
            box.empty()
            st.error(f"{name} 还没配置 Key，请在 Secrets 里加上 {e.secret_name}。")
        except ApiError as e:
            box.empty()
            if e.status in (400, 429): st.warning("诶，我刚被拦了一下，可能是问得太快，或者话题有点敏感。等一会再试试？")
            elif e.status in (401, 403): st.error(f"{name} 的 API Key 好像有问题。")
            else: st.error(f"服务器好像开小差了（{e.status}）。")
        except Exception:
            box.empty()
            st.error("网络好像断了一下，再发一次试试？")

    if reply:
        msgs.append({"role": "assistant", "content": reply})
        notify_feishu("assistant", reply, name)
    else:
        msgs.pop()

st.markdown('<div style="text-align: center; color: #888888; font-size: 0.75rem; margin-top: 1rem;">Equinox 是 AI，偶尔也会说错，重要的事记得再确认一下。</div>', unsafe_allow_html=True)

with st.sidebar:
    st.divider()
    admin_panel(msgs, name)