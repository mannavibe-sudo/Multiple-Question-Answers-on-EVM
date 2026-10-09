"""EVM Online Exam - Streamlit app
Run:  streamlit run app.py
"""
import hmac
import json
import re
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from fpdf import FPDF

BASE = Path(__file__).parent
QUESTIONS = json.loads((BASE / "questions.json").read_text(encoding="utf-8"))
DB_FILE = BASE / "data" / "results.db"
DB_FILE.parent.mkdir(exist_ok=True)

TITLE = "EVM Knowledge Test"
PASS_PERCENT = 60  # pass marks % (badal sakte hain)
LABELS = "ABCD"

st.set_page_config(page_title=TITLE, page_icon="🗳️", layout="centered")


# ---------------------------------------------------------------- helpers
def valid_mobile(m: str) -> bool:
    return bool(re.fullmatch(r"[6-9]\d{9}", m))


def valid_email(e: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e))


def db():
    """SQLite connection. Mobile is PRIMARY KEY and Email is UNIQUE, so one mobile /
    one email can never have two attempts, even if many people submit together."""
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS results (
        Mobile TEXT PRIMARY KEY, Timestamp TEXT, Name TEXT, Designation TEXT,
        District TEXT, Email TEXT UNIQUE, Score INT, Total INT, Percent REAL,
        Correct INT, Wrong INT, "Not Attempted" INT, Result TEXT)""")
    return con


def load_results() -> pd.DataFrame:
    con = db()
    try:
        return pd.read_sql_query("SELECT * FROM results ORDER BY Timestamp", con)
    finally:
        con.close()


def used_fields(mobile: str, email: str) -> list:
    """Returns which of mobile / email were already used for an attempt."""
    con = db()
    try:
        out = []
        if con.execute("SELECT 1 FROM results WHERE Mobile=?", (mobile,)).fetchone():
            out.append("Mobile number")
        if con.execute("SELECT 1 FROM results WHERE Email=?", (email.lower(),)).fetchone():
            out.append("Email ID")
        return out
    finally:
        con.close()


def evaluate(answers: dict) -> dict:
    """answers: {question_id: selected_index or None}"""
    rows, correct, wrong, skipped = [], 0, 0, 0
    for q in QUESTIONS:
        sel = answers.get(q["id"])
        if sel is None:
            status, skipped = "Not Attempted", skipped + 1
        elif sel == q["answer"]:
            status, correct = "Correct", correct + 1
        else:
            status, wrong = "Wrong", wrong + 1
        rows.append({
            "No": q["id"],
            "Question": q["question"],
            "Your Answer": "-" if sel is None else f'{LABELS[sel]}. {q["options"][sel]}',
            "Correct Answer": f'{LABELS[q["answer"]]}. {q["options"][q["answer"]]}',
            "Status": status,
        })
    total = len(QUESTIONS)
    pct = round(correct * 100 / total, 2)
    return {
        "rows": rows, "correct": correct, "wrong": wrong, "skipped": skipped,
        "total": total, "percent": pct,
        "result": "PASS" if pct >= PASS_PERCENT else "FAIL",
    }


def save_result(user: dict, res: dict) -> bool:
    """True = saved, False = this mobile/email has already attempted."""
    con = db()
    try:
        with con:
            con.execute(
                "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user["Mobile"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 user["Name"], user["Designation"], user["District"], user["Email"].lower(),
                 res["correct"], res["total"], res["percent"],
                 res["correct"], res["wrong"], res["skipped"], res["result"]))
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def pdf_safe(text: str) -> str:
    text = str(text).replace("…", "...").replace("–", "-").replace("’", "'")
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(user: dict, res: dict) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, pdf_safe(f"{TITLE} - Result Report"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    for k, v in user.items():
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(40, 7, pdf_safe(k + ":"))
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, pdf_safe(v), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(40, 7, "")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, pdf_safe(
        f"Score: {res['correct']}/{res['total']}  |  {res['percent']}%  |  {res['result']}"),
        new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, pdf_safe(
        f"Correct: {res['correct']}   Wrong: {res['wrong']}   Not attempted: {res['skipped']}"),
        new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, pdf_safe(f"Date: {datetime.now():%d-%m-%Y %H:%M}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Question-wise Report", new_x="LMARGIN", new_y="NEXT")
    for r in res["rows"]:
        if pdf.get_y() > 255:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(0, 5.5, pdf_safe(f"Q{r['No']}. {r['Question']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.5, pdf_safe(f"Your answer: {r['Your Answer']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 5.5, pdf_safe(f"Correct answer: {r['Correct Answer']}"), new_x="LMARGIN", new_y="NEXT")
        color = {"Correct": (0, 130, 0), "Wrong": (200, 0, 0)}.get(r["Status"], (110, 110, 110))
        pdf.set_text_color(*color)
        pdf.cell(0, 5.5, r["Status"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
    return bytes(pdf.output())


# ---------------------------------------------------------------- pages
def page_register():
    st.title("🗳️ " + TITLE)
    st.caption(f"{len(QUESTIONS)} multiple choice questions • Pass marks: {PASS_PERCENT}% "
               "• Each mobile number and email ID can be used only once.")
    with st.form("register"):
        name = st.text_input("Name *")
        designation = st.text_input("Designation *")
        mobile = st.text_input("Mobile *", max_chars=10, placeholder="10 digit mobile number")
        district = st.text_input("District Name *")
        email = st.text_input("Email ID *")
        go = st.form_submit_button("Start Exam", type="primary")

    if go:
        name, designation, district = name.strip(), designation.strip(), district.strip()
        mobile, email = mobile.strip(), email.strip()
        errors = []
        if not name: errors.append("Please enter your Name.")
        if not designation: errors.append("Please enter your Designation.")
        if not valid_mobile(mobile): errors.append("Please enter a valid 10 digit Mobile number.")
        if not district: errors.append("Please enter your District Name.")
        if not valid_email(email): errors.append("Please enter a valid Email ID.")
        if not errors:
            for f in used_fields(mobile, email):
                errors.append(f"This {f} has already been used to take the exam.")
        if errors:
            for e in errors:
                st.error(e)
            return
        st.session_state.user = {
            "Name": name, "Designation": designation, "Mobile": mobile,
            "District": district, "Email": email,
        }
        st.session_state.stage = "quiz"
        st.rerun()


def page_quiz():
    u = st.session_state.user
    st.title("🗳️ " + TITLE)
    st.info(f"**{u['Name']}** • {u['Designation']} • {u['District']}")
    st.caption("Select one answer for each question, then press Submit at the bottom. "
               "You can submit only once.")

    with st.form("quiz"):
        for q in QUESTIONS:
            st.markdown(f"**Q{q['id']}. {q['question']}**")
            st.radio(
                "Select one", options=range(len(q["options"])),
                format_func=lambda i, q=q: f"{LABELS[i]}. {q['options'][i]}",
                index=None, key=f"q_{q['id']}", label_visibility="collapsed",
            )
            st.divider()
        submit = st.form_submit_button("Submit Exam", type="primary")

    if submit:
        answers = {q["id"]: st.session_state.get(f"q_{q['id']}") for q in QUESTIONS}
        res = evaluate(answers)
        if not save_result(u, res):
            st.error("This Mobile number or Email ID has already been used to take the exam.")
            return
        st.session_state.res = res
        st.session_state.stage = "result"
        st.rerun()


def page_result():
    """Candidate sees ONLY his/her own result (from session) - nobody else's."""
    u, res = st.session_state.user, st.session_state.res
    st.title("📊 Your Result")
    (st.success if res["result"] == "PASS" else st.error)(
        f"{u['Name']} - {res['result']} ({res['percent']}%)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Score", f"{res['correct']}/{res['total']}")
    c2.metric("Correct", res["correct"])
    c3.metric("Wrong", res["wrong"])
    c4.metric("Not Attempted", res["skipped"])

    df = pd.DataFrame(res["rows"])
    st.subheader("Question-wise Report")
    st.dataframe(
        df.style.map(
            lambda s: {"Correct": "background-color:#d4edda",
                       "Wrong": "background-color:#f8d7da"}.get(s, ""),
            subset=["Status"]),
        hide_index=True, width="stretch")

    st.download_button("Download PDF Report", build_pdf(
        {k: u[k] for k in ("Name", "Designation", "Mobile", "District", "Email")}, res),
        file_name=f"EVM_Result_{u['Mobile']}.pdf", mime="application/pdf")


