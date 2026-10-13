import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.loja.com.br/seu-produto"
PRECO_ALVO = 1500.00
TOPICO_NTFY = "emanuel-alerta-8f3k2x"


def buscar_preco():
    html = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    # A maioria das lojas publica o preço num bloco de dados estruturados (JSON-LD)
    for tag in soup.find_all("script", type="application/ld+json"):
        achado = re.search(r'"price"\s*:\s*"?([\d.]+)', tag.string or "")
        if achado:
            return float(achado.group(1))
    return None


preco = buscar_preco()
print("Preço encontrado:", preco)

if preco is not None and preco <= PRECO_ALVO:
    requests.post(
        f"https://ntfy.sh/{TOPICO_NTFY}",
        data=f"Baixou para R$ {preco:.2f} (alvo: R$ {PRECO_ALVO:.2f})".encode("utf-8"),
        headers={"Title": "Alerta de preco", "Click": URL, "Priority": "high"},
        timeout=30,
    )
