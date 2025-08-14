import sqlite3
from contextlib import closing
from datetime import datetime
import pandas as pd
import streamlit as st

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="IdeaShelf", page_icon="📚", layout="wide")

DB_PATH = "books.db"

# -----------------------------
# DB 함수
# -----------------------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                author TEXT,
                genre TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                nickname TEXT,
                rating INTEGER,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reviews_book ON reviews(book_id);")

def seed_books():
    # 초기 샘플 데이터 (원하시면 자유롭게 수정/추가)
    sample = [
        # 소설
        ("82년생 김지영", "조남주", "소설"),
        ("채식주의자", "한강", "소설"),
        ("소년이 온다", "한강", "소설"),
        ("아몬드", "손원평", "소설"),
        ("용의자 x의 헌신", "히가시노 게이고", "소설"),
        # 에세이
        ("무례한 사람에게 웃으며 대처하는 법", "정문정", "에세이"),
        ("여덟 단어", "박웅현", "에세이"),
        ("아침에 일어나면 꼭 해야 할 일들", "김민식", "에세이"),
        # 과학
        ("코스모스", "칼 세이건", "과학"),
        ("빅 히스토리", "데이비드 크리스천", "과학"),
        ("세상은 수학이다", "최재천·김민형", "과학"),
        # 역사
        ("역사의 역사", "유시민", "역사"),
        ("거꾸로 읽는 세계사", "유시민", "역사"),
        ("지리의 힘", "팀 마샬", "역사"),
        # 자기계발
        ("아주 작은 습관의 힘", "제임스 클리어", "자기계발"),
        ("미라클 모닝", "할 엘로드", "자기계발"),
    ]
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        for title, author, genre in sample:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO books(title, author, genre) VALUES(?,?,?)",
                    (title, author, genre),
                )
            except sqlite3.IntegrityError:
                pass

def get_genres():
    with closing(get_conn()) as conn:
        df = pd.read_sql_query("SELECT DISTINCT genre FROM books ORDER BY genre", conn)
    return df["genre"].tolist()

def get_books_by_genre(genre):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT id, title, author, genre FROM books WHERE genre=? ORDER BY title",
            conn, params=(genre,),
        )

def search_books(q):
    like = f"%{q}%"
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            """
            SELECT id, title, author, genre
            FROM books
            WHERE title LIKE ? OR author LIKE ?
            ORDER BY title
            """,
            conn, params=(like, like),
        )

def get_book(book_id:int):
    with closing(get_conn()) as conn:
        df = pd.read_sql_query(
            "SELECT id, title, author, genre FROM books WHERE id=?",
            conn, params=(book_id,),
        )
    return df.iloc[0].to_dict() if not df.empty else None

def add_book(title, author, genre):
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO books(title, author, genre) VALUES(?,?,?)",
                  (title.strip(), author.strip() if author else "", genre.strip()))
        # 방금 넣은(또는 기존) id 반환
        row = pd.read_sql_query("SELECT id FROM books WHERE title=?", conn, params=(title.strip(),))
    return int(row.iloc[0]["id"])

