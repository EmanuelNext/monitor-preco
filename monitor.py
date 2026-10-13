import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PRODUTO = "Bambu Lab A1 Combo (AMS Lite)"
PRECO_ALVO = 4200.00
# Abaixo disso é quase certo que o anúncio é de outro produto (A1 mini, só o AMS, peça)
PRECO_MINIMO_PLAUSIVEL = 2500.00

PASTA = Path(__file__).parent
# O mesmo script roda no GitHub Actions e no PC (tarefa agendada do Windows)
NO_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"

# O nome do tópico funciona como senha e não fica no código:
# no GitHub vem do secret NTFY_TOPIC; no PC, do arquivo ntfy_topico.txt
ARQUIVO_TOPICO = PASTA / "ntfy_topico.txt"
TOPICO_NTFY = os.environ.get("NTFY_TOPIC", "").strip()
if not TOPICO_NTFY and ARQUIVO_TOPICO.exists():
    TOPICO_NTFY = ARQUIVO_TOPICO.read_text(encoding="utf-8-sig").strip()

# Cada lado guarda o próprio estado, para o do PC não conflitar com o que o GitHub grava no repositório
ARQUIVO_ESTADO = PASTA / ("estado.json" if NO_GITHUB else "estado.local.json")

LOJAS = [
    {
        "nome": "KaBuM (kit)",
        "url": "https://www.kabum.com.br/produto/1019424/impressora-3d-bambu-lab-a1-combo-ams-lite",
        "tipo": "jsonld",
    },
    {
        "nome": "KaBuM",
        "url": "https://www.kabum.com.br/produto/679162/impressora-3d-bambu-lab-a1-com-ams-lite-velocidade-de-impressao-500mm-s-wi-fi-bambu-bus-bivolt-pf002-a-sa005-bra",
        "tipo": "jsonld",
    },
    {
        "nome": "Amazon",
        "url": "https://www.amazon.com.br/dp/B0DD81K7V7",
        "tipo": "amazon",
        # A Amazon bloqueia os servidores do GitHub, então só o PC checa esta loja
        "so_local": True,
    },
    {
        "nome": "NIC3D",
        "url": "https://www.nic3d.com.br/products/impressora-3d-bambu-lab-a1-combo-ams-lite-4-cores-256mm-profissional",
        "tipo": "jsonld",
    },
    {
        "nome": "3D Prime",
        "url": "https://3dprime.com.br/produto/impressora-3d-bambu-lab-a1-com-ams-lite-combo/",
        "tipo": "jsonld",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    # Sem estes a Amazon devolve uma página reduzida, sem o bloco de preço
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def para_float(valor):
    """Aceita 4579, "4769.10" e "R$ 4.176,05"."""
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^\d.,]", "", str(valor))
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def tem_tipo(no, tipo):
    tipos = no.get("@type")
    return tipo in (tipos if isinstance(tipos, list) else [tipos])


def produtos_jsonld(no):
    """Percorre o JSON-LD (que pode vir aninhado em listas e @graph) atrás dos nós Product."""
    if isinstance(no, list):
        for item in no:
            yield from produtos_jsonld(item)
    elif isinstance(no, dict):
        if tem_tipo(no, "Product"):
            yield no
        for valor in no.values():
            if isinstance(valor, (list, dict)):
                yield from produtos_jsonld(valor)


def preco_jsonld(soup):
    precos = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(tag.string or "")
        except ValueError:
            continue
        for produto in produtos_jsonld(dados):
            ofertas = produto.get("offers") or []
            for oferta in ofertas if isinstance(ofertas, list) else [ofertas]:
                if "OutOfStock" in str(oferta.get("availability", "")):
                    continue
                preco = para_float(oferta.get("price") or oferta.get("lowPrice") or "")
                if preco:
                    precos.append(preco)
    return min(precos, default=None)


def preco_amazon(soup):
    # A Amazon não publica JSON-LD; o preço à vista fica neste bloco
    tag = soup.select_one("#corePrice_feature_div .a-offscreen")
    return para_float(tag.get_text()) if tag else None


EXTRATORES = {"jsonld": preco_jsonld, "amazon": preco_amazon}


def buscar_preco(loja):
    resposta = requests.get(loja["url"], headers=HEADERS, timeout=30)
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "html.parser")
    preco = EXTRATORES[loja["tipo"]](soup)
    if preco is None and "captcha" in resposta.text.lower():
        raise ValueError("a loja pediu captcha, bloqueando o acesso automático")
    if preco is not None and preco < PRECO_MINIMO_PLAUSIVEL:
        raise ValueError(f"preço R$ {preco:.2f} baixo demais, o anúncio deve ter mudado")
    return preco


