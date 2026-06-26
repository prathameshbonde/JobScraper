import os
import io
import sys
import yaml
import shutil
from contextlib import redirect_stdout
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 1. Establish project root context
# Switch working directory to project root (parent of ui/) to ensure relative paths
# for resume.tex, prompts/, config.yaml, and python imports resolve correctly.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

# Append project root to sys.path to allow importing rewriter and compiler
if project_root not in sys.path:
    sys.path.append(project_root)

# Load local environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from rewriter import generate_tailored_resume
from compiler import compile_resume

app = FastAPI(title="AI Resume Tailoring Suite")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File Paths (relative to project root)
RESUME_PATH = "resume.tex"
CONFIG_PATH = "config.yaml"
PROMPTS_DIR = "prompts"
TAILORED_PDF_PATH = "Resume_Tailored.pdf"
TAILORED_TEX_PATH = "Resume_Tailored.tex"

# Static Directory (relative to script location)
STATIC_DIR = os.path.join(script_dir, "static")

# Pydantic schemas
class TailorRequest(BaseModel):
    job_description: str
    model_name: str = None

class SaveConfigRequest(BaseModel):
    file_type: str  # 'resume', 'summary_prompt', 'skills_prompt', 'experience_prompt'
    content: str

def read_file_content(path, default=""):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return default

def write_file_content(path, content):
    # Create backup first if file exists
    if os.path.exists(path):
        backup_path = f"{path}.bak"
        shutil.copy2(path, backup_path)
    
    # Ensure parent directories exist
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

@app.get("/api/config")
def get_config():
    # Read resume.tex
    resume_content = read_file_content(RESUME_PATH)
    
    # Read prompts
    summary_prompt = read_file_content(os.path.join(PROMPTS_DIR, "summary_prompt.md"))
    skills_prompt = read_file_content(os.path.join(PROMPTS_DIR, "skills_prompt.md"))
    experience_prompt = read_file_content(os.path.join(PROMPTS_DIR, "experience_prompt.md"))
    
    # Read config.yaml for model list / default model
    default_model = "gemini-2.0-flash"
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config_data = yaml.safe_load(f)
                default_model = config_data.get("gemini_settings", {}).get("model_name", "gemini-2.0-flash")
        except Exception:
            pass
            
    return {
        "resume": resume_content,
        "summary_prompt": summary_prompt,
        "skills_prompt": skills_prompt,
        "experience_prompt": experience_prompt,
        "default_model": default_model,
        "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro"]
    }

@app.post("/api/save-config")
def save_config(req: SaveConfigRequest):
    if req.file_type == "resume":
        target_path = RESUME_PATH
    elif req.file_type == "summary_prompt":
        target_path = os.path.join(PROMPTS_DIR, "summary_prompt.md")
    elif req.file_type == "skills_prompt":
        target_path = os.path.join(PROMPTS_DIR, "skills_prompt.md")
    elif req.file_type == "experience_prompt":
        target_path = os.path.join(PROMPTS_DIR, "experience_prompt.md")
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
        
    try:
        write_file_content(target_path, req.content)
        return {"status": "success", "message": f"Successfully saved {req.file_type}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

@app.post("/api/tailor")
def tailor_resume(req: TailorRequest):
    if not req.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")
        
    # Read master resume
    master_latex = read_file_content(RESUME_PATH)
    if not master_latex:
        raise HTTPException(status_code=404, detail="Master resume.tex template not found")
        
    model = req.model_name or "gemini-2.0-flash"
    
    # Redirect stdout to capture logs
    log_capture = io.StringIO()
    tailored_latex = ""
    compilation_success = False
    
    print("[SERVER] [INFO] Initiating ad-hoc resume tailoring process...")
    try:
        with redirect_stdout(log_capture):
            # Tailor LaTeX
            tailored_latex = generate_tailored_resume(master_latex, req.job_description, model_name=model)
            
            # Save tailored LaTeX to disk
            with open(TAILORED_TEX_PATH, "w", encoding="utf-8") as f:
                f.write(tailored_latex)
            print(f"[SERVER] [INFO] Saved tailored LaTeX source to '{TAILORED_TEX_PATH}'")
            
            # Compile tailored LaTeX into PDF
            compilation_success = compile_resume(tailored_latex, TAILORED_PDF_PATH)
            
    except Exception as e:
        import traceback
        traceback.print_exc(file=log_capture)
        print(f"[SERVER] [ERROR] Tailoring failed: {str(e)}")
        
    logs = log_capture.getvalue()
    
    return {
        "status": "success" if (tailored_latex and compilation_success) else "partial_success" if tailored_latex else "failed",
        "tailored_latex": tailored_latex,
        "compilation_success": compilation_success,
        "logs": logs
    }

@app.get("/api/download-pdf")
def download_pdf():
    if os.path.exists(TAILORED_PDF_PATH):
        return FileResponse(
            path=TAILORED_PDF_PATH,
            filename="Resume_Tailored.pdf",
            media_type="application/pdf"
        )
    raise HTTPException(status_code=404, detail="Tailored PDF file not found. Run tailoring first.")

# Serve index.html statically from root route
@app.get("/")
def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Frontend files not found. Please create the static/ index.html, style.css, and app.js files.</h2>")

# Mount the static directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    # Load port/host configurations from environment or default
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting resume tailoring server at http://{host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=True)
