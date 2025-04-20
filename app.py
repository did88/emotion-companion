import streamlit as st
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

# 앱 설정
st.set_page_config(page_title="감정 위로 챗봇", page_icon="🫂")
font_path = "./fonts/NanumGothic.ttf"
fontprop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = fontprop.get_name()

# Firebase 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
ADMIN_EMAIL = "wsryang@gmail.com"

if "user" not in st.session_state:
    st.session_state["user"] = None

if st.session_state["user"] is None:
    st.title("✉️ 감정 위로 챗봇 로그인 / 회원가입")
    tab1, tab2 = st.tabs(["로그인", "회원가입"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("이메일 입력", key="login_email", autocomplete="email")
            password = st.text_input("비밀번호 입력", type="password", key="login_password", autocomplete="current-password")
            reset_pw = st.checkbox("비밀번호 재설정 메일 보내기")
            submitted = st.form_submit_button("로그인")

            if submitted:
                api_key = st.secrets["FIREBASE_WEB_API_KEY"]
                if reset_pw:
                    res = requests.post(
                        f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}",
                        json={"requestType": "PASSWORD_RESET", "email": email}
                    )
                    if res.status_code == 200:
                        st.success("비밀번호 재설정 이메일이 발송되었습니다. 메일함을 확인해주세요.")
                    else:
                        st.error("비밀번호 재설정 실패")
                else:
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
            입력한 감정과 AI의 응답은 저장되며, 익명 분석 및 서비스 개선 목적으로 사용됩니다.
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

    st.markdown("""
    🛡️ **감정데이터 수집 안내**

    - 입력한 감정 텍스트와 AI 응답은 익명으로 저장되며, 향후 통계 및 서비스 개선에 사용될 수 있습니다.
    - 데이터는 외부에 공개되지 않으며, 개인 식별이 불가능한 형태로만 활용됩니다.
    """)
    consent = st.checkbox("위 내용을 읽고 이해했으며, 감정데이터 수집에 동의합니다.")

    user_input = st.text_area("지금 느끼는 감정을 한 줄로 표현해 주세요.", placeholder="예: 너무 지치고 무기력해요...")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if st.button("위로받기"):
        if not consent:
            st.warning("감정 위로를 받기 위해서는 동의가 필요합니다.")
        elif not user_input.strip():
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

                st.success(reply)
                st.session_state.chat_history.append({"user": user_input, "assistant": reply})

    if st.button("로그아웃"):
        st.session_state["user"] = None
        st.session_state.chat_history = []
        st.rerun()

    with st.expander("🕘 내 감정 히스토리 보기"):
        st.markdown("#### 📊 감정 카테고리 자동 분류 결과")
        category_keywords = {
            "스트레스": ["지치", "짜증", "불안", "과로", "긴장"],
            "우울": ["무기력", "우울", "의욕", "힘들", "외롭"],
            "기쁨": ["행복", "기쁨", "뿌듯", "좋아", "감사"],
            "분노": ["화남", "짜증", "열받", "불공정"],
            "불안": ["걱정", "두려움", "불안", "초조"]
        }
        db = SessionLocal()
        records = db.query(EmotionRecord).filter_by(email=st.session_state["user"]).order_by(EmotionRecord.timestamp.desc()).limit(100).all()
        db.close()
        if records:
            # 카테고리 통계
            category_counts = {}
            for r in records:
                matched = False
                for cat, kws in category_keywords.items():
                    if any(kw in r.user_input for kw in kws):
                        category_counts[cat] = category_counts.get(cat, 0) + 1
                        matched = True
                        break
                if not matched:
                    category_counts["기타"] = category_counts.get("기타", 0) + 1

            if category_counts:
                cat_names, cat_vals = zip(*category_counts.items())
                fig3, ax3 = plt.subplots()
                ax3.bar(cat_names, cat_vals)
                ax3.set_title("내 감정 분포", fontproperties=fontprop)
                ax3.set_xticklabels(cat_names, fontproperties=fontprop, rotation=30)
                st.pyplot(fig3)

            for r in records:
                st.markdown(f"**🕓 {r.timestamp.strftime('%Y-%m-%d %H:%M')}**\n- 입력: `{r.user_input}`\n- GPT 위로: _\"{r.gpt_reply}\"_\n---")
        else:
            st.info("아직 저장된 감정 기록이 없습니다.")

    if st.session_state["user"] == ADMIN_EMAIL:
        with st.expander("📂 관리자용 감정 분석 패널", expanded=False):
            st.markdown("### 전체 감정 기록 통계")
            db = SessionLocal()
            records = db.query(EmotionRecord).order_by(EmotionRecord.timestamp.desc()).all()

            emails = sorted(set(r.email for r in records))
            selected_email = st.selectbox("👤 특정 사용자 이메일 선택", options=["전체 보기"] + emails)
            if selected_email != "전체 보기":
                records = [r for r in records if r.email == selected_email]

            st.write(f"총 기록 수: {len(records)}개")

            if records:
                st.markdown("#### 감정 입력 예시")
                for r in records[:5]:
                    st.markdown(f"- {r.user_input} → _{r.gpt_reply}_")

                keywords = [w for r in records for w in r.user_input.split() if len(w) > 1]
                common = Counter(keywords).most_common(10)
                if common:
                    words, counts = zip(*common)
                    fig, ax = plt.subplots()
                    ax.bar(words, counts)
                    ax.set_title("감정 키워드 빈도수 상위 10개", fontproperties=fontprop)
                    ax.set_xticklabels(words, fontproperties=fontprop, rotation=45)
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
