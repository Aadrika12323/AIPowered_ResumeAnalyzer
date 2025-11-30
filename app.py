import os
import json
import fitz  # PyMuPDF
from dotenv import load_dotenv
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
from groq import Groq

# Load .env file
load_dotenv()

app = Flask(__name__)

# Load Groq API key
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY)


# ---------------------------------------------------------
# 1. FIXED PDF TEXT EXTRACTION (NO PERMISSION ERROR)
# ---------------------------------------------------------
def extract_text_from_pdf(pdf_file):
    try:
        # Always save inside project folder, not temp
        os.makedirs("uploads", exist_ok=True)

        save_path = os.path.join("uploads", "uploaded_resume.pdf")
        pdf_file.save(save_path)

        text = ""
        doc = fitz.open(save_path)

        for page in doc:
            text += page.get_text()

        return text

    except Exception as e:
        print("PDF Extract Error:", e)
        return ""
    

# ---------------------------------------------------------
# 2. SKILL EXTRACTION USING CORRECT GROQ MODEL
# ---------------------------------------------------------
def extract_skills(text, source):
    prompt = f"""
    Extract all technical and soft skills from this {source}.
    Return ONLY valid JSON in this EXACT format:

    {{
        "skills": ["skill1", "skill2", "skill3"]
    }}

    Text:
    {text}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # CORRECT MODEL
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON output
        data = json.loads(content)
        return data.get("skills", [])

    except Exception as e:
        print("GROQ ERROR:", e)
        return []


# ---------------------------------------------------------
# 3. ANALYSIS LOGIC (ATS SCORE)
# ---------------------------------------------------------
def analyze_resume(resume_text, job_description):
    resume_skills = extract_skills(resume_text, "resume")
    jd_skills = extract_skills(job_description, "job description")

    matched = list(set(resume_skills) & set(jd_skills))
    missing = list(set(jd_skills) - set(resume_skills))

    score = int((len(matched) / len(jd_skills)) * 100) if jd_skills else 0

    return resume_skills, jd_skills, matched, missing, score


# ---------------------------------------------------------
# 4. ROUTES
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        resume_file = request.files["resume"]
        job_description = request.form["job_description"]

        # Extract text safely
        resume_text = extract_text_from_pdf(resume_file)

        print("Extracted Resume Text Length:", len(resume_text))

        # Run ATS analysis
        resume_skills, jd_skills, matched, missing, score = analyze_resume(
            resume_text, job_description
        )

        return render_template(
            "result.html",
            score=score,
            resume_skills=resume_skills,
            jd_skills=jd_skills,
            matched=matched,
            missing=missing
        )

    except Exception as e:
        print("UNEXPECTED ERROR:", e)
        return render_template("result.html", error="Unexpected error occurred.")


# ---------------------------------------------------------
# 5. RUN APP
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
