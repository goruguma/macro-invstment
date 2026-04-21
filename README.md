# Macro Daily Briefing (Streamlit)

거시 지표를 매일 아침 한 화면에서 확인하는 Streamlit 대시보드입니다.

## 포함 지표
- NFCI 10년 추이 (FRED)
- AAII Investor Sentiment (Bull/Bear/Neutral)
- US High-Yield Spread (FRED: BAMLH0A0HYM2)
- CNN Fear & Greed 게이지 + 추이
- CBOE Put/Call Ratio (6개월)
- Sector Momentum (미국 섹터 ETF 1개월 수익률)

## 1) 로컬에서 먼저 실행해보기 (5분)
```bash
pip install -r requirements.txt
streamlit run app.py
```

앱 실행 후 왼쪽 사이드바에 **FRED API Key**를 입력하면 데이터가 표시됩니다.

---

## 2) GitHub에 코드 올리기
아래는 터미널에서 가장 기본적인 흐름입니다.

```bash
git init
git add .
git commit -m "Initial macro dashboard"
git branch -M main
git remote add origin https://github.com/<YOUR_ID>/<YOUR_REPO>.git
git push -u origin main
```

> 이미 저장소가 있다면 `git init`, `remote add`는 생략하고 `git add/commit/push`만 하면 됩니다.

---

## 3) Streamlit Community Cloud 배포 (핵심)
1. [https://share.streamlit.io](https://share.streamlit.io) 접속
2. **GitHub 계정으로 로그인**
3. **New app** 클릭
4. 아래 항목 선택
   - Repository: 방금 올린 GitHub 저장소
   - Branch: `main`
   - Main file path: `app.py`
5. **Deploy** 클릭

여기까지 하면 앱 URL이 생성됩니다.

---

## 4) FRED API Key를 안전하게 넣는 방법 (권장)
사이드바에 직접 입력해도 되지만, 운영용으로는 **Secrets**를 권장합니다.

### 방법 A: Streamlit Secrets 사용
Streamlit 앱 설정에서 **Secrets**에 아래처럼 저장:

```toml
FRED_API_KEY = "여기에_본인_api_key"
```

그 다음 `app.py`에서 아래처럼 우선순위로 읽으면 편합니다.

```python
fred_key = st.secrets.get("FRED_API_KEY", "")
if not fred_key:
    fred_key = st.sidebar.text_input("FRED API Key", type="password")
```

### 방법 B: 매번 사이드바 입력
현재 코드 그대로 사용하면 됩니다.

현재 `app.py`는 `st.secrets["FRED_API_KEY"]`를 먼저 확인하고, 없을 때만 사이드바 입력을 사용합니다.

---

## 5) 매일 자동 최신 상태로 보는 방법
이 앱은 열릴 때마다 최신 데이터를 조회합니다(캐시 1시간).
- 즉, **매일 아침 URL 접속**만 해도 최신값 반영
- 코드 수정 후 GitHub에 push하면 Streamlit이 자동 재배포

---

## 6) 배포 시 자주 막히는 포인트
- `ModuleNotFoundError` 발생: `requirements.txt` 누락/오타 확인
- FRED 데이터 안 나옴: API Key 확인 (공백/만료 여부)
- 외부 데이터(CNN/CBOE) 일시 실패: 잠시 후 새로고침
- main file path 오류: `app.py` 경로가 루트인지 확인

---

## 7) 체크리스트 (이대로 하면 거의 성공)
- [ ] GitHub에 `app.py`, `requirements.txt` 푸시 완료
- [ ] Streamlit에서 repo/branch/path 정확히 선택
- [ ] Secrets 또는 사이드바에 FRED API Key 설정
- [ ] 앱 URL 접속 후 각 차트 정상 노출 확인

필요하면 다음 단계로, 제가 **Secrets 방식이 반영된 `app.py` 코드까지 바로 수정**해서 더 편하게 배포 가능하게 만들어드릴게요.
