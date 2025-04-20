import streamlit as st
st.set_page_config(page_title="감정 위로 챗봇", page_icon="🫂")

from openai import OpenAI
import requests
from datetime import datetime
import uuid
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from collections import Counter

import firebase_admin
from firebase_admin import credentials

from db import SessionLocal, EmotionRecord

# 서버 배포용 한글 폰트 설정 (NanumGothic.ttf 필요)
font_path = "./fonts/NanumGothic.ttf"
fontprop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = fontprop.get_name()

# Firebase 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

# OpenAI 클라이언트
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    st.title("✉️ 감정 위로 챗봇 로그인 / 회원가입")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("이메일 입력", key="login_email", autocomplete="email")
            password = st.text_input("비밀번호 입력", type="password", key="login_password", autocomplete="current-password")
            submitted = st.form_submit_button("로그인")
            if submitted:
                api_key = st.secrets["FIREBASE_WEB_API_KEY"]
                res = requests.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
                    json={"email": email, "password": password, "returnSecureToken": True}
                )
                if res.status_code == 200:
                    st.session_state["user"] = res.json()["email"]
                    st.success(f"{email} 님, 로그인되었습니다!")
                    st.rerun()
                else:
                    st.error("로그인 실패")

    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("이메일", key="signup_email", autocomplete="email")
            new_password = st.text_input("비밀번호", type="password", key="signup_password", autocomplete="new-password")
            confirm_password = st.text_input("비밀번호 확인", type="password", key="signup_confirm", autocomplete="new-password")
            st.markdown("""
            #### ✅ 이용 약관 안내
            본 감정 위로 챗봇은 감정 공감을 위한 도구이며, 의료 조언이 아닙니다.
            데이터는 개인화와 서비스 향상 목적 외에는 사용되지 않습니다.
            """)
            agree = st.checkbox("위 내용을 모두 읽고 이해했으며, 동의합니다.")
            submitted = st.form_submit_button("회원가입")

            if submitted:
                if not agree:
                    st.warning("회원가입을 위해 약관 동의가 필요합니다.")
                elif new_password != confirm_password:
                    st.warning("비밀번호가 일치하지 않습니다.")
                elif len(new_password) < 6:
                    st.warning("비밀번호는 6자 이상이어야 합니다.")
                else:
                    api_key = st.secrets["FIREBASE_WEB_API_KEY"]
                    res = requests.post(
                        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
                        json={"email": new_email, "password": new_password, "returnSecureToken": True}
                    )
                    if res.status_code == 200:
                        st.success("회원가입 완료! 로그인 탭으로 이동해주세요.")
                    else:
                        error_info = res.json().get("error", {}).get("message", "알 수 없는 오류")
                        st.error(f"회원가입 실패: {error_info}")

else:
    st.title("🫂 감정 위로 챗봇")
    st.write(f"{st.session_state['user']} 님, 오늘 기분은 어떠신가요?")
    user_input = st.text_area("지금 느끼는 감정을 한 줄로 표현해 주세요.", placeholder="예: 너무 지치고 무기력해요...")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if st.button("위로받기"):
        if not user_input.strip():
            st.warning("감정을 입력해 주세요.")
        else:
            messages = [{"role": "system", "content": "당신은 섬세하고 따뜻한 감정 상담가입니다."}]
            for m in st.session_state.chat_history:
                messages.append({"role": "user", "content": m["user"]})
                messages.append({"role": "assistant", "content": m["assistant"]})
            messages.append({"role": "user", "content": user_input})

            with st.spinner("당신의 마음을 이해하는 중입니다..."):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()
                st.success(reply)

                db = SessionLocal()
                record = EmotionRecord(
                    id=str(uuid.uuid4()),
                    email=st.session_state["user"],
                    user_input=user_input,
                    gpt_reply=reply,
                )
                db.add(record)
                db.commit()
                db.close()

                st.session_state.chat_history.append({"user": user_input, "assistant": reply})

    if st.button("로그아웃"):
        st.session_state["user"] = None
        st.session_state.chat_history = []
        st.rerun()

    with st.expander("🕘 이전 감정 히스토리 보기"):
        db = SessionLocal()
        records = db.query(EmotionRecord).filter_by(email=st.session_state["user"]).order_by(EmotionRecord.timestamp.desc()).limit(100).all()
        db.close()
        if records:
            for r in records:
                st.markdown(f"**🕓 {r.timestamp.strftime('%Y-%m-%d %H:%M')}**\n- 입력: `{r.user_input}`\n- GPT 위로: _\"{r.gpt_reply}\"_\n---")
        else:
            st.info("아직 저장된 감정 기록이 없습니다.")

    with st.expander("📊 감정 분석 보기"):
        db = SessionLocal()
        records = db.query(EmotionRecord).filter_by(email=st.session_state["user"]).all()
        db.close()

        if records:
            all_inputs = "\n".join([r.user_input for r in records])
            prompt = f"""
            다음은 한 사용자의 감정 기록입니다. 이 기록을 분석해 주세요.
            1. 자주 등장하는 감정 키워드 3~5개
            2. 감정의 전반적인 경향
            3. 이 사용자가 지금 가장 필요로 하는 심리적 메시지 한 문장
            텍스트:\n{all_inputs}
            """
            with st.spinner("감정을 분석 중입니다..."):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                st.markdown("#### 분석 결과")
                st.markdown(response.choices[0].message.content.strip())

            keywords = [w for r in records for w in r.user_input.split() if len(w) > 1]
            common = Counter(keywords).most_common(10)
            if common:
                words, counts = zip(*common)
                fig, ax = plt.subplots()
                ax.bar(words, counts)
                ax.set_title("감정 키워드 빈도수 상위 10개", fontproperties=fontprop)
                ax.set_xticklabels(words, fontproperties=fontprop, rotation=45)
                ax.tick_params(axis='x', labelsize=10)
                st.pyplot(fig)

            df = pd.DataFrame([(r.timestamp.date(), 1) for r in records], columns=["date", "count"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.groupby("date").sum().reset_index()
            if not df.empty:
                fig2, ax2 = plt.subplots()
                ax2.plot(df["date"], df["count"], marker='o')
                ax2.set_title("일자별 감정 입력 수 추이", fontproperties=fontprop)
                ax2.set_xlabel("날짜", fontproperties=fontprop)
                ax2.set_ylabel("입력 수", fontproperties=fontprop)
                ax2.set_xticks(df["date"])
                ax2.set_xticklabels(df["date"].dt.strftime('%Y-%m-%d'), fontproperties=fontprop, rotation=45)
                ax2.grid(True)
                st.pyplot(fig2)
        else:
            st.info("분석할 감정 기록이 없습니다.")
