from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os, re, json, time, uuid, random, base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Must be before pyplot import
import matplotlib.pyplot as plt
from urllib.parse import urlparse
from datetime import datetime
import requests, nltk, networkx as nx, matplotlib.pyplot as plt
from collections import Counter
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from newspaper import Article, Config
from googlesearch import search
from bs4 import BeautifulSoup
from markupsafe import escape  # Added for security
from wikipediaapi import Wikipedia, ExtractFormat

# Setup
app = Flask(__name__)
matplotlib.use('Agg')
import nltk
nltk.download('punkt', download_dir='nltk_data')
nltk.download('stopwords', download_dir='nltk_data')
nltk.download('averaged_perceptron_tagger', download_dir='nltk_data')



# Directories
for d in ['user_engagement', 'feedback_data', 'knowledge_base', 'nltk_data']:
    os.makedirs(d, exist_ok=True)
nltk.data.path.append('./nltk_data')

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
]

# Sites that block scraping - skip these
BLOCKED_DOMAINS = {
    'pexels.com', 'adobe.com', 'shutterstock.com', 'istockphoto.com',
    'gettyimages.com', 'depositphotos.com', 'alamy.com', 'dreamstime.com'
}

# Common sense responses
COMMON_PHRASES = {
    r"\b(hi|hello|hey|greetings|good morning|good afternoon)\b": 
        "Hello! How can I assist you today?",
    r"\b(bye|goodbye|see you|farewell)\b": 
        "Goodbye! Feel free to return if you have more questions.",
    r"\b(thank you|thanks|appreciate)\b": 
        "You're welcome! Is there anything else I can help with?",
    r"\b(how are you|how's it going)\b": 
        "I'm a digital assistant, but I'm functioning well! How can I help you?",
    r"\b(who are you|what are you)\b": 
        "I'm INFOSYNTH, your web-search assistant. I can find information and summarize web content for you!",
    r"\b(help|support|instructions)\b":
        "I can help you with: \n- Factual questions \n- Educational topics \n- Research summaries \nJust ask me anything!"
}

# Educational focus patterns
EDUCATIONAL_PATTERNS = [
    r"explain\s+(.*)",
    r"what\s+is\s+(.*)",
    r"define\s+(.*)",
    r"how\s+does\s+(.*)\s+work",
    r"who\s+was\s+(.*)",
    r"describe\s+(.*)"
]

@app.route('/')
def index():
    return render_template_string(open('index.html').read())

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/messages/initial', methods=['GET'])
def initial_message():
    return jsonify({"messages":[{"sender":"bot","content":"Hello! I'm INFOSYNTH, your web-search assistant. Ask me anything!"}]})

def track_engagement(session_id, question, response_time, feedback=None):
    data = {"timestamp": datetime.now().isoformat(), "question": question, "response_time": response_time, "feedback": feedback}
    path = f"user_engagement/{session_id}.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            sessions = json.load(f)
    else:
        sessions = {"sessions": []}
    sessions["sessions"].append(data)
    with open(path, 'w') as f:
        json.dump(sessions, f, indent=2)
    if feedback:
        with open(f"feedback_data/{session_id}_{int(time.time())}.json", 'w') as f:
            json.dump(data, f)

