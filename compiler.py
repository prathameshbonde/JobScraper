import subprocess
import os
import shutil
import platform

def compile_resume(latex_content, output_pdf_name):
    print(f"[COMPILER] [INFO] Initiating LaTeX compilation process for: '{output_pdf_name}'...")
    print(f"[COMPILER] [DEBUG] Current Working Directory: '{os.getcwd()}'")
    
    # Establish a unique temporary file prefix
    temp_prefix = "temp_compile_resume"
    temp_tex = f"{temp_prefix}.tex"
    temp_pdf = f"{temp_prefix}.pdf"
    
    print(f"[COMPILER] [DEBUG] Generating temporary LaTeX source file: '{temp_tex}'...")
    # Write tailored LaTeX code to temporary file
    with open(temp_tex, "w", encoding="utf-8") as f:
        f.write(latex_content)
    print(f"[COMPILER] [DEBUG] Successfully wrote {len(latex_content)} characters of LaTeX code to '{temp_tex}'.")
        
    success = False
    try:
        # Base pdflatex arguments
        cmd = ["pdflatex", "-interaction=nonstopmode"]
        
        # Add auto-install flag for Windows MiKTeX setups to prevent prompt hangs
        print(f"[COMPILER] [INFO] Checking hosting Operating System platforms...")
        sys_os = platform.system()
        if sys_os == "Windows":
            print("[COMPILER] [INFO] Windows OS detected. Automatically appending '--enable-installer' command argument to let MiKTeX resolve packages silently.")
            cmd.append("--enable-installer")
        else:
            print(f"[COMPILER] [INFO] Non-Windows OS detected ({sys_os}). Using standard compiler args.")
            
        cmd.append(temp_tex)
        
        print(f"[COMPILER] [INFO] Spawning LaTeX compiler process: {' '.join(cmd)}...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45
        )
        
        print(f"[COMPILER] [INFO] LaTeX compiler subprocess completed. Return code: {result.returncode}")
        
        # Validate output success (Accept PDF if generated, even with minor exit code 1 warnings)
        if os.path.exists(temp_pdf):
            if result.returncode == 0:
                print(f"[COMPILER] [INFO] Output PDF created successfully: '{temp_pdf}'. Moving to target destination '{output_pdf_name}'...")
            else:
                print(f"[COMPILER] [WARNING] LaTeX compiler exited with code {result.returncode}, but a compiled PDF was successfully generated. Proceeding with generated PDF.")
                # Load and display warnings for diagnostic help
                temp_log = f"{temp_prefix}.log"
                log_content = ""
                if os.path.exists(temp_log):
                    try:
                        with open(temp_log, "r", encoding="utf-8", errors="ignore") as lf:
                            log_content = lf.read()
                    except Exception:
                        pass
                diagnostic_source = log_content if log_content else (result.stdout if result.stdout else "")
                if diagnostic_source:
                    error_lines = [line.strip() for line in diagnostic_source.split('\n') if line.strip().startswith('!')]
                    if error_lines:
                        print("[COMPILER] [WARNING] --- DETECTED NON-FATAL COMPILER WARNINGS ---")
                        for err in error_lines[:8]: # Limit to 8 to avoid log flood
                            print(f"  {err}")
                        print("[COMPILER] [WARNING] -----------------------------------------------")
            
            # Move compiled PDF to target output location
            shutil.move(temp_pdf, output_pdf_name)
            print(f"[COMPILER] [INFO] Successfully moved resume PDF to: '{os.path.abspath(output_pdf_name)}'")
            success = True
        else:
            print(f"[COMPILER] [ERROR] LaTeX compilation failed. Exit code: {result.returncode}. Output PDF '{temp_pdf}' not found or compiler crashed.")
            
            # Read and print details from the LaTeX log file if it exists
            temp_log = f"{temp_prefix}.log"
            log_content = ""
            if os.path.exists(temp_log):
                try:
                    with open(temp_log, "r", encoding="utf-8", errors="ignore") as lf:
                        log_content = lf.read()
                    print(f"[COMPILER] [INFO] Successfully loaded diagnostics from compiler log file '{temp_log}' ({len(log_content)} bytes).")
                except Exception as le:
                    print(f"[COMPILER] [WARNING] Failed to load compiler log file '{temp_log}': {le}")
            
            # Check stderr for wrapper-level errors (like MiKTeX update blockers)
            if result.stderr and result.stderr.strip():
                print("[COMPILER] [ERROR] --- DETECTED COMPILER PROCESS ERRORS (stderr) ---")
                print(result.stderr.strip())
                print("[COMPILER] [ERROR] -----------------------------------------------------")
                
            # Use log content if found, fallback to stdout
            diagnostic_source = log_content if log_content else (result.stdout if result.stdout else "")
            
            if diagnostic_source:
                error_lines = [line.strip() for line in diagnostic_source.split('\n') if line.strip().startswith('!')]
                if error_lines:
                    print("[COMPILER] [ERROR] --- DETECTED LATEX COMPILER SYNTAX ERRORS ---")
                    for err in error_lines[:15]: # Limit to 15 to avoid text flood
                        print(f"  {err}")
                    print("[COMPILER] [ERROR] ------------------------------------------------")
                
                print("[COMPILER] [DEBUG] --- pdflatex trailing compiler logs snippet ---")
                print(diagnostic_source[-1500:] if len(diagnostic_source) > 1500 else diagnostic_source)
                print("[COMPILER] [DEBUG] -----------------------------------------------")
    except FileNotFoundError:
        print("[COMPILER] [ERROR] 'pdflatex' executable was not found on the system environmental PATH variable.")
        print("  - Troubleshooting: Install TeX Live (Linux/Ubuntu) or MiKTeX (Windows) and verify that 'pdflatex' runs in a shell.")
        print("  - Pipeline will continue, falling back to providing raw LaTeX inline text in the email digest.")
    except subprocess.TimeoutExpired:
        print("[COMPILER] [ERROR] LaTeX compiler command timed out (45 seconds limit exceeded). Execution halted.")
    except Exception as e:
        print(f"[COMPILER] [ERROR] An unexpected error occurred during LaTeX compilation: {e}")
    finally:
        print("[COMPILER] [DEBUG] Commencing temporary LaTeX artifacts cleanup...")
        # Clean up temporary compilation artifacts
        for ext in [".tex", ".aux", ".log", ".out", ".pdf"]:
            file_to_remove = f"{temp_prefix}{ext}"
            if os.path.exists(file_to_remove):
                try:
                    os.remove(file_to_remove)
                    print(f"  - Cleaned up temp file: '{file_to_remove}'")
                except Exception as e:
                    print(f"  - [WARNING] Failed to delete temp file {file_to_remove}: {e}")
                    
    return success
