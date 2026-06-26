import re
import os
from google import genai
from google.genai import types

def sanitize_for_latex(text_payload):
    # 1. Temporarily protect valid mathematical tildes (like $\sim$) from being escaped
    # Use an underscore-free placeholder so that the escape rules do not modify it
    placeholder = "LATEXMATHSIMPLACEHOLDER"
    # Match any spacing variations of $\sim$
    text_payload = re.sub(r'\$\s*\\sim\s*\$', placeholder, text_payload)
    
    # Track escaping modifications for diagnostic clarity
    escaped_amp = len(re.findall(r'(?<!\\)&', text_payload))
    escaped_pct = len(re.findall(r'(?<!\\)%', text_payload))
    escaped_dlr = len(re.findall(r'(?<!\\)\$', text_payload))
    escaped_und = len(re.findall(r'(?<!\\)_', text_payload))
    escaped_num = len(re.findall(r'(?<!\\)#', text_payload))
    
    if any([escaped_amp, escaped_pct, escaped_dlr, escaped_und, escaped_num]):
        print(f"[REWRITER] [DEBUG] Escaping unescaped LaTeX control characters in response payload:")
        if escaped_amp: print(f"  - Escaped {escaped_amp} '&' symbol(s)")
        if escaped_pct: print(f"  - Escaped {escaped_pct} '%' symbol(s)")
        if escaped_dlr: print(f"  - Escaped {escaped_dlr} '$' symbol(s)")
        if escaped_und: print(f"  - Escaped {escaped_und} '_' symbol(s)")
        if escaped_num: print(f"  - Escaped {escaped_num} '#' symbol(s)")

    # Regex lookbehind escaping to prevent LaTeX compilation crashes
    text_payload = re.sub(r'(?<!\\)&', r'\&', text_payload)
    text_payload = re.sub(r'(?<!\\)%', r'\%', text_payload)
    text_payload = re.sub(r'(?<!\\)\$', r'\$', text_payload)
    text_payload = re.sub(r'(?<!\\)_', r'\_', text_payload)
    text_payload = re.sub(r'(?<!\\)#', r'\#', text_payload)
    
    # 2. Restore protected math tildes
    text_payload = text_payload.replace(placeholder, r"$\sim$")
    return text_payload

def strip_markdown(text):
    initial_len = len(text)
    text = text.strip()
    match = re.search(r'```(?:latex)?\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        print(f"[REWRITER] [DEBUG] Markdown code block stripped (Original: {initial_len} chars -> Stripped: {len(extracted)} chars).")
        return extracted
    
    cleaned = text.replace("```latex", "").replace("```", "").strip()
    if len(cleaned) != initial_len:
         print(f"[REWRITER] [DEBUG] Basic markdown backticks removed (Remaining: {len(cleaned)} chars).")
    return cleaned

def tailor_section(section_name, section_content, job_description, model_name="gemini-2.0-flash"):
    print(f"[REWRITER] [INFO] Initiating tailoring for section: '{section_name}' (Original content size: {len(section_content)} chars)...")
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("[REWRITER] [ERROR] GEMINI_API_KEY environment variable is not defined.")
        raise ValueError("Missing GEMINI_API_KEY environment variable.")
        
    print(f"[REWRITER] [DEBUG] API key verified (length: {len(api_key)} chars). Instantiating google-genai client...")
    # Initialize the new SDK client with the API key
    client = genai.Client(api_key=api_key)
    
    # Custom instructions depending on the section type (Loaded from external markdown files)
    role_instruction = ""
    if "SUMMARY" in section_name:
        prompt_path = os.path.join("prompts", "summary_prompt.md")
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    role_instruction = pf.read().strip()
                print(f"[REWRITER] [INFO] Loaded summary system instructions from '{prompt_path}' ({len(role_instruction)} chars).")
            except Exception as pe:
                print(f"[REWRITER] [WARNING] Failed to load prompt file {prompt_path}: {pe}. Using fallback.")
        
        if not role_instruction:
            role_instruction = (
                "You are a professional technical resume writer. Your task is to rewrite the professional "
                "Summary section of a software engineer's resume to highlight skills and experience relevant "
                "to the targeted Job Description.\n"
                "Constraints:\n"
                "1. Focus on keywords, tools, and achievements that match the Job Description.\n"
                "2. Keep the length and format identical (typically 2-3 sentences max, using standard bolding \\textbf{...}).\n"
                "3. DO NOT alter any LaTeX formatting commands.\n"
                "4. Return ONLY the rewritten text fragment. No markdown formatting, no conversational text, no ```latex blocks."
            )
    elif "SKILLS" in section_name:
        prompt_path = os.path.join("prompts", "skills_prompt.md")
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    role_instruction = pf.read().strip()
                print(f"[REWRITER] [INFO] Loaded skills system instructions from '{prompt_path}' ({len(role_instruction)} chars).")
            except Exception as pe:
                print(f"[REWRITER] [WARNING] Failed to load prompt file {prompt_path}: {pe}. Using fallback.")
        
        if not role_instruction:
            role_instruction = (
                "You are a professional technical resume writer and ATS optimization expert. Your task is to review "
                "and adapt the Skills section (the \\begin{description} ... \\end{description} block) of a software engineer's "
                "resume to maximize its ATS matching score against a targeted Job Description.\n"
                "Constraints:\n"
                "1. Keep all structural LaTeX commands exactly the same, especially \\begin{description}, \\end{description}, and \\item[\\textbf{Category:}].\n"
                "2. Identify the most critical keywords, programming languages, libraries, tools, and platforms listed in the targeted Job Description.\n"
                "3. Reorder the categories or the skills inside each category so that the most relevant and highly-sought skills for this specific job appear FIRST.\n"
                "4. Do NOT fabricate skills that the candidate does not have; rather, highlight and prioritize matching existing skills.\n"
                "5. Return ONLY the rewritten LaTeX block starting with \\begin{description} and ending with \\end{description}.\n"
                "6. Do not write any markdown code blocks, intro text, or outro explanations."
            )
    else:
        prompt_path = os.path.join("prompts", "experience_prompt.md")
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as pf:
                    role_instruction = pf.read().strip()
                print(f"[REWRITER] [INFO] Loaded experience system instructions from '{prompt_path}' ({len(role_instruction)} chars).")
            except Exception as pe:
                print(f"[REWRITER] [WARNING] Failed to load prompt file {prompt_path}: {pe}. Using fallback.")
                
        if not role_instruction:
            role_instruction = (
                "You are a professional technical resume writer. Your task is to review and adapt the experience "
                "bullet points (the \\begin{itemize} ... \\end{itemize} block) of a software engineer's resume "
                "to align with a targeted Job Description.\n"
                "Constraints:\n"
                "1. Keep all structural LaTeX commands exactly the same, especially \\begin{itemize}, \\end{itemize}, and \\item.\n"
                "2. Tailor and emphasize key metrics, tech stack items (like Spring Boot, LangGraph, OpenShift, Kubernetes, etc.) "
                "that are relevant to the targeted Job Description.\n"
                "3. Do not make up achievements or fake roles; rather, reframe existing bullet points to showcase relevant expertise.\n"
                "4. Return ONLY the rewritten LaTeX block starting with \\begin{itemize} and ending with \\end{itemize}.\n"
                "5. Do not write any markdown code blocks, intro text, or outro explanations.\n"
                "6. Always format mathematical tildes for percentages in the exact format $\\sim$XX% (e.g., $\\sim$30% or $\\sim$35%). The tilde (\\sim) MUST be wrapped in math mode ($) to ensure clean compiling."
            )

    prompt = (
        f"--- ORIGINAL RESUME FRAGMENT ---\n{section_content}\n\n"
        f"--- TARGET JOB DESCRIPTION ---\n{job_description}\n\n"
        f"Please perform the translation/adaptation now."
    )
    
    print(f"[REWRITER] [DEBUG] Model: '{model_name}'. System Instructions size: {len(role_instruction)} chars. Prompt size: {len(prompt)} chars.")
    
    print(f"[REWRITER] [INFO] Sending content tailoring request to Gemini Model '{model_name}' using new Client SDK...")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            system_instruction=role_instruction
        )
    )
    
    print(f"[REWRITER] [INFO] API response received successfully (Size: {len(response.text)} chars). Post-processing...")
    cleaned_output = strip_markdown(response.text)
    sanitized_output = sanitize_for_latex(cleaned_output)
    print(f"[REWRITER] [INFO] Completed tailoring section '{section_name}'. Output size: {len(sanitized_output)} chars.")
    return sanitized_output

