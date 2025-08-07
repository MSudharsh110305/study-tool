import os
import logging
from datetime import datetime, timedelta
import requests
import google.generativeai as genai
from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
import io
from bs4 import BeautifulSoup
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class ibpsGen:
    def __init__(self):
        self.gApi = os.getenv('GEMINI_API_KEY')
        self.nApi = os.getenv('NEWS_API_KEY')
        self.eUser = os.getenv('EMAIL_USER')
        self.ePass = os.getenv('EMAIL_PASSWORD')
        self.recpEmail = os.getenv('RECIPIENT_EMAIL')
        
        reqVars = {
            'GEMINI_API_KEY': self.gApi,
            'EMAIL_USER': self.eUser,
            'EMAIL_PASSWORD': self.ePass,
            'RECIPIENT_EMAIL': self.recpEmail
        }
        
        missing = [v for v, val in reqVars.items() if not val]
        if missing:
            raise ValueError(f"Missing vars: {', '.join(missing)}")
        
        genai.configure(api_key=self.gApi)
        self.mdl = genai.GenerativeModel('gemini-1.5-flash')
        
        self.initDb()
    
    def initDb(self):
        conn = sqlite3.connect('reports.db', check_same_thread=False)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS daily_rpts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dt TEXT UNIQUE,
                cont TEXT,
                mcqs TEXT,
                pdf_gen BOOLEAN,
                email_sent BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS app_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lvl TEXT,
                msg TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def logDb(self, lvl, msg):
        try:
            conn = sqlite3.connect('reports.db', check_same_thread=False)
            cur = conn.cursor()
            cur.execute('INSERT INTO app_logs (lvl, msg) VALUES (?, ?)', (lvl, msg))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"log err: {str(e)}")
    
    def getNews(self):
        newsArts = []
        
        try:
            if self.nApi:
                url = "https://newsapi.org/v2/everything"
                params = {
                    'q': 'India AND (RBI OR SEBI OR banking OR economic)',
                    'language': 'en',
                    'sortBy': 'publishedAt',
                    'from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                    'apiKey': self.nApi
                }
                
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    arts = data.get('articles', [])
                    bankArts = [
                        art for art in arts 
                        if any(kw.lower() in (art.get('title', '') + art.get('description', '')).lower() 
                              for kw in ['RBI', 'SEBI', 'bank', 'financial', 'UPI'])
                    ]
                    newsArts.extend(bankArts[:4])
            
            rssNews = self.getRss()
            newsArts.extend(rssNews)
            
        except Exception as e:
            self.logDb('ERROR', f"news err: {str(e)}")
            logger.error(f"news err: {str(e)}")
        
        return newsArts[:8]
    
    def getRss(self):
        rssArts = []
        feeds = [
            'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
            'https://www.business-standard.com/rss/finance-103.rss'
        ]
        
        for feedUrl in feeds:
            try:
                hdr = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(feedUrl, headers=hdr, timeout=10)
                soup = BeautifulSoup(resp.content, 'xml')
                items = soup.find_all('item')[:3]
                
                for itm in items:
                    ttl = itm.find('title')
                    desc = itm.find('description')
                    
                    if ttl and desc:
                        ttlTxt = ttl.text.strip()
                        descTxt = BeautifulSoup(desc.text, 'html.parser').get_text().strip()[:200]
                        
                        if any(kw.lower() in (ttlTxt + descTxt).lower() 
                              for kw in ['RBI', 'bank', 'financial']):
                            rssArts.append({
                                'title': ttlTxt,
                                'description': descTxt,
                                'source': {'name': 'RSS'},
                                'publishedAt': datetime.now().isoformat()
                            })
            except Exception as e:
                logger.error(f"rss err {feedUrl}: {str(e)}")
        
        return rssArts
    
    def genContent(self, newsArts):
        if not newsArts:
            return self.getFallback()
        
        try:
            newsTxt = "\n\n".join([
                f"TITLE: {art.get('title', 'N/A')}\nDESC: {art.get('description', 'N/A')[:200]}"
                for art in newsArts if art.get('title') and art.get('description')
            ])
            
            if not newsTxt.strip():
                return self.getFallback()
            
            currDt = datetime.now().strftime('%d %B %Y')
            
            prompt = f"""convert banking news to ibps rrb exam format for {currDt}

for each news make:

🔷 HEADLINE: [clear title]
🔹 SUMMARY: [30-50 words only]
🔹 KEY TERMS: [abbreviations with full forms]
🔹 DEFINITIONS: [important concepts]
🔹 CAUSE/REASON: [why happened]
🔹 IMPACT/EFFECT: [effect on banking economy]
🔹 FUTURE OUTLOOK: [what next]
🔹 IBPS RRB RELEVANCE: [exam angle mcq topics]

then add:

✅ QUICK REVISION CAPSULES (10 points):
[bullet points]

✅ STATIC GK ANCHORS:
[link to syllabus]

✅ EXPECTED MCQs (5 questions):
Q1. question?
A) opt B) opt C) opt D) opt
Answer: X

news: {newsTxt[:3000]}

focus on rbi sebi banking only exam style simple language"""
            
            resp = self.mdl.generate_content(prompt)
            
            if resp and resp.text:
                return resp.text
            else:
                self.logDb('ERROR', "empty gemini resp")
                return self.getFallback()
            
        except Exception as e:
            self.logDb('ERROR', f"gemini err: {str(e)}")
            logger.error(f"gemini err: {str(e)}")
            return self.getFallback()
    
    def getFallback(self):
        today = datetime.now().strftime('%d %B %Y')
        
        return f"""🔷 HEADLINE: IBPS RRB Update - {today}

🔹 SUMMARY: banking economic updates for ibps rrb exam prep with regulatory changes market news

🔹 KEY TERMS:
• RBI - Reserve Bank of India
• SEBI - Securities Exchange Board of India
• NPCI - National Payments Corporation of India
• UPI - Unified Payments Interface

🔹 DEFINITIONS:
• Repo Rate: rate at which rbi lends to banks
• Bank Rate: lending rate without collateral

✅ QUICK REVISION CAPSULES:
1. rbi is central bank of india est 1935
2. current rbi governor shaktikanta das
3. sebi regulates capital markets
4. upi enables instant payments
5. npci manages retail payments
6. banking sector key for economy
7. financial inclusion govt priority
8. digital banking expanding fast
9. regulatory compliance mandatory
10. current affairs crucial for exams

✅ EXPECTED MCQs:
Q1. current rbi governor?
A) urjit patel B) shaktikanta das C) raghuram rajan D) subbarao
Answer: B

Q2. sebi regulates?
A) banking B) securities market C) insurance D) all
Answer: B

Q3. upi full form?
A) united payments B) unified payments interface C) universal payments D) unique payments
Answer: B

Q4. npci headquarter?
A) delhi B) mumbai C) bangalore D) chennai
Answer: B

Q5. rbi established year?
A) 1934 B) 1935 C) 1947 D) 1950
Answer: B"""
    
    def makePdf(self, cont, dtStr):
        try:
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch)
            
            styles = getSampleStyleSheet()
            
            ttlStyle = ParagraphStyle(
                'ttl',
                parent=styles['Title'],
                fontSize=16,
                textColor=HexColor('#1f4e79'),
                spaceAfter=25,
                alignment=1
            )
            
            hdStyle = ParagraphStyle(
                'hd',
                parent=styles['Heading2'],
                fontSize=11,
                textColor=HexColor('#2e5984'),
                spaceBefore=8,
                spaceAfter=6
            )
            
            story = []
            story.append(Paragraph(f"IBPS RRB Report - {dtStr}", ttlStyle))
            story.append(Spacer(1, 15))
            
            lines = cont.split('\n')
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                    
                if ln.startswith('🔷') or ln.startswith('🔹') or ln.startswith('✅'):
                    story.append(Paragraph(ln, hdStyle))
                else:
                    story.append(Paragraph(ln, styles['Normal']))
                story.append(Spacer(1, 3))
            
            doc.build(story)
            pdfData = buf.getvalue()
            buf.close()
            return pdfData
            
        except Exception as e:
            self.logDb('ERROR', f"pdf err: {str(e)}")
            return None
    
    def sendMail(self, pdfData, dtStr):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.eUser
            msg['To'] = self.recpEmail
            msg['Subject'] = f"IBPS RRB Report - {dtStr}"
            
            body = f"""your daily ibps rrb study material for {dtStr}

includes:
- banking economic news
- structured exam content
- revision capsules
- practice mcqs
- static gk links

good luck!"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            if pdfData:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pdfData)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename=report_{dtStr.replace(" ", "_")}.pdf'
                )
                msg.attach(part)
            
            srv = smtplib.SMTP('smtp.gmail.com', 587)
            srv.starttls()
            srv.login(self.eUser, self.ePass)
            srv.sendmail(self.eUser, self.recpEmail, msg.as_string())
            srv.quit()
            return True
            
        except Exception as e:
            self.logDb('ERROR', f"email err: {str(e)}")
            return False
    
    def genRpt(self):
        istTz = pytz.timezone('Asia/Kolkata')
        dtStr = datetime.now(istTz).strftime('%d %B %Y')
        
        try:
            self.logDb('INFO', f"start gen {dtStr}")
            
            conn = sqlite3.connect('reports.db', check_same_thread=False)
            cur = conn.cursor()
            cur.execute('SELECT id FROM daily_rpts WHERE dt = ?', (dtStr,))
            existing = cur.fetchone()
            
            if existing:
                self.logDb('INFO', f"already gen {dtStr}")
                conn.close()
                return {"status": "exists", "date": dtStr}
            
            newsArts = self.getNews()
            logger.info(f"got {len(newsArts)} articles")
            
            structCont = self.genContent(newsArts)
            
            pdfData = self.makePdf(structCont, dtStr)
            pdfGen = pdfData is not None
            
            emailSent = False
            if pdfData:
                emailSent = self.sendMail(pdfData, dtStr)
            
            cur.execute('''
                INSERT INTO daily_rpts (dt, cont, pdf_gen, email_sent)
                VALUES (?, ?, ?, ?)
            ''', (dtStr, structCont, pdfGen, emailSent))
            
            conn.commit()
            conn.close()
            
            statusMsg = f"gen {dtStr} pdf:{'y' if pdfGen else 'n'} email:{'y' if emailSent else 'n'}"
            self.logDb('INFO', statusMsg)
            
            return {
                "status": "success",
                "date": dtStr,
                "pdf_generated": pdfGen,
                "email_sent": emailSent
            }
            
        except Exception as e:
            errMsg = f"gen err: {str(e)}"
            self.logDb('ERROR', errMsg)
            return {"status": "error", "message": str(e)}

try:
    rptGen = ibpsGen()
    logger.info("gen init success")
except Exception as e:
    logger.error(f"init fail: {str(e)}")
    rptGen = None

@app.route('/')
def dash():
    if not rptGen:
        return "app not configured check env vars"
    
    try:
        conn = sqlite3.connect('reports.db', check_same_thread=False)
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM daily_rpts ORDER BY created_at DESC LIMIT 7')
        recentRpts = cur.fetchall()
        
        cur.execute('SELECT * FROM app_logs ORDER BY ts DESC LIMIT 10')
        recentLogs = cur.fetchall()
        
        conn.close()
        
        istTime = datetime.now(pytz.timezone('Asia/Kolkata'))
        
        html = f"""<!DOCTYPE html>
