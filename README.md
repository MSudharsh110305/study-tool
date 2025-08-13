<div align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=32&duration=3000&pause=1000&color=2E9EF7&center=true&vCenter=true&width=600&lines=IBPS+RRB+Study+Tool;AI+News+Generator;Banking+Exam+Preparation" alt="Typing SVG" />
</div>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white" alt="Railway" />
</div>

<br />

<div align="center">
  <h3>Banking News Aggregator for Exam Preparation</h3>
  <p><em>Automated news processing with AI-generated glossaries and practice questions</em></p>
</div>

<hr />

<h2>🌟 <strong>Project Overview</strong></h2>

<p>This application automatically aggregates banking and financial news from multiple sources, processes them using Google Gemini AI, and generates comprehensive study materials for exam preparation. The system delivers daily reports with simplified explanations and practice questions directly to users' email.</p>

<table>
<tr>
<td width="50%" valign="top">

<h3>🤖 <strong>AI Features</strong></h3>
<ul>
<li>Intelligent Content Processing using Google Gemini</li>
<li>Auto-Generated Glossaries for banking terminology</li>
<li>Practice MCQ Generation from current events</li>
<li>Smart News Categorization by relevance</li>
</ul>

</td>
<td width="50%" valign="top">

<h3>⚡ <strong>Automation</strong></h3>
<ul>
<li>Daily Scheduled Reports at 8:00 PM IST</li>
<li>Multi-Source News Aggregation from RSS and APIs</li>
<li>Professional PDF Generation with proper formatting</li>
<li>Automated Email Delivery with attachments</li>
</ul>

</td>
</tr>
</table>

<hr />

<h2>🚀 <strong>Key Features</strong></h2>

<ul>
<li><strong>📰 News Aggregation</strong> - Fetches content from financial news sources using targeted keywords</li>
<li><strong>🧠 AI Processing</strong> - Generates beginner-friendly explanations for complex banking terms</li>
<li><strong>❓ MCQ Generation</strong> - Creates practice questions based on current banking developments</li>
<li><strong>⏰ Automated Scheduling</strong> - Daily report generation and email delivery</li>
<li><strong>💻 Web Dashboard</strong> - Manual control and status monitoring interface</li>
</ul>

<hr />

<h2>🛠️ <strong>Setup Instructions</strong></h2>

<h3><strong>Requirements</strong></h3>
<p>Python 3.9+, Google Gemini API Key, Gmail Account with App Password</p>

<h3><strong>Installation</strong></h3>
<pre>
git clone https://github.com/MSudharsh110305/study-tool.git
cd study-tool
pip install -r requirements.txt
</pre>

<h3><strong>Configuration</strong></h3>
<p>Create <code>.env</code> file:</p>
<pre>
GEMINI_API_KEY=your_gemini_api_key
EMAIL_USER=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
RECIPIENT_EMAIL=recipient@gmail.com
NEWS_API_KEY=your_newsapi_key
</pre>

<h3><strong>Run Application</strong></h3>
<pre>
python app.py
</pre>
<p>Access at <code>http://localhost:5000</code></p>

<hr />

<h2>🌐 <strong>Deployment</strong></h2>

<h3><strong>Railway Platform</strong></h3>
<ol>
<li><strong>Push to GitHub:</strong> <code>git add . && git commit -m "Deploy" && git push origin main</code></li>
<li><strong>Deploy on Railway:</strong> Visit railway.app → Deploy from GitHub → Select your repository</li>
<li><strong>Add Environment Variables:</strong> Go to Variables tab and add all variables from your .env file</li>
<li><strong>Done!</strong> Application auto-deploys and starts sending daily reports</li>
</ol>

<hr />

<h2>🔑 <strong>API Configuration</strong></h2>

<details>
<summary><strong>API Key Setup</strong></summary>

<p><strong>Google Gemini API:</strong></p>
<ul>
<li>Visit <a href="https://makersuite.google.com/app/apikey" target="_blank">Google AI Studio</a></li>
<li>Generate API key for project</li>
</ul>

<p><strong>Gmail App Password:</strong></p>
<ul>
<li>Enable 2-Factor Authentication</li>
<li>Generate app-specific password in account security settings</li>
</ul>

<p><strong>News API (Optional):</strong></p>
<ul>
<li>Register at <a href="https://newsapi.org/" target="_blank">NewsAPI.org</a> for additional news sources</li>
</ul>

</details>

<hr />

<h2>📁 <strong>Project Structure</strong></h2>

<pre>
📦 study-tool/
├── 📁 config/
│   ├── main_prompt.txt
│   ├── mcq_prompt.txt
│   ├── email_template.txt
│   ├── news_queries.txt
│   ├── rss_feeds.txt
│   ├── news_sites.txt
│   └── relevant_keywords.txt
├── 🐍 app.py
├── 📋 requirements.txt
└── 🌐 .env
</pre>

<p><strong>Configuration Files:</strong></p>
<ul>
<li><code>config/main_prompt.txt</code> - AI processing instructions</li>
<li><code>config/mcq_prompt.txt</code> - MCQ generation prompt</li>
<li><code>config/email_template.txt</code> - Email body template</li>
<li><code>config/news_queries.txt</code> - Search terms for news</li>
<li><code>config/rss_feeds.txt</code> - RSS feed URLs</li>
<li><code>config/news_sites.txt</code> - News websites to scrape</li>
<li><code>config/relevant_keywords.txt</code> - Keywords for filtering</li>
</ul>

<hr />

<h2>💻 <strong>Usage</strong></h2>

<ul>
<li><strong>🟢 Generate Report</strong> - Create today's news summary with fresh content</li>
<li><strong>🔴 Force Generate</strong> - Override existing daily report</li>
<li><strong>📊 View Status</strong> - Monitor recent report generation history</li>
</ul>

<hr />

<h2>🎯 <strong>Project Objectives</strong></h2>

<ul>
<li><strong>Educational Support:</strong> Assist IBPS RRB exam candidates with current affairs</li>
<li><strong>Automation:</strong> Reduce manual effort in news compilation and processing</li>
<li><strong>AI Integration:</strong> Demonstrate practical application of language models</li>
<li><strong>User Experience:</strong> Provide accessible explanations for complex financial concepts</li>
</ul>

<hr />

<div align="center">
  <h3>🌟Hope you find this stuff useful!!</h3>
</div>
