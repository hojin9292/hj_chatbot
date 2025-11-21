import streamlit as st
import requests
import json
import base64
import os

# 1. 페이지 설정
st.set_page_config(page_title="학적 파트너", page_icon="🏫")
st.title("🏫 학적 파트너")

# 2. API 키 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("API 키가 없습니다.")
    st.stop()

API_KEY = st.secrets["GEMINI_API_KEY"]

# 3. 채팅 함수 (AI Studio 키 전용)
def call_gemini(prompt, pdf_files):
    # AI Studio 키는 이 모델이 100% 작동합니다. (이름 변경 금지)
    model_name = "models/gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
    
    system_instruction = """
    당신은 학교 학적 업무를 지원하는 전문 어시스턴트입니다. 
    답변은 제공된 문서에 기반해야 하며, 답변 끝에 (문서명, 페이지)를 출처로 남겨야 합니다.
    """
    
    parts = [{"text": system_instruction}, {"text": f"질문: {prompt}"}]
    
    # PDF 첨부
    if pdf_files:
        for pdf_path in pdf_files:
            try:
                with open(pdf_path, "rb") as f:
                    pdf_data = base64.b64encode(f.read()).decode("utf-8")
                    parts.append({
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": pdf_data
                        }
                    })
            except:
                pass

    payload = {"contents": [{"parts": parts}]}
    
    response = requests.post(
        url, 
        headers={"Content-Type": "application/json"}, 
        data=json.dumps(payload),
        timeout=30
    )
    return response

# PDF 파일 찾기
pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]

# 4. 화면 표시
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 학적 규정에 대해 질문해주세요."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_box = st.empty()
        msg_box.markdown("생성 중... ⏳")
        
        try:
            res = call_gemini(prompt, pdf_files)
            
            if res.status_code == 200:
                ans = res.json()['candidates'][0]['content']['parts'][0]['text']
                msg_box.markdown(ans)
                st.session_state.messages.append({"role": "assistant", "content": ans})
            else:
                # 에러 발생 시 원인 출력
                msg_box.error(f"오류: {res.status_code}")
                st.json(res.json())
        except Exception as e:
            msg_box.error(f"에러: {e}")
