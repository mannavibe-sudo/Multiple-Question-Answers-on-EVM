# 🗳️ EVM Online Exam (Python + Streamlit)

Name, Designation, Mobile, District, Email lekar 40 MCQ puchta hai, result + PDF report banata hai.

## Files
| File | Kaam |
|---|---|
| `app.py` | Poora exam app |
| `questions.json` | 40 questions, options, sahi answer |
| `parse_docx.py` | Word file se `questions.json` dobara banane ke liye |
| `requirements.txt` | Python packages |

## Local mein chalana
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + free hosting (Streamlit Community Cloud)
1. GitHub par naya repo banayein aur ye saari files upload/push karein.
2. https://share.streamlit.io par GitHub se login karein → **New app** → repo chunein → Main file: `app.py` → **Deploy**.
3. App ke **Settings → Secrets** mein ye daalein (admin page ke liye):
   ```
   ADMIN_PASSWORD = "apna-password"
   ```
4. Exam link sab ko bhej dein. Sabke results dekhne ke liye link ke aage `?page=admin` lagayein.

## Features
- Registration validation (10 digit mobile, valid email)
- Ek mobile number se ek hi attempt
- Result: score, % , PASS/FAIL (pass % `app.py` mein `PASS_PERCENT` se badlein)
- Question-wise report, PDF + CSV download
- Admin page: sabhi candidates ka data, district-wise average, CSV download

## Dhyan dein
Streamlit Cloud par `data/results.db` app restart/redeploy hone par mit sakti hai.
Isliye exam ke dauran/baad mein admin page se CSV download karte rahein (admin page > Download all results).
Pakka storage chahiye to Google Sheets ya database jodna padega.
