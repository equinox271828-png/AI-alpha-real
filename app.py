import base64
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Equinox", page_icon="🌗", layout="wide",
    initial_sidebar_state="collapsed",
)

# ====== 读取 Secrets ======
def plain(x):
    """把 st.secrets 里的嵌套对象转成普通 dict/list。"""
    if hasattr(x, "items"):
        return {k: plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(i) for i in x]
    return x


def secret(name, default=None):
    try:
        return plain(st.secrets[name])
    except Exception:
        return default


USERS = {str(k): str(v) for k, v in (secret("users", {}) or {}).items()}
USERS_L = {k.lower(): k for k in USERS}          # 登录时不区分大小写
ADMIN_USERS = set(secret("ADMIN_USERS", []) or [])
UNLIMITED_USERS = set(secret("UNLIMITED_USERS", []) or []) | ADMIN_USERS
DAILY_TOKEN_LIMIT = int(secret("DAILY_TOKEN_LIMIT", 8192))
MAX_CONTEXT = int(secret("MAX_CONTEXT", 20))
SYSTEM_PROMPT = str(secret("SYSTEM_PROMPT", "") or "")   # 人设空位

RELAY_BASE_URL = str(secret("RELAY_BASE_URL", "") or "").rstrip("/")
RELAY_API_KEY = secret("RELAY_API_KEY")

FEISHU_WEBHOOK = secret("FEISHU_WEBHOOK")
FEISHU_SECRET = secret("FEISHU_SECRET")

_sb = secret("supabase", {}) or {}
SB_URL = str(_sb.get("url", "")).rstrip("/")
SB_KEY = _sb.get("key", "")

# 模型表：全部来自 Secrets 的 [[models]]
MODELS = []
for _m in secret("models", []) or []:
    if _m.get("name") and _m.get("id"):
        MODELS.append({
            "name": str(_m["name"]),
            "id": str(_m["id"]),
            "limited": bool(_m.get("limited", False)),
            "temp": float(_m.get("temp", 0.7)),
            "max_tokens": int(_m.get("max_tokens", 2048)),
            "desc": str(_m.get("desc", "")),
        })
MODEL_MAP = {m["name"]: m for m in MODELS}

TZ = timezone(timedelta(hours=8))   # 额度按北京时间每天 0 点重置


def chat_url():
    """中转站地址：填到 /v1 为止即可，会自动补 /chat/completions。"""
    if RELAY_BASE_URL.endswith("/chat/completions"):
        return RELAY_BASE_URL
    return RELAY_BASE_URL + "/chat/completions"


def est_tokens(s):
    """粗略估算 token：汉字约 1 字 1 token，其他约 4 字符 1 token。"""
    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    return cjk + (len(s) - cjk) // 4 + 1


@st.cache_resource
def get_jobs():
    """跨会话共享的生成任务表：{job_id: {...}}。"""
    return {}
# ====== Supabase（REST 接口） ======
def sb_ok():
    return bool(SB_URL and SB_KEY)


