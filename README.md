# monitor-preco
Monitorar preco de produtos para Emanuel e notificar.

Hoje acompanha a **Bambu Lab A1 Combo (AMS Lite)** e avisa pelo [ntfy](https://ntfy.sh) quando alguma loja chega a **R$ 4.200,00 ou menos**.

## Lojas
KaBuM (dois anúncios), Amazon, NIC3D e 3D Prime. A lista fica em `LOJAS`, no `monitor.py`.

O Mercado Livre não está na lista: ele redireciona qualquer acesso sem login para uma tela de verificação de conta, então o script não consegue ler o preço.

## Configuração
O nome do tópico do ntfy fica no secret `NTFY_TOPIC` do repositório (Settings > Secrets and variables > Actions). Use um nome longo e difícil de adivinhar e assine o mesmo tópico no app do ntfy.

## Como funciona
O GitHub Actions roda o `monitor.py` a cada 30 minutos. O alerta sai na primeira vez que uma loja cruza o alvo e de novo só se o preço cair ainda mais; o último preço avisado fica em `estado.json`, gravado pelo próprio workflow.

Loja que falha vira um aviso no log da execução. A execução só falha se nenhuma loja responder ou se um alerta não puder ser enviado.

Para rodar localmente:

    pip install -r requirements.txt
    python monitor.py