def fetch_entity_images(query, max_images=5):
    """
    Fetch educational images using a multi-source approach with advanced bypass techniques.
    Prioritizes free, public domain sources with educational relevance.
    """
    # Attempt 1: Enhanced DuckDuckGo with anti-blocking techniques
    try:
        with requests.Session() as s:
            # Rotate between different browser profiles
            browser_profiles = [
                # Chrome profile
                {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://duckduckgo.com/',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                },
                # Firefox profile
                {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://duckduckgo.com/',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            ]
            
            for profile in browser_profiles:
                try:
                    s.headers.update(profile)
                    
                    # Initial request with randomized parameters
                    res = s.get(
                        "https://duckduckgo.com/",
                        params={
                            'q': query,
                            't': 'h_',  # Time-based parameter
                            'ia': 'web',
                            'kl': random.choice(['wt-wt', 'us-en', 'uk-en'])
                        },
                        timeout=8
                    )
                    res.raise_for_status()
                    
                    # Dynamic VQD extraction with multiple patterns
                    vqd = None
                    vqd_patterns = [
                        r'vqd=([\d-]+)',
                        r'vqd["\']?\s*[:=]\s*["\']?([\d-]+)',
                        r'vqd_4\s*=\s*["\']([\d-]+)["\']'
                    ]
                    
                    for pattern in vqd_patterns:
                        if match := re.search(pattern, res.text):
                            vqd = match.group(1)
                            break
                    
                    if not vqd:
                        continue  # Try next profile
                    
                    # Image API parameters with randomization
                    params = {
                        'l': 'us-en',
                        'o': 'json',
                        'q': query,
                        'vqd': vqd,
                        'f': ',,,',
                        'p': random.randint(1, 3),  # Random page
                        'v7exp': 'a',
                        'spell': '1',
                        'ct': random.choice(['US', 'UK', 'CA']),  # Random country
                        'df': datetime.now().strftime("%Y-%m-%d"),  # Current date
                        's': random.randint(0, 50),  # Random offset
                        'ex': '-1'  # Safe search
                    }
                    
                    # Retry with header rotation
                    for attempt in range(3):
                        try:
                            # Rotate User-Agent for each attempt
                            s.headers['User-Agent'] = random.choice(USER_AGENTS)
                            
                            img_res = s.get(
                                "https://duckduckgo.com/i.js",
                                params=params,
                                timeout=12
                            )
                            img_res.raise_for_status()
                            
                            # Parse response
                            data = img_res.json()
                            images = data.get('results', [])
                            valid_urls = []
                            
                            for img in images:
                                if img_url := img.get('image'):
                                    valid_urls.append(img_url)
                                    if len(valid_urls) >= max_images:
                                        return valid_urls
                            
                            if valid_urls:
                                return valid_urls
                                
                        except requests.HTTPError as e:
                            if e.response.status_code in [403, 429]:
                                # Simulate human-like browsing patterns
                                time.sleep(2 + random.random() * 3)  # Random delay 2-5s
                                # Randomly change some headers
                                s.headers['Accept-Language'] = random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.8'])
                            else:
                                break
                except Exception:
                    continue
    except Exception as e:
        print(f"DuckDuckGo method failed: {str(e)}")

    # Attempt 2: Wikimedia Commons (high-quality educational images)
    try:
        params = {
            "action": "query",
            "generator": "images",
            "titles": query,
            "gimlimit": max_images,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
            "formatversion": 2
        }
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=params,
            headers={'User-Agent': random.choice(USER_AGENTS)},
            timeout=10
        )
        data = response.json()
        urls = []
        for page in data.get("query", {}).get("pages", []):
            if image_info := page.get("imageinfo"):
                if image_url := image_info[0].get("url"):
                    urls.append(image_url)
        if urls:
            return urls[:max_images]
    except Exception as e:
        print(f"Wikimedia method failed: {str(e)}")

    # Attempt 3: Openverse (Creative Commons search)
    try:
        response = requests.get(
            "https://api.openverse.engineering/v1/images/",
            params={
                "q": query,
                "license_type": "commercial,modification",
                "page_size": max_images
            },
            headers={'User-Agent': random.choice(USER_AGENTS)},
            timeout=10
        )
        data = response.json()
        return [result["url"] for result in data.get("results", [])[:max_images]]
    except Exception as e:
        print(f"Openverse method failed: {str(e)}")

    # Attempt 4: Wikipedia page images
    try:
        wiki_wiki = Wikipedia(
            user_agent=f'INFOSYNTH/1.0 ({random.choice(USER_AGENTS)})',
            language='en'
        )
        page = wiki_wiki.page(query)
        if page.exists():
            images = []
            for img in page.images.values():
                if img.url.lower().endswith(('.jpg', '.jpeg', '.png', '.svg')):
                    images.append(img.url)
                    if len(images) >= max_images:
                        break
            return images
    except Exception as e:
        print(f"Wikipedia images method failed: {str(e)}")

    # Attempt 5: Public domain fallback (Pixabay API - requires key)
    try:
        api_key = os.getenv("PIXABAY_API_KEY")
        if api_key:
            response = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": api_key,
                    "q": query,
                    "image_type": "photo",
                    "safesearch": "true",
                    "per_page": max_images
                },
                timeout=10
            )
            data = response.json()
            return [hit["webformatURL"] for hit in data.get("hits", [])]
    except Exception as e:
        print(f"Pixabay method failed: {str(e)}")

    # Attempt 6: Simple Google search fallback (last resort)
    try:
        search_results = search(
            f"{query} site:commons.wikimedia.org OR site:flickr.com filetype:jpg",
            num_results=max_images * 2,
            advanced=True
        )
        urls = []
        for result in search_results:
            url = result.url
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                urls.append(url)
            if len(urls) >= max_images:
                break
        return urls
    except Exception as e:
        print(f"Google search fallback failed: {str(e)}")

    return []  # Return empty list if all methods fail
