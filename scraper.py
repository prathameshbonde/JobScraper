import os
import json
import yaml
import time
import random
import pandas as pd
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from jobspy import scrape_jobs

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def is_title_match(job_title, configured_titles):
    if not job_title or not configured_titles:
        return False
    job_title_lower = job_title.lower()
    for title in configured_titles:
        if title.lower() in job_title_lower:
            return True
    return False

def calculate_job_score(company, date_posted, tier_1_companies):
    # 1. Company Tier Boost
    company_name = str(company).strip().lower()
    is_tier_1 = False
    for tier_1_company in tier_1_companies:
        if tier_1_company.strip().lower() in company_name:
            is_tier_1 = True
            break
            
    company_score = 100 if is_tier_1 else 0
    
    # 2. Freshness Boost
    freshness_hours = 24.0
    if date_posted:
        try:
            if isinstance(date_posted, (date, datetime)):
                post_date = date_posted
            else:
                post_date = datetime.strptime(str(date_posted).strip()[:10], "%Y-%m-%d").date()
            today = date.today()
            delta = today - post_date
            freshness_hours = max(0.0, float(delta.days * 24))
        except Exception:
            freshness_hours = 24.0
            
    freshness_score = max(0.0, 24.0 - freshness_hours)
    total_score = company_score + freshness_score
    
    return total_score, is_tier_1, freshness_hours

