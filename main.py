import os
import sys
import json
import yaml
import time
from datetime import datetime

# Load local environment variables from a .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import fetch_and_filter_jobs
from rewriter import generate_tailored_resume
from compiler import compile_resume
from notifier import dispatch_daily_digest

def run_pipeline():
    start_time = time.time()
    print("======================================================================")
    print("      STARTING JOB ACQUISITION & AI RESUME TAILORING PIPELINE")
    print("======================================================================")
    print(f"[ORCHESTRATOR] [INFO] Pipeline started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 0. System Pre-flight Verification
    print("[ORCHESTRATOR] [INFO] Commencing Pre-flight asset verifications...")
    master_resume_path = "resume.tex"
    if not os.path.exists(master_resume_path):
        print(f"[ORCHESTRATOR] [CRITICAL] Baseline master file '{master_resume_path}' was not found in directory.")
        print("  - Troubleshooting: Please add your master LaTeX resume file 'resume.tex' in the project directory.")
        sys.exit(1)
        
    print(f"[ORCHESTRATOR] [INFO] Master template '{master_resume_path}' found. Loading content...")
    with open(master_resume_path, "r", encoding="utf-8") as f:
        master_latex = f.read()
        
    print(f"[ORCHESTRATOR] [INFO] Master file loaded successfully. Size: {len(master_latex)} characters.")
    
    # Verify marker comments exist to protect compilation safety
    print("[ORCHESTRATOR] [DEBUG] Verifying comment-tag markers inside resume.tex...")
    has_summary = "% %START_SUMMARY%" in master_latex and "% %END_SUMMARY%" in master_latex
    has_experience = "% %START_EXPERIENCE_1%" in master_latex and "% %END_EXPERIENCE_1%" in master_latex
    print(f"  - SUMMARY markers found: {has_summary}")
    print(f"  - EXPERIENCE_1 markers found: {has_experience}")
    if not (has_summary or has_experience):
        print("[ORCHESTRATOR] [WARNING] No standard tagging comment markers discovered in resume.tex. The pipeline will not be able to customize sections.")

    # 1. Fetch & Filter Job Openings
    print("[ORCHESTRATOR] [INFO] Launching Scraper Engine...")
    new_jobs = fetch_and_filter_jobs()
    if not new_jobs:
        print("[ORCHESTRATOR] [INFO] No new job listings found today. State is up-to-date. Pipeline execution halted cleanly.")
        print(f"[ORCHESTRATOR] [INFO] Total Execution Time: {time.time() - start_time:.2f} seconds.")
        print("======================================================================")
        return
        
    # Load settings config
    print("[ORCHESTRATOR] [INFO] Parsing config.yaml settings...")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    params = config.get("search_parameters", {})
    gemini_config = config.get("gemini_settings", {})
    model_name = gemini_config.get("model_name", "gemini-2.0-flash")
    max_limit = params.get("max_jobs_to_tailor", 5)
    
    # Bypassing resume rewriting flag (supports env or config)
    bypass_rewriting = os.environ.get("BYPASS_REWRITING", "").strip().lower() in ("true", "1", "yes")
    if not bypass_rewriting:
        bypass_rewriting = params.get("bypass_rewriting", config.get("bypass_rewriting", False))
    
    recipient_email = os.environ.get("RECEIVER_EMAIL")
    
    if not recipient_email:
        print("[ORCHESTRATOR] [WARNING] RECEIVER_EMAIL environment variable is missing.")
        print("  - Pipeline will run in MOCK email mode (using mock_receiver@example.com). Set RECEIVER_EMAIL in your .env or secrets to receive emails.")
        recipient_email = "mock_receiver@example.com"
        
    print(f"[ORCHESTRATOR] [INFO] Configured run parameters:")
    print(f"  - Selected Gemini Model: '{model_name}'")
    print(f"  - New unprocessed jobs found: {len(new_jobs)}")
    print(f"  - Pipeline processing ceiling limit: {max_limit}")
    print(f"  - Bypass Resume Rewriting: {bypass_rewriting}")
    print(f"  - Target notification email: '{recipient_email}'")
    
    active_payloads = []
    processed_this_run = []
    
    jobs_to_process = new_jobs[:max_limit]
    
    if bypass_rewriting:
        print(f"[ORCHESTRATOR] [INFO] Bypassing AI tailoring loop. Packing {len(jobs_to_process)} job listings directly...")
        for idx, job in enumerate(jobs_to_process):
            job['tailored_latex'] = None
            job['pdf_path'] = None
            active_payloads.append(job)
            processed_this_run.append({
                "job_key": job["job_key"],
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "url": job["url"],
                "processed_at": datetime.now().isoformat()
            })
    else:
        print(f"[ORCHESTRATOR] [INFO] Starting optimization loop for {len(jobs_to_process)} active job matches...")
        # 2. Iterate, Tailor, and Compile Resumes
        for idx, job in enumerate(jobs_to_process):
            print(f"\n[ORCHESTRATOR] [INFO] ==================================================")
            print(f"[ORCHESTRATOR] [INFO] Match {idx+1}/{len(jobs_to_process)}: '{job['title']}' at '{job['company']}'")
            print(f"[ORCHESTRATOR] [INFO] Location: '{job['location']}' | URL: '{job['url']}'")
            print("[ORCHESTRATOR] [INFO] ==================================================")
            
            try:
                # Construction of a secure company name for local file naming
                safe_company = "".join([c for c in job['company'] if c.isalnum()]).strip()
                if not safe_company:
                    safe_company = f"Company_{idx+1}"
                pdf_filename = f"Resume_{safe_company}.pdf"
                
                # Tailor the LaTeX content against job description
                if not job.get('description'):
                    print(f"[ORCHESTRATOR] [WARNING] Empty job description for '{job['title']}'. Skipping AI tailoring (output would be identical to master resume).")
                    tailored_latex = master_latex
                else:
                    print(f"[ORCHESTRATOR] [INFO] Invoking AI rewriter for '{job['title']}' using model '{model_name}'...")
                    tailored_latex = generate_tailored_resume(master_latex, job['description'], model_name=model_name)
                job['tailored_latex'] = tailored_latex
                
                # Compile tailored LaTeX into PDF
                print(f"[ORCHESTRATOR] [INFO] Sending tailored resume code to LaTeX compiler...")
                compilation_success = compile_resume(tailored_latex, pdf_filename)
                if compilation_success:
                    job['pdf_path'] = pdf_filename
                    print(f"[ORCHESTRATOR] [INFO] PDF compilation successful: '{pdf_filename}' added to attachments.")
                else:
                    job['pdf_path'] = None
                    print("[ORCHESTRATOR] [WARNING] PDF compilation was skipped or failed. Falling back to sending raw LaTeX in email body.")
                    
                active_payloads.append(job)
                
                # Log state data payload
                processed_this_run.append({
                    "job_key": job["job_key"],
                    "title": job["title"],
                    "company": job["company"],
                    "location": job["location"],
                    "url": job["url"],
                    "processed_at": datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"[ORCHESTRATOR] [ERROR] General exception crashed tailoring loop for '{job['title']}': {e}")
            
    # 3. Deliver Digest Notification via SMTP
    if active_payloads:
        print(f"\n[ORCHESTRATOR] [INFO] Optimizations completed. Dispatching email digest to '{recipient_email}'...")
        dispatch_daily_digest(recipient_email, active_payloads, bypass_rewriting=bypass_rewriting)
        
        # 4. Merge and Commit State
        state_file = "processed_jobs.json"
        print(f"[ORCHESTRATOR] [INFO] Merging {len(processed_this_run)} newly processed listings into state database '{state_file}'...")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    state_data = json.load(f)
            except Exception as e:
                print(f"[ORCHESTRATOR] [WARNING] State database read error: {e}. Starting with empty array.")
                state_data = []
        else:
            state_data = []
            
        state_data.extend(processed_this_run)
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=2)
        print(f"[ORCHESTRATOR] [INFO] State database successfully updated. Current size: {len(state_data)} items.")
            
        # 5. Local Temp Cleanup of compiled PDFs
        print("[ORCHESTRATOR] [INFO] Running cleanups for temporary local PDF attachments...")
        for job in active_payloads:
            pdf_path = job.get('pdf_path')
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    print(f"  - Deleted compiled attachment: '{pdf_path}'")
                except Exception as e:
                    print(f"  - [WARNING] Failed to delete temporary PDF {pdf_path}: {e}")
                    
        total_time = time.time() - start_time
        print("======================================================================")
        print("           DAILY AGENT RUN COMPLETED SUCCESSFULLY")
        print("======================================================================")
        print(f"  - Processed Matches: {len(processed_this_run)}")
        print(f"  - Emailed Recipient: '{recipient_email}'")
        print(f"  - Total Execution Time: {total_time:.2f} seconds")
        print("======================================================================")
    else:
        print("[ORCHESTRATOR] [INFO] No job tailoring operations completed successfully today. Email notification skipped.")
        print(f"[ORCHESTRATOR] [INFO] Total Execution Time: {time.time() - start_time:.2f} seconds.")
        print("======================================================================")

if __name__ == "__main__":
    run_pipeline()
