import requests
from bs4 import BeautifulSoup

def fetch_quotes():
    # The URL of the website we want to scrape
    url = "http://quotes.toscrape.com/"
    
    # Send an HTTP GET request to the URL
    print(f"Fetching data from {url}...\n")
    response = requests.get(url)
    
    # Check if the request was successful (Status Code 200)
    if response.status_code == 200:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all HTML blocks containing a quote
        quotes = soup.find_all('div', class_='quote')
        
        # Loop through each block, extract the text and author, and print them
        for i, quote_block in enumerate(quotes, 1):
            text = quote_block.find('span', class_='text').text
            author = quote_block.find('small', class_='author').text
            print(f"{i}. {text}")
            print(f"   — {author}\n")
            
    else:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")

if __name__ == "__main__":
    fetch_quotes()