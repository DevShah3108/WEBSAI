from flask import Flask, request, jsonify, render_template_string
import requests
import random
from requests.exceptions import HTTPError
from googlesearch import search
from newspaper import Article, Config
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize
import nltk
import re
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from collections import Counter
import time
import concurrent.futures
from urllib.parse import urlparse
import os

app = Flask(__name__)

# Download all required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt_tab', quiet=True)  # Add missing resource

# Set NLTK data path explicitly to ensure resources are found
nltk_data_path = os.path.join(os.getcwd(), 'nltk_data')
os.makedirs(nltk_data_path, exist_ok=True)
nltk.data.path.append(nltk_data_path)

@app.route('/')
def index():
    return render_template_string(open('index.html').read())

@app.route('/api/messages/initial', methods=['GET'])
def initial_message():
    return jsonify({
        "messages": [
            {
                "sender": "bot",
                "content": "Hello! I'm WEBSAI. Ask me anything and I'll search the web for reliable answers with visualizations."
            }
        ]
    })

def generate_bar_chart(data_points, labels):
    """Generate a bar chart image from data points"""
    plt.figure(figsize=(10, 6))
    plt.bar(labels, data_points, color='#6366f1')
    plt.ylabel('Importance')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png')
    img_buffer.seek(0)
    plt.close()
    
    return base64.b64encode(img_buffer.read()).decode('utf-8')

# User agent rotation list
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36'
]

def is_valid_url(url):
    """Check if a URL is properly formatted"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def fetch_article(url):
    """Fetch and process a single article with timeout handling"""
    if not is_valid_url(url):
        print(f"Skipping invalid URL: {url}")
        return None
        
    try:
        config = Config()
        config.browser_user_agent = random.choice(USER_AGENTS)
        config.request_timeout = 10
        config.thread_timeout_seconds = 10
        
        print(f"Processing article: {url}")
        article = Article(url, config=config)
        article.download()
        article.parse()
        article.nlp()
        
        return {
            'title': article.title,
            'text': article.text,
            'summary': article.summary,
            'keywords': article.keywords,
            'source': url,
            'source_quality': 1.0
        }
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return None

def process_articles(query, num_results=5):
    """Search web and process articles for reliable information"""
    # Get search results with retries
    search_results = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Searching for: {query} (attempt {attempt+1}/{max_retries})")
            # Use the correct search parameters
            search_results = list(search(
                query, 
                num_results=num_results,
                advanced=True,
                sleep_interval=random.uniform(5.0, 10.0)
            ))
            print(f"Found {len(search_results)} search results")
            break
        except HTTPError as e:
            if e.response.status_code == 429:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Google blocked us (429). Waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                continue
            else:
                print(f"HTTP Error: {e}")
                break
        except Exception as e:
            print(f"Search error: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
            else:
                print("Max retries exceeded for search")
            continue

    if not search_results:
        print("No search results found")
        return None

    # Process articles in parallel with timeout
    articles = []
    urls = [result.url for result in search_results]
    valid_urls = [url for url in urls if is_valid_url(url)]
    
    print(f"Processing {len(valid_urls)} valid URLs")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(fetch_article, url): url for url in valid_urls}
        for future in concurrent.futures.as_completed(future_to_url, timeout=15):
            url = future_to_url[future]
            try:
                article = future.result()
                if article:
                    articles.append(article)
            except Exception as e:
                print(f"Article processing failed for {url}: {str(e)}")
    
    if not articles:
        print("No articles successfully processed")
        return None
    
    # Analyze and combine information
    all_text = "\n\n".join([a['text'] for a in articles])
    sentences = sent_tokenize(all_text)
    
    # Calculate sentence importance
    stop_words = set(stopwords.words('english'))
    word_freq = Counter()
    for sentence in sentences:
        words = [word.lower() for word in re.findall(r'\w+', sentence) 
                 if word.lower() not in stop_words and len(word) > 2]
        word_freq.update(words)
    
    # Score sentences based on word frequency
    sentence_scores = {}
    for i, sentence in enumerate(sentences):
        words = re.findall(r'\w+', sentence)
        if len(words) < 5:  # Skip very short sentences
            continue
        score = sum(word_freq[word.lower()] for word in words if word.lower() in word_freq)
        sentence_scores[i] = score / len(words)
    
    # Get top 5 key points
    top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    key_points = [sentences[idx] for idx, score in top_sentences]
    
    # Create visualization data
    visualization_data = None
    try:
        # Extract numerical data from text for visualization
        numbers = re.findall(r'\d+\.\d+|\d+', all_text)
        if numbers:
            # Convert to floats and take top 5
            num_values = sorted([float(num) for num in numbers], reverse=True)[:5]
            labels = [f"Fact {i+1}" for i in range(len(num_values))]
            visualization_data = generate_bar_chart(num_values, labels)
    except Exception as e:
        print(f"Visualization error: {e}")
    
    return {
        'key_points': key_points,
        'sources': [a['source'] for a in articles],
        'visualization': visualization_data
    }

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({
            "content": "Please enter a valid question",
            "imageUrl": None
        })
    
    # Add typing indicator simulation
    time.sleep(1.5)
    
    # Process articles
    result = process_articles(user_message)
    
    if not result:
        return jsonify({
            "content": "I couldn't find reliable information on this topic. Try asking something else.",
            "imageUrl": None
        })
    
    # Build response
    response_content = "<h4>Based on my research:</h4><ul>"
    for point in result['key_points']:
        response_content += f"<li>{point}</li>"
    response_content += "</ul>"
    
    response_content += "<p>Sources used:</p><ul>"
    for source in result['sources'][:3]:
        response_content += f"<li><a href='{source}' target='_blank'>{source[:60]}...</a></li>"
    response_content += "</ul>"
    
    # Add visualization if available
    image_url = None
    if result['visualization']:
        image_url = f"data:image/png;base64,{result['visualization']}"
    
    return jsonify({
        "content": response_content,
        "imageUrl": image_url
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)