def get_reviews(book_id:int):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            """
            SELECT id, nickname, rating, content, created_at
            FROM reviews
            WHERE book_id=?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            conn, params=(book_id,),
        )

def add_review(book_id:int, nickname, rating, content):
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO reviews(book_id, nickname, rating, content, created_at)
            VALUES(?,?,?,?,?)
            """,
            (book_id, nickname.strip() if nickname else "익명", int(rating) if rating else None, content.strip(),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

# -----------------------------
# 유틸 / 스타일
# -----------------------------
def stars(n):
    try:
        n = int(n)
        return "⭐" * n + "☆" * (5 - n)
    except Exception:
        return "평점 없음"

def card(title, body, footer=None):
    st.markdown(
        f"""
        <div style="
            border:1px solid #e5e7eb;
            border-radius:16px;
            padding:16px;
            margin-bottom:10px;
            background:white;
            ">
            <div style="font-weight:700;font-size:18px;margin-bottom:6px;">{title}</div>
            <div style="color:#374151; line-height:1.5;">{body}</div>
            {f'<div style="margin-top:8px;color:#6b7280;font-size:12px;">{footer}</div>' if footer else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def book_row(b):
    left, right = st.columns([6,1])
    with left:
        st.markdown(f"**{b['title']}** · {b['author'] if b['author'] else '작자 미상'}  \n`{b['genre']}`")
    with right:
        if st.button("자세히", key=f"book_{b['id']}"):
            st.session_state.page = "detail"
            st.session_state.current_book_id = int(b["id"])

# -----------------------------
# 초기화
# -----------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_book_id" not in st.session_state:
    st.session_state.current_book_id = None

init_db()
seed_books()

# -----------------------------
# 사이드바
# -----------------------------
with st.sidebar:
    st.markdown("## 📚IdeaShelf")
    st.caption("장르별 탐색 · 통합 검색 · 감상평 작성/열람")

    search_q = st.text_input("🔎 책 제목/저자 검색", placeholder="예) 아몬드, 한강, 유시민 ...")
    if search_q:
        st.session_state.page = "search"

    st.markdown("---")
    try:
        genres = get_genres()
    except Exception:
        genres = []
    genre_sel = st.selectbox("🎨 장르 선택", options=["(선택)"] + genres, index=0)
    if genre_sel != "(선택)":
        st.session_state.page = "browse"
        st.session_state.selected_genre = genre_sel

    st.markdown("---")
    st.markdown("### ➕ 도서 직접 추가")
    with st.form("add_book_form", clear_on_submit=True):
        nb_title = st.text_input("책 제목")
        nb_author = st.text_input("저자(선택)")
        nb_genre = st.text_input("장르(예: 소설, 에세이, 과학...)")
        submitted = st.form_submit_button("추가")
        if submitted:
            if not nb_title or not nb_genre:
                st.warning("제목과 장르는 필수입니다.")
            else:
                new_id = add_book(nb_title, nb_author, nb_genre)
                st.success(f"도서가 등록되었습니다: {nb_title}")
                st.session_state.page = "detail"
                st.session_state.current_book_id = new_id

# -----------------------------
# 메인 레이아웃 - 헤더
# -----------------------------
st.markdown(
    """
    <style>
    .title-area{display:flex;align-items:center;gap:10px;}
    .badge{padding:4px 10px;border-radius:999px;background:#f3f4f6;color:#374151;font-size:12px;}
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown('<div class="title-area"><h1 style="margin:0">📖IdeaShelf</h1><span class="badge">Streamlit</span></div>', unsafe_allow_html=True)
st.caption("IdeaShelf에서 도서에 대한 아이디어를 전 세계 사람들과 공유하세요!")

# -----------------------------
# 페이지: 홈
# -----------------------------
def render_home():
    st.subheader("시작하기")
    c1, c2, c3 = st.columns(3)

    with c1:
        card("1) 장르 고르기", "왼쪽 사이드바에서 **장르**를 선택하면 해당 장르의 책 목록이 보여요.")
    with c2:
        card("2) 검색하기", "상단 검색창에 **제목/저자**를 입력하면 통합 검색이 가능합니다.")
    with c3:
        card("3) 감상 남기기", "책 상세 페이지에서 **닉네임·평점·감상평**을 작성해 게시해보세요.")

    st.subheader("인기 장르 둘러보기")
    # 인기 장르: 테이블로 가볍게 노출
    gdf = pd.DataFrame({"장르": get_genres()})
    st.dataframe(gdf, use_container_width=True, hide_index=True)

# -----------------------------
# 페이지: 장르별 탐색
# -----------------------------
def render_browse(genre):
    st.subheader(f"장르: {genre}")
    df = get_books_by_genre(genre)
    if df.empty:
        st.info("해당 장르에 등록된 책이 아직 없습니다. 사이드바에서 도서를 직접 추가할 수 있어요.")
        return
    for _, row in df.iterrows():
        book_row(row)

# -----------------------------
# 페이지: 검색 결과
# -----------------------------
def render_search(q):
    st.subheader(f"검색: “{q}”")
    df = search_books(q)
    if df.empty:
        st.warning("검색 결과가 없습니다. 정확한 제목/저자를 다시 시도하거나, 사이드바에서 도서를 직접 추가해보세요.")
        return
    for _, row in df.iterrows():
        book_row(row)

# -----------------------------
# 페이지: 책 상세 + 감상평
# -----------------------------
def render_detail(book_id:int):
    book = get_book(book_id)
    if not book:
        st.error("도서를 찾을 수 없습니다.")
        return

    st.markdown(f"### {book['title']}")
    st.markdown(f"- 저자: **{book['author'] or '작자 미상'}**  \n- 장르: `{book['genre']}`")

    st.markdown("---")
    st.markdown("#### ✍️ 감상평 작성")
    with st.form(key=f"review_form_{book_id}", clear_on_submit=True):
        col1, col2 = st.columns([2,1])
        with col1:
            nickname = st.text_input("닉네임 (미입력 시 '익명')", value="")
        with col2:
            rating = st.slider("평점", min_value=1, max_value=5, value=5)
        content = st.text_area("감상평", placeholder="자유롭게 생각과 느낌을 적어주세요.", height=140)
        submit = st.form_submit_button("게시")
        if submit:
            if not content.strip():
                st.warning("감상평을 입력해주세요.")
            else:
                add_review(book_id, nickname, rating, content)
                st.success("감상평이 등록되었습니다!")
                st.experimental_rerun()

    st.markdown("---")
    st.markdown("#### 🗂️ 감상평 모아보기")
    rdf = get_reviews(book_id)
    if rdf.empty:
        st.info("아직 등록된 감상평이 없습니다. 첫 감상평을 남겨보세요!")
    else:
        st.caption(f"총 {len(rdf)}개")
        for _, r in rdf.iterrows():
            header = f"{r['nickname'] or '익명'} · {stars(r['rating'])}"
            card(header, r["content"].replace("\n", "<br>"),
                 footer=r["created_at"])

# -----------------------------
# 라우팅
# -----------------------------
page = st.session_state.page
if page == "home":
    render_home()
elif page == "browse":
    render_browse(st.session_state.get("selected_genre", None) or "")
elif page == "search":
    if search_q:
        render_search(search_q)
    else:
        st.info("검색어를 입력해주세요.")
elif page == "detail":
    if st.session_state.current_book_id:
        if st.button("← 목록으로", use_container_width=False):
            # 이전 페이지로 대략 이동(장르 선택이 있으면 browse, 없으면 home)
            if st.session_state.get("selected_genre"):
                st.session_state.page = "browse"
            else:
                st.session_state.page = "home"
            st.experimental_rerun()
        render_detail(st.session_state.current_book_id)
    else:
        st.info("먼저 책을 선택해주세요.")
else:
    render_home()

