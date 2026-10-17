import streamlit as st
import requests
import json

st.title("Equinox AI alpha")

api_key = st.secrets["ZHIPU_API_KEY"]

# 1. 定义你的人设
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

# 2. 初始化时，把人设塞进对话最前面
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


for msg in st.session_state.messages:
    if msg["role"] != "system":   # 不显示 system 消息
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
def stream_response(messages):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": "glm-5.3-flash",
        "messages": messages,
        "stream": True
    }
    
    response = requests.post(url, headers=headers, json=data, stream=True)
    
    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8")
        if line.startswith("data: "):
            json_str = line[6:]
            if json_str == "[DONE]":
                break
            try:
                chunk = json.loads(json_str)
                delta = chunk["choices"][0]["delta"]
                if "content" in delta and delta["content"]:
                    yield delta["content"]
            except:
                continue

if user_input := st.chat_input("说点什么..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.chat_message("assistant"):
        full_reply = st.write_stream(stream_response(st.session_state.messages))
    
    st.session_state.messages.append({"role": "assistant", "content": full_reply})