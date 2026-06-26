// STATE & INITIAL CONFIGURATION
let currentConfig = {
    resume: "",
    summary_prompt: "",
    skills_prompt: "",
    experience_prompt: "",
    default_model: "gemini-2.0-flash",
    models: []
};

let activePromptTab = "summary"; // summary, skills, experience

// DOM ELEMENTS
const navItems = document.querySelectorAll(".nav-item");
const tabPanes = document.querySelectorAll(".tab-pane");
const pageTitle = document.getElementById("page-title");
const pageSubtitle = document.getElementById("page-subtitle");
const modelSelect = document.getElementById("model-select");

// Workspace DOM Elements
const jdTextarea = document.getElementById("jd-textarea");
const clearJdBtn = document.getElementById("clear-jd-btn");
const tailorBtn = document.getElementById("tailor-btn");
const outputEmptyState = document.getElementById("output-empty-state");
const outputProcessingState = document.getElementById("output-processing-state");
const outputResultState = document.getElementById("output-result-state");
const outputActions = document.getElementById("output-actions");
const processingStep = document.getElementById("processing-step");
const miniLogPre = document.getElementById("mini-log-pre");
const copyTexBtn = document.getElementById("copy-tex-btn");
const downloadPdfBtn = document.getElementById("download-pdf-btn");
const tailoredLatexPreview = document.getElementById("tailored-latex-preview");
const bannerStatus = document.getElementById("banner-status");
const statusTitle = document.getElementById("status-title");
const statusDesc = document.getElementById("status-desc");

// Template Editor DOM Elements
const resumeEditor = document.getElementById("resume-editor");
const saveResumeBtn = document.getElementById("save-resume-btn");
const resumeSaveStatus = document.getElementById("resume-save-status");

// Prompt Editor DOM Elements
const promptNavItems = document.querySelectorAll(".prompt-nav-item");
const promptEditorTitle = document.getElementById("prompt-editor-title");
const promptEditor = document.getElementById("prompt-editor");
const savePromptBtn = document.getElementById("save-prompt-btn");
const promptSaveStatus = document.getElementById("prompt-save-status");

// Console Logs DOM Elements
const consoleLogsPre = document.getElementById("console-logs-pre");
const clearLogsBtn = document.getElementById("clear-logs-btn");

// Toast Container
const toastContainer = document.getElementById("toast-container");

// HEADER TITLES FOR NAVIGATION TABS
const tabHeaderInfo = {
    workspace: {
        title: "Ad-Hoc Workspace",
        subtitle: "Paste a job description to instantly optimize and compile your resume."
    },
    template: {
        title: "Master Template Editor",
        subtitle: "Modify the baseline resume.tex file. AI customizations will be safe-injected here."
    },
    prompts: {
        title: "AI Prompt Optimization",
        subtitle: "Edit the system prompts guiding Gemini's rewriting parameters."
    },
    logs: {
        title: "System Diagnostics Console",
        subtitle: "Live output from the AI compiler and pipeline runs."
    }
};

// INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
    initApp();
    setupEventListeners();
});

// FUNCTIONS
async function initApp() {
    appendLog("Initializing UI Client and connecting to local FastAPI server...");
    try {
        const response = await fetch("/api/config");
        if (!response.ok) throw new Error("Failed to connect to local server configuration.");
        
        currentConfig = await response.ok ? await response.json() : currentConfig;
        appendLog("Configuration loaded successfully from disk!");
        
        // Populate model dropdown
        modelSelect.innerHTML = "";
        currentConfig.models.forEach(model => {
            const option = document.createElement("option");
            option.value = model;
            option.textContent = model;
            if (model === currentConfig.default_model) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        });

        // Populate Master Template Editor
        resumeEditor.value = currentConfig.resume;
        
        // Populate System Prompt Editor (Active: summary)
        loadPromptContent("summary");
        
        showToast("Connected to Local Server", "success");
    } catch (error) {
        console.error(error);
        appendLog(`[ERROR] Initialization failed: ${error.message}`);
        showToast("Server Connection Failed", "error");
    }
}