def enviar_ntfy(mensagem, **headers):
    resposta = requests.post(
        f"https://ntfy.sh/{TOPICO_NTFY}",
        data=mensagem.encode("utf-8"),
        headers=headers,
        timeout=30,
    )
    resposta.raise_for_status()


def notificar(loja, preco):
    enviar_ntfy(
        f"{PRODUTO} por R$ {preco:.2f} na {loja['nome']} (alvo: R$ {PRECO_ALVO:.2f})",
        Title="Alerta de preco",
        Click=loja["url"],
        Priority="high",
    )


def main():
    # estado.json guarda o último preço já avisado de cada loja, para não repetir o alerta
    estado = json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8")) if ARQUIVO_ESTADO.exists() else {}
    novo_estado = dict(estado)
    lidas = 0
    erro = False
    # O GitHub checa as lojas comuns e o PC só as bloqueadas lá, assim nenhum alerta sai em dobro
    lojas = [loja for loja in LOJAS if loja.get("so_local", False) != NO_GITHUB]

    # Marcando "teste" ao rodar o workflow manualmente, confere se o alerta chega no celular
    if os.environ.get("TESTE") == "true":
        if not TOPICO_NTFY:
            sys.exit("::error::O tópico do ntfy não está definido")
        enviar_ntfy(f"Teste do monitor de {PRODUTO}: o alerta está funcionando", Title="Teste do monitor de preco")
        print("Notificação de teste enviada")

    for loja in lojas:
        nome = loja["nome"]
        try:
            preco = buscar_preco(loja)
        except (requests.RequestException, ValueError) as e:
            print(f"::warning::{nome}: falha ao ler o preço ({e})")
            continue
        if preco is None:
            print(f"::warning::{nome}: preço não encontrado (página bloqueada, sem estoque ou layout mudou)")
            continue

        lidas += 1
        print(f"{nome}: R$ {preco:.2f}")

        if preco > PRECO_ALVO:
            novo_estado.pop(nome, None)  # voltou a subir: o próximo alerta vale de novo
            continue
        # Só avisa na primeira vez que cruza o alvo ou quando cai ainda mais
        if nome in estado and preco >= estado[nome]:
            continue
        if not TOPICO_NTFY:
            print(f"::error::{nome} está abaixo do alvo, mas o tópico do ntfy não está definido")
            erro = True
            continue
        try:
            notificar(loja, preco)
        except requests.RequestException as e:
            print(f"::error::{nome}: falha ao enviar o alerta ({e})")
            erro = True
            continue
        print(f"{nome}: alerta enviado")
        novo_estado[nome] = preco

    if novo_estado != estado:
        ARQUIVO_ESTADO.write_text(json.dumps(novo_estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if lidas == 0:
        print("::error::Nenhuma loja retornou preço")
        erro = True
    sys.exit(1 if erro else 0)


if __name__ == "__main__":
    if sys.stdout is None:
        # Tarefa agendada roda com pythonw, que não tem console: a saída vai para um arquivo
        sys.stdout = sys.stderr = open(PASTA / "monitor.log", "a", encoding="utf-8", buffering=1)
        print(f"--- {datetime.now():%d/%m/%Y %H:%M}")
    main()
