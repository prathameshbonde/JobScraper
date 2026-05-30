# Automated Job Search & AI Resume Tailoring Pipeline

A cost-efficient, fully automated, serverless pipeline running entirely on GitHub Actions. It scrapes daily job postings across LinkedIn, Indeed, and Glassdoor, deduplicates them using a git-backed local state database, uses Google Gemini 2.0 Flash to tailor your resume summary and experience bullet points for specific matches, compiles the customized LaTeX resumes into high-quality PDFs, and emails a daily digest directly to your inbox with the PDFs attached.

---

## 🛠️ Architecture & Data Flow

```
       [1. GitHub Actions (Cron Trigger)]
                       │
                       ▼
         [2. Ingestion (python-jobspy)]  ──(Scrapes LinkedIn, Indeed, Glassdoor)
                       │
                       ▼
     [3. Deduplication (Local JSON State)]  ──(Filters against processed_jobs.json)
                       │
                       ▼
       [4. Tailor (Gemini 2.0 Flash)]   ──(Updates Summary & Bullet Points)
                       │
                       ▼
         [5. Compile (TeX Live Runner)]  ──(Generates ready-to-use PDFs)
                       │
                       ▼
          [6. Dispatch (Secure SMTP)]    ──(HTML Digest with PDF Attachments)
                       │
                       ▼
        [7. Commit (Git Auto-Commit)]    ──(Saves new keys in processed_jobs.json)
```

---

## 📂 Project Structure

```
├── .github/workflows/
│   └── daily_agent.yml        # GitHub Actions Cron Configuration
├── prompts/
│   ├── summary_prompt.md      # Professional Summary AI System Prompts
│   └── experience_prompt.md   # Experience Bullet Points AI System Prompts
├── config.yaml                # Job Search & SMTP Configuration File
├── processed_jobs.json        # Deduplication Database State File
├── resume.tex                 # Master LaTeX Resume Template
├── scraper.py                 # Jobspy Scraping & State Filter Logic
├── rewriter.py                # Gemini API Structured Tailoring Logic
├── compiler.py                # Automated Local LaTeX Compiling Routine
├── notifier.py                # Email Digest Creation & SMTP Dispatcher
├── main.py                    # Orchestration Execution Controller
├── test_pipeline.py           # Local Validation & Parsing Unit Tests
└── requirements.txt           # Python Package Dependencies
```

---

## ⚙️ Configuration Setup (`config.yaml`)

Search parameters and limits are externalized in `config.yaml` at the root of the repository:

```yaml
search_parameters:
  titles:
    - "Software Engineer"
    - "Backend Engineer"
    - "Generative AI Engineer"
    - "Java Developer"
  locations:
    - "Bengaluru"
  country: "india"
  results_wanted: 30
  hours_old: 24
  max_jobs_to_tailor: 5

email_settings:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
```

---

## 🏷️ LaTeX Resume Comment Tagging

Annotate specific blocks in your master `resume.tex` file using targeted comments. The pipeline extracts only these sections, sends them to Gemini for keyword optimization, and replaces them—leaving the rest of the LaTeX layout 100% untouched and safe from compiler errors:

```latex
% %START_SUMMARY%
Detail-oriented Software Engineer with a passion for building scalable systems.
% %END_SUMMARY%

...

\section{Experience}
% %START_EXPERIENCE_1%
\begin{itemize}
    \item Developed high-throughput API microservices using Python and Spring Boot.
    \item Reduced database query latency by 35% through query optimization.
\end{itemize}
% %END_EXPERIENCE_1%
```

---

## 📝 Customizing AI Prompts

The system prompts (AI instructions) defining the tailoring logic have been externalized into clean markdown files inside the `prompts/` directory to separate code from AI engineering:

* **[prompts/summary_prompt.md](file:///d:/Projects/JobWorkflow/prompts/summary_prompt.md)**: Manages how Gemini rewrites your **Professional Summary** to align with keywords and highlights matching the JD.
* **[prompts/skills_prompt.md](file:///d:/Projects/JobWorkflow/prompts/skills_prompt.md)**: Manages how Gemini reorganizes and prioritizes your **Technical Skills list** to maximize keyword matching scores against ATS parsers.
* **[prompts/experience_prompt.md](file:///d:/Projects/JobWorkflow/prompts/experience_prompt.md)**: Manages how Gemini tailors your **Work Experience bullet points** (keeping structural LaTeX commands like `\item` intact).

*You can open, edit, and optimize these markdown files directly to adjust the AI's tone, rules, constraints, and behavior without ever touching the Python source code.*

---

## 🚀 Getting Started

### 1. Local Run Requirements

Ensure you have Python 3.10+ and a LaTeX environment installed locally (e.g., TeX Live or MiKTeX on your system PATH to run automated PDF compilation).

```bash
# Clone the repository
git clone <your-repository-url>
cd <repository-directory>

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Local Environment Variables

To run the pipeline locally, define the following variables in your terminal or shell profile:

```bash
export GEMINI_API_KEY="your-google-ai-studio-key"
export RECEIVER_EMAIL="destination-email@example.com"
export EMAIL_SENDER="sender-email@example.com"
export SMTP_USER="your-smtp-username"
export SMTP_PASSWORD="your-smtp-app-password"
```

### 3. Run Pipeline Locally

```bash
# Run unit tests to verify parsing & escaping
python test_pipeline.py

# Run the full pipeline
python main.py
```

---

## ☁️ GitHub Actions Automated Deployment

1. Push this directory to your private GitHub repository.
2. Navigate to your repository on GitHub, then click on **Settings > Secrets and variables > Actions > New repository secret**.
3. Create the following Secrets:

| Secret Name | Description | Example / Default |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Your Google AI Studio API key | `AIzaSy...` |
| `RECEIVER_EMAIL` | The destination email for digests | `recipient@example.com` |
| `EMAIL_SENDER` | The sending email address | `sender@example.com` |
| `SMTP_USER` | SMTP authentication username | `sender@example.com` |
| `SMTP_PASSWORD` | SMTP password / App Password | `abcd efgh ijkl mnop` |
| `SMTP_SERVER` | SMTP host gateway address | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port address | `587` |

Once configured, GitHub Actions will run the pipeline automatically on the cron schedule (preconfigured for daily runs at 10:00 AM IST) and commit deduplication updates back to the branch.
