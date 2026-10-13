# monitor-preco
Monitorar preco de produtos para Emanuel e notificar.

Hoje acompanha a **Bambu Lab A1 Combo (AMS Lite)** e avisa pelo [ntfy](https://ntfy.sh) quando alguma loja chega a **R$ 4.200,00 ou menos**.

## Lojas
KaBuM (dois anúncios), Amazon, NIC3D e 3D Prime. A lista fica em `LOJAS`, no `monitor.py`.

A Amazon bloqueia os servidores do GitHub, então ela é checada só pelo PC (lojas marcadas com `so_local`). As outras são checadas só pelo GitHub, para nenhum alerta sair em dobro.

O Mercado Livre não está na lista: ele redireciona qualquer acesso sem login para uma tela de verificação de conta, então o script não consegue ler o preço.

## Como funciona
O alerta sai na primeira vez que uma loja cruza o alvo e de novo só se o preço cair ainda mais.

### No GitHub
O GitHub Actions roda o `monitor.py` a cada 30 minutos. O tópico do ntfy fica no secret `NTFY_TOPIC` (Settings > Secrets and variables > Actions) e o último preço avisado em `estado.json`, gravado pelo próprio workflow.

Loja que falha vira um aviso no log da execução. A execução só falha se nenhuma loja responder ou se um alerta não puder ser enviado.

Para conferir se o alerta chega no celular, rode o workflow manualmente marcando "Enviar uma notificação de teste".

### No PC
A tarefa agendada `MonitorPreco` do Windows roda o mesmo script a cada 30 minutos, enquanto o PC estiver ligado e com a sessão aberta. O tópico do ntfy fica em `ntfy_topico.txt`, o estado em `estado.local.json` e a saída em `monitor.log` (nenhum dos três vai para o repositório).

Preparar o ambiente:

    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt

Criar a tarefa (PowerShell, dentro da pasta do projeto):

    $acao = New-ScheduledTaskAction -Execute "$PWD\.venv\Scripts\pythonw.exe" -Argument "`"$PWD\monitor.py`"" -WorkingDirectory $PWD
    $gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
    $config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName MonitorPreco -Action $acao -Trigger $gatilho -Settings $config

Pausar, retomar e remover:

    Disable-ScheduledTask -TaskName MonitorPreco
    Enable-ScheduledTask -TaskName MonitorPreco
    Unregister-ScheduledTask -TaskName MonitorPreco -Confirm:$false
