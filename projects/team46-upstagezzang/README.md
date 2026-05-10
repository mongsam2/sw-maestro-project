# AI · SW 마에스트로 프로젝트 기획 파트너

SW Maestro 연수생들의 프로젝트 기획 데이터를 수집·분석하여 **주제 중복을 방지**하고, LLM 기반 **유사도 측정**과 **아이디어 융합(Cross-Insight)**, **멘토링 요약**을 제공하는 기획 보조 시스템입니다.

사용자는 챗봇과 대화하며 기획 카드를 채워 넣고, 시스템은 이를 구조화·임베딩하여 벡터 DB에 저장한 뒤, 기존 등록 기획안과 비교한 분석 리포트를 돌려줍니다.

## 기술 스택

- **UI**: Streamlit (`src/main.py` 진입)
- **에이전트 오케스트레이션**: LangGraph (대화형 그래프 — interrupt 기반)
- **LLM/임베딩**: LangChain OpenAI (모델은 `.env`로 교체 가능)
- **벡터 DB**: Chroma (로컬 영속화 — `data/chroma`)
- **메타데이터 DB**: SQLite + SQLAlchemy (`data/metadata.db`)
- **선택 기능**: Tavily 웹 검색(자기 점검 보강용)

## 디렉터리 구조

```
src/
├── main.py              # Streamlit 앱 엔트리포인트. 단계(phase)별 UI 핸들러 라우팅
├── config.py            # pydantic-settings 기반 환경설정 (.env 로드)
├── models.py            # ProjectCard, SimilarityResult, CrossInsight,
│                        # AnalysisReport, SelfCheckReport 등 도메인 스키마
├── session.py           # Streamlit ↔ LangGraph 상태 동기화, thread 관리, run_graph()
├── sample_data.py       # 데모용 샘플 기획안 로더
├── sample_data.json     # 초기 적재되는 샘플 프로젝트 데이터
│
├── agent/               # LLM 에이전트 / LangGraph 그래프
│   ├── graph.py         # chat_graph 정의 (Streamlit용 대화형, interrupt 기반):
│   │                    #   greeting → wait_input → extract → check_missing →
│   │                    #   (ask_question | self_check) → confirm →
│   │                    #   embed_and_store → search_similar →
│   │                    #   cross_insights → mentoring
│   ├── conversation.py  # 대화 흐름 보조 유틸 (가시성에 따른 임베딩 텍스트 등)
│   ├── prompts.py       # prompts.toml 로더 (STRUCTURE / EXTRACT / SELF_CHECK /
│   │                    # SIMILARITY / CROSS_INSIGHT / MENTORING / GREETING …)
│   └── prompts.toml     # 모든 프롬프트 템플릿이 모인 단일 소스
│
├── core/                # LLM·임베딩·파싱 등 저수준 클라이언트
│   ├── llm.py           # ChatOpenAI 팩토리 (api_base 교체 가능)
│   ├── embedding.py     # OpenAIEmbeddings 팩토리 (API key 미설정 시 zero-vector)
│   └── parser.py        # LLM JSON 응답 파서 (코드펜스 제거 + 재시도)
│
├── db/                  # 영속 계층
│   ├── metadata_store.py# SQLite + SQLAlchemy로 ProjectCard CRUD
│   └── vector_store.py  # Chroma 컬렉션(코사인) — add/search/count
│
├── service/             # 비즈니스 로직 (그래프 노드에서 호출)
│   ├── analyzer.py      # 임베딩 텍스트 생성, 유사도 분석,
│   │                    # Cross-Insight 생성, 멘토링 요약 생성
│   ├── checker.py       # 자기 점검 리포트 (선택적으로 Tavily 웹 검색 보강)
│   └── trend.py         # 등록 기획안의 도메인/타겟층 분포 트렌드 분석
│
└── ui/                  # Streamlit 화면 (graph_phase별 분기)
    ├── chat.py          # 'collecting' 단계 — 챗봇 입력 화면
    ├── confirm.py       # 'confirming' 단계 — 카드 확인·저장·공개 범위 선택
    ├── report.py        # 'analyzing' / 'done' 단계 — 유사도 리포트, Cross-Insight,
    │                    # 멘토링 1분 요약·예상 질문
    ├── list_view.py     # 'list' 단계 — 등록된 기획안 목록
    ├── trend.py         # 'trend' 단계 — 트렌드 대시보드
    └── sidebar.py       # 사이드바 — 단계 전환·세션 리셋
```

## 데이터 플로우 (대화형 그래프)

1. **greeting** — 새 ProjectCard 생성, 인사말 출력
2. **wait_input → extract_fields** — 사용자 답변을 LLM이 카드 필드로 구조화
3. **check_missing** — 필수 항목 누락 시 `ask_question`으로 다음 질문 생성, 그렇지 않으면 자기 점검
4. **self_check → confirm** — 사용자에게 카드 확인·공개 범위(요약/전체) 선택을 받음
5. **embed_and_store** — 가시성에 맞춰 임베딩 텍스트 생성 → Chroma + SQLite 저장
6. **search_similar** — 벡터 검색 후 LLM이 항목별(문제/대상/해결/기술) 점수와 위험도(High/Medium/Low) 산출
7. **cross_insights** — 유사 팀과의 조합으로 파생 아이디어 생성
8. **mentoring** — 1분 설명문, 차별화 포인트, 예상 질문 생성

## Docker로 실행하기

### 사전 준비

- Docker / Docker Compose 설치
- `.env.example`을 참고하여 프로젝트 루트에 `.env` 파일 생성

```bash
cp .env.example .env
```

`.env` 파일을 열고 `OPENAI_API_KEY`(Upstage API 키)를 채워 넣습니다.
Docker Compose에서는 `CHROMA_HOST`/`CHROMA_PORT`가 컨테이너 환경변수로 자동 주입(`chromadb:8000`)되므로 `.env`의 값은 그대로 두어도 됩니다.

### 빌드 및 실행

프로젝트 루트(`compose.yml`이 있는 위치)에서:

```bash
docker compose up --build
```

- `chromadb` 서비스가 먼저 기동되며 healthcheck를 통과하면 `app` 서비스(Streamlit)가 시작됩니다.
- 데이터는 `./data` 디렉터리에 영속됩니다.

### Streamlit 데모 접속

브라우저에서 다음 주소로 접속합니다:

```
http://localhost:8501
```

(ChromaDB는 호스트 기준 `http://localhost:8001`로 노출됩니다.)

### 종료

```bash
docker compose down
```

데이터까지 함께 삭제하려면 `./data` 디렉터리를 직접 제거하세요.
