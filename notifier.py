import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def dispatch_daily_digest(recipient_email, daily_jobs_list, bypass_rewriting=False):
    print("[NOTIFIER] [INFO] Preparing daily digest email...")
    
    if not daily_jobs_list: 
        print("[NOTIFIER] [WARNING] Daily jobs list is empty. Skipping digest email dispatcher.")
        return
        
    sender_email = os.environ.get('EMAIL_SENDER')
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port_str = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    
    # Hide password chars in logs for security
    masked_pw = ("*" * len(smtp_password)) if smtp_password else "None"
    
    print(f"[NOTIFIER] [INFO] Loaded SMTP configuration settings:")
    print(f"  - SMTP Server: {smtp_server}")
    print(f"  - SMTP Port: {smtp_port_str}")
    print(f"  - Sender Email: {sender_email}")
    print(f"  - SMTP User: {smtp_user}")
    print(f"  - SMTP Password configured: {masked_pw != 'None'}")
    print(f"  - Recipient: {recipient_email}")
    print(f"  - Jobs to Notify: {len(daily_jobs_list)}")
    
    if not all([sender_email, smtp_user, smtp_password]):
        print("[NOTIFIER] [ERROR] SMTP credentials not fully configured in environment variables.")
        print("  - Troubleshooting: Ensure EMAIL_SENDER, SMTP_USER, and SMTP_PASSWORD are set in your .env file or GitHub Secrets.")
        print("  - Email dispatch skipped.")
        return
        
    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        print(f"[NOTIFIER] [WARNING] Invalid SMTP_PORT '{smtp_port_str}'. Defaulting to 587.")
        smtp_port = 587
        
    print("[NOTIFIER] [DEBUG] Assembling MIME Multipart email content structure...")
    msg = MIMEMultipart()
    subject_title = "Daily Job Opportunities Digest" if bypass_rewriting else "Daily Tailored Job Opportunities Digest"
    msg['Subject'] = f"{subject_title} ({len(daily_jobs_list)} Matches)"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    # Premium responsive HTML header and design
    title_text = "Daily Job Opportunities Digest" if bypass_rewriting else "Daily AI Resume Tailoring Digest"
    greeting_text = (
        "We successfully scanned for new job listings that match your configured interests."
        if bypass_rewriting else
        "We successfully scanned for new listings and tailored your resume bullet points using Gemini 2.0 Flash to align with these active roles."
    )
    
    html_body = f"""
    <html>
        <body style="font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1f2937; background-color: #f3f4f6; margin: 0; padding: 20px;">
            <div style="max-width: 650px; margin: 20px auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025);">
                
                <!-- HEADER HEADER -->
                <div style="background: linear-gradient(135deg, #1e3a8a, #2563eb); padding: 35px 30px; text-align: center; color: #ffffff;">
                    <h1 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.025em; text-shadow: 0 2px 4px rgba(0,0,0,0.15);">{title_text}</h1>
                    <p style="margin: 8px 0 0 0; color: #93c5fd; font-size: 15px; font-weight: 500;">Ephemeral Serverless Pipeline Execution Complete</p>
                </div>
                
                <!-- MAIN CONTENT AREA -->
                <div style="padding: 30px 25px;">
                    <p style="font-size: 16px; margin-top: 0; color: #4b5563; margin-bottom: 25px;">
                        Hello Prathamesh, <br><br>
                        {greeting_text}
                    </p>
    """
    
    attached_pdf_count = 0
    
    for idx, job in enumerate(daily_jobs_list):
        has_pdf = 'pdf_path' in job and job['pdf_path'] and os.path.exists(job['pdf_path'])
        
        print(f"[NOTIFIER] [DEBUG] Processing Match #{idx+1}: '{job['title']}' at '{job['company']}'...")
        if has_pdf:
            pdf_size = os.path.getsize(job['pdf_path'])
            print(f"  - Found compiled PDF: '{job['pdf_path']}' (Size: {pdf_size} bytes)")
        else:
            print("  - Notice: No compiled PDF found. Fallback inline LaTeX will be injected.")
            
        if bypass_rewriting:
            pdf_status_badge = '<span style="background-color: #eff6ff; color: #1e40af; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 20px; float: right; margin-left: 10px;">Direct Match</span>'
        else:
            pdf_status_badge = (
                '<span style="background-color: #d1fae5; color: #065f46; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 20px; float: right; margin-left: 10px;">PDF Attached</span>'
                if has_pdf else
                '<span style="background-color: #fef3c7; color: #92400e; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 20px; float: right; margin-left: 10px;">Raw LaTeX Included</span>'
            )
        
        html_body += f"""
        <div style="margin-bottom: 30px; border: 1px solid #f3f4f6; background-color: #fafafa; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
            {pdf_status_badge}
            <span style="display: inline-block; background-color: #eff6ff; color: #1e40af; font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 6px; margin-bottom: 10px;">Match #{idx+1}</span>
            
            <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #111827; line-height: 1.3;">{job['title']}</h3>
            <p style="margin: 6px 0; font-size: 14px; font-weight: 600; color: #4b5563;">{job['company']} <span style="font-weight: normal; color: #9ca3af;">• {job['location']}</span></p>
            
            <div style="margin-top: 15px;">
                <a href="{job['url']}" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 8px 16px; font-size: 13px; font-weight: 600; text-decoration: none; border-radius: 6px; box-shadow: 0 2px 4px rgba(37,99,235,0.2);">View Job Description</a>
            </div>
        """
        
        # If compilation failed or skipped, include raw LaTeX fragments in email body
        if not has_pdf and 'tailored_latex' in job and job['tailored_latex']:
            html_body += f"""
            <h4 style="margin: 20px 0 8px 0; color: #374151; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em;">Tailored Experience Bullets (LaTeX code):</h4>
            <pre style="background-color: #f1f5f9; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; font-size: 12px; color: #0f172a; margin: 0; max-height: 250px; overflow-y: auto;">{job['tailored_latex']}</pre>
            """
            
        html_body += "</div>"
        
        # Attach the compiled PDF to the email message structure
        if has_pdf:
            try:
                with open(job['pdf_path'], 'rb') as f:
                    pdf_data = f.read()
                    pdf_attachment = MIMEApplication(pdf_data, _subtype="pdf")
                    safe_filename = os.path.basename(job['pdf_path'])
                    pdf_attachment.add_header('Content-Disposition', 'attachment', filename=safe_filename)
                    msg.attach(pdf_attachment)
                attached_pdf_count += 1
                print(f"  - Successfully attached '{safe_filename}' to MIME payload.")
            except Exception as e:
                print(f"[NOTIFIER] [ERROR] Failed to attach PDF file '{job['pdf_path']}': {e}")
                
    if bypass_rewriting:
        footer_message = "Successfully fetched and delivered your daily job listings."
    else:
        footer_message = f"Successfully attached {attached_pdf_count} customized resume PDFs to this digest."
        
    html_body += f"""
                    <p style="font-size: 14px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px; text-align: center;">
                        {footer_message}
                    </p>
                </div>
                
                <!-- FOOTER FOOTER -->
                <div style="background-color: #f9fafb; border-top: 1px solid #e5e7eb; padding: 20px; text-align: center; color: #9ca3af; font-size: 12px;">
                    Stateless GitHub Actions Cron runner sequence complete. processed_jobs.json updated.
                </div>
            </div>
        </body>
    </html>
    """
    
    print("[NOTIFIER] [DEBUG] Attaching HTML layout body to email payload...")
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        print(f"[NOTIFIER] [INFO] Establishing SMTP connection to {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        
        print("[NOTIFIER] [INFO] Connection established. Starting TLS secure channel...")
        server.starttls()
        
        print(f"[NOTIFIER] [INFO] TLS connection activated. Authenticating as user '{smtp_user}'...")
        server.login(smtp_user, smtp_password)
        
        print(f"[NOTIFIER] [INFO] Authentication successful. Delivering email payload to '{recipient_email}'...")
        server.sendmail(sender_email, recipient_email, msg.as_string())
        
        print("[NOTIFIER] [INFO] Email sent successfully. Terminating SMTP session...")
        server.quit()
        print(f"[NOTIFIER] [INFO] Daily digest successfully sent to {recipient_email}. Network session closed cleanly.")
    except Exception as e:
        print(f"[NOTIFIER] [ERROR] Failed to dispatch daily digest email: {e}")
        print("  - Troubleshooting: Verify SMTP login credentials, verify that SMTP server/ports are correct, and verify App Password permissions.")
