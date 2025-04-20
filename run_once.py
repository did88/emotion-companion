# run_once.py
from db import Base, engine

if __name__ == "__main__":
    print("🚀 emotion_records 테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    print("✅ 생성 완료!")
