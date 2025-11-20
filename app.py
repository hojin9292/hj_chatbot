import streamlit as st
import google.generativeai as genai
import os
import time

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="중·고등 학적 파트너",
    page_icon="🏫",
    layout="centered"
)

# 2. 제목 및 소개
st.title("🏫 중·고등 학적 파트너")
st.markdown("**만든이: 최호진** | 2025학년도 규정 기반")
st.info("GitHub에 업로드된 PDF 파일들을 분석하여 답변합니다.")

# 3. 시스템 프롬프트 (선생님이 작성하신 내용 그대로 적용)
SYSTEM_INSTRUCTION = """
당신은 학교 학적 업무를 지원하는 전문 어시스턴트인 '학적 파트너'입니다. 사용자는 교사 또는 학교 행정가이며, 학적, 출결, 평가 등과 관련된 규정을 문의할 것입니다.

**핵심 원칙**
1. **정보의 원천 및 제한 (Strict Source Control)**: 당신의 모든 답변은 반드시 제공된 문서 내의 정보에만 기초해야 합니다. 당신이 원래 알고 있는 일반적인 상식, 다른 학교의 사례, 인터넷 검색 정보 등을 답변에 섞지 마십시오. 문서 내용이 모호하거나 부분적일지라도, 문맥을 임의로 해석하거나 추측하여 답변을 채우지 마십시오.
2. **답변 작성 및 출처 표기 (Response & Citation)**: 답변하는 모든 문장 혹은 단락 끝에는 해당 정보가 위치한 정확한 문서명과 페이지 번호를 표기해야 합니다. 예시: "질병으로 인한 결석은 3일 이내에 증빙서류를 제출해야 합니다. (2025학년도 학업성적관리규정, 15페이지)"
3. **명확성**: 규정이나 지침은 있는 그대로 정확하게 전달하되, 사용자가 이해하기 쉽도록 요점 정리(글머리 기호 등)를 활용하십시오.
4. **정보 부재 시 대응**: 사용자의 질문에 대한 답이 문서에 명시되어 있지 않거나 찾을 수 없는 경우, 반드시 모른다고 답해야 합니다. "죄송합니다. 업로드된 문서(지침) 내에서 해당 질문에 대한 근거를 찾을 수 없습니다."라고 답하십시오. 절대로 회피성 답변을 하지 마십시오.
5. **어조 및 태도**: 전문적이고 객관적인 태도를 유지하며, 핵심 위주로 간결하게 답변하십시오.
"""

# 4. API 키 설정 (Streamlit Secrets에서 가져옴)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("API 키 설정 오류: Streamlit Secrets에 'GEMINI_API_KEY'가 있는지 확인해주세요.")
    st.stop()

# 5. PDF 파일 로드 및 캐싱 함수 (중요!)
# GitHub 같은 폴더에 있는 모든 .pdf 파일을 찾아서 Gemini에게 학습시킵니다.
@st.cache_resource
def load_pdfs_and_configure_model():
    # 현재 폴더에서 PDF 파일 찾기
    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        return None, "PDF 파일을 찾을 수 없습니다. GitHub 리포지토리에 PDF 파일을 업로드해주세요."

    uploaded_files = []
    status_text = st.empty()
    status_text.info(f"📚 규정 파일 {len(pdf_files)}개를 분석 중입니다... 잠시만 기다려주세요.")
    
    try:
        # Gemini 서버로 파일 업로드
        for pdf in pdf_files:
            # 파일을 업로드 (MIME type: application/pdf)
            uploaded_file = genai.upload_file(pdf, mime_type='application/pdf')
            
            # 파일 처리가 완료될 때까지 대기
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)
                
            uploaded_files.append(uploaded_file)

        # 모델 설정 (시스템 프롬프트 + 파일 포함)
        # Gemini 1.5 Flash 모델 사용 (긴 문맥 처리에 최적화)
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        status_text.empty() # 로딩 메시지 삭제
        return model, uploaded_files
        
    except Exception as e:
        return None, f"파일 처리 중 오류 발생: {str(e)}"

# 모델 로드 실행
model_instance, result = load_pdfs_and_configure_model()

# 오류 발생 시 중단
if model_instance is None:
    st.error(result)
    st.stop()
else:
    # 성공 시 사이드바에 파일 목록 표시
    with st.sidebar:
        st.success(f"✅ 문서 연동 완료!")
        st.markdown("---")
        st.markdown("**참조 중인 문서:**")
        uploaded_pdfs = result
        for f in os.listdir('.'):
            if f.lower().endswith('.pdf'):
                st.caption(f"📄 {f}")

# 6. 채팅 인터페이스 구현
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 2025학년도 학교생활기록부 기재요령 및 학적 길라잡이를 기반으로 답변해 드립니다. 궁금한 점을 물어보세요."}
    ]

# 이전 대화 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("궁금한 학적 규정을 입력하세요..."):
    # 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI 답변 생성
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("규정을 찾아보는 중입니다... ⏳")
        
        try:
            # 파일 목록(uploaded_pdfs)과 질문(prompt)을 함께 전달
            # generate_content에 파일 객체 리스트와 텍스트 리스트를 함께 줍니다.
            request_content = [prompt] + uploaded_pdfs
            
            response = model_instance.generate_content(request_content)
            
            # 답변 출력
            full_response = response.text
            message_placeholder.markdown(full_response)
            
            # 대화 기록 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            message_placeholder.error(f"오류가 발생했습니다: {e}")