def scrape_single_query(title, location, results_wanted, hours_old, country, max_retries=3):
    # Add a small stagger delay on thread startup to avoid concurrent rate-limit triggers
    stagger_delay = random.uniform(0.2, 2.0)
    time.sleep(stagger_delay)
    
    df = pd.DataFrame()
    for attempt in range(max_retries):
        print(f"[SCRAPER] [INFO] Scrape attempt {attempt+1}/{max_retries} for title='{title}', location='{location}', results_wanted={results_wanted}...")
        try:
            if attempt > 0:
                sleep_time = random.uniform(3, 8)
                print(f"[SCRAPER] [DEBUG] Rate limit cooling down. Sleeping for {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                
            df = scrape_jobs(
                site_name=["linkedin"],
                search_term=title,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_submission=country,
                linkedin_fetch_description=True
            )
            
            if not df.empty:
                print(f"[SCRAPER] [INFO] Scrape attempt {attempt+1} succeeded. Yield: {len(df)} postings found for '{title}'.")
            else:
                print(f"[SCRAPER] [INFO] Scraped successfully but no postings returned for '{title}' in '{location}'.")
            
            break
        except Exception as e:
            print(f"[SCRAPER] [ERROR] Scraper execution crashed on attempt {attempt+1} for '{title}': {e}")
            if attempt == max_retries - 1:
                print(f"[SCRAPER] [WARNING] All {max_retries} attempts crashed for '{title}' in '{location}'.")
                
    return df

def fetch_and_filter_jobs():
    print("[SCRAPER] [INFO] Loading configuration from config.yaml...")
    config = load_config()
    params = config.get("search_parameters", {})
    
    titles = params.get("titles", ["Software Engineer"])
    locations = params.get("locations", ["Bengaluru"])
    country = params.get("country", "india")
    results_wanted = params.get("results_wanted", 30)
    hours_old = params.get("hours_old", 24)
    tier_1_companies = params.get("tier_1_companies", [])
    
    print(f"[SCRAPER] [INFO] Loaded Search Configurations:")
    print(f"  - Target Job Titles: {titles}")
    print(f"  - Locations: {locations}")
    print(f"  - Target Country: {country}")
    print(f"  - Max Results Desired Per Scraper Run: {results_wanted}")
    print(f"  - Post Age Threshold: {hours_old} hours")
    print(f"  - Tier 1 Companies (High Priority Boost): {tier_1_companies}")
    
    # Load historical processed jobs database
    state_file = "processed_jobs.json"
    print(f"[SCRAPER] [INFO] Opening state database file: '{state_file}'...")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                processed_jobs = json.load(f)
            print(f"[SCRAPER] [INFO] Successfully loaded {len(processed_jobs)} historical processed jobs from state database.")
        except Exception as e:
            print(f"[SCRAPER] [WARNING] Failed to parse {state_file} ({e}). Initializing empty list.")
            processed_jobs = []
    else:
        print(f"[SCRAPER] [INFO] State database '{state_file}' does not exist yet. Starting fresh.")
        processed_jobs = []
        
    processed_keys = {job.get("job_key") for job in processed_jobs if "job_key" in job}
    print(f"[SCRAPER] [DEBUG] Historical processed keys loaded: {list(processed_keys)[:5]}... (total {len(processed_keys)} keys)")
    
    aggregated_dfs = []
    
    # Generate list of tasks (combinations of title and location)
    tasks = []
    for title in titles:
        for location in locations:
            tasks.append((title, location))
            
    max_workers = min(len(tasks), 4) # Avoid spawning too many threads, max 4 workers is safe
    print(f"[SCRAPER] [INFO] Initiating parallel scraping with {max_workers} threads for {len(tasks)} target search queries...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                scrape_single_query,
                task[0],
                task[1],
                results_wanted,
                hours_old,
                country
            ): task for task in tasks
        }
        
        for future in as_completed(futures):
            task = futures[future]
            title, location = task
            try:
                df = future.result()
                if not df.empty:
                    aggregated_dfs.append(df)
            except Exception as e:
                print(f"[SCRAPER] [ERROR] Parallel scraping task failed for '{title}' in '{location}': {e}")
                
    if not aggregated_dfs:
        print("[SCRAPER] [INFO] No job search results aggregated today from any source.")
        return []
        
    # Combine dataframes and drop duplicate scraped rows
    print("[SCRAPER] [INFO] Merging results from all scraped sources...")
    combined_df = pd.concat(aggregated_dfs, ignore_index=True)
    initial_length = len(combined_df)
    
    if "job_url" in combined_df.columns:
        combined_df.drop_duplicates(subset=["job_url"], inplace=True)
        print(f"[SCRAPER] [INFO] Deduplicated combined DataFrame by URL: dropped {initial_length - len(combined_df)} duplicates (remaining: {len(combined_df)}).")
        
    validated_jobs = []
    skipped_dupes_count = 0
    skipped_invalid_count = 0
    skipped_title_filter_count = 0
    
    print("[SCRAPER] [INFO] Starting state deduplication and parsing checks...")
    for idx, row in combined_df.iterrows():
        site = row.get("site", "unknown")
        site_id = str(row.get("id", ""))
        
        if site_id:
            unique_key = f"{site}_{site_id}"
        else:
            unique_key = str(row.get("job_url", f"manual_{idx}"))
            
        # Filter duplicates against git state
        if unique_key in processed_keys:
            skipped_dupes_count += 1
            # Very verbose tracking commented out or kept as minor debug statements
            # print(f"[SCRAPER] [DEBUG] Key '{unique_key}' already exists in state database. Skipping.")
            continue
            
        job_payload = {
            'job_key': unique_key,
            'title': str(row.get('title', 'N/A')).strip(),
            'company': str(row.get('company', 'N/A')).strip(),
            'location': str(row.get('location', 'N/A')).strip(),
            'url': str(row.get('job_url', '')).strip(),
            'description': str(row.get('description') or '').strip()
        }

        if not job_payload['description'] or job_payload['description'].lower() in ('none', 'nan'):
            job_payload['description'] = ''
            print(f"[SCRAPER] [WARNING] No description fetched for '{job_payload['title']}' at '{job_payload['company']}'. AI tailoring will have no JD to work with.")
        
        # Validation checks
        if job_payload['title'] == 'N/A' or not job_payload['url']:
            skipped_invalid_count += 1
            print(f"[SCRAPER] [WARNING] Skipped listing with invalid schema: title='{job_payload['title']}', url='{job_payload['url']}'")
            continue
            
        # Strict job title filter check
        if not is_title_match(job_payload['title'], titles):
            skipped_title_filter_count += 1
            # print(f"[SCRAPER] [DEBUG] Skipped listing due to job title mismatch: title='{job_payload['title']}'")
            continue
            
        # Calculate Priority Ranking Score
        total_score, is_tier_1, freshness_hours = calculate_job_score(
            job_payload['company'],
            row.get("date_posted"),
            tier_1_companies
        )
        
        job_payload['score'] = total_score
        job_payload['is_tier_1'] = is_tier_1
        job_payload['freshness_hours'] = freshness_hours
        
        validated_jobs.append(job_payload)
        # print(f"[SCRAPER] [DEBUG] Verified new unique posting: '{job_payload['title']}' at '{job_payload['company']}' (Key: {unique_key})")
                
    # Sort validated jobs by total ranking score (highest score first)
    validated_jobs.sort(key=lambda x: x.get('score', 0.0), reverse=True)
    
    print(f"[SCRAPER] [INFO] Processing complete:")
    print(f"  - Total Raw Combined Postings: {initial_length}")
    print(f"  - Skipped (Seen Duplicates in state): {skipped_dupes_count}")
    print(f"  - Skipped (Missing Title or URL schema): {skipped_invalid_count}")
    print(f"  - Skipped (Title mismatch filter): {skipped_title_filter_count}")
    print(f"  - Yield (New Unprocessed Jobs): {len(validated_jobs)}")
    
    if validated_jobs:
        print(f"[SCRAPER] [INFO] Priority Ranking sorted {len(validated_jobs)} jobs. Top matches:")
        for idx, job in enumerate(validated_jobs[:5]):
            print(f"  - Rank {idx+1}: '{job['title']}' at '{job['company']}' (Score: {job['score']:.1f}, Tier-1: {job['is_tier_1']}, Age: {job['freshness_hours']:.1f} hrs)")
            
    return validated_jobs
