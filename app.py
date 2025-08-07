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
from reportlab.lib.enums import TA_CENTER
import io
from bs4 import BeautifulSoup
import pytz
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import json

load_dotenv()

app = Flask(__name__)

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
        
        self.setup_database()
    
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
    
    def fetch_real_news(self):
        """Fetch real news from multiple sources"""
        all_articles = []
        
        # 1. News API - Get real banking and economic news
        if self.news_api_key:
            news_queries = [
                'RBI monetary policy India banking',
                'SEBI regulations Indian stock market',
                'Indian economy GDP inflation rate',
                'government schemes India welfare',
                'international trade India agreements',
                'Indian sports achievements awards',
                'banking sector India developments'
            ]
            
            for query in news_queries:
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
        
        # 2. RSS Feed scraping from major Indian news sources
        rss_feeds = [
            'https://economictimes.indiatimes.com/rss_feed.xml',
            'https://www.business-standard.com/rss/finance-103.rss',
            'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',
            'https://timesofindia.indiatimes.com/rssfeeds/296589292.cms',
            'https://www.ndtv.com/india-news/rss',
            'https://economictimes.indiatimes.com/industry/banking/finance/rssfeeds/13358259.cms'
        ]
        
        for feed_url in rss_feeds:
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
        
        # 3. Web scraping from specific news sites
        news_sites = [
            'https://www.thehindu.com/business/',
            'https://www.livemint.com/economy',
            'https://www.financialexpress.com/economy/'
        ]
        
        for site_url in news_sites:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
                response = requests.get(site_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract headlines and descriptions
                headlines = soup.find_all(['h1', 'h2', 'h3'], class_=lambda x: x and ('headline' in x.lower() or 'title' in x.lower()))
                
                for headline in headlines[:5]:
                    title_text = headline.get_text().strip()
                    if len(title_text) > 20:
                        # Try to find associated description
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
        
        # Remove duplicates and filter for relevance
        unique_articles = []
        seen_titles = set()
        
        for article in all_articles:
            title = article['title'].lower()
            title_key = ' '.join(title.split()[:8])
            
            if title_key not in seen_titles and len(article['title']) > 15:
                # Check relevance for banking exams
                content = (article['title'] + ' ' + article['description']).lower()
                relevant_keywords = [
                    'rbi', 'sebi', 'bank', 'economic', 'government', 'policy', 'inflation',
                    'gdp', 'market', 'trade', 'scheme', 'award', 'sports', 'international',
                    'finance', 'monetary', 'rupee', 'investment', 'growth'
                ]
                
                if any(keyword in content for keyword in relevant_keywords):
                    seen_titles.add(title_key)
                    unique_articles.append(article)
        
        print(f"Fetched {len(unique_articles)} unique relevant articles")
        return unique_articles
    
    def categorize_and_process_news(self, articles):
        """Categorize news and process with Gemini AI"""
        if not articles:
            return "No news articles found to process."
        
        # Group articles by category
        categories = {
            'banking_finance': [],
            'economic': [],
            'government_schemes': [],
            'international': [],
            'sports_awards': [],
            'general': []
        }
        
        for article in articles:
            content = (article['title'] + ' ' + article['description']).lower()
            
            if any(kw in content for kw in ['rbi', 'sebi', 'bank', 'finance', 'loan', 'credit']):
                categories['banking_finance'].append(article)
            elif any(kw in content for kw in ['gdp', 'economic', 'inflation', 'growth', 'trade']):
                categories['economic'].append(article)
            elif any(kw in content for kw in ['scheme', 'yojana', 'government', 'welfare', 'policy']):
                categories['government_schemes'].append(article)
            elif any(kw in content for kw in ['international', 'foreign', 'trade', 'agreement', 'diplomatic']):
                categories['international'].append(article)
            elif any(kw in content for kw in ['sport', 'award', 'achievement', 'honor', 'recognition']):
                categories['sports_awards'].append(article)
            else:
                categories['general'].append(article)
        
        # Process each category with Gemini AI
        processed_content = []
        current_date = datetime.now().strftime('%d %B %Y')
        
        for category_name, category_articles in categories.items():
            if not category_articles:
                continue
                
            # Prepare articles for AI processing
            articles_text = "\n\n".join([
                f"TITLE: {article['title']}\nDESCRIPTION: {article['description']}\nSOURCE: {article['source']}"
                for article in category_articles[:10]  # Process up to 10 articles per category
            ])
            
            prompt = f"""Process these real news articles for IBPS RRB banking exam preparation on {current_date}.

Create detailed summaries for each news item in this format:

**HEADLINE:** [Clear, concise headline]
**SUMMARY:** [3-4 sentences explaining the news and its significance]
**KEY POINTS:**
• [Important detail 1]
• [Important detail 2] 
• [Important detail 3]
**EXAM RELEVANCE:** [How this relates to IBPS RRB syllabus]

News Articles:
{articles_text}

Make it comprehensive and exam-focused. Include exact figures, names, and dates mentioned in the news."""

            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=3000
                    )
                )
                
                if response and response.text:
                    category_title = category_name.replace('_', ' ').title()
                    processed_content.append(f"\n## {category_title}\n\n{response.text.strip()}")
                    
            except Exception as e:
                print(f"Gemini processing error for {category_name}: {e}")
        
        if processed_content:
            final_content = f"# IBPS RRB Daily News Summary - {current_date}\n"
            final_content += f"**Total Articles Processed:** {len(articles)}\n\n"
            final_content += "\n".join(processed_content)
            
            # Add MCQs based on the news
            mcq_prompt = f"""Based on the above news summary, create 5 multiple choice questions for IBPS RRB exam:

Create questions in this format:
Q1. [Question based on the news]
A) Option 1  B) Option 2  C) Option 3  D) Option 4
Answer: [Correct option] - [Brief explanation]

Focus on facts, figures, and important details from today's news."""

            try:
                mcq_response = self.model.generate_content(mcq_prompt)
                if mcq_response and mcq_response.text:
                    final_content += f"\n\n## Practice MCQs\n\n{mcq_response.text.strip()}"
            except Exception as e:
                print(f"MCQ generation error: {e}")
            
            return final_content
        else:
            return "Unable to process news articles with AI."
    
    def create_pdf(self, content, date_str):
        """Create formatted PDF"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'Title', parent=styles['Title'], fontSize=16,
                textColor=HexColor('#2d3748'), spaceAfter=20, alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'Heading', parent=styles['Heading2'], fontSize=12,
                textColor=HexColor('#4a5568'), spaceBefore=10, spaceAfter=8
            )
            
            content_style = ParagraphStyle(
                'Content', parent=styles['Normal'], fontSize=10,
                spaceBefore=3, spaceAfter=3, leading=12
            )
            
            story = []
            story.append(Paragraph(f"IBPS RRB Daily News Summary - {date_str}", title_style))
            story.append(Spacer(1, 20))
            
            # Process content line by line
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 4))
                elif line.startswith('#'):
                    story.append(Paragraph(line.replace('#', '').strip(), heading_style))
                elif line.startswith('**') and line.endswith('**'):
                    story.append(Paragraph(f"<b>{line[2:-2]}</b>", content_style))
                else:
                    story.append(Paragraph(line, content_style))
                story.append(Spacer(1, 2))
            
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
            
            email_body = f"""Dear IBPS RRB Aspirant,