function setupEventListeners() {
    // Tab switching
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            switchTab(targetTab);
            
            // Mark active nav menu item
            navItems.forEach(nav => nav.classList.remove("active"));
            item.classList.add("active");
        });
    });

    // Clear JD
    clearJdBtn.addEventListener("click", () => {
        jdTextarea.value = "";
        showToast("Job Description cleared", "info");
    });

    // Run Tailoring Pipeline
    tailorBtn.addEventListener("click", handleTailoringRun);

    // Save Master LaTeX Template
    saveResumeBtn.addEventListener("click", () => saveFile("resume", resumeEditor.value, resumeSaveStatus));

    // Prompt Sidebar Tab Switching
    promptNavItems.forEach(item => {
        item.addEventListener("click", () => {
            const promptType = item.getAttribute("data-prompt");
            promptNavItems.forEach(btn => btn.classList.remove("active"));
            item.classList.add("active");
            loadPromptContent(promptType);
        });
    });

    // Save Active Prompt
    savePromptBtn.addEventListener("click", () => {
        const fileKey = `${activePromptTab}_prompt`;
        saveFile(fileKey, promptEditor.value, promptSaveStatus);
        
        // Update local state
        currentConfig[fileKey] = promptEditor.value;
    });

    // Copy Tailored LaTeX
    copyTexBtn.addEventListener("click", () => {
        if (!tailoredLatexPreview.value) return;
        navigator.clipboard.writeText(tailoredLatexPreview.value)
            .then(() => showToast("LaTeX source copied!", "success"))
            .catch(() => showToast("Copy failed", "error"));
    });

    // Clear System Console logs
    clearLogsBtn.addEventListener("click", () => {
        consoleLogsPre.textContent = "[CONSOLE CLEANED]\n";
        showToast("Console cleared", "info");
    });
}

function switchTab(tabId) {
    // Hide all tab panes
    tabPanes.forEach(pane => pane.classList.remove("active"));
    
    // Show target tab pane
    const targetPane = document.getElementById(`tab-${tabId}`);
    if (targetPane) {
        targetPane.classList.add("active");
    }

    // Update Header
    const headerInfo = tabHeaderInfo[tabId] || { title: "App", subtitle: "" };
    pageTitle.textContent = headerInfo.title;
    pageSubtitle.textContent = headerInfo.subtitle;
}

function loadPromptContent(promptType) {
    activePromptTab = promptType;
    let title = "Summary System Prompt";
    let text = currentConfig.summary_prompt;

    if (promptType === "skills") {
        title = "Skills System Prompt";
        text = currentConfig.skills_prompt;
    } else if (promptType === "experience") {
        title = "Experience System Prompt";
        text = currentConfig.experience_prompt;
    }

    promptEditorTitle.textContent = title;
    promptEditor.value = text;
    appendLog(`Loaded prompt editor view: '${promptType}'`);
}

// SAVE FILE SERVICE
async function saveFile(fileType, content, statusEl) {
    statusEl.textContent = "Saving...";
    statusEl.className = "save-status-msg";
    
    try {
        const response = await fetch("/api/save-config", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                file_type: fileType,
                content: content
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Server failed to save the file.");
        }

        statusEl.textContent = "Saved successfully!";
        statusEl.classList.add("success");
        showToast("Saved successfully", "success");
        appendLog(`Successfully saved local changes to '${fileType}' configuration.`);

        setTimeout(() => {
            statusEl.textContent = "";
        }, 3000);
    } catch (error) {
        console.error(error);
        statusEl.textContent = "Save failed!";
        statusEl.classList.add("error");
        showToast(`Save failed: ${error.message}`, "error");
        appendLog(`[ERROR] Failed to save configuration '${fileType}': ${error.message}`);
    }
}

