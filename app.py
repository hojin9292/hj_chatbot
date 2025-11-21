import streamlit as st
import requests
import json
import base64
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="중·고등 학적 파트너", page_icon="🏫", layout="centered")
st.title("🏫 학적 파트너 (Flash 강제 고정)")

# 2. API 키 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
    st.stop()

API_KEY = st.secrets["GEMINI_API_KEY"]

# 3. [해결책] 복잡한 탐색 로직 제거 -> 무료 티어 보장 모델 강제 지정
# 구글 API에서 무료로 가장 안정적인 모델명을 하드코딩합니다.
# 앞에 'models/'를 붙여야 정확하게 인식하는 경우가 있어 추가합니다.
TARGET_MODEL = "models/gemini-1.5-flash"

# 사이드바에 현재 상태 표시
with st.sidebar:
    st.info(f"🎯 타겟 모델: {TARGET_MODEL}")
    st.caption("실험용 모델(exp)이 잡히는 것을 방지하기 위해 표준 모델로 고정했습니다.")

# 4. 채팅 로직
SYSTEM_PROMPT = """
당신은 학교 학적 업무를 지원하는 전문 어시스턴트입니다.
답변 끝에는 반드시 근거(문서명, 페이지)를 명시해야 합니다.
문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 답변하세요.
"""

def call_gemini(prompt, pdf_files):
    # 모델명을 탐색하지 않고 TARGET_MODEL 변수를 바로 사용
    url = f"https://generativelanguage.googleapis.com/v1beta/{TARGET_MODEL}:generateContent?key={API_KEY}"
    
    parts = [{"text": SYSTEM_PROMPT}, {"text": f"질문: {prompt}"}]
    
    # PDF 첨부 로직
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
    
    # 타임아웃을 30초로 넉넉하게 설정 (PDF 처리 시간 고려)
    response = requests.post(
        url, 
        headers={"Content-Type": "application/json"}, 
        data=json.dumps(payload),
        timeout=30
    )
    return response

# PDF 파일 찾기
pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]

# 5. 채팅 UI
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_box = st.empty()
        msg_box.markdown("답변 생성 중... ⏳")
        
        try:
            res = call_gemini(prompt, pdf_files)
            
            if res.status_code == 200:
                try:
                    answer = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    msg_box.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except KeyError:
                    # 200 OK지만 내용이 비어있는 경우 (안전 필터 등)
                    msg_box.error("답변이 생성되지 않았습니다. (보안 필터 또는 내용 없음)")
                    st.json(res.json())
            else:
                # 에러 발생 시 상세 정보 출력
                error_data = res.json()
                error_msg = error_data.get("error", {}).get("message", "")
                
                msg_box.error(f"❌ 통신 오류: {res.status_code}")
                
                # 429 (사용량 초과) 에러 처리
                if res.status_code == 429:
                    st.warning("⚠️ 무료 사용량을 초과했습니다. (잠시 후 다시 시도하세요)")
                else:
                    st.code(error_msg)
                    
        except Exception as e:
            msg_box.error(f"시스템 오류: {e}")
