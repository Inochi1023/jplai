import streamlit as st
import speech_recognition as sr
import google.generativeai as genai
from gtts import gTTS
import io
import base64
import tempfile
import os
from audio_recorder_streamlit import audio_recorder

gemini_api_key = "AIzaSyAoy_kLi5udJ7rl58s8URzp7q-1W8lLve4"


# 페이지 설정
st.set_page_config(
    page_title="일본어 발음 교정 AI 어시스턴트",
    page_icon="🗾",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
.main-header {
    text-align: center;
    color: #2E86AB;
    margin-bottom: 2rem;
}
.chat-message {
    padding: 1rem;
    border-radius: 10px;
    margin: 1rem 0;
}
.user-message {
    background-color: #E3F2FD;
    border-left: 4px solid #2196F3;
}
.ai-message {
    background-color: #F3E5F5;
    border-left: 4px solid #9C27B0;
}
.translation-box {
    background-color: #E8F5E8;
    border: 1px solid #4CAF50;
    border-radius: 5px;
    padding: 10px;
    margin-top: 10px;
    font-style: italic;
    color: #2E7D32;
}
</style>
""", unsafe_allow_html=True)

# 제목
st.markdown("<h1 class='main-header'>🗾 일본어 발음 교정 AI 어시스턴트</h1>", unsafe_allow_html=True)

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정")

    # 언어 설정
    recognition_lang = st.selectbox("음성 인식 언어", ["ja-JP", "ko-KR"], index=0)

    if st.button("🗑️ 대화 기록 초기화"):
        st.session_state.messages = []
        st.rerun()

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# Gemini 설정
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')


def recognize_speech_from_audio(audio_bytes):
    """오디오 바이트에서 음성을 인식하는 함수"""
    try:
        # 음성 인식기 초기화
        r = sr.Recognizer()

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name

        # 오디오 파일에서 음성 인식
        with sr.AudioFile(tmp_file_path) as source:
            audio = r.record(source)
            text = r.recognize_google(audio, language=recognition_lang)

        # 임시 파일 삭제
        os.unlink(tmp_file_path)

        return text
    except sr.UnknownValueError:
        return "음성을 인식할 수 없습니다."
    except sr.RequestError as e:
        return f"음성 인식 서비스 오류: {e}"
    except Exception as e:
        return f"오류 발생: {e}"


def get_gemini_response(user_input):
    """Gemini API를 사용하여 일본어 발음 교정 및 피드백 생성"""
    try:
        prompt = f"""
        너는 일본어로 사용자와 일상적인 대화를 할 거고
        사용자의 발음을 분석해서 정확도를 0%~100%로 나타내주고 발음교정을 할수 있게 그 발음에 대한 피드백을 해주고 교정할 수 있는 자연스러운 표현을 정해주고
        너가 자연스럽게 대화를 이어나가면 돼
        사용자 입력: "{user_input}"
        다음 형식으로 응답해주세요:
        "당신의 발음 정확도:N%\n
        자연스러운 표현:(너가 판단했을때 자연스러운 표현)\n
        (이어나갈 대화)"
        
        예) 사용자 입력이 "こんちは"이면
        너는 "정확도:5/10\n
        자연스러운 표현:こんにちは\n
        こんにちは! 何を言ってみましょうか？"
        
        이제부터 바로 대화 시작이야
        알겠다는 말 하지 말고 사용자의 입력을 분석하도록 해
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini API 오류: {e}"


def text_to_speech(text, lang='ja'):
    """텍스트를 음성으로 변환"""
    try:
        # AI 응답에서 일본어 대화 부분만 추출
        lines = text.split('\n')
        japanese_dialogue = ""

        # 각 라인을 확인하여 일본어 대화 부분 찾기
        for line in lines:
            line = line.strip()
            # "당신의 발음 정확도"나 "자연스러운 표현" 라인은 건너뛰기
            if line.startswith("당신의 발음 정확도") or line.startswith("자연스러운 표현"):
                continue
            # 일본어가 포함된 라인이면서 대화 부분인 경우
            if any('\u3040' <= char <= '\u309F' or  # 히라가나
                   '\u30A0' <= char <= '\u30FF' or  # 카타카나
                   '\u4E00' <= char <= '\u9FAF'  # 한자
                   for char in line):
                japanese_dialogue = line
                break

        # 일본어 대화가 없으면 전체 텍스트에서 일본어 추출
        if not japanese_dialogue:
            import re
            japanese_parts = re.findall(r'[ひらがなカタカナ一-龯！？。、]+', text)
            if japanese_parts:
                japanese_dialogue = ''.join(japanese_parts)
            else:
                japanese_dialogue = "こんにちは"  # 기본값

        print(f"TTS로 변환할 텍스트: {japanese_dialogue}")  # 디버깅용

        tts = gTTS(text=japanese_dialogue, lang=lang, slow=False)

        # 메모리에 오디오 저장
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)

        return audio_buffer.getvalue()
    except Exception as e:
        st.error(f"음성 합성 오류: {e}")
        return None


def play_audio(audio_bytes):
    """오디오 재생을 위한 HTML 생성"""
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
        <audio controls autoplay>
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        """
        return audio_html
    return ""


# 메인 인터페이스
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🎤 음성 입력")

    # 오디오 녹음기
    audio_bytes = audio_recorder(
        text="녹음 시작/중지",
        recording_color="#e74c3c",
        neutral_color="#34495e",
        icon_name="microphone",
        icon_size="2x"
    )

    if audio_bytes and gemini_api_key:
        with st.spinner("음성을 분석 중입니다..."):
            # 음성 인식
            recognized_text = recognize_speech_from_audio(audio_bytes)

            if recognized_text and "오류" not in recognized_text and "인식할 수 없습니다" not in recognized_text:
                # 사용자 메시지 추가
                st.session_state.messages.append({"role": "user", "content": recognized_text})

                # Gemini로 분석
                ai_response = get_gemini_response(recognized_text)
                
                # 번역 추가
                translation = translate_japanese_to_korean(ai_response)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": ai_response,
                    "translation": translation
                })

                # TTS 생성
                audio_response = text_to_speech(ai_response)
                if audio_response:
                    st.session_state.messages[-1]["audio"] = audio_response
            else:
                st.error(recognized_text)

    elif audio_bytes and not gemini_api_key:
        st.warning("Gemini API 키를 입력해주세요.")

with col2:
    st.subheader("📊 학습 통계")

    # 간단한 통계
    total_messages = len([msg for msg in st.session_state.messages if msg["role"] == "user"])
    st.metric("총 연습 횟수", total_messages)

    if total_messages > 0:
        st.success("계속 연습하세요! 💪")

# 대화 기록 표시
st.subheader("💬 대화 기록")

for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <strong>🗣️ 사용자:</strong><br>
            {message["content"]}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message ai-message">
            <strong>🤖 AI 선생님:</strong><br>
            {message["content"]}
        </div>
        """, unsafe_allow_html=True)


        # 오디오가 있으면 재생
        if "audio" in message:
            audio_html = play_audio(message["audio"])
            if audio_html:
                st.markdown(audio_html, unsafe_allow_html=True)

# 사용법 안내
if not st.session_state.messages:
    st.info("""
    📝 **사용법:**
    1. 마이크 버튼을 눌러 일본어로 말해보세요!
    2. AI가 정확도랑 자연스러운 대화를 알려줍니다!
    3. AI랑 재미있게 대화하며 공부해봐요!
    """)
