# Promo Bot para WhatsApp

Bot em Python que procura promoções, filtra descontos, evita publicações repetidas, mantém histórico de preços e envia as melhores ofertas a um grupo do WhatsApp usando WAHA. Inclui painel web em `http://localhost:8000`.

## Início rápido no Windows

1. Instale e abra o [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Nesta pasta, copie o arquivo de configuração:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Troque os três valores `replace-with-...` no `.env` por segredos longos e diferentes. Eles protegem a API, o painel e o Swagger do WAHA.
4. Inicie os contêineres:

   ```powershell
   docker compose up -d --build
   ```

5. Abra o painel do WAHA em [http://localhost:3000/dashboard/](http://localhost:3000/dashboard/), entre com as credenciais do `.env`, conecte o servidor usando `WAHA_API_KEY`, crie/inicie a sessão `default` e leia o QR Code com o WhatsApp.
6. Descubra o ID do grupo no painel/API do WAHA. Ele se parece com `120363xxxxxxxx@g.us`.
7. Coloque esse valor em `WAHA_CHAT_ID` no `.env` e reinicie:

   ```powershell
   docker compose restart promo-bot
   ```

8. Abra o painel do bot em [http://localhost:8000](http://localhost:8000). Uma busca também pode ser iniciada manualmente com `POST http://localhost:8000/scan`.

Sem `WAHA_CHAT_ID`, o bot inicia normalmente, pesquisa e salva ofertas, mas não as marca como enviadas.

## Comandos úteis

```powershell
docker compose up -d
docker compose down
docker compose logs -f promo-bot
docker compose restart promo-bot
docker compose ps
```

## Configuração

As regras gerais ficam no `.env`:

- `SCAN_INTERVAL_MINUTES`: intervalo entre buscas.
- `MIN_DISCOUNT`, `MIN_PRICE`, `MAX_PRICE`: filtro geral.
- `MAX_POSTS_PER_RUN`: limite por execução.
- `REPOST_AFTER_HOURS`: prazo para permitir republicação.
- `SIGNIFICANT_PRICE_DROP_PERCENT`: queda mínima que libera republicação antecipada.
- `RUN_SCAN_ON_STARTUP`: faz uma busca ao iniciar.

As pesquisas e descontos por categoria ficam em `config/products.json`. Edite ou acrescente itens no mesmo formato. Os cupons manuais ficam em `config/coupons.json`; exemplo:

```json
{
  "mercadolivre": [
    {"code": "TECH20", "discount": "20%", "min_value": 100, "expires_at": "2026-12-31"}
  ],
  "shopee": [],
  "aliexpress": []
}
```

Cupons vencidos, inválidos ou cujo valor mínimo não é atendido são ignorados.

## Lojas e afiliados

- **Mercado Livre:** usa o endpoint oficial de busca, que atualmente exige `MERCADOLIVRE_ACCESS_TOKEN`. Crie uma aplicação, conclua o OAuth seguindo a [documentação oficial de autenticação](https://developers.mercadolivre.com.br/autenticacao-e-autorizacao) e coloque o access token no `.env`. Sem ele, essa fonte é ignorada. `MERCADOLIVRE_AFFILIATE_TAG` acrescenta o identificador `matt_tool` aos links quando sua conta possuir esse recurso.
- **Shopee:** só é habilitada quando `SHOPEE_APP_ID` e `SHOPEE_SECRET` estão preenchidos. A busca usa a Affiliate Open API e os links retornados por ela. O acesso depende da aprovação no programa de afiliados. Se o esquema disponibilizado para sua conta diferir, ajuste a consulta em `providers/shopee.py` conforme a documentação do portal.
- **AliExpress:** só é habilitado com `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` e `ALIEXPRESS_TRACKING_ID`. Usa `aliexpress.affiliate.product.query` e o link promocional retornado pela API oficial de afiliados.

Não há scraping, contorno de CAPTCHA ou acesso a API privada. Uma loja desativada ou com erro não impede as demais nem derruba o painel.

## Painel e API

- `GET /` — painel HTML.
- `GET /offers?limit=100` — ofertas encontradas.
- `GET /history?limit=100` — amostras de preço.
- `GET /stats` — totais, lojas, erros e última busca.
- `GET /health` — banco, WhatsApp e providers.
- `POST /scan` — inicia uma busca manual (espera o término).
- `GET /docs` — documentação interativa do FastAPI.

O painel não possui login. Mantenha a porta `8000` acessível apenas localmente ou coloque autenticação em um proxy reverso antes de expor à internet.

## Como a seleção funciona

Somente produtos com preço anterior real e desconto calculável passam pelo filtro. A pontuação considera desconto, relevância da categoria, cupom e menor preço histórico. Quando o preço de referência está muito acima da mediana histórica, a oferta recebe uma penalização — o bot não afirma que houve fraude.

SQLite é criado automaticamente em `data/promotions.db`. Os volumes do Compose preservam o banco e as sessões do WAHA.

## Testes locais

Com Python 3.12 instalado:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Ou rode os testes sem instalar Python no Windows:

```powershell
docker compose --profile test run --rm tests
```

## Solução de problemas

- **Nada é enviado:** confira `WAHA_CHAT_ID`, sessão `default`, QR Code e `WAHA_API_KEY`; veja `/health` e os logs.
- **Shopee/AliExpress aparecem como `false`:** isso é esperado sem credenciais completas.
- **Mercado Livre aparece como `false`:** configure um access token válido e confirme o acesso ao endpoint no portal de desenvolvedores.
- **Uma oferta não reaparece:** consulte `sent_offers`/`REPOST_AFTER_HOURS`; uma queda de preço ou novo cupom permite envio antecipado.
- **Alterou o `.env`:** use `docker compose up -d --force-recreate promo-bot` para recriar o contêiner com as novas variáveis.
