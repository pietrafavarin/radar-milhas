# ✈️ Radar de Milhas

Painel pessoal que, 3 vezes por dia (7h, 12h e 19h), lê os blogs de milhas, encontra passagens em milhas,
compara cada preço com a média histórica do mesmo destino, programa e cabine, e cruza com as promoções de
transferência da **Livelo** e da **Esfera** que estão ativas.

## O que aparece no painel

| Seção | O que mostra |
|---|---|
| 🔥 Melhores do dia | Ofertas das últimas 72h, ordenadas por desconto vs. média (com peso extra para saída de SP, executiva e bônus Livelo/Esfera ativo) |
| 💳 Bônus de transferência | Promoções Livelo/Esfera ativas, se o bônus está acima ou abaixo do usual e até quando valem |
| 🌎 Por destino | Destinos agrupados por região. Clique para ver o histórico de preços e a média por programa |
| 📋 Todas as ofertas | Tabela com 120 dias de ofertas, com ordenação e filtros |

Quando uma passagem é de um programa com bônus ativo (ex.: LATAM Pass + Livelo 27%), o card mostra quantos
pontos Livelo/Esfera você precisaria transferir (considerando paridade 1:1).

## Como colocar no ar (uma vez só, ~5 minutos)

1. Crie uma conta em https://github.com, se ainda não tiver.
2. Crie um repositório **público** chamado `radar-milhas` (o GitHub Pages grátis exige repositório público;
   os dados são só de blogs públicos, nada pessoal).
3. No PowerShell, dentro desta pasta:
   ```powershell
   git init -b main
   git add .
   git commit -m "Radar de Milhas"
   git remote add origin https://github.com/SEU_USUARIO/radar-milhas.git
   git push -u origin main
   ```
4. No repositório: **Settings → Pages → Branch: `main`, pasta `/docs` → Save**.
5. Em **Actions**, habilite os workflows se pedir e clique em **Radar de Milhas → Run workflow** para testar.
6. O painel fica em `https://SEU_USUARIO.github.io/radar-milhas/`. Salve nos favoritos do celular.

## Alertas no Telegram (opcional, ~3 minutos)

O radar manda mensagem quando aparece:
- passagem **≥ 10% abaixo da média** saindo de SP (ou sem origem informada), publicada nas últimas 72h;
- bônus **Livelo/Esfera ativo** igual ou acima do usual para aquele programa.

Cada oferta é avisada uma vez só, com no máximo 8 mensagens por execução. Na primeira execução chega uma mensagem
"Radar ativado" com os destaques do momento.

1. No Telegram, abra o **@BotFather**, mande `/newbot` e escolha um nome. Ele responde com um **token**.
2. Abra o seu bot novo e mande um "oi" para ele.
3. No PowerShell, nesta pasta, descubra o seu chat id:
   ```powershell
   $env:TELEGRAM_TOKEN = "COLE_O_TOKEN_AQUI"
   py run.py --descobrir-chat
   ```
4. No GitHub: **Settings → Secrets and variables → Actions → New repository secret**, crie
   `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`.
5. Rode o workflow manualmente (Actions → Radar de Milhas → Run workflow) e veja a mensagem chegar.

Para mudar as regras sem mexer no código, crie em **Variables** (mesma tela):
`ALERTA_DESCONTO_MIN` (ex.: `20` para avisar só ofertas 20% abaixo) e `ALERTA_SO_SP` (`0` para todas as origens).

Testes locais: `py run.py --offline --simular-alertas` mostra o que seria enviado, e `py run.py --testar-alerta`
manda uma mensagem de teste (com `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` definidos).

## Rodar no seu computador

```powershell
py run.py                # coleta e atualiza docs/data.json
py -m http.server -d docs 8000   # depois abra http://localhost:8000
py -m unittest discover -s tests   # testes do extrator
```

`py run.py --paginas 25` refaz a carga histórica (vários meses). `py run.py --offline` só recalcula.

## Como funciona

- `radar/collect.py`: feeds RSS do Melhores Destinos, Passageiro de Primeira, Pontos pra Voar e Alta Renda (com pausa entre pedidos)
- `radar/ppv.py`: lê as tabelas dos "Alerta PPV" (rota, milhas e data exata de cada voo)
- `radar/enrich.py`: lê o período de viagem no texto completo dos posts do Melhores Destinos
- `radar/parser.py`: identifica programa, milhas por trecho, cabine, origem, destino, bônus e prazo
- `radar/places.py`: dicionário de ~200 destinos com região. Adicione cidades aqui se faltar alguma
- `radar/analyze.py`: média aparada dos últimos 12 meses, ranking do dia e cruzamento com Livelo/Esfera
- `data/posts.json`: histórico (cresce a cada execução; é ele que deixa a média mais precisa)
- `docs/`: o site estático

### Limites que vale saber

- Só aparecem ofertas que os blogs publicam. O radar não consulta Smiles/LATAM/Azul diretamente (eles não têm API
  pública e bloqueiam robôs).
- A "média" é das ofertas divulgadas, que já são promoções. Ficar abaixo dela é sinal de oferta muito boa.
- Valores são lidos do texto dos posts. Erros pontuais de leitura podem acontecer: sempre confira no link antes de transferir.
- Pontos necessários assumem paridade 1:1 entre Livelo/Esfera e o programa aéreo.
