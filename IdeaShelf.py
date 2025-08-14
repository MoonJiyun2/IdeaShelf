import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from PIL import Image
import os

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="IdeaShelf", page_icon="📚", layout="wide")
DB_PATH = "books.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------
# DB 함수
# -----------------------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                author TEXT,
                genre TEXT NOT NULL,
                cover_path TEXT
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                parent_id INTEGER,
                nickname TEXT,
                rating INTEGER,
                content TEXT NOT NULL,
                likes INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );
        """)
        conn.commit()

def seed_books():
    sample = [
        ("82년생 김지영", "조남주", "소설", None),
        ("채식주의자", "한강", "소설", None),
        ("무례한 사람에게 웃으며 대처하는 법", "정문정", "에세이", None),
        ("코스모스", "칼 세이건", "과학", None),
        ("역사의 역사", "유시민", "역사", None),
    ]
    with get_conn() as conn:
        c = conn.cursor()
        for title, author, genre, cover_path in sample:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO books(title, author, genre, cover_path) VALUES(?,?,?,?)",
                    (title, author, genre, cover_path)
                )
            except sqlite3.Error as e:
                print(f"DB 삽입 오류: {e}")
        conn.commit()

def get_genres():
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT DISTINCT genre FROM books ORDER BY genre", conn)
    return df["genre"].tolist()

def get_books_by_genre(genre):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM books WHERE genre=? ORDER BY title",
            conn, params=(genre,)
        )

def search_books(q):
    like = f"%{q}%"
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title",
            conn, params=(like, like)
        )

def get_book(book_id:int):
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM books WHERE id=?", conn, params=(book_id,))
    return df.iloc[0].to_dict() if not df.empty else None

def add_book(title, author, genre, cover_file):
    cover_path = None
    if cover_file:
        img = Image.open(cover_file)
        cover_path = os.path.join(UPLOAD_DIR, f"{datetime.now().timestamp()}_{cover_file.name}")
        img.save(cover_path)

    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO books(title, author, genre, cover_path) VALUES(?,?,?,?)",
            (title.strip(), author.strip() if author else "", genre.strip(), cover_path)
        )
        conn.commit()
        df = pd.read_sql_query("SELECT id FROM books WHERE title=?", conn, params=(title.strip(),))
    return int(df.iloc[0]["id"])

def get_reviews(book_id:int, parent_id=None):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM reviews WHERE book_id=? AND parent_id IS ? ORDER BY likes DESC, datetime(created_at) DESC",
            conn, params=(book_id, parent_id)
        )

def add_review(book_id:int, content, nickname=None, rating=5, parent_id=None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO reviews(book_id, parent_id, nickname, rating, content, created_at) VALUES(?,?,?,?,?,?)",
            (book_id, parent_id, nickname or "익명", rating, content.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

def like_review(review_id:int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE reviews SET likes = likes + 1 WHERE id=?", (review_id,))
        conn.commit()

# -----------------------------
# 유틸
# -----------------------------
def stars(n):
    return "⭐" * int(n) + "☆" * (5 - int(n))

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
    st.title("📚 IdeaShelf")

    search_q = st.text_input("🔍 검색", placeholder="책 제목 또는 저자")
    if search_q:
        st.session_state.page = "search"
        st.rerun()

    genres = get_genres()
    genre_sel = st.selectbox("🎨 장르 선택", ["(선택)"] + genres)
    if genre_sel != "(선택)":
        st.session_state.page = "browse"
        st.session_state.selected_genre = genre_sel
        st.rerun()

    st.markdown("---")
    st.subheader("➕ 도서 추가")
    with st.form("add_book_form", clear_on_submit=True):
        nb_title = st.text_input("책 제목")
        nb_author = st.text_input("저자")
        nb_genre = st.text_input("장르")
        cover_file = st.file_uploader("표지 이미지 업로드", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("등록")
        if submitted:
            if nb_title and nb_genre:
                new_id = add_book(nb_title, nb_author, nb_genre, cover_file)
                st.success(f"'{nb_title}' 등록 완료!")
                st.session_state.page = "detail"
                st.session_state.current_book_id = new_id
                st.rerun()
            else:
                st.warning("제목과 장르는 필수입니다.")

# -----------------------------
# 페이지 함수
# -----------------------------
def render_books(df):
    for _, b in df.iterrows():
        cols = st.columns([1, 3])
        with cols[0]:
            if b["cover_path"] and os.path.exists(b["cover_path"]):
                st.image(b["cover_path"], width=80)
            else:
                st.image("https://via.placeholder.com/80", width=80)
        with cols[1]:
            st.markdown(f"**{b['title']}** · {b['author'] or '작자 미상'}  \n`{b['genre']}`")
            if st.button("📖 자세히", key=f"book_{b['id']}"):
                st.session_state.page = "detail"
                st.session_state.current_book_id = int(b["id"])
                st.rerun()

def render_home():
    st.header("환영합니다! 📖")
    st.write("장르를 선택하거나 검색해 책을 찾아보세요.")

def render_browse(genre):
    st.header(f"장르: {genre}")
    df = get_books_by_genre(genre)
    render_books(df)

def render_search(q):
    st.header(f"검색: {q}")
    df = search_books(q)
    render_books(df)

def render_reviews(book_id, parent_id=None, level=0):
    reviews = get_reviews(book_id, parent_id)
    indent = "    " * level
    for _, r in reviews.iterrows():
        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(f"{indent}**{r['nickname']}** · {stars(r['rating'])}")
            st.write(indent + r["content"])
            st.caption(r["created_at"])
            # 대댓글 작성
            with st.expander(f"{indent}💬 답글 달기"):
                nickname = st.text_input(f"닉네임", value="", key=f"reply_nick_{r['id']}")
                content = st.text_area(f"답글 내용", key=f"reply_text_{r['id']}")
                if st.button(f"등록", key=f"reply_btn_{r['id']}"):
                    if content.strip():
                        add_review(book_id, content, nickname=nickname, rating=5, parent_id=r['id'])
                        st.success("답글 등록!")
                        st.rerun()
                    else:
                        st.warning("내용을 입력해주세요.")
        with cols[1]:
            if st.button(f"👍 {r['likes']}", key=f"like_{r['id']}"):
                like_review(r["id"])
                st.rerun()
        render_reviews(book_id, parent_id=r["id"], level=level+1)

def render_detail(book_id):
    book = get_book(book_id)
    if not book:
        st.error("책을 찾을 수 없습니다.")
        return

    st.subheader(f"{book['title']}")
    st.write(f"저자: {book['author'] or '작자 미상'}")
    st.write(f"장르: `{book['genre']}`")
    if book["cover_path"] and os.path.exists(book["cover_path"]):
        st.image(book["cover_path"], width=200)

    st.markdown("---")
    st.subheader("✍️ 감상평 작성")
    with st.form(f"review_form_{book_id}", clear_on_submit=True):
        nickname = st.text_input("닉네임", value="")
        rating = st.slider("평점", 1, 5, 5)
        content = st.text_area("감상평")
        submitted = st.form_submit_button("등록")
        if submitted:
            if content.strip():
                add_review(book_id, content, nickname=nickname, rating=rating)
                st.success("감상평이 등록되었습니다.")
                st.rerun()
           
