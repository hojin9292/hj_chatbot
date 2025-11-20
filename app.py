import streamlit as st
import requests
import json
import base64
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="중·고등 학적 파트너", page_icon="🏫", layout="centered")
st.title("🏫 학적 파트너 (자동 연결 모드)")

# 2. API 키 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("🚨 Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
    st.stop()

API_KEY = st.secrets["GEMINI_API_KEY"]

# 3. [핵심] 사용 가능한 모델 자동 탐색 함수
@st.cache_resource
def find_working_model(api_key):
    # 구글에 "내 키로 쓸 수 있는 모델 목록 보여줘" 요청
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, response.json() # 에러 발생
        
        data = response.json()
        # 'generateContent' 기능을 지원하는 모델만 필터링
        available_models = [
            m['name'] for m in data.get('models', [])
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        # 우선순위: 1.5 Flash -> 1.5 Pro -> 1.0 Pro 순서로 찾음
        preferred_order = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        
        for model in preferred_order:
            if model in available_models:
                return model, available_models
        
        # 우선순위 모델이 없으면 아무거나 첫 번째 것 선택
        if available_models:
            return available_models[0], available_models
            
        return None, "사용 가능한 모델이 없습니다. (API 설정 확인 필요)"
        
    except Exception as e:
        return None, str(e)

# 4. 모델 탐색 실행
with st.spinner("🔑 API 키 권한 및 사용 가능 모델 확인 중..."):
    selected_model, debug_info = find_working_model(API_KEY)

# 5. 진단 결과 처리 (여기가 중요합니다!)
if selected_model:
    st.success(f"✅ 연결 성공! 현재 사용 중인 모델: **{selected_model}**")
else:
    st.error("🚫 치명적 오류: API 키는 맞지만, 사용할 수 있는 모델이 없습니다.")
    
    # 상세 원인 분석
    if isinstance(debug_info, dict) and 'error' in debug_info:
        err_msg = debug_info['error'].get('message', '')
        st.error(f"구글 서버 메시지: {err_msg}")
        
        if "API has not been used" in err_msg or "not enabled" in err_msg:
            st.warning("""
            [해결 방법]
            선생님, 구글 클라우드 콘솔에서 **'Generative Language API'**가 꺼져 있습니다.
            1. Google Cloud Console 접속
            2. 검색창에 'Generative Language API' 검색
            3. **'ENABLE(사용)'** 버튼 클릭
            4. 5분 뒤 다시 접속하면 해결됩니다.
            """)
    else:
        st.code(debug_info)
    st.stop()

# 6. 채팅 로직 (선택된 모델로 대화)
SYSTEM_PROMPT = """
당신은 학교 학적 업무를 지원하는 전문 어시스턴트입니다.
답변 끝에는 반드시 근거(문서명, 페이지)를 명시해야 합니다.
"""

def call_gemini(prompt, pdf_files, model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
    
    parts = [{"text": SYSTEM_PROMPT}, {"text": f"질문: {prompt}"}]
    
    # PDF 첨부 (모델이 1.5 버전일 때만 가능, 1.0은 텍스트만)
    is_vision_model = "1.5" in model_name
    if is_vision_model:
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
    elif pdf_files:
        st.toast("⚠️ 현재 연결된 모델(Gemini Pro)은 PDF 직접 읽기를 지원하지 않습니다. 텍스트로 질문해주세요.", icon="ℹ️")

    payload = {"contents": [{"parts": parts}]}
    response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    return response

# PDF 파일 찾기
pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]

# 채팅 UI
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
            res = call_gemini(prompt, pdf_files, selected_model)
            
            if res.status_code == 200:
                answer = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                msg_box.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                msg_box.error(f"오류 발생: {res.status_code}")
                msg_box.json(res.json())
        except Exception as e:
            msg_box.error(f"통신 오류: {e}")