def sb(method, table, params=None, body=None):
    r = requests.request(
        method, f"{SB_URL}/rest/v1/{table}", params=params, json=body, timeout=8,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    r.raise_for_status()
    return r.json() if method == "GET" else None


def today_start():
    return datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def db_sessions(user):
    """历史对话列表：按最近活跃排序，标题取每个会话的第一句话。"""
    rows = sb("GET", "chats", {
        "username": f"eq.{user}", "role": "eq.user",
        "select": "session_id,content,created_at",
        "order": "created_at.desc", "limit": "300",
    })
    seen = {}
    for r in rows:
        sid = r["session_id"]
        if sid not in seen:                 # 倒序遍历，第一次见到的是最新
            seen[sid] = {"id": sid, "title": ""}
        seen[sid]["title"] = r["content"].strip().replace("\n", " ")[:30]  # 不断覆盖，最终是最早一句
    return list(seen.values())


def db_load(user, sid):
    rows = sb("GET", "chats", {
        "username": f"eq.{user}", "session_id": f"eq.{sid}",
        "select": "role,content,model", "order": "created_at.asc,id.asc", "limit": "500",
    })
    return [{"role": r["role"], "content": r["content"], "model": r.get("model") or ""} for r in rows]


def db_delete(user, sid):
    sb("DELETE", "chats", {"username": f"eq.{user}", "session_id": f"eq.{sid}"})


def db_used(user):
    """今天已用的「受限模型」token 数。"""
    rows = sb("GET", "chats", {
        "username": f"eq.{user}", "created_at": f"gte.{today_start()}",
        "select": "model,tokens", "limit": "5000",
    })
    limited = {m["name"] for m in MODELS if m["limited"]}
    return sum(int(r.get("tokens") or 0) for r in rows if r.get("model") in limited)


def db_overview():
    """管理员用：所有人今天的用量。"""
    rows = sb("GET", "chats", {
        "created_at": f"gte.{today_start()}",
        "select": "username,role,model,tokens", "limit": "10000",
    })
    limited = {m["name"] for m in MODELS if m["limited"]}
    agg = {u: {"user": u, "asks": 0, "limited": 0, "total": 0} for u in USERS}
    for r in rows:
        a = agg.setdefault(r["username"], {"user": r["username"], "asks": 0, "limited": 0, "total": 0})
        tk = int(r.get("tokens") or 0)
        a["total"] += tk
        if r.get("role") == "user":
            a["asks"] += 1
        if r.get("model") in limited:
            a["limited"] += tk
    for a in agg.values():
        a["limit"] = "∞" if a["user"] in UNLIMITED_USERS else DAILY_TOKEN_LIMIT
    return list(agg.values())


# ====== 飞书推送 ======
def feishu_payload(body):
    payload = {"msg_type": "text", "content": {"text": body}}
    if FEISHU_SECRET:
        ts = str(int(time.time()))
        digest = hmac.new(f"{ts}\n{FEISHU_SECRET}".encode(), digestmod=hashlib.sha256).digest()
        payload["timestamp"] = ts
        payload["sign"] = base64.b64encode(digest).decode()
    return payload


def _post_feishu(payload):
    try:
        requests.post(FEISHU_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass   # 推送失败不影响聊天


def notify_feishu(role, text, model, user, sid):
    """异步推送，不用 session_state，后台线程里也能调。"""
    if not FEISHU_WEBHOOK or not text:
        return
    who = f"🙂 {user}" if role == "user" else "🌗 Equinox"
    body = f"【Equinox】{who} · {model} · #{sid[:6]}\n{text[:3000]}"
    threading.Thread(target=_post_feishu, args=(feishu_payload(body),), daemon=True).start()
# ====== 调用模型（后台线程，流式） ======
class ApiError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


def api_error_text(status):
    if status in (401, 403):
        return "中转站 Key 无效或没权限，请检查 Secrets。"
    if status == 404:
        return "找不到这个模型，请检查 Secrets 里该模型的 id。"
    if status == 400:
        return "请求被拒绝（400），可能是型号名不对，或内容被拦截。"
    if status == 429:
        return "请求太频繁，或中转站余额不足，稍后再试。"
    return f"服务器开小差了（{status}），稍后再试。"


def run_job(job, url, key, body_base, meta):
    """
    后台线程：边读模型的流式输出边写进 job["text"]，前端轮询读取。
    结束后自己存档到 Supabase、推送飞书，所以用户关掉网页也不丢。
    注意：线程里不能碰 st.session_state。
    """
    usage = None
    try:
        for attempt in (0, 1):
            body = dict(body_base)
            if attempt == 0:
                body["stream_options"] = {"include_usage": True}   # 让中转站返回真实 token 用量
            with requests.post(
                url, headers={"Authorization": f"Bearer {key}"},
                json=body, stream=True, timeout=(8, 90),
            ) as res:
                if res.status_code == 400 and attempt == 0:
                    continue        # 个别中转站不认 stream_options，去掉重试一次
                if res.status_code != 200:
                    raise ApiError(res.status_code)
                for raw in res.iter_lines(chunk_size=None):
                    if job["stop"]:
                        break
                    if not raw or not raw.startswith(b"data:"):
                        continue
                    payload = raw[5:].strip()
                    if payload == b"[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except ValueError:
                        continue
                    if obj.get("usage"):
                        usage = obj["usage"]
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    piece = (choices[0].get("delta") or {}).get("content")
                    if piece:
                        job["text"] += piece
            break
    except ApiError as e:
        job["error"] = api_error_text(e.status)
    except Exception:
        job["error"] = "网络好像断了一下，再发一次试试。"
    finally:
        text = job["text"]
        if text:
            tk = int((usage or {}).get("completion_tokens") or est_tokens(text))
            if sb_ok():
                try:
                    sb("POST", "chats", body=[{
                        "username": meta["user"], "session_id": meta["sid"], "role": "assistant",
                        "content": text, "model": meta["model"], "tokens": tk,
                    }])
                except Exception:
                    job["save_failed"] = True
            notify_feishu("assistant", text, meta["model"], meta["user"], meta["sid"])
        job["done"] = True
# ====== 会话状态 ======
def notify(text, restore=None):
    """给前端弹一个提示；restore 表示把没发出去的文字还给输入框。"""
    st.session_state.notice = {"id": uuid.uuid4().hex, "text": text, "restore": restore}


def detach_job():
    """切换会话/退出时，停掉当前生成任务。"""
    jid = st.session_state.pop("job_id", None)
    if jid:
        job = get_jobs().pop(jid, None)
        if job:
            job["stop"] = True


def new_chat():
    detach_job()
    st.session_state.sid = uuid.uuid4().hex
    st.session_state.messages = []


def sync_job():
    """每次运行时检查生成任务：完成则把回复并入当前对话。返回仍在进行的 job。"""
    ss = st.session_state
    jid = ss.get("job_id")
    if not jid:
        return None
    job = get_jobs().get(jid)
    if job is None:
        ss.pop("job_id", None)
        return None
    if not job["done"]:
        return job
    if job["text"]:
        ss.messages.append({"role": "assistant", "content": job["text"], "model": job["model"]})
    if job["error"]:
        notify(job["error"])
    elif job.get("save_failed"):
        notify("这条回复没能存档，刷新后可能丢失。")
    get_jobs().pop(jid, None)
    ss.pop("job_id", None)
    ss.dirty = True
    return None


def refresh_side(user):
    """刷新历史列表和今日用量。"""
    ss = st.session_state
    if not sb_ok():
        ss.sessions, ss.used = [], 0
        return
    try:
        ss.sessions = db_sessions(user)
        ss.used = db_used(user)
    except Exception:
        notify("读取历史/额度失败，请检查 Supabase 配置。")


# ====== 事件处理（前端点了什么，在这里响应） ======
def do_login(u, p):
    ss = st.session_state
    left = ss.get("locked_until", 0) - time.time()
    if left > 0:
        ss.login_err = f"尝试次数太多，请 {int(left) + 1} 秒后再试。"
        return True
    key = USERS_L.get(str(u).strip().lower())
    real = USERS.get(key, "\x00") if key else "\x00"
    ok = hmac.compare_digest(str(p).encode(), real.encode()) and key is not None
    if ok:
        ss.update(username=key, login_err="", fails=0, dirty=True)
        new_chat()
    else:
        ss.fails = ss.get("fails", 0) + 1
        if ss.fails >= 5:                       # 连错 5 次锁 5 分钟
            ss.locked_until = time.time() + 300
            ss.fails = 0
        ss.login_err = "用户名或密码不对。"
    return True


def on_send(text, model_name):
    ss = st.session_state
    user = ss.username
    text = (text or "").strip()
    if not text or ss.get("job_id"):
        return False
    spec = MODEL_MAP.get(model_name)
    if not spec:
        notify("没有这个模型。", text)
        return True
    if not (RELAY_BASE_URL and RELAY_API_KEY):
        notify("中转站还没配置（RELAY_BASE_URL / RELAY_API_KEY）。", text)
        return True

    # 额度检查：只限制「受限模型」，无限额度账号跳过
    if spec["limited"] and user not in UNLIMITED_USERS:
        if not sb_ok():
            notify("没配置 Supabase，无法统计额度。", text)
            return True
        try:
            used = db_used(user)
        except Exception:
            notify("额度服务暂时不可用，请稍后再试。", text)
            return True
        if used >= DAILY_TOKEN_LIMIT:
            notify(f"今天的额度用完了（{used}/{DAILY_TOKEN_LIMIT} tokens），明天恢复；也可以换 GLM / DeepSeek。", text)
            return True

    # 记录并存档用户消息
    ss.messages.append({"role": "user", "content": text, "model": model_name})
    if sb_ok():
        try:
            sb("POST", "chats", body=[{
                "username": user, "session_id": ss.sid, "role": "user",
                "content": text, "model": model_name, "tokens": est_tokens(text),
            }])
        except Exception:
            notify("这条消息没能存档，刷新后可能丢失。")
    notify_feishu("user", text, model_name, user, ss.sid)

    # 组装上下文：人设（可空）+ 最近 N 条
    ctx = [{"role": m["role"], "content": m["content"]} for m in ss.messages][-MAX_CONTEXT:]
    if SYSTEM_PROMPT.strip():
        ctx = [{"role": "system", "content": SYSTEM_PROMPT}] + ctx
    body = {
        "model": spec["id"], "messages": ctx, "stream": True,
        "temperature": spec["temp"], "max_tokens": spec["max_tokens"],
    }

    job = {"text": "", "done": False, "error": None, "stop": False, "model": model_name}
    jid = uuid.uuid4().hex
    get_jobs()[jid] = job
    threading.Thread(
        target=run_job,
        args=(job, chat_url(), RELAY_API_KEY, body, {"user": user, "sid": ss.sid, "model": model_name}),
        daemon=True,
    ).start()
    ss.job_id = jid
    ss.dirty = True
    return True


def handle(ev):
    """处理前端事件；返回 True 表示需要重新渲染。"""
    ss = st.session_state
    t = ev.get("type")
    if t == "login":
        return do_login(ev.get("u", ""), ev.get("p", ""))
    user = ss.get("username")
    if not user or t == "poll":
        return False

    if t == "send":
        return on_send(ev.get("text"), ev.get("model"))
    if t == "stop":
        job = get_jobs().get(ss.get("job_id"))
        if job:
            job["stop"] = True
        return False
    if t == "new":
        new_chat()
        ss.dirty = True
        return True
    if t == "open":
        sid = ev.get("sid")
        if sid and sid != ss.sid:
            if not sb_ok():
                return False
            try:
                rows = db_load(user, sid)
            except Exception:
                notify("读取对话失败。")
                return True
            detach_job()
            ss.sid, ss.messages = sid, rows
        return True
    if t == "delete":
        sid = ev.get("sid")
        try:
            db_delete(user, sid)
        except Exception:
            notify("删除失败。")
            return True
        if sid == ss.sid:
            new_chat()
        ss.dirty = True
        return True
    if t == "logout":
        eid = ss.get("last_eid")      # 保留事件 id，否则会重复处理退出事件陷入循环
        detach_job()
        ss.clear()
        ss["last_eid"] = eid
        return True

    # ---- 管理员 ----
    if user in ADMIN_USERS:
        if t in ("admin_open", "admin_refresh"):
            try:
                ss.admin = {"rows": db_overview(), "msg": ""}
            except Exception:
                ss.admin = {"rows": [], "msg": "读取用量失败，请检查 Supabase。"}
            return True
        if t == "admin_close":
            ss.admin = None
            return True
        if t == "feishu_test":
            msg = "还没配置 FEISHU_WEBHOOK。"
            if FEISHU_WEBHOOK:
                try:
                    r = requests.post(FEISHU_WEBHOOK, json=feishu_payload("【Equinox】飞书推送测试"), timeout=5)
                    msg = f"HTTP {r.status_code}：{r.text[:120]}"
                except Exception as e:
                    msg = f"请求失败：{type(e).__name__}"
            ss.admin = dict(ss.get("admin") or {"rows": []}, msg=msg)
            return True
    return False


# ====== 构造发给前端的状态 ======
def build_state():
    ss = st.session_state
    ss.tick = ss.get("tick", 0) + 1       # 保证每次 args 都不同，前端才会收到渲染事件
    user = ss.get("username")
    if not user:
        return {"view": "login", "tick": ss.tick, "err": ss.get("login_err", "")}

    job = sync_job()
    if ss.pop("dirty", False):
        refresh_side(user)
    return {
        "view": "chat", "tick": ss.tick, "user": user,
        "is_admin": user in ADMIN_USERS,
        "models": [{"name": m["name"], "desc": m["desc"], "limited": m["limited"]} for m in MODELS],
        "limit": None if user in UNLIMITED_USERS else DAILY_TOKEN_LIMIT,
        "used": ss.get("used", 0),
        "sessions": ss.get("sessions", []),
        "sid": ss.get("sid"),
        "messages": ss.get("messages", []),
        "generating": bool(job),
        "stream": job["text"] if job else "",
        "notice": ss.get("notice"),
        "admin": ss.get("admin"),
    }