def generate_tailored_resume(master_latex, job_description, model_name="gemini-2.0-flash"):
    print("[REWRITER] [INFO] Starting resume parsing loop for comment-tagged sections...")
    # Find all tagged sections: % %START_SECTIONNAME% ... % %END_SECTIONNAME%
    pattern = r'%\s*%START_(\w+)%\s*(.*?)\s*%\s*%END_\1%'
    sections = re.findall(pattern, master_latex, re.DOTALL)
    
    if not sections:
        print("[REWRITER] [WARNING] No comment-tagged sections found in master resume. (Markers should match '% %START_SECTIONNAME%' and '% %END_SECTIONNAME%'). Returning original resume.")
        return master_latex
        
    print(f"[REWRITER] [INFO] Discovered {len(sections)} sections in master resume: {[s[0] for s in sections]}")
    tailored_latex = master_latex
    
    for section_name, original_content in sections:
        print(f"[REWRITER] [INFO] Entering tailoring loop for '{section_name}'...")
        try:
            tailored_content = tailor_section(section_name, original_content, job_description, model_name=model_name)
            
            # Double check to prevent blank section overrides
            if tailored_content:
                # Find the exact block in the master template using search
                replace_pattern = rf"(%\s*%START_{section_name}%\s*).*?(\s*%\s*%END_{section_name}%)"
                match = re.search(replace_pattern, tailored_latex, flags=re.DOTALL)
                if match:
                    start_idx, end_idx = match.span()
                    # Reconstruct the string using safe slice replacement
                    start_tag = match.group(1)
                    end_tag = match.group(2)
                    
                    tailored_latex = (
                        tailored_latex[:start_idx] +
                        start_tag + tailored_content + end_tag +
                        tailored_latex[end_idx:]
                    )
                    print(f"[REWRITER] [INFO] Successfully performed slice insertion for section '{section_name}' into master template.")
                else:
                    print(f"[REWRITER] [WARNING] Marker tags for '{section_name}' were not found in template string during replacement.")
            else:
                print(f"[REWRITER] [WARNING] Tailor returned empty content for '{section_name}'. Leaving section unchanged.")
        except Exception as e:
            print(f"[REWRITER] [ERROR] Failed to tailor section '{section_name}': {e}. Section left unchanged.")
            
    print("[REWRITER] [INFO] Resume parsing and section tailoring loop completed successfully.")
    return tailored_latex
