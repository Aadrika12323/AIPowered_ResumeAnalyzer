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
# 1. PDF TEXT EXTRACTION (PDF ONLY as you requested)
# ---------------------------------------------------------
def extract_text_from_pdf(pdf_file):
    try:
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
# 2. SKILL EXTRACTION USING GROQ
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
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        return data.get("skills", [])

    except Exception as e:
        print("GROQ ERROR:", e)
        return []


# ---------------------------------------------------------
# 3. ANALYSIS (ATS SCORE)
# ---------------------------------------------------------
def analyze_resume(resume_text, job_description):
    resume_skills = [s.lower() for s in extract_skills(resume_text, "resume")]
    jd_skills = [s.lower() for s in extract_skills(job_description, "job description")]

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



# --------------------- ATS ANALYZER ----------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        resume_file = request.files["resume"]
        job_description = request.form["job_description"]

        # Extract PDF text
        resume_text = extract_text_from_pdf(resume_file)

        resume_skills, jd_skills, matched, missing, score = analyze_resume(
            resume_text, job_description
        )

        return render_template(
            "result.html",
            score=score,
            required=jd_skills,
            matched=matched,
            missing=missing
        )

    except Exception as e:
        print("UNEXPECTED ERROR:", e)
        return render_template("result.html", error="Unexpected error occurred.")



# --------------------- RESUME COMPARISON ----------------------
@app.route("/compare", methods=["POST"])
def compare():
    try:
        resume1 = request.files["resume1"]
        resume2 = request.files["resume2"]

        # Extract PDF text from both resumes
        text1 = extract_text_from_pdf(resume1)
        text2 = extract_text_from_pdf(resume2)

        skills1 = extract_skills(text1, "Resume 1")
        skills2 = extract_skills(text2, "Resume 2")

        skills1 = [s.lower() for s in skills1]
        skills2 = [s.lower() for s in skills2]

        matched = sorted(list(set(skills1) & set(skills2)))
        missing_from_r2 = sorted(list(set(skills1) - set(skills2)))

        score = int((len(matched) / max(len(skills1), len(skills2))) * 100) if skills1 and skills2 else 0

        return render_template(
            "result.html",
            score=score,
            required=sorted(list(set(skills1 + skills2))),  # all skills involved
            matched=matched,                               # common skills
            missing=missing_from_r2                        # things R2 doesn't have
        )

    except Exception as e:
        print("COMPARE ERROR:", e)
        return render_template("result.html", error="Comparison failed.")



# ---------------------------------------------------------
# 5. RUN APP
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