def extract_main_content(html):
    """Extract main content using readability algorithm"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove non-content elements
    for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        element.decompose()
    
    # Score paragraphs by text density
    paragraphs = soup.find_all(['p', 'div'])
    best_paragraph = None
    highest_score = 0
    
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) < 100: 
            continue
            
        # Calculate text density
        words = text.split()
        links = p.find_all('a')
        score = len(words) / (1 + len(links))
        
        if score > highest_score:
            highest_score = score
            best_paragraph = p
    
    return best_paragraph.get_text() if best_paragraph else ""

def fetch_article(url):
    try:
        # Skip blocked image/video domains
        domain = urlparse(url).netloc.lower()
        if any(blocked in domain for blocked in BLOCKED_DOMAINS):
            print(f"Skipping blocked domain: {domain}")
            return None
            
        config = Config()
        config.browser_user_agent = random.choice(USER_AGENTS)
        config.request_timeout = 15
        article = Article(url, config=config)
        article.download()
        
        # Handle download errors
        if article.download_state != 2:  # Not successful
            print(f"Download failed for {url} with state {article.download_state}")
            return None
            
        article.html = article.html or ""
        article.text = extract_main_content(article.html) or article.text
        article.parse()
        article.nlp()
        
        return {
            "title": article.title,
            "content": article.text or article.summary,  # Unified content field
            "source": url,
            "source_domain": urlparse(url).netloc
        }
    except Exception as e:
        print(f"Article fetch error for {url}: {e}")
        return None

def assess_quality(domain):
    return 1.5 if any(d in domain for d in ['.gov', '.edu', 'wikipedia.org']) else 0.7 if any(d in domain for d in ['.blog', '.wordpress']) else 1.0

def generate_direct_answer(q, sentences):
    q_words = set([w.lower() for w in word_tokenize(q) if w.isalnum()])
    best, score = '', -1
    
    for s in sentences:
        s_words = [w.lower() for w in word_tokenize(s) if w.isalnum()]
        common = q_words & set(s_words)
        sc = len(common) + (3 if s.split()[0].lower() in ['yes','no'] else 0) + (2 if re.search(r'\d', s) else 0)
        
        # Boost for educational phrases
        if any(re.match(p, s, re.I) for p in EDUCATIONAL_PATTERNS):
            sc += 5
            
        if sc > score:
            score, best = sc, s
            
    return best or (sentences[0] if sentences else "I couldn't find a direct answer. Check the key points below.")

def handle_common_message(message):
    """Check for common phrases and return appropriate response"""
    message_lower = message.lower()
    for pattern, response in COMMON_PHRASES.items():
        if re.search(pattern, message_lower):
            return response
    return None

def get_wikipedia_summary(query):
    """Get structured summary from Wikipedia"""
    try:
        wiki_wiki = Wikipedia(
            user_agent='INFOSYNTH/1.0 (https://github.com/your-repo)',
            language='en',
            extract_format=ExtractFormat.WIKI  # Fixed format
        )
        page = wiki_wiki.page(query)
        if page.exists():
            return {
                "title": page.title,
                "content": page.summary[0:1000],
                "source": page.fullurl,  # Changed key from 'url' to 'source'
                "source_domain": "wikipedia.org"
            }
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return None

def process_articles(query, session_id):
    start = time.time()
    try:
        # Check Wikipedia first for factual queries
        wiki_result = get_wikipedia_summary(query)
        articles = []
        
        if wiki_result:
            articles.append(wiki_result)
        
        # Search the web with domain filtering
        urls = []
        for result in search(query, num_results=10, advanced=True):
            domain = urlparse(result.url).netloc.lower()
            if not any(blocked in domain for blocked in BLOCKED_DOMAINS):
                urls.append(result.url)
            if len(urls) >= 8:  # Get extra URLs to account for failures
                break
                
        # Process URLs
        for url in urls:
            if article := fetch_article(url):
                articles.append(article)
            if len(articles) >= 5:  # Limit to 5 articles
                break
                
        if not articles:
            return None
            
        # Create weighted text corpus using unified 'content' field
        text = ""
        for a in articles:
            weight = 3 if "wikipedia.org" in a['source_domain'] else 1
            if content := a.get('content'):
                text += (content * weight) + "\n\n"
        
        # Extract key information
        sents = sent_tokenize(text)
        words = [w.lower() for s in sents for w in word_tokenize(s) 
                 if w.lower() not in stopwords.words('english') and len(w) > 2]
        freq = Counter(words)
        scores = {s: sum(freq.get(w.lower(), 0) for w in word_tokenize(s))
                  for s in sents if len(s.split()) > 5}
        
        # Select best key points
        key_pts = []
        seen = set()
        for s, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            clean_s = re.sub(r'\s+', ' ', s).strip()
            if clean_s not in seen and len(clean_s) < 200:
                seen.add(clean_s)
                key_pts.append(clean_s)
            if len(key_pts) >= 5:
                break
        
        # Get educational images
        image_urls = fetch_entity_images(query, max_images=5)
        
        track_engagement(session_id, query, time.time() - start)
        return {
            "direct_answer": generate_direct_answer(query, sents),
            "key_points": key_pts,
            "sources": list({a['source'] for a in articles}),
            "image_urls": image_urls
        }
    except Exception as e:
        print(f"Process error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json
    msg = data.get('message','').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))
    
    if not msg:
        return jsonify({
            "content": "Please ask a valid question.",
            "imageUrls": [],
            "session_id": session_id
        })
    
    # Handle common messages
    if common_response := handle_common_message(msg):
        return jsonify({
            "content": common_response,
            "imageUrls": [],
            "session_id": session_id
        })
    
    # Simulate processing delay for UX
    time.sleep(1.2)
    
    # Process substantive queries
    result = process_articles(msg, session_id)
    if not result:
        return jsonify({
            "content": "I couldn't find reliable information. Try rephrasing or asking about something else.",
            "imageUrls": [],
            "session_id": session_id
        })
    
    # Format educational response with proper escaping
    html = f"<div class='response'>"
    
    if result['direct_answer']:
        safe_answer = escape(result['direct_answer'])
        html += f"<p class='direct-answer'><strong>Answer:</strong> {safe_answer}</p>"
    
    if result['key_points']:
        html += "<p class='key-points'><strong>Key Points:</strong></p><ul>"
        for p in result['key_points']:
            safe_p = escape(p)
            html += f"<li>{safe_p}</li>"
        html += "</ul>"
    
    if result['sources']:
        html += "<p class='sources'><strong>Sources:</strong></p><ul>"
        for src in result['sources']:
            safe_src = escape(src)
            domain = escape(urlparse(src).netloc)
            html += f"<li><a href='{safe_src}' target='_blank' rel='noopener'>{domain}</a></li>"
        html += "</ul>"
    
    # Add image carousel with error handling
    if result.get('image_urls'):
        html += "<div class='image-carousel'>"
        for img_url in result['image_urls']:
            safe_url = escape(img_url)
            safe_msg = escape(msg)
            html += f"""
            <div class='image-wrapper'>
                <img 
                    src='{safe_url}' 
                    alt='{safe_msg} illustration' 
                    class='response-image' 
                    loading='lazy'
                    onerror="this.parentElement.style.display='none'"
                >
            </div>
            """
        html += "</div>"
    
    html += "</div>"
    
    return jsonify({
        "content": html,
        "imageUrls": result.get('image_urls', []),
        "session_id": session_id
    })

@app.route('/api/feedback', methods=['POST'])
def feedback():
    data = request.json
    if all(k in data for k in ['session_id', 'feedback', 'question']):
        track_engagement(data['session_id'], data['question'], 0, data['feedback'])
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Missing data"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)