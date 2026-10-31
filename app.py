from __future__ import annotations

import json
import os
import sqlite3
import threading
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "finances_data" / "financas.db"
HOST, PORT = "127.0.0.1", 8765


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (
          id INTEGER PRIMARY KEY, date TEXT NOT NULL, description TEXT NOT NULL,
          kind TEXT NOT NULL CHECK(kind IN ('income','expense','card')),
          amount REAL NOT NULL CHECK(amount >= 0), status TEXT NOT NULL DEFAULT 'actual',
          category TEXT NOT NULL DEFAULT '', installments INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bills (
          id INTEGER PRIMARY KEY, month TEXT NOT NULL, name TEXT NOT NULL,
          amount REAL NOT NULL, due_day INTEGER NOT NULL DEFAULT 5,
          paid REAL NOT NULL DEFAULT 0, replicate INTEGER NOT NULL DEFAULT 0,
          UNIQUE(month,name)
        );
        CREATE TABLE IF NOT EXISTS transfers (
          id INTEGER PRIMARY KEY, date TEXT NOT NULL, month TEXT NOT NULL,
          amount REAL NOT NULL, description TEXT NOT NULL DEFAULT 'Repasse da esposa'
        );
        CREATE TABLE IF NOT EXISTS card_cycles (
          month TEXT PRIMARY KEY, start_date TEXT NOT NULL, close_date TEXT NOT NULL,
          payment_date TEXT NOT NULL, opening_balance REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS apartment_entries (
          id INTEGER PRIMARY KEY, date TEXT NOT NULL, source TEXT NOT NULL,
          objective TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Outros', plan TEXT NOT NULL DEFAULT '',
          installment_number INTEGER, installment_total INTEGER, reference TEXT NOT NULL DEFAULT '',
          balance_after REAL,
          nominal_amount REAL NOT NULL CHECK(nominal_amount >= 0),
          corrected_amount REAL NOT NULL CHECK(corrected_amount >= 0),
          notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS apartment_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        apartment_columns = {r["name"] for r in con.execute("PRAGMA table_info(apartment_entries)")}
        for name, declaration in (("category", "TEXT NOT NULL DEFAULT 'Outros'"), ("plan", "TEXT NOT NULL DEFAULT ''"), ("reference", "TEXT NOT NULL DEFAULT ''"), ("balance_after", "REAL")):
            if name not in apartment_columns: con.execute(f"ALTER TABLE apartment_entries ADD COLUMN {name} {declaration}")
        if "category" not in apartment_columns:
            con.execute("UPDATE apartment_entries SET category=CASE WHEN lower(objective) LIKE '%evolu%' THEN 'Evolução' WHEN lower(objective) LIKE '%entrada%' OR lower(objective) LIKE '%sinal%' THEN 'Entrada' WHEN lower(objective) LIKE '%taxa%' OR lower(objective) LIKE '%tarifa%' OR lower(objective) LIKE '%corret%' THEN 'Taxas' ELSE 'Outros' END")
        con.execute("UPDATE apartment_entries SET plan='Entrada principal' WHERE category='Entrada' AND installment_total>1 AND plan=''")
        con.execute("DELETE FROM apartment_settings WHERE key IN ('historic_paid_nominal','historic_paid_corrected','historic_fees','historic_evolution','historic_invested_amount','historic_invested_reference','entry_installments_remaining')")
        bill_columns = {r["name"] for r in con.execute("PRAGMA table_info(bills)")}
        if "replicate" not in bill_columns:
            con.execute("ALTER TABLE bills ADD COLUMN replicate INTEGER NOT NULL DEFAULT 0")
        defaults = {
          "reserve_floor":"40", "daily_card_plan":"40", "salary":"0", "salary_day":"30",
          "household_day":"5", "card_payment_day":"5", "card_start_day":"1",
          "card_close_day":"28", "wife_share":"34.9", "projection_months":"12",
          "wife_debt_initial_month":"2026-11", "wife_debt_initial_amount":"4266.35"
        }
        for k,v in defaults.items(): con.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k,v))
        apartment_defaults = {
          "property_value_brokerage":"333318.00", "property_value_signature":"367199.91",
          "financed_amount":"270348.08"
        }
        for k,v in apartment_defaults.items(): con.execute("INSERT OR IGNORE INTO apartment_settings VALUES (?,?)", (k,v))


def rowdicts(rows): return [dict(r) for r in rows]


def state():
    today = date.today().isoformat()
    with db() as con:
        settings = {r["key"]: r["value"] for r in con.execute("SELECT * FROM settings")}
        tx = rowdicts(con.execute("SELECT * FROM transactions ORDER BY date DESC,id DESC LIMIT 500"))
        bills = rowdicts(con.execute("SELECT * FROM bills ORDER BY month DESC,due_day,name"))
        transfers = rowdicts(con.execute("SELECT * FROM transfers ORDER BY date DESC,id DESC LIMIT 200"))
        cycles = rowdicts(con.execute("SELECT * FROM card_cycles ORDER BY month DESC LIMIT 24"))
        alltx = rowdicts(con.execute("SELECT * FROM transactions"))
        apartment_entries = rowdicts(con.execute("SELECT * FROM apartment_entries ORDER BY date DESC,id DESC"))
        apartment_settings = {r["key"]:r["value"] for r in con.execute("SELECT * FROM apartment_settings")}
    return {"today":today,"settings":settings,"transactions":tx,"bills":bills,"transfers":transfers,"cycles":cycles,"allTransactions":alltx,"apartmentEntries":apartment_entries,"apartmentSettings":apartment_settings}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(raw)
    def json_body(self):
        n=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/state": return self.send(200,json.dumps(state(),ensure_ascii=False))
        if path=="/api/backup":
            return self.send(200,DB_PATH.read_bytes(),"application/vnd.sqlite3",{"Content-Disposition":"attachment; filename=financas-backup.db"})
        if path=="/": path="/index.html"
        target=(ROOT/"web"/path.lstrip("/")).resolve()
        if not str(target).startswith(str((ROOT/"web").resolve())) or not target.is_file(): return self.send(404,"Not found","text/plain")
        ctype="text/html; charset=utf-8" if target.suffix==".html" else "text/javascript; charset=utf-8" if target.suffix==".js" else "text/css; charset=utf-8"
        return self.send(200,target.read_bytes(),ctype)
    def do_POST(self):
        path=urlparse(self.path).path; data=self.json_body()
        try:
            with db() as con:
                if path=="/api/transactions":
                    con.execute("INSERT INTO transactions(date,description,kind,amount,status,category,installments) VALUES(?,?,?,?,?,?,?)",(data["date"],data["description"],data["kind"],float(data["amount"]),data.get("status","actual"),data.get("category",""),int(data.get("installments",1))))
                elif path=="/api/bills":
                    con.execute("INSERT INTO bills(month,name,amount,due_day,paid,replicate) VALUES(?,?,?,?,?,?) ON CONFLICT(month,name) DO UPDATE SET amount=excluded.amount,due_day=excluded.due_day,paid=excluded.paid,replicate=excluded.replicate",(data["month"],data["name"],float(data["amount"]),int(data.get("due_day",5)),float(data.get("paid",0)),1 if data.get("replicate") else 0))
                elif path=="/api/bills/pay":
                    bill=con.execute("SELECT * FROM bills WHERE id=?",(int(data["id"]),)).fetchone()
                    if not bill: return self.send(404,json.dumps({"error":"Conta não encontrada"},ensure_ascii=False))
                    remaining=max(0.0,float(bill["amount"])-float(bill["paid"]))
                    if remaining<=0: return self.send(400,json.dumps({"error":"Esta conta já está marcada como paga"},ensure_ascii=False))
                    tx_date=data.get("date",date.today().isoformat())
                    con.execute("INSERT INTO transactions(date,description,kind,amount,status,category,installments) VALUES(?,?,?,?,?,?,1)",(tx_date,f"Pagamento da conta: {bill['name']}","expense",remaining,"actual","Contas da casa"))
                    con.execute("UPDATE bills SET paid=amount WHERE id=?",(int(data["id"]),))
                elif path=="/api/transfers":
                    con.execute("INSERT INTO transfers(date,month,amount,description) VALUES(?,?,?,?)",(data["date"],data["month"],float(data["amount"]),data.get("description","Repasse da esposa")))
                elif path=="/api/cycles":
                    con.execute("INSERT INTO card_cycles(month,start_date,close_date,payment_date,opening_balance) VALUES(?,?,?,?,?) ON CONFLICT(month) DO UPDATE SET start_date=excluded.start_date,close_date=excluded.close_date,payment_date=excluded.payment_date,opening_balance=excluded.opening_balance",(data["month"],data["start_date"],data["close_date"],data["payment_date"],float(data.get("opening_balance",0))))
                elif path=="/api/settings":
                    for k,v in data.items(): con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
                elif path=="/api/apartment/settings":
                    for k,v in data.items(): con.execute("INSERT INTO apartment_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
                elif path=="/api/apartment/entries":
                    values=(data["date"],data["source"],data["objective"],data.get("category","Outros"),data.get("plan",""),int(data["installment_number"]) if data.get("installment_number") else None,int(data["installment_total"]) if data.get("installment_total") else None,data.get("reference",""),float(data["balance_after"]) if data.get("balance_after") else None,float(data["nominal_amount"]),float(data["corrected_amount"]),data.get("notes",""))
                    if data.get("id"):
                        con.execute("UPDATE apartment_entries SET date=?,source=?,objective=?,category=?,plan=?,installment_number=?,installment_total=?,reference=?,balance_after=?,nominal_amount=?,corrected_amount=?,notes=? WHERE id=?",(*values,int(data["id"])))
                    else:
                        con.execute("INSERT INTO apartment_entries(date,source,objective,category,plan,installment_number,installment_total,reference,balance_after,nominal_amount,corrected_amount,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",values)
                else: return self.send(404,json.dumps({"error":"Endpoint não encontrado"}))
            return self.send(200,json.dumps({"ok":True}))
        except (KeyError,ValueError,sqlite3.Error) as e: return self.send(400,json.dumps({"error":str(e)},ensure_ascii=False))
    def do_DELETE(self):
        p=urlparse(self.path).path.split("/")
        tables={"transactions":"transactions","bills":"bills","transfers":"transfers","apartment":"apartment_entries"}
        try:
            if len(p)==4 and p[2] in tables:
                with db() as con: con.execute(f"DELETE FROM {tables[p[2]]} WHERE id=?",(int(p[3]),))
            elif len(p)==4 and p[2]=="cycles":
                with db() as con: con.execute("DELETE FROM card_cycles WHERE month=?",(p[3],))
            else: return self.send(404,"{}")
            return self.send(200,"{\"ok\":true}")
        except ValueError: return self.send(400,"{}")


if __name__=="__main__":
    init_db()
    url=f"http://{HOST}:{PORT}"
    threading.Timer(0.8,lambda:webbrowser.open(url)).start()
    print(f"Finanças está aberto em {url}. Feche esta janela para encerrar.")
    try: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: pass
