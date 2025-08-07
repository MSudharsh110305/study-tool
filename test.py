import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

response = model.generate_content("Write a short banking news summary for IBPS RRB exam")
print(response.text if response and response.text else "API failed")