<html>
<head>
<title>IBPS RRB Generator</title>
<style>
body{{font-family:Arial;margin:20px;background:#f5f5f5}}
.container{{max-width:1200px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1f4e79,#2e5984);color:white;padding:20px;border-radius:10px;text-align:center}}
.card{{background:white;margin:20px 0;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}}
.btn{{background:#007bff;color:white;padding:10px 20px;border:none;border-radius:5px;text-decoration:none;display:inline-block;margin:5px}}
.btn:hover{{background:#0056b3}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}
th{{background:#f8f9fa}}
.status-good{{color:#28a745}}
.status-bad{{color:#dc3545}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>IBPS RRB Generator</h1>
<p>gemini powered daily reports</p>
<p>status: running</p>
</div>

<div class="card">
<h2>system status</h2>
<p>gemini api: {'ok' if os.getenv('GEMINI_API_KEY') else 'missing'}</p>
<p>email: {'ok' if os.getenv('EMAIL_USER') else 'missing'}</p>
<p>next report: tomorrow 7:30 am ist</p>
<p>current: {istTime.strftime('%d %B %Y %I:%M %p')}</p>
<a href="/gen-now" class="btn">generate now</a>
<a href="/test-email" class="btn">test email</a>
</div>

<div class="card">
<h2>recent reports</h2>
<table>
<tr><th>date</th><th>pdf</th><th>email</th><th>created</th></tr>"""
        
        if recentRpts:
            for rpt in recentRpts:
                html += f"""<tr>
<td>{rpt[1]}</td>
<td class="{'status-good' if rpt[3] else 'status-bad'}">{'✓' if rpt[3] else '✗'}</td>
<td class="{'status-good' if rpt[4] else 'status-bad'}">{'✓' if rpt[4] else '✗'}</td>
<td>{rpt[5]}</td>
</tr>"""
        else:
            html += "<tr><td colspan='4'>no reports yet</td></tr>"
        
        html += """</table>
</div>

<div class="card">
<h2>logs</h2>
<table>
<tr><th>time</th><th>level</th><th>message</th></tr>"""
        
        if recentLogs:
            for log in recentLogs:
                html += f"<tr><td>{log[1]}</td><td>{log[2]}</td><td>{log[3]}</td></tr>"
        
        html += """</table>
</div>
</div>
</body>
</html>"""
        
        return html
        
    except Exception as e:
        return f"dash err: {str(e)}"

@app.route('/gen-now')
def genNow():
    if not rptGen:
        return jsonify({"status": "error", "msg": "not init"})
    
    try:
        result = rptGen.genRpt()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/test-email')
def testEmail():
    if not rptGen:
        return jsonify({"status": "error", "msg": "not init"})
    
    try:
        testCont = "test email ibps rrb gen working"
        pdfData = rptGen.makePdf(testCont, "TEST")
        success = rptGen.sendMail(pdfData, "TEST")
        
        if success:
            return jsonify({"status": "success", "msg": "test email sent"})
        else:
            return jsonify({"status": "error", "msg": "email failed"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/health')
def health():
    istTime = datetime.now(pytz.timezone('Asia/Kolkata'))
    return jsonify({
        "status": "ok",
        "time": istTime.isoformat(),
        "gen_ready": rptGen is not None
    })

sched = BackgroundScheduler()

if rptGen:
    istTz = pytz.timezone('Asia/Kolkata')
    sched.add_job(
        func=rptGen.genRpt,
        trigger=CronTrigger(hour=7, minute=30, timezone=istTz),
        id='daily_job',
        name='daily ibps report',
        replace_existing=True
    )
    sched.start()
    logger.info("sched started")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
