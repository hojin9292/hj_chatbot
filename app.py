import streamlit as st
import requests
import json
import base64
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="중·고등 학적 파트너", page_icon="🏫", layout="centered")
st.title("🏫 학적 파트너 (자동 우회 접속)")

# 2. API 키 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
    st.stop()

API_KEY = st.secrets["GEMINI_API_KEY"]

# 3. [해결책] 하나가 막히면 다음 걸로 뚫는 "모델 후보 리스트"
# 선생님 계정에서 정확히 어떤 이름이 먹힐지 모르니, 가능한 변형을 다 넣었습니다.
MODEL_CANDIDATES = [
    "models/gemini-1.5-flash",      # 1순위: 기본 Flash
    "models/gemini-1.5-flash-001",  # 2순위: 구버전 명칭 Flash
    "models/gemini-1.5-flash-002",  # 3순위: 신버전 명칭 Flash
    "models/gemini-1.5-pro",        # 4순위: Pro (Flash 안되면 이거라도)
    "models/gemini-1.5-pro-001",    # 5순위: 구버전 명칭 Pro
]

# 4. 시스템 프롬프트
SYSTEM_PROMPT = """
당신은 학교 학적 업무를 지원하는 전문 어시스턴트입니다.
답변 끝에는 반드시 근거(문서명, 페이지)를 명시해야 합니다.
문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 답변하세요.
"""

def call_gemini_with_retry(prompt, pdf_files):
    # PDF 데이터 준비 (한 번만 변환해서 계속 재사용)
    parts = [{"text": SYSTEM_PROMPT}, {"text": f"질문: {prompt}"}]
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
    headers = {"Content-Type": "application/json"}

    # [핵심 로직] 리스트에 있는 모델들을 하나씩 순서대로 시도
    last_error = ""
    
    for model_name in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
        
        try:
            # 타임아웃 30초
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            
            # 200 OK면 바로 성공! (반복문 탈출)
            if response.status_code == 200:
                return model_name, response
            
            # 404(모델 없음)면 다음 후보 시도
            elif response.status_code == 404:
                continue 
            
            # 429(사용량 초과)나 기타 에러면 즉시 중단하고 에러 보고
            else:
                return model_name, response
                
        except Exception as e:
            last_error = str(e)
            continue

    # 여기까지 왔다는 건 모든 후보가 실패했다는 뜻
    return None, last_error

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
        msg_box.markdown("접속 가능한 AI 모델을 찾는 중... 📡")
        
        try:
            # 재시도 함수 호출
            success_model, res_or_err = call_gemini_with_retry(prompt, pdf_files)
            
            if success_model and isinstance(res_or_err, requests.models.Response):
                # 성공 시
                res = res_or_err
                if res.status_code == 200:
                    try:
                        answer = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                        msg_box.markdown(answer)
                        st.toast(f"연결된 모델: {success_model}", icon="✅") # 성공한 모델명을 작게 보여줌
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                    except KeyError:
                        msg_box.error("답변이 비어있습니다. (보안 필터 등)")
                else:
                    # 400, 500 등 에러
                    msg_box.error(f"❌ 오류 ({success_model}): {res.status_code}")
                    if res.status_code == 429:
                        st.warning("모든 모델의 무료 사용량이 초과되었습니다. 잠시 후 다시 시도해주세요.")
                    else:
                        st.json(res.json())
            else:
                # 모든 모델 실패 시
                msg_box.error("❌ 모든 모델 연결 실패")
                st.warning("API 키는 맞지만, 사용 가능한 모델을 찾지 못했습니다. (404 Not Found 반복)")
                if res_or_err:
                    st.code(f"마지막 에러: {res_or_err}")

        except Exception as e:
            msg_box.error(f"시스템 오류: {e}")
