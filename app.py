import streamlit as st
import requests
import json
import base64
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="중·고등 학적 파트너", page_icon="🏫", layout="centered")
st.title("🏫 중·고등 학적 파트너 (Direct API)")
st.info("라이브러리 없이 구글 서버와 직접 통신합니다. (PDF 분석 포함)")

# 2. API 키 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("비밀 키(Secrets)가 설정되지 않았습니다.")
    st.stop()

API_KEY = st.secrets["GEMINI_API_KEY"]

# 3. 시스템 프롬프트
SYSTEM_PROMPT = """
당신은 학교 학적 업무를 지원하는 전문 어시스턴트입니다.
제공된 PDF 문서의 내용을 기반으로 답변해야 하며, 답변 끝에는 반드시 근거(문서명, 페이지)를 명시해야 합니다.
문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 답변하세요.
"""

# 4. 직접 통신 함수 (라이브러리 X)
def call_gemini_direct(prompt, pdf_files):
    # 1) 사용할 모델 주소 (최신 1.5 Flash 모델 사용)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    # 2) 보낼 데이터 조립
    parts = [{"text": SYSTEM_PROMPT}, {"text": f"질문: {prompt}"}]
    
    # PDF 파일들을 base64 코드로 변환해서 첨부
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
        except Exception as e:
            st.error(f"파일 읽기 실패 ({pdf_path}): {e}")

    payload = {
        "contents": [{"parts": parts}]
    }

    # 3) 전송 (POST 요청)
    response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    
    return response

# 5. 현재 폴더의 PDF 찾기
pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]

# 사이드바 표시
with st.sidebar:
    st.header("📂 문서 목록")
    if pdf_files:
        for f in pdf_files:
            st.success(f"📄 {f}")
    else:
        st.warning("PDF 파일이 없습니다.")

# 6. 채팅 인터페이스
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
        msg_box.markdown("직통 회선으로 연결 중... 📡")
        
        try:
            # 함수 호출
            res = call_gemini_direct(prompt, pdf_files)
            
            if res.status_code == 200:
                # 성공 시
                result_json = res.json()
                try:
                    answer = result_json["candidates"][0]["content"]["parts"][0]["text"]
                    msg_box.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except:
                    msg_box.error("답변을 해석할 수 없습니다. (안전 필터 등)")
                    st.json(result_json) # 디버깅용 원본 출력
            else:
                # 실패 시 (여기가 진짜 중요합니다. 구글이 보낸 진짜 에러 메시지를 보여줌)
                error_msg = res.json().get("error", {}).get("message", "알 수 없는 오류")
                msg_box.error(f"❌ 구글 서버 거부: {res.status_code}")
                msg_box.code(error_msg) # 에러 내용 그대로 출력
                
        except Exception as e:
            msg_box.error(f"전송 중 오류 발생: {e}")