Your comprehensive daily news summary for {date_str} is ready.

This report includes real-time news analysis covering:
• Banking and Financial sector developments
• Economic indicators and policy changes  
• Government schemes and initiatives
• International affairs and trade news
• Sports achievements and awards
• Important current affairs for your exam

All content is processed from live news sources and analyzed specifically for IBPS RRB exam relevance.

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
                    f'attachment; filename=IBPS_RRB_News_{date_str.replace(" ", "_")}.pdf'
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
    
    def generate_daily_report(self):
        """Main function to generate daily report"""
        ist_tz = pytz.timezone('Asia/Kolkata')
        date_str = datetime.now(ist_tz).strftime('%d %B %Y')
        
        try:
            print(f"Starting news processing for {date_str}")
            
            # Check if already generated today
            conn = sqlite3.connect('news_reports.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM daily_reports WHERE date = ?', (date_str,))
            if cursor.fetchone():
                print(f"Report already generated for {date_str}")
                conn.close()
                return {"status": "already_exists", "date": date_str}
            conn.close()
            
            # Fetch real news
            articles = self.fetch_real_news()
            if not articles:
                print("No articles found")
                return {"status": "error", "message": "No news articles found"}
            
            # Process with AI
            processed_content = self.categorize_and_process_news(articles)
            
            # Create PDF
            pdf_data = self.create_pdf(processed_content, date_str)
            
            # Send email
            email_sent = self.send_email(processed_content, pdf_data, date_str)
            
            # Save to database
            conn = sqlite3.connect('news_reports.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO daily_reports (date, content, articles_count)
                VALUES (?, ?, ?)
            ''', (date_str, processed_content, len(articles)))
            conn.commit()
            conn.close()
            
            print(f"Report generated successfully - Articles: {len(articles)}, Email: {'✓' if email_sent else '✗'}")
            
            return {
                "status": "success",
                "date": date_str,
                "articles_processed": len(articles),
                "email_sent": email_sent
            }
            
        except Exception as e:
            print(f"Report generation error: {e}")
            return {"status": "error", "message": str(e)}

# Initialize processor
try:
    processor = NewsProcessor()
    print("News processor initialized successfully")
except Exception as e:
    print(f"Initialization error: {e}")
    processor = None

@app.route('/')
def dashboard():
    if not processor:
        return "System not configured properly. Check environment variables."
    
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<title>IBPS RRB News Processor</title>
<style>
body{{font-family:Arial,sans-serif;margin:40px;background:#f8f9fa}}
.container{{max-width:800px;margin:0 auto}}
.header{{background:#2d3748;color:white;padding:30px;border-radius:8px;text-align:center}}
.card{{background:white;margin:20px 0;padding:25px;border-radius:8px;border:1px solid #e2e8f0}}
.btn{{background:#3182ce;color:white;padding:12px 24px;border:none;border-radius:5px;text-decoration:none;display:inline-block;margin:8px}}
.status{{background:#e6fffa;padding:15px;border-radius:5px;border-left:4px solid #38b2ac}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>IBPS RRB Real News Processor</h1>
<p>Live News Fetching & AI Processing System</p>
</div>

<div class="card">
<h2>System Status</h2>
<div class="status">
<strong>Status: Active</strong><br>
Real-time news fetching from multiple sources<br>
AI processing with Gemini<br>
Daily reports at 7:30 AM IST
</div>
<p><strong>Current Time:</strong> {ist_time.strftime('%d %B %Y, %I:%M %p IST')}</p>
</div>

<div class="card">
<h2>Actions</h2>
<a href="/generate" class="btn">Generate Today's Report</a>
<a href="/test" class="btn">Test System</a>
</div>

<div class="card">
<h2>Data Sources</h2>
<ul>
<li>News API - Real-time banking and economic news</li>
<li>RSS Feeds - Economic Times, Business Standard, Hindu</li>
<li>Web Scraping - Live news from major sites</li>
<li>AI Processing - Gemini 1.5 Flash for analysis</li>
<li>Email Delivery - Automated daily summaries</li>
</ul>
</div>
</div>
</body>
</html>"""
    
    return html

@app.route('/generate')
def generate_report():
    if not processor:
        return jsonify({"status": "error", "message": "System not initialized"})
    
    result = processor.generate_daily_report()
    return jsonify(result)

@app.route('/test')
def test_system():
    if not processor:
        return jsonify({"status": "error", "message": "System not initialized"})
    
    # Quick test with few articles
    try:
        articles = processor.fetch_real_news()[:5]
        if articles:
            return jsonify({
                "status": "success", 
                "message": f"Test successful - Found {len(articles)} articles",
                "sample_titles": [art['title'][:50] + "..." for art in articles[:3]]
            })
        else:
            return jsonify({"status": "error", "message": "No articles found in test"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Scheduler
scheduler = BackgroundScheduler()

if processor:
    ist_tz = pytz.timezone('Asia/Kolkata')
    scheduler.add_job(
        func=processor.generate_daily_report,
        trigger=CronTrigger(hour=7, minute=30, timezone=ist_tz),
        id='daily_news_job'
    )
    scheduler.start()
    print("Scheduler started - Daily reports at 7:30 AM IST")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