def to_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Results")
    return buf.getvalue()


def page_admin():
    st.title("🔐 Admin Dashboard")
    try:
        admin_pw = st.secrets["ADMIN_PASSWORD"]
    except Exception:
        st.warning("ADMIN_PASSWORD is not set in Secrets (see README).")
        return
    if not st.session_state.get("admin_ok"):
        with st.form("admin_login"):
            pw = st.text_input("Admin Password", type="password")
            ok = st.form_submit_button("Login", type="primary")
        if ok:
            if hmac.compare_digest(pw, str(admin_pw)):
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Wrong password.")
        return

    df = load_results()
    if df.empty:
        st.info("No results yet.")
        return
    df = df.rename(columns={"Percent": "Percent (%)"})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Candidates", len(df))
    c2.metric("Pass", int((df["Result"] == "PASS").sum()))
    c3.metric("Fail", int((df["Result"] == "FAIL").sum()))
    c4.metric("Average %", round(df["Percent (%)"].mean(), 2))

    f1, f2 = st.columns(2)
    district = f1.selectbox("District", ["All"] + sorted(df["District"].unique()))
    search = f2.text_input("Search (name / mobile / email)")
    view = df if district == "All" else df[df["District"] == district]
    if search.strip():
        t = search.strip().lower()
        view = view[view[["Name", "Mobile", "Email"]].astype(str).apply(
            lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)]

    cols = ["Name", "Designation", "Mobile", "District", "Email", "Score", "Total",
            "Percent (%)", "Result", "Correct", "Wrong", "Not Attempted", "Timestamp"]
    view = view[cols].reset_index(drop=True)
    view.index += 1
    st.dataframe(view, width="stretch")
    st.caption(f"Showing {len(view)} of {len(df)} candidates")

    st.download_button("Download Results (Excel)", to_excel(view),
                       file_name="EVM_All_Results.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.button("Logout"):
        st.session_state.admin_ok = False
        st.rerun()


# ---------------------------------------------------------------- router
if st.query_params.get("page") == "admin":   # URL: <app link>/?page=admin
    page_admin()
else:
    st.session_state.setdefault("stage", "register")
    {"register": page_register, "quiz": page_quiz, "result": page_result}[st.session_state.stage]()
