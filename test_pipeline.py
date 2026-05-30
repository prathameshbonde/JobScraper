import sys
from unittest.mock import MagicMock
import types

# Mock new google-genai SDK for testing robustness
google_mock = types.ModuleType('google')
sys.modules['google'] = google_mock

genai_mock = types.ModuleType('google.genai')
google_mock.genai = genai_mock
sys.modules['google.genai'] = genai_mock

types_mock = types.ModuleType('google.genai.types')
genai_mock.types = types_mock
sys.modules['google.genai.types'] = types_mock

genai_mock.Client = MagicMock()
types_mock.GenerateContentConfig = MagicMock()

# Setup client generator hierarchy
client_instance = MagicMock()
genai_mock.Client.return_value = client_instance
response_mock = MagicMock()
client_instance.models.generate_content.return_value = response_mock
response_mock.text = "Mocked Response Text"

sys.modules['jobspy'] = MagicMock()

import unittest
import re
from rewriter import sanitize_for_latex, strip_markdown
from scraper import load_config, is_title_match, calculate_job_score

class TestPipelineComponents(unittest.TestCase):

    def test_latex_sanitization(self):
        # 1. Unescaped characters should get escaped
        self.assertEqual(sanitize_for_latex("Java & Spring Boot"), r"Java \& Spring Boot")
        self.assertEqual(sanitize_for_latex("Achieved 95% efficiency gains"), r"Achieved 95\% efficiency gains")
        self.assertEqual(sanitize_for_latex("Saved $1000 annually"), r"Saved \$1000 annually")
        self.assertEqual(sanitize_for_latex("user_name variable"), r"user\_name variable")
        self.assertEqual(sanitize_for_latex("Check ticket #123"), r"Check ticket \#123")
        
        # 2. Already escaped characters should NOT be double-escaped
        self.assertEqual(sanitize_for_latex(r"Java \& Spring Boot"), r"Java \& Spring Boot")
        self.assertEqual(sanitize_for_latex(r"Achieved 95\% efficiency"), r"Achieved 95\% efficiency")
        self.assertEqual(sanitize_for_latex(r"Saved \$1000"), r"Saved \$1000")
        self.assertEqual(sanitize_for_latex(r"user\_name variable"), r"user\_name variable")
        self.assertEqual(sanitize_for_latex(r"Check ticket \#123"), r"Check ticket \#123")
        
        # 3. Mixed escaped and unescaped
        self.assertEqual(sanitize_for_latex(r"We have 10% and 20\% growth"), r"We have 10\% and 20\% growth")
        
        # 4. Protected mathematical tildes ($\sim$) should remain intact
        self.assertEqual(sanitize_for_latex(r"boosting performance by $\sim$30%"), r"boosting performance by $\sim$30\%")
        self.assertEqual(sanitize_for_latex(r"improving by $\sim$ 35%"), r"improving by $\sim$ 35\%")

    def test_strip_markdown(self):
        # Standard latex code blocks
        self.assertEqual(strip_markdown("```latex\n\\item Dynamic text\n```"), "\\item Dynamic text")
        # Code block without language identifier
        self.assertEqual(strip_markdown("```\n\\item Dynamic text\n```"), "\\item Dynamic text")
        # Text without code blocks
        self.assertEqual(strip_markdown("\\item Dynamic text"), "\\item Dynamic text")

    def test_config_loading(self):
        config = load_config()
        self.assertIn("search_parameters", config)
        self.assertIn("email_settings", config)
        
        params = config["search_parameters"]
        self.assertIn("titles", params)
        self.assertIn("locations", params)
        self.assertTrue(len(params["titles"]) > 0)

    def test_safe_slice_replacement(self):
        from rewriter import generate_tailored_resume
        from unittest.mock import patch
        
        master_latex = (
            "Some header\n"
            "% %START_SUMMARY%\n"
            "Original summary text\n"
            "% %END_SUMMARY%\n"
            "Some footer"
        )
        
        # Mock tailor_section to return a string containing backslashes (like \item or \textbf)
        # which would trigger a 'bad escape' error in re.sub()
        tailored_summary = r"\textbf{Tailored} summary with \item bullets and \i escapes"
        
        with patch('rewriter.tailor_section', return_value=tailored_summary):
            result = generate_tailored_resume(master_latex, "Some target JD")
            
            # The result should contain the tailored content correctly replaced
            self.assertIn(tailored_summary, result)
            self.assertIn("% %START_SUMMARY%", result)
            self.assertIn("% %END_SUMMARY%", result)

    def test_title_filtering(self):
        # 1. Matching substring (case-insensitive)
        self.assertTrue(is_title_match("Senior Software Engineer", ["Software Engineer"]))
        self.assertTrue(is_title_match("software engineer 2", ["Software Engineer 2"]))
        self.assertTrue(is_title_match("SOFTWARE ENGINEER II", ["software engineer ii"]))
        
        # 2. Non-matching title
        self.assertFalse(is_title_match("Tool Tester", ["Software Engineer", "Software Engineer 2"]))
        
        # 3. Empty boundaries
        self.assertFalse(is_title_match("", ["Software Engineer"]))
        self.assertFalse(is_title_match("Software Engineer", []))
        self.assertFalse(is_title_match(None, ["Software Engineer"]))

    def test_job_ranking(self):
        from datetime import date, timedelta
        tier_1 = ["Google", "Amazon", "Abnormal AI"]
        
        # 1. Tier-1 company boost works
        # Today (age 0)
        score1, is_t1_1, age1 = calculate_job_score("Google LLC", date.today(), tier_1)
        self.assertTrue(is_t1_1)
        self.assertEqual(age1, 0.0)
        self.assertEqual(score1, 124.0) # 100 + 24
        
        # Yesterday (age 24 hrs)
        score2, is_t1_2, age2 = calculate_job_score("Amazon India", date.today() - timedelta(days=1), tier_1)
        self.assertTrue(is_t1_2)
        self.assertEqual(age2, 24.0)
        self.assertEqual(score2, 100.0) # 100 + 0
        
        # 2. Non-Tier-1 company has lower score but maintains freshness sorting
        # Non-tier-1 today
        score3, is_t1_3, age3 = calculate_job_score("Random Corp", date.today(), tier_1)
        self.assertFalse(is_t1_3)
        self.assertEqual(score3, 24.0) # 0 + 24
        
        # Non-tier-1 yesterday
        score4, is_t1_4, age4 = calculate_job_score("Random Corp", date.today() - timedelta(days=1), tier_1)
        self.assertFalse(is_t1_4)
        self.assertEqual(score4, 0.0) # 0 + 0
        
        # 3. Precedence check: Tier-1 yesterday always beats Non-Tier-1 today
        # score2 (100.0) > score3 (24.0)
        self.assertTrue(score2 > score3)

if __name__ == "__main__":
    unittest.main()
