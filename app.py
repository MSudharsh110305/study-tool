import os
import requests
import google.generativeai as genai
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from bs4 import BeautifulSoup
import pytz
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import json
import re

load_dotenv()

app = Flask(__name__)

class ConfigLoader:
    """Utility class to load configuration from text files"""
    
    @staticmethod
    def load_lines(filename):
        """Load lines from a text file, ignoring empty lines and comments"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                lines = [line.strip() for line in file.readlines()]
                return [line for line in lines if line and not line.startswith('#')]
        except FileNotFoundError:
            print(f"Warning: {filename} not found, using default values")
            return []
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return []
    
    @staticmethod
    def load_text(filename):
        """Load entire text content from a file"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            print(f"Warning: {filename} not found, using default values")
            return ""
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return ""

class NewsProcessor:

    def __init__(self):
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.email_user = os.getenv('EMAIL_USER')
        self.email_pass = os.getenv('EMAIL_PASSWORD')
        self.recipient = os.getenv('RECIPIENT_EMAIL')

        if not all([self.gemini_key, self.email_user, self.email_pass, self.recipient]):
            raise ValueError("Missing required environment variables")

        genai.configure(api_key=self.gemini_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.load_config()
        self.setup_database()

    def load_config(self):
        """Load all configuration from external files"""
        self.news_queries = ConfigLoader.load_lines('news_queries.txt')
        self.rss_feeds = ConfigLoader.load_lines('rss_feeds.txt')
        self.news_sites = ConfigLoader.load_lines('news_sites.txt')
        self.relevant_keywords = ConfigLoader.load_lines('relevant_keywords.txt')
        self.main_prompt_template = ConfigLoader.load_text('main_prompt.txt')
        self.mcq_prompt_template = ConfigLoader.load_text('mcq_prompt.txt')
        self.email_template = ConfigLoader.load_text('email_template.txt')
        
        if not self.news_queries:
            self.news_queries = [
                'RBI monetary policy India banking',
                'SEBI regulations Indian stock market',
                'Indian economy GDP inflation rate',
                'government schemes India welfare banking',
                'banking sector India developments',
                'financial inclusion digital payments India',
                'NBFC regulations India',
                'agricultural credit rural banking India'
            ]
        
        if not self.rss_feeds:
            self.rss_feeds = [
                'https://economictimes.indiatimes.com/rss_feed.xml',
                'https://www.business-standard.com/rss/finance-103.rss',
                'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',
                'https://timesofindia.indiatimes.com/rssfeeds/296589292.cms',
                'https://www.ndtv.com/india-news/rss',
                'https://economictimes.indiatimes.com/industry/banking/finance/rssfeeds/13358259.cms'
            ]
        
        if not self.news_sites:
            self.news_sites = [
                'https://www.thehindu.com/business/',
                'https://www.livemint.com/economy',
                'https://www.financialexpress.com/economy/'
            ]
        
        if not self.relevant_keywords:
            self.relevant_keywords = [
                'rbi', 'sebi', 'bank', 'economic', 'government', 'policy', 'inflation',
                'gdp', 'market', 'trade', 'scheme', 'award', 'sports', 'international',
                'finance', 'monetary', 'rupee', 'investment', 'growth'
            ]

    def setup_database(self):
        conn = sqlite3.connect('news_reports.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                content TEXT,
                articles_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def calculate_relevance_score(self, article):
        """Calculate relevance score for IBPS RRB banking exam"""
        content = (article['title'] + ' ' + article['description']).lower()
        
        high_relevance_keywords = [
            'rbi', 'sebi', 'bank', 'banking', 'finance', 'financial', 'monetary', 'policy',
            'inflation', 'gdp', 'economic', 'economy', 'government', 'scheme', 'yojana',
            'rupee', 'investment', 'growth', 'credit', 'loan', 'deposit', 'interest',
            'rate', 'budget', 'fiscal', 'revenue', 'tax', 'subsidy', 'npa', 'nbfc',
            'cooperative', 'rrb', 'rural', 'agriculture', 'farmer', 'kisan', 'msp'
        ]
        
        medium_relevance_keywords = [
            'trade', 'market', 'nifty', 'sensex', 'mutual', 'fund', 'insurance',
            'bonds', 'equity', 'debt', 'capital', 'regulation', 'compliance',
            'digital', 'payment', 'upi', 'fintech'
        ]
        
        low_relevance_keywords = [
            'international', 'foreign', 'sports', 'award', 'achievement'
        ]
        
        score = 0
        for keyword in high_relevance_keywords:
            if keyword in content:
                score += 3
        
        for keyword in medium_relevance_keywords:
            if keyword in content:
                score += 2
                
        for keyword in low_relevance_keywords:
            if keyword in content:
                score += 1
                
        return score

    def improved_categorization(self, article):
        """Improved categorization logic with better accuracy"""
        content = (article['title'] + ' ' + article['description']).lower()
        
        banking_keywords = [
            'rbi', 'sebi', 'bank', 'banking', 'finance', 'financial', 'credit',
            'loan', 'deposit', 'interest', 'monetary', 'npa', 'nbfc', 'cooperative',
            'rrb', 'payment', 'upi', 'digital banking', 'fintech'
        ]
        
        economic_keywords = [
            'gdp', 'inflation', 'growth', 'economic', 'economy', 'fiscal',
            'revenue', 'budget', 'trade', 'export', 'import', 'market',
            'nifty', 'sensex', 'investment'
        ]
        
        government_scheme_keywords = [
            'scheme', 'yojana', 'welfare', 'subsidy', 'government program',
            'policy launch', 'initiative', 'beneficiary', 'allocation'
        ]
        
        international_keywords = [
            'international', 'foreign', 'global', 'world', 'diplomatic',
            'bilateral', 'multilateral', 'treaty', 'agreement'
        ]
        
        sports_awards_keywords = [
            'sport', 'sports', 'award', 'medal', 'championship', 'tournament',
            'achievement', 'honor', 'recognition', 'prize'
        ]
        
        if any(kw in content for kw in banking_keywords):
            return 'banking_finance'
        elif any(kw in content for kw in economic_keywords):
            return 'economic'
        elif any(kw in content for kw in government_scheme_keywords):
            return 'government_schemes'
        elif any(kw in content for kw in international_keywords):
            return 'international'
        elif any(kw in content for kw in sports_awards_keywords):
            return 'sports_awards'
        else:
            return 'general'

    def fetch_real_news(self):
        """Fetch real news from multiple sources with improved filtering"""
        all_articles = []

        if self.news_api_key:
            for query in self.news_queries:
                try:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        'q': query,
                        'language': 'en',
                        'sortBy': 'publishedAt',
                        'from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                        'pageSize': 20,
                        'apiKey': self.news_api_key
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        articles = data.get('articles', [])
                        for article in articles:
                            if article.get('title') and article.get('description'):
                                all_articles.append({
                                    'title': article['title'],
                                    'description': article['description'],
                                    'source': article.get('source', {}).get('name', 'News API'),
                                    'url': article.get('url', ''),
                                    'published': article.get('publishedAt', '')
                                })
                    time.sleep(0.5)
                except Exception as e:
                    print(f"News API error for query {query}: {e}")

        for feed_url in self.rss_feeds:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
                response = requests.get(feed_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')

                for item in items:
                    title = item.find('title')
                    description = item.find('description')
                    pub_date = item.find('pubDate')
                    if title and description:
                        title_text = title.text.strip()
                        desc_text = BeautifulSoup(description.text, 'html.parser').get_text().strip()[:300]
                        all_articles.append({
                            'title': title_text,
                            'description': desc_text,
                            'source': feed_url.split('/')[2],
                            'url': '',
                            'published': pub_date.text if pub_date else ''
                        })
            except Exception as e:
                print(f"RSS feed error for {feed_url}: {e}")

        for site_url in self.news_sites:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
                response = requests.get(site_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')

                headlines = soup.find_all(['h1', 'h2', 'h3'], class_=lambda x: x and ('headline' in x.lower() or 'title' in x.lower()))
                for headline in headlines[:5]:
                    title_text = headline.get_text().strip()
                    if len(title_text) > 20:
                        desc_elem = headline.find_next(['p', 'div'], class_=lambda x: x and ('summary' in x.lower() or 'desc' in x.lower()))
                        desc_text = desc_elem.get_text().strip()[:200] if desc_elem else title_text
                        all_articles.append({
                            'title': title_text,
                            'description': desc_text,
                            'source': site_url.split('/')[2],
                            'url': site_url,
                            'published': datetime.now().isoformat()
                        })
            except Exception as e:
                print(f"Web scraping error for {site_url}: {e}")

        filtered_articles = []
        seen_titles = set()
        
        for article in all_articles:
            title = article['title'].lower()
            title_key = ' '.join(title.split()[:8])
            
            if title_key not in seen_titles and len(article['title']) > 15:
                relevance_score = self.calculate_relevance_score(article)
                if relevance_score >= 2:
                    seen_titles.add(title_key)
                    article['relevance_score'] = relevance_score
                    filtered_articles.append(article)

        filtered_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        print(f"Fetched {len(filtered_articles)} highly relevant articles")
        return filtered_articles

    def categorize_and_process_news(self, articles):
        """Improved categorization and processing with clean format"""
        if not articles:
            return "No news articles found to process."

        categories = {
            'banking_finance': [],
            'economic': [],
            'government_schemes': [],
            'international': [],
            'sports_awards': [],
            'general': []
        }

        for article in articles:
            category = self.improved_categorization(article)
            categories[category].append(article)

        processed_content = []
        current_date = datetime.now().strftime('%d %B %Y')

        for category_name, category_articles in categories.items():
            if not category_articles:
                continue

            category_articles = sorted(category_articles, key=lambda x: x.get('relevance_score', 0), reverse=True)[:8]

            articles_text = "\n\n".join([
                f"TITLE: {article['title']}\nDESCRIPTION: {article['description']}\nSOURCE: {article['source']}\nRELEVANCE_SCORE: {article.get('relevance_score', 'N/A')}"
                for article in category_articles
            ])

            prompt = self.main_prompt_template.format(
                current_date=current_date,
                articles_text=articles_text
            )

            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=4000,
                        top_p=0.95,
                        top_k=40
                    )
                )

                if response and response.text:
                    category_title = category_name.replace('_', ' ').title()
                    processed_content.append(f"\n{category_title}\n\n{response.text.strip()}")

            except Exception as e:
                print(f"Gemini processing error for {category_name}: {e}")

        if processed_content:
            final_content = f"IBPS RRB Daily News Summary - {current_date}\n"
            final_content += f"Total High-Quality Articles Processed: {len(articles)}\n\n"
            final_content += "\n".join(processed_content)

            try:
                mcq_prompt = f"{final_content}\n\n{self.mcq_prompt_template}"
                mcq_response = self.model.generate_content(
                    mcq_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2000
                    )
                )
                if mcq_response and mcq_response.text:
                    final_content += f"\n\nPractice MCQs Based on Today's News\n\n{mcq_response.text.strip()}"
            except Exception as e:
                print(f"MCQ generation error: {e}")

            final_content = self.fix_currency_symbols(final_content)
            
            return final_content
        else:
            return "Unable to process news articles with AI."

    def fix_currency_symbols(self, content):
        """Fix currency symbol encoding issues"""
        content = re.sub(r'\bI(\d+(?:,\d+)*(?:\.\d+)?)\s*(crore|lakh|billion|million|thousand)', r'₹\1 \2', content)
        content = re.sub(r'Rs\.?\s*(\d+)', r'₹\1', content)
        content = re.sub(r'INR\s*(\d+)', r'₹\1', content)
        content = content.replace('I crore', '₹ crore')
        content = content.replace('I lakh', '₹ lakh')
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        return content

    def create_pdf(self, content, date_str):
        """Create formatted PDF with clean formatting - only titles bold and big"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()

            main_title_style = ParagraphStyle(
                'MainTitle', parent=styles['Title'], fontSize=18,
                textColor=HexColor('#2c3748'), spaceAfter=20, alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )

            category_title_style = ParagraphStyle(
                'CategoryTitle', parent=styles['Heading1'], fontSize=16,
                textColor=HexColor('#1a365d'), spaceBefore=15, spaceAfter=10,
                fontName='Helvetica-Bold', alignment=TA_LEFT
            )

            headline_style = ParagraphStyle(
                'Headline', parent=styles['Heading2'], fontSize=14,
                textColor=HexColor('#2d3748'), spaceBefore=8, spaceAfter=4,
                fontName='Helvetica-Bold', alignment=TA_LEFT
            )

            normal_style = ParagraphStyle(
                'Normal', parent=styles['Normal'], fontSize=11,
                spaceBefore=3, spaceAfter=8, leading=13,
                fontName='Helvetica', alignment=TA_LEFT
            )

            story = []
            
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 6))
                elif line.startswith('IBPS RRB Daily News Summary'):
                    story.append(Paragraph(line, main_title_style))
                elif line in ['Banking Finance', 'Economic', 'Government Schemes', 'International', 'Sports Awards', 'General', 'Practice MCQs Based on Today\'s News']:
                    story.append(Paragraph(line, category_title_style))
                elif line.startswith('HEADLINE:'):
                    clean_line = line.replace('HEADLINE:', '').strip()
                    story.append(Paragraph(clean_line, headline_style))
                elif line.startswith('SUMMARY:'):
                    clean_line = line.replace('SUMMARY:', '').strip()
                    story.append(Paragraph(clean_line, normal_style))
                elif line.startswith('Q') and ('A)' in line or 'B)' in line or 'C)' in line or 'D)' in line):
                    story.append(Paragraph(line, normal_style))
                elif line.startswith('Answer:'):
                    story.append(Paragraph(line, normal_style))
                    story.append(Spacer(1, 8))
                elif line.startswith('Total High-Quality Articles'):
                    story.append(Paragraph(line, normal_style))
                else:
                    story.append(Paragraph(line, normal_style))

            doc.build(story)
            return buffer.getvalue()

        except Exception as e:
            print(f"PDF creation error: {e}")
            return None

    def send_email(self, content, pdf_data, date_str):
        """Send email with news summary"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.recipient
            msg['Subject'] = f"IBPS RRB Daily News Summary - {date_str}"

            email_body = self.email_template.format(date_str=date_str) if self.email_template else f"""Dear IBPS RRB Aspirant,

Your clean and formatted daily news summary for {date_str} is ready.

This final enhanced report features:

• Clean formatting with proper titles and content
• Fixed currency symbols (₹)
• No formatting issues or broken symbols
• High-quality relevant articles only
• Banking and Financial sector developments
• Economic indicators and policy changes  
• Government schemes and initiatives
• Clean MCQs without formatting issues

All content is processed from live news sources and optimized for IBPS RRB exam preparation.

Best wishes for your preparation!

IBPS RRB Study Assistant"""

            msg.attach(MIMEText(email_body, 'plain'))

            if pdf_data:
                from email.mime.base import MIMEBase
                from email import encoders

                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pdf_data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename=IBPS_RRB_News_Clean_{date_str.replace(" ", "_")}.pdf'
                )
                msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email_user, self.email_pass)
            server.sendmail(self.email_user, self.recipient, msg.as_string())
            server.quit()
            return True

        except Exception as e:
            print(f"Email sending error: {e}")
            return False

    def generate_daily_report(self, force=False):
        """Main function to generate daily report with clean formatting"""
        ist_tz = pytz.timezone('Asia/Kolkata')
        date_str = datetime.now(ist_tz).strftime('%d %B %Y')

        try:
            print(f"Starting clean format news processing for {date_str}")

            if not force:
                conn = sqlite3.connect('news_reports.db', check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM daily_reports WHERE date = ?', (date_str,))
                if cursor.fetchone():
                    print(f"Report already generated for {date_str}")
                    conn.close()
                    return {"status": "already_exists", "date": date_str}
                conn.close()
            else:
                print(f"Force generating clean format report for {date_str}")

            articles = self.fetch_real_news()
            if not articles:
                print("No relevant articles found")
                return {"status": "error", "message": "No relevant news articles found"}

            processed_content = self.categorize_and_process_news(articles)

            pdf_data = self.create_pdf(processed_content, date_str)

            email_sent = self.send_email(processed_content, pdf_data, date_str)

            conn = sqlite3.connect('news_reports.db', check_same_thread=False)
            cursor = conn.cursor()
            
            if force:
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_reports (date, content, articles_count)
                    VALUES (?, ?, ?)
                ''', (date_str, processed_content, len(articles)))
            else:
                cursor.execute('''
                    INSERT INTO daily_reports (date, content, articles_count)
                    VALUES (?, ?, ?)
                ''', (date_str, processed_content, len(articles)))
            
            conn.commit()
            conn.close()

            status_text = "Force generated" if force else "Generated"
            print(f"Clean format report {status_text} successfully - Articles: {len(articles)}, Email: {'✓' if email_sent else '✗'}")

            return {
                "status": "success",
                "date": date_str,
                "articles_processed": len(articles),
                "email_sent": email_sent,
                "forced": force
            }

        except Exception as e:
            print(f"Report generation error: {e}")
            return {"status": "error", "message": str(e)}

try:
    processor = NewsProcessor()
    print("Clean Format News processor initialized successfully")
except Exception as e:
    print(f"Initialization error: {e}")
    processor = None

@app.route('/')
def dashboard():
    if not processor:
        return "System not configured properly. Check environment variables."
    
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IBPS RRB News Generator - Clean Format</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; text-align: center; }}
            .info {{ background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .status {{ padding: 10px; border-radius: 5px; margin: 10px 0; }}
            .success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            button {{ background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 5px; }}
            button:hover {{ background: #0056b3; }}
            .force-btn {{ background: #dc3545; }}
            .force-btn:hover {{ background: #c82333; }}
            .config-info {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #ffeaa7; }}
            .button-group {{ text-align: center; margin: 30px 0; }}
            .improvements {{ background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border: 1px solid #c3e6cb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>IBPS RRB News Generator (Final Clean v4.0)</h1>
            <div class="info">
                <strong>Current Time:</strong> {ist_time.strftime('%d %B %Y, %I:%M %p IST')}<br>
                <strong>AI Model:</strong> Gemini-1.5-Flash (Clean Format)<br>
                <strong>Email Status:</strong> {'Configured' if processor.email_user else 'Not Configured'}
            </div>
            
            <div class="improvements">
                <strong>FINAL FIXES APPLIED:</strong><br>
                ✓ Only titles are bold and big (headlines and categories)<br>
                ✓ All content text is normal formatting<br>
                ✓ Removed ALL ** symbols from MCQs<br>
                ✓ Fixed currency symbols (proper ₹ display)<br>
                ✓ Clean PDF formatting without HTML issues<br>
                ✓ Perfect readability and professional format
            </div>
            
            <div class="config-info">
                <strong>System Status:</strong><br>
                • News Queries: {len(processor.news_queries)} loaded<br>
                • RSS Feeds: {len(processor.rss_feeds)} loaded<br>
                • News Sites: {len(processor.news_sites)} loaded<br>
                • Keywords: {len(processor.relevant_keywords)} loaded<br>
                • Format: Clean Professional Template
            </div>
            
            <div class="button-group">
                <button onclick="generateReport()">Generate Clean Report</button>
                <button class="force-btn" onclick="forceGenerateReport()">Force Generate</button>
            </div>
            
            <div id="status"></div>
            
            <div style="margin-top: 30px; text-align: center; color: #666;">
                <p>Final Clean Format IBPS RRB Banking Exam News System</p>
                <p>Perfect formatting • Professional appearance • Ready for exam prep</p>
            </div>
        </div>
        
        <script>
        function generateReport() {{
            document.getElementById('status').innerHTML = '<div class="status">Generating final clean report... This may take 2-3 minutes</div>';
            fetch('/generate')
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        document.getElementById('status').innerHTML = 
                            `<div class="status success">Perfect clean report generated!<br>
                            Articles processed: ${{data.articles_processed}}<br>
                            Email sent: ${{data.email_sent ? 'Yes' : 'No'}}<br>
                            <small>Clean formatting with proper titles and content</small></div>`;
                    }} else if (data.status === 'already_exists') {{
                        document.getElementById('status').innerHTML = 
                            '<div class="status success">Report already generated for today<br><small>Use "Force Generate" for new clean version</small></div>';
                    }} else {{
                        document.getElementById('status').innerHTML = 
                            `<div class="status error">Error: ${{data.message}}</div>`;
                    }}
                }})
                .catch(error => {{
                    document.getElementById('status').innerHTML = 
                        '<div class="status error">Network error occurred</div>';
                }});
        }}
        
        function forceGenerateReport() {{
            if (confirm('Generate new clean formatted report (will overwrite existing)?')) {{
                document.getElementById('status').innerHTML = '<div class="status">Force generating clean report... This may take 2-3 minutes</div>';
                fetch('/force-generate')
                    .then(response => response.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            document.getElementById('status').innerHTML = 
                                `<div class="status success">Perfect clean report generated!<br>
                                Articles processed: ${{data.articles_processed}}<br>
                                Email sent: ${{data.email_sent ? 'Yes' : 'No'}}<br>
                                <small>Final clean format with perfect formatting</small></div>`;
                        }} else {{
                            document.getElementById('status').innerHTML = 
                                `<div class="status error">Error: ${{data.message}}</div>`;
                        }}
                    }})
                    .catch(error => {{
                        document.getElementById('status').innerHTML = 
                            '<div class="status error">Network error occurred</div>';
                    }});
            }}
        }}
        </script>
    </body>
    </html>
    """
    return html

@app.route('/generate')
def generate_report():
    if not processor:
        return jsonify({"status": "error", "message": "System not initialized"})
    
    result = processor.generate_daily_report(force=False)
    return jsonify(result)

@app.route('/force-generate')
def force_generate_report():
    if not processor:
        return jsonify({"status": "error", "message": "System not initialized"})
    
    result = processor.generate_daily_report(force=True)
    return jsonify(result)

@app.route('/status')
def status():
    if not processor:
        return jsonify({"status": "error", "message": "System not initialized"})
    
    conn = sqlite3.connect('news_reports.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT date, articles_count, created_at FROM daily_reports ORDER BY created_at DESC LIMIT 10')
    reports = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "status": "active",
        "recent_reports": [{"date": r[0], "articles": r[1], "created": r[2]} for r in reports]
    })

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: processor.generate_daily_report() if processor else None,
    trigger=CronTrigger(hour=20, minute=0, timezone=pytz.timezone('Asia/Kolkata')),
    id='daily_news_report',
    name='Generate daily IBPS RRB news report',
    replace_existing=True
)

scheduler.start()

if __name__ == '__main__':
    print("Final Clean Format IBPS RRB News Generator starting...")
    print(f"Loaded {len(processor.news_queries) if processor else 0} news queries")
    print(f"Loaded {len(processor.rss_feeds) if processor else 0} RSS feeds") 
    print(f"Loaded {len(processor.news_sites) if processor else 0} news sites")
    app.run(host='0.0.0.0', port=5000, debug=True)
