import streamlit as st
import requests
import json

st.title("Equinox AI alpha")

api_key = st.secrets["ZHIPU_API_KEY"]

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
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