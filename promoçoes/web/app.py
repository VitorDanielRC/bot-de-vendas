from __future__ import annotations

import html
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from database.db import Database
from services.pipeline import PromotionPipeline
from services.status import RuntimeStatus
from services.whatsapp import WhatsAppService


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def create_app(
    database: Database,
    status: RuntimeStatus,
    whatsapp: WhatsAppService,
    pipeline: PromotionPipeline,
    lifespan: Any = None,
) -> FastAPI:
    app = FastAPI(title="Promo Bot", version="1.0.0", lifespan=lifespan)

    class GroupSelection(BaseModel):
        chat_id: str

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        stats = await stats_endpoint()
        offers = database.query(
            "SELECT store, title, price, discount, coupon, found_at FROM offers ORDER BY found_at DESC LIMIT 20"
        )
        status_json = html.escape(json.dumps(stats, ensure_ascii=False, indent=2))
        return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
        <meta name='viewport' content='width=device-width,initial-scale=1'><title>Promo Bot</title>
        <style>body{{font:15px system-ui;max-width:1200px;margin:32px auto;padding:0 18px;background:#f5f7fb;color:#182230}}
        h1{{color:#e85d04}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:white;padding:16px;border-radius:10px;box-shadow:0 2px 9px #0001}}
        table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:9px;text-align:left;border-bottom:1px solid #ddd}}pre{{white-space:pre-wrap}}</style>
        </head><body><h1>🔥 Promo Bot</h1><div class='cards'><div class='card'><b>Encontradas</b><br>{stats['offers_found']}</div>
        <div class='card'><b>Enviadas</b><br>{stats['offers_sent']}</div><div class='card'><b>Última busca</b><br>{stats['last_scan'] or 'ainda não executada'}</div></div>
        <p><a href='/whatsapp'>Conectar WhatsApp e escolher grupo →</a></p>
        <h2>Ofertas recentes</h2>{_table(offers, ['store','title','price','discount','coupon','found_at'])}
        <h2>Estado</h2><pre>{status_json}</pre></body></html>"""

    @app.get("/whatsapp", response_class=HTMLResponse)
    async def whatsapp_setup() -> str:
        return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1"><title>Conectar WhatsApp</title>
        <style>body{font:16px system-ui;max-width:760px;margin:32px auto;padding:0 18px;background:#f5f7fb;color:#182230}
        main{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 10px #0001}h1{color:#138a52}
        #qr{width:min(100%,360px);display:none;margin:16px auto}select,button{font:inherit;padding:10px;margin:6px 0}
        button{background:#138a52;color:white;border:0;border-radius:8px;cursor:pointer}#groups{display:none}
        #message{padding:12px;background:#eef2f5;border-radius:8px;white-space:pre-wrap}</style></head>
        <body><main><a href="/">← Painel</a><h1>Conectar WhatsApp</h1>
        <p id="message">Verificando a sessão…</p><img id="qr" alt="QR Code do WhatsApp">
        <section id="groups"><h2>Escolha o grupo de ofertas</h2><select id="groupList"></select><br>
        <button id="save">Usar este grupo</button></section></main>
        <script>
        const message=document.getElementById('message'), qr=document.getElementById('qr'), groups=document.getElementById('groups');
        let groupsLoaded=false;
        async function refresh(){
          try{
            const s=await (await fetch('/whatsapp/status')).json();
            if(s.status==='WORKING'){
              qr.style.display='none'; message.textContent=s.chat_id ? 'WhatsApp conectado. Grupo configurado: '+s.chat_id : 'WhatsApp conectado. Escolha abaixo o grupo para as ofertas.';
              groups.style.display='block'; if(!groupsLoaded) await loadGroups();
            } else if(s.status==='SCAN_QR_CODE'){
              groups.style.display='none'; message.textContent='Leia o QR Code no WhatsApp: Configurações → Aparelhos conectados → Conectar aparelho.';
              qr.src='/whatsapp/qr?t='+Date.now(); qr.style.display='block';
            } else { qr.style.display='none'; groups.style.display='none'; message.textContent='Estado da sessão: '+(s.status||'indisponível')+(s.error?' — '+s.error:''); }
          } catch(e){ message.textContent='Não consegui consultar o WAHA. Confirme se o serviço está ativo e recarregue.'; }
        }
        async function loadGroups(){
          const select=document.getElementById('groupList');
          try { const response=await fetch('/whatsapp/groups'); if(!response.ok) throw new Error(); const data=await response.json(); select.replaceChildren();
            for(const g of data){const id=g.id||g.gid||g.chatId||''; if(!id.endsWith('@g.us')) continue;
              const option=document.createElement('option'); option.value=id; option.textContent=(g.name||g.subject||id)+' — '+id; select.append(option); }
            groupsLoaded=true;
            if(!select.options.length) message.textContent='WhatsApp conectado, mas não encontrei grupos. Confirme que essa conta participa de um grupo e recarregue.';
          } catch(e){ message.textContent='Não consegui carregar os grupos. Aguarde alguns segundos e recarregue.'; }
        }
        document.getElementById('save').addEventListener('click',async()=>{
          const chat_id=document.getElementById('groupList').value;
          const response=await fetch('/whatsapp/select-group',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chat_id})});
          const result=await response.json(); message.textContent=response.ok?'Grupo salvo. O bot já pode publicar ofertas.':(result.detail||'Não foi possível salvar o grupo.');
        });
        refresh(); setInterval(refresh,12000);
        </script></body></html>"""

    @app.get("/whatsapp/status")
    async def whatsapp_status() -> dict[str, Any]:
        try:
            info = await whatsapp.session_info()
            return {"status": info.get("status", "UNKNOWN"), "chat_id": whatsapp.settings.waha_chat_id}
        except Exception as exc:
            return {"status": "UNAVAILABLE", "chat_id": whatsapp.settings.waha_chat_id, "error": str(exc)}

    @app.get("/whatsapp/qr")
    async def whatsapp_qr() -> Response:
        try:
            qr_response = await whatsapp.get_qr()
            return Response(content=qr_response.content, media_type=qr_response.headers.get("content-type", "image/png"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="QR Code ainda não está disponível; tente novamente em alguns segundos.") from exc

    @app.get("/whatsapp/groups")
    async def whatsapp_groups() -> list[dict[str, Any]]:
        try:
            return await whatsapp.groups()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Grupos indisponíveis até o WhatsApp conectar.") from exc

    @app.post("/whatsapp/select-group")
    async def select_whatsapp_group(selection: GroupSelection) -> dict[str, str]:
        chat_id = selection.chat_id.strip()
        if not chat_id.endswith("@g.us"):
            raise HTTPException(status_code=422, detail="Selecione um grupo do WhatsApp.")
        try:
            known_groups = await whatsapp.groups()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Conecte o WhatsApp antes de escolher um grupo.") from exc
        if not any((group.get("id") or group.get("gid") or group.get("chatId")) == chat_id for group in known_groups):
            raise HTTPException(status_code=404, detail="Esse grupo não apareceu na lista da conta conectada.")
        database.set_setting("waha_chat_id", chat_id)
        whatsapp.settings.waha_chat_id = chat_id
        return {"status": "saved", "chat_id": chat_id}

    @app.get("/offers")
    async def offers_endpoint(limit: int = Query(100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return database.query("SELECT * FROM offers ORDER BY found_at DESC LIMIT ?", (limit,))

    @app.get("/history")
    async def history_endpoint(limit: int = Query(100, ge=1, le=1000)) -> list[dict[str, Any]]:
        return database.query("SELECT * FROM price_history ORDER BY timestamp DESC LIMIT ?", (limit,))

    @app.get("/stats")
    async def stats_endpoint() -> dict[str, Any]:
        counts = database.query(
            """SELECT (SELECT COUNT(*) FROM offers) offers_found,
            (SELECT COUNT(*) FROM sent_offers) offers_sent,
            (SELECT COUNT(*) FROM price_history) price_samples"""
        )[0]
        stores = database.query("SELECT store, COUNT(*) count FROM offers GROUP BY store ORDER BY count DESC")
        snapshot = status.snapshot()
        return {**counts, "stores": stores, "last_scan": snapshot["last_scan"], "errors": snapshot["last_errors"]}

    @app.get("/health")
    async def health_endpoint() -> dict[str, Any]:
        snapshot = status.snapshot()
        return {
            "status": "ok" if database.health() else "degraded",
            "database": database.health(),
            "whatsapp": await whatsapp.health(),
            **snapshot["providers"],
            "scan_running": snapshot["running"],
        }

    @app.post("/scan")
    async def scan_endpoint(request: Request) -> dict[str, Any]:
        # Operação local; não há autenticação embutida. Não exponha a porta sem proxy/autenticação.
        return await pipeline.run()

    return app