// TAILORING SUBMIT SERVICE
async function handleTailoringRun() {
    const jdText = jdTextarea.value.trim();
    if (!jdText) {
        showToast("Please enter a job description", "error");
        return;
    }

    const selectedModel = modelSelect.value;
    appendLog(`[PIPELINE] Starting resume optimization workflow with model: ${selectedModel}`);
    
    // UI State transitions
    tailorBtn.disabled = true;
    tailorBtn.querySelector(".btn-text").classList.add("hidden");
    tailorBtn.querySelector(".spinner-loader").classList.remove("hidden");
    
    outputEmptyState.classList.add("hidden");
    outputResultState.classList.add("hidden");
    outputActions.classList.add("hidden");
    outputProcessingState.classList.remove("hidden");
    
    processingStep.textContent = "Connecting to Gemini Engine...";
    miniLogPre.textContent = "Connecting client to Gemini Model API...\n";

    try {
        // We'll update the steps in a faux progress loop while waiting for response
        const progressSteps = [
            "Sending raw sections to Gemini...",
            "AI is tailoring resume summary to match job keywords...",
            "AI is optimizing technical skills placement...",
            "AI is reframing experience bullet points...",
            "Validating generated LaTeX structure...",
            "Writing tailored LaTeX file...",
            "Compiling LaTeX to PDF with MiKTeX pdflatex..."
        ];
        
        let stepIdx = 0;
        const progressInterval = setInterval(() => {
            if (stepIdx < progressSteps.length) {
                processingStep.textContent = progressSteps[stepIdx];
                miniLogPre.textContent += `[PROCESS] ${progressSteps[stepIdx]}\n`;
                // Scroll mini console to bottom
                document.querySelector(".mini-console").scrollTop = document.querySelector(".mini-console").scrollHeight;
                stepIdx++;
            }
        }, 2200);

        const response = await fetch("/api/tailor", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                job_description: jdText,
                model_name: selectedModel
            })
        });

        clearInterval(progressInterval);

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Tailoring failed on the server.");
        }

        const result = await response.json();
        
        // Append raw backend logs to app console
        appendLog(`--- BACKEND TAILORING RUN LOGS ---\n${result.logs}\n---------------------------------`);
        
        outputProcessingState.classList.add("hidden");
        outputResultState.classList.remove("hidden");
        
        tailoredLatexPreview.value = result.tailored_latex || "";

        if (result.compilation_success) {
            bannerStatus.className = "compilation-success-banner";
            statusTitle.textContent = "Resume Customization Complete";
            statusDesc.textContent = "LaTeX compiled successfully! PDF ready for download.";
            
            // Set dynamic download link with cachebuster
            downloadPdfBtn.href = `/api/download-pdf?t=${new Date().getTime()}`;
            downloadPdfBtn.classList.remove("hidden");
            
            showToast("Resume tailored and compiled!", "success");
        } else {
            bannerStatus.className = "compilation-success-banner failed";
            statusTitle.textContent = "Tailored with Compilation Warnings";
            statusDesc.textContent = "LaTeX source was updated, but PDF compiler failed. Check console logs for errors.";
            
            downloadPdfBtn.classList.add("hidden");
            showToast("Tailoring completed with compilation errors", "warning");
        }
        
        outputActions.classList.remove("hidden");

    } catch (error) {
        console.error(error);
        appendLog(`[ERROR] Pipeline run failed: ${error.message}`);
        showToast(`Tailoring failed: ${error.message}`, "error");
        
        outputProcessingState.classList.add("hidden");
        outputEmptyState.classList.remove("hidden");
    } finally {
        tailorBtn.disabled = false;
        tailorBtn.querySelector(".btn-text").classList.remove("hidden");
        tailorBtn.querySelector(".spinner-loader").classList.add("hidden");
    }
}

// LOGGING UTILITIES
function appendLog(message) {
    const timestamp = new Date().toLocaleTimeString();
    const formattedMsg = `[${timestamp}] ${message}\n`;
    consoleLogsPre.textContent += formattedMsg;
    // Auto scroll console page if it is active
    document.querySelector(".console-body").scrollTop = document.querySelector(".console-body").scrollHeight;
}

// TOAST UTILITIES
function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let iconClass = "fa-circle-check";
    if (type === "error") {
        iconClass = "fa-circle-exclamation";
    } else if (type === "info") {
        iconClass = "fa-circle-info";
    } else if (type === "warning") {
        iconClass = "fa-triangle-exclamation";
    }

    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <span>${message}</span>
    `;

    toastContainer.appendChild(toast);

    // Fade and remove after 3.5 seconds
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(20px)";
        toast.style.transition = "opacity 0.4s ease, transform 0.4s ease";
        setTimeout(() => {
            toast.remove();
        }, 400);
    }, 3500);
}
