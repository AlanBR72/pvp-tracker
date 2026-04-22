import requests
from bs4 import BeautifulSoup

nome = "Virtue Alan"
url = f"https://www.rucoyonline.com/characters/{nome.replace(' ', '%20')}"

headers = {
    "User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers, timeout=10)

print("STATUS:", r.status_code)

soup = BeautifulSoup(r.text, "html.parser")

print("\n=== TEXTO BRUTO (PARTE) ===\n")
print(soup.text[:1000])  # só começo
