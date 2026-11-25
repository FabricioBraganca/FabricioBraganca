import csv
import io
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATUSES = {"Aberta", "Em atendimento", "Aguardando peça", "Concluída", "Cancelada"}
PRIORITIES = {"Baixa", "Normal", "Alta", "Urgente"}


class AppError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def required_text(value, field, limit=200):
    if not isinstance(value, str) or not value.strip():
        raise AppError(400, f"O campo '{field}' é obrigatório.")
    value = value.strip()
    if len(value) > limit:
        raise AppError(400, f"O campo '{field}' deve ter no máximo {limit} caracteres.")
    return value


def positive_int(value, field):
    if isinstance(value, bool):
        raise AppError(400, f"O campo '{field}' deve ser um número inteiro positivo.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise AppError(400, f"O campo '{field}' deve ser um número inteiro positivo.") from None
    if number <= 0 or str(number) != str(value).strip():
        raise AppError(400, f"O campo '{field}' deve ser um número inteiro positivo.")
    return number


def nonnegative_int(value, field):
    message = f"O campo '{field}' deve ser um inteiro maior ou igual a zero."
    if isinstance(value, bool):
        raise AppError(400, message)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise AppError(400, message) from None
    if number < 0 or (isinstance(value, float) and not value.is_integer()):
        raise AppError(400, message)
    if isinstance(value, str) and not re.fullmatch(r"\+?\d+", value.strip()):
        raise AppError(400, message)
    return number


def nonnegative_number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AppError(400, f"O campo '{field}' deve ser um número maior ou igual a zero.") from None
    if number < 0 or number == float("inf") or number != number:
        raise AppError(400, f"O campo '{field}' deve ser um número maior ou igual a zero.")
    return number


class Service:
    def __init__(self, db_path=None):
        configured_path = db_path or os.environ.get("TONER_DB_PATH")
        self.db_path = Path(configured_path) if configured_path else BASE_DIR / "data" / "toner_manager.sqlite3"

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS toners (
                    id INTEGER PRIMARY KEY,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    min_stock INTEGER NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS toner_lots (
                    id INTEGER PRIMARY KEY,
                    toner_id INTEGER NOT NULL REFERENCES toners(id),
                    quantity_remaining INTEGER NOT NULL CHECK (quantity_remaining >= 0),
                    cost_per_unit REAL NOT NULL CHECK (cost_per_unit >= 0),
                    received_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_orders (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id),
                    equipment TEXT NOT NULL,
                    issue TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolution TEXT NOT NULL DEFAULT '',
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id INTEGER PRIMARY KEY,
                    toner_id INTEGER NOT NULL REFERENCES toners(id),
                    lot_id INTEGER REFERENCES toner_lots(id),
                    work_order_id INTEGER REFERENCES work_orders(id),
                    movement_type TEXT NOT NULL CHECK (movement_type IN ('IN', 'OUT')),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_lots_fifo ON toner_lots(toner_id, received_at, id);
                CREATE INDEX IF NOT EXISTS idx_movements_date ON stock_movements(created_at, movement_type);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON work_orders(status, opened_at);
                """
            )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def list_clients(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE")]

    def add_client(self, data):
        name = required_text(data.get("name"), "name")
        phone = str(data.get("phone", "")).strip()[:60]
        email = str(data.get("email", "")).strip()[:200]
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise AppError(400, "Informe um e-mail válido.")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO clients(name, phone, email, created_at) VALUES (?, ?, ?, ?)",
                (name, phone, email, self._now()),
            )
            return dict(db.execute("SELECT * FROM clients WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def list_toners(self):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT t.id, t.sku, t.name, t.min_stock, t.created_at,
                       COALESCE(SUM(l.quantity_remaining), 0) AS quantity,
                       COALESCE(SUM(l.quantity_remaining * l.cost_per_unit), 0) AS inventory_value
                FROM toners t LEFT JOIN toner_lots l ON l.toner_id = t.id
                GROUP BY t.id ORDER BY t.name COLLATE NOCASE
                """
            )
            return [dict(row) for row in rows]

    def add_toner(self, data):
        sku = required_text(data.get("sku"), "sku", 80)
        name = required_text(data.get("name"), "name")
        min_stock = nonnegative_int(data.get("min_stock", 0), "min_stock")
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "INSERT INTO toners(sku, name, min_stock, created_at) VALUES (?, ?, ?, ?)",
                    (sku, name, min_stock, self._now()),
                )
                toner_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise AppError(409, "Já existe um toner cadastrado com esse código/SKU.") from None
        return next(toner for toner in self.list_toners() if toner["id"] == toner_id)

    def receive_stock(self, data):
        toner_id = positive_int(data.get("toner_id"), "toner_id")
        quantity = positive_int(data.get("quantity"), "quantity")
        cost = nonnegative_number(data.get("cost_per_unit", 0), "cost_per_unit")
        received_at = str(data.get("received_at") or date.today().isoformat())
        try:
            date.fromisoformat(received_at)
        except ValueError:
            raise AppError(400, "A data de entrada deve estar no formato AAAA-MM-DD.") from None
        now = self._now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM toners WHERE id = ?", (toner_id,)).fetchone():
                raise AppError(404, "Toner não encontrado.")
            cursor = db.execute(
                "INSERT INTO toner_lots(toner_id, quantity_remaining, cost_per_unit, received_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (toner_id, quantity, cost, received_at, now),
            )
            db.execute(
                "INSERT INTO stock_movements(toner_id, lot_id, movement_type, quantity, unit_cost, note, created_at) VALUES (?, ?, 'IN', ?, ?, ?, ?)",
                (toner_id, cursor.lastrowid, quantity, cost, str(data.get("note", ""))[:250], now),
            )
        return {"message": "Entrada registrada.", "quantity_added": quantity}

    def consume_stock(self, data):
        toner_id = positive_int(data.get("toner_id"), "toner_id")
        quantity = positive_int(data.get("quantity"), "quantity")
        order_value = data.get("work_order_id")
        order_id = positive_int(order_value, "work_order_id") if order_value not in (None, "") else None
        now = self._now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM toners WHERE id = ?", (toner_id,)).fetchone():
                raise AppError(404, "Toner não encontrado.")
            if order_id is not None and not db.execute("SELECT 1 FROM work_orders WHERE id = ?", (order_id,)).fetchone():
                raise AppError(404, "Ordem de serviço não encontrada.")
            lots = db.execute(
                "SELECT id, quantity_remaining, cost_per_unit FROM toner_lots WHERE toner_id = ? AND quantity_remaining > 0 ORDER BY received_at, id",
                (toner_id,),
            ).fetchall()
            available = sum(row["quantity_remaining"] for row in lots)
            if available < quantity:
                raise AppError(409, f"Estoque insuficiente: há {available} unidade(s) disponível(is).")
            remaining = quantity
            for lot in lots:
                used = min(remaining, lot["quantity_remaining"])
                if not used:
                    continue
                db.execute("UPDATE toner_lots SET quantity_remaining = quantity_remaining - ? WHERE id = ?", (used, lot["id"]))
                db.execute(
                    "INSERT INTO stock_movements(toner_id, lot_id, work_order_id, movement_type, quantity, unit_cost, note, created_at) VALUES (?, ?, ?, 'OUT', ?, ?, ?, ?)",
                    (toner_id, lot["id"], order_id, used, lot["cost_per_unit"], str(data.get("note", ""))[:250], now),
                )
                remaining -= used
                if remaining == 0:
                    break
        return {"message": "Baixa registrada seguindo FIFO.", "quantity_removed": quantity}

    def list_work_orders(self):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT w.*, c.name AS client_name, c.phone AS client_phone
                FROM work_orders w JOIN clients c ON c.id = w.client_id
                ORDER BY CASE w.status WHEN 'Aberta' THEN 0 WHEN 'Em atendimento' THEN 1 WHEN 'Aguardando peça' THEN 2 ELSE 3 END,
                         w.opened_at DESC
                """
            )
            return [dict(row) for row in rows]

    def add_work_order(self, data):
        client_id = positive_int(data.get("client_id"), "client_id")
        equipment = required_text(data.get("equipment"), "equipment")
        issue = required_text(data.get("issue"), "issue", 2000)
        priority = data.get("priority", "Normal")
        if priority not in PRIORITIES:
            raise AppError(400, "Prioridade inválida.")
        now = self._now()
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "INSERT INTO work_orders(client_id, equipment, issue, priority, status, opened_at, updated_at) VALUES (?, ?, ?, ?, 'Aberta', ?, ?)",
                    (client_id, equipment, issue, priority, now, now),
                )
                order_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise AppError(404, "Cliente não encontrado.") from None
        return next(order for order in self.list_work_orders() if order["id"] == order_id)

    def update_work_order(self, order_id, data):
        updates = {}
        if "status" in data:
            if data["status"] not in STATUSES:
                raise AppError(400, "Status inválido.")
            updates["status"] = data["status"]
        if "priority" in data:
            if data["priority"] not in PRIORITIES:
                raise AppError(400, "Prioridade inválida.")
            updates["priority"] = data["priority"]
        if "resolution" in data:
            if not isinstance(data["resolution"], str) or len(data["resolution"]) > 2000:
                raise AppError(400, "A solução deve ter até 2000 caracteres.")
            updates["resolution"] = data["resolution"].strip()
        if not updates:
            raise AppError(400, "Informe ao menos um campo para atualizar.")
        updates["updated_at"] = self._now()
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE work_orders SET " + ", ".join(f"{field} = ?" for field in updates) + " WHERE id = ?",
                (*updates.values(), order_id),
            )
            if cursor.rowcount == 0:
                raise AppError(404, "Ordem de serviço não encontrada.")
        return next(order for order in self.list_work_orders() if order["id"] == order_id)

    def dashboard(self):
        with self._connect() as db:
            open_orders = db.execute("SELECT COUNT(*) FROM work_orders WHERE status IN ('Aberta', 'Em atendimento', 'Aguardando peça')").fetchone()[0]
            active_stock = db.execute(
                "SELECT COALESCE(SUM(l.quantity_remaining), 0), COALESCE(SUM(l.quantity_remaining * l.cost_per_unit), 0) FROM toner_lots l"
            ).fetchone()
            low_stock = db.execute(
                """
                SELECT t.id, t.sku, t.name, t.min_stock, COALESCE(SUM(l.quantity_remaining), 0) AS quantity
                FROM toners t LEFT JOIN toner_lots l ON l.toner_id = t.id
                GROUP BY t.id HAVING quantity <= t.min_stock ORDER BY quantity, t.name
                """
            ).fetchall()
            monthly_usage = db.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM stock_movements WHERE movement_type = 'OUT' AND date(created_at) >= date('now', 'start of month')"
            ).fetchone()[0]
            recent = db.execute(
                """
                SELECT w.id, w.equipment, w.status, w.priority, w.opened_at, c.name AS client_name
                FROM work_orders w JOIN clients c ON c.id = w.client_id ORDER BY w.opened_at DESC LIMIT 5
                """
            ).fetchall()
        return {
            "open_work_orders": open_orders,
            "stock_units": active_stock[0],
            "inventory_value": round(active_stock[1], 2),
            "monthly_consumption": monthly_usage,
            "low_stock": [dict(row) for row in low_stock],
            "recent_work_orders": [dict(row) for row in recent],
        }

    def answer_assistant(self, question):
        question = required_text(question, "question", 1000)
        normalized = question.casefold()
        dashboard = self.dashboard()
        if re.search(r"\bos\b", normalized) or any(word in normalized for word in ("ordem", "chamado", "atendimento")):
            orders = self.list_work_orders()
            active = [order for order in orders if order["status"] in {"Aberta", "Em atendimento", "Aguardando peça"}]
            if not active:
                return {"answer": "Não há ordens de serviço em aberto no momento.", "work_orders": []}
            preview = "; ".join(f"OS #{order['id']} ({order['client_name']}) — {order['status']}" for order in active[:5])
            return {"answer": f"Há {len(active)} OS em aberto. {preview}", "work_orders": active[:5]}
        if any(word in normalized for word in ("estoque", "toner", "mínimo", "minimo", "repor")):
            low = dashboard["low_stock"]
            if not low:
                return {"answer": "Todos os toners cadastrados estão acima do estoque mínimo.", "low_stock": []}
            items = "; ".join(f"{item['name']}: {item['quantity']} unidade(s), mínimo {item['min_stock']}" for item in low)
            return {"answer": f"{len(low)} toner(s) no mínimo ou abaixo dele: {items}.", "low_stock": low}
        return {
            "answer": "Posso consultar OS em aberto e toners no mínimo. Experimente perguntar 'Quais OS estão abertas?' ou 'Qual toner preciso repor?'.",
            "work_orders_open": dashboard["open_work_orders"],
            "low_stock_count": len(dashboard["low_stock"]),
        }

    def import_csv(self, resource, csv_text):
        if resource not in {"clients", "toners"}:
            raise AppError(400, "Importação disponível somente para clientes e toners.")
        if not isinstance(csv_text, str) or len(csv_text) > 2_000_000:
            raise AppError(400, "Envie um CSV válido de até 2 MB.")
        try:
            reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
            required = {"name", "phone", "email"} if resource == "clients" else {"sku", "name", "min_stock"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise AppError(400, f"Cabeçalhos obrigatórios: {', '.join(sorted(required))}.")
            rows = list(reader)
            if not rows or len(rows) > 5000:
                raise AppError(400, "O CSV deve conter entre 1 e 5000 linhas.")
            clean_rows = []
            for line_number, row in enumerate(rows, start=2):
                if resource == "clients":
                    name = required_text(row.get("name"), f"name (linha {line_number})")
                    phone = str(row.get("phone", "")).strip()[:60]
                    email = str(row.get("email", "")).strip()[:200]
                    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                        raise AppError(400, f"E-mail inválido na linha {line_number}.")
                    clean_rows.append((name, phone, email, self._now()))
                else:
                    sku = required_text(row.get("sku"), f"sku (linha {line_number})", 80)
                    name = required_text(row.get("name"), f"name (linha {line_number})")
                    try:
                        min_stock = nonnegative_int(row.get("min_stock", "0"), "min_stock")
                    except AppError:
                        raise AppError(400, f"Estoque mínimo inválido na linha {line_number}.") from None
                    clean_rows.append((sku, name, min_stock, self._now()))
        except csv.Error as error:
            raise AppError(400, f"CSV inválido: {error}") from None
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                if resource == "clients":
                    db.executemany("INSERT INTO clients(name, phone, email, created_at) VALUES (?, ?, ?, ?)", clean_rows)
                else:
                    db.executemany("INSERT INTO toners(sku, name, min_stock, created_at) VALUES (?, ?, ?, ?)", clean_rows)
        except sqlite3.IntegrityError:
            raise AppError(409, "Importação cancelada: há registro duplicado (por exemplo, um SKU já cadastrado).") from None
        return {"imported": len(clean_rows)}

    def export_csv(self, resource):
        queries = {
            "clients": ("SELECT id, name, phone, email, created_at FROM clients ORDER BY id", ("id", "name", "phone", "email", "created_at")),
            "toners": ("SELECT id, sku, name, min_stock, created_at FROM toners ORDER BY id", ("id", "sku", "name", "min_stock", "created_at")),
            "work-orders": ("SELECT w.id, c.name AS client, w.equipment, w.issue, w.priority, w.status, w.resolution, w.opened_at FROM work_orders w JOIN clients c ON c.id = w.client_id ORDER BY w.id", ("id", "client", "equipment", "issue", "priority", "status", "resolution", "opened_at")),
            "stock": ("SELECT t.sku, t.name, COALESCE(SUM(l.quantity_remaining), 0) AS quantity, t.min_stock FROM toners t LEFT JOIN toner_lots l ON l.toner_id = t.id GROUP BY t.id ORDER BY t.name", ("sku", "name", "quantity", "min_stock")),
        }
        if resource not in queries:
            raise AppError(404, "Recurso de exportação inválido.")
        query, headers = queries[resource]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        with self._connect() as db:
            writer.writerows(tuple(self._safe_csv_value(value) for value in row) for row in db.execute(query))
        return output.getvalue()

    @staticmethod
    def _safe_csv_value(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value


class RequestHandler(BaseHTTPRequestHandler):
    service = None

    def log_message(self, format_string, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format_string % args}")

    def _send(self, status, body, content_type="application/json; charset=utf-8", extra_headers=None):
        encoded = body.encode("utf-8") if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise AppError(400, "Cabeçalho Content-Length inválido.") from None
        if length <= 0 or length > 2_000_000:
            raise AppError(400, "O corpo da requisição deve ter entre 1 byte e 2 MB.")
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError(400, "Envie um JSON válido.") from None
        if not isinstance(body, dict):
            raise AppError(400, "O corpo JSON deve ser um objeto.")
        return body

    def _handle(self, action):
        try:
            action()
        except AppError as error:
            self._send(error.status, {"error": str(error)})
        except sqlite3.Error:
            self._send(500, {"error": "Erro interno ao acessar o banco de dados."})
        except Exception:
            self._send(500, {"error": "Erro interno do servidor."})

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            self._static("index.html", "text/html; charset=utf-8")
            return
        if path in {"/styles.css", "/app.js"}:
            filename = path.lstrip("/")
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "text/javascript; charset=utf-8"
            self._static(filename, content_type)
            return

        def action():
            if path == "/api/health":
                self._send(200, {"status": "ok"})
            elif path == "/api/dashboard":
                self._send(200, self.service.dashboard())
            elif path == "/api/clients":
                self._send(200, self.service.list_clients())
            elif path == "/api/toners":
                self._send(200, self.service.list_toners())
            elif path == "/api/work-orders":
                self._send(200, self.service.list_work_orders())
            elif path.startswith("/api/export/"):
                resource = path.removeprefix("/api/export/")
                content = self.service.export_csv(resource)
                self._send(200, content, "text/csv; charset=utf-8", {"Content-Disposition": f'attachment; filename="{resource}.csv"'})
            else:
                raise AppError(404, "Rota não encontrada.")

        self._handle(action)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)

        def action():
            data = self._read_json()
            if path == "/api/clients":
                self._send(201, self.service.add_client(data))
            elif path == "/api/toners":
                self._send(201, self.service.add_toner(data))
            elif path == "/api/stock/receipts":
                self._send(201, self.service.receive_stock(data))
            elif path == "/api/stock/consume":
                self._send(201, self.service.consume_stock(data))
            elif path == "/api/work-orders":
                self._send(201, self.service.add_work_order(data))
            elif path == "/api/assistant":
                self._send(200, self.service.answer_assistant(data.get("question")))
            elif path.startswith("/api/import/"):
                resource = path.removeprefix("/api/import/")
                self._send(201, self.service.import_csv(resource, data.get("csv")))
            else:
                raise AppError(404, "Rota não encontrada.")

        self._handle(action)

    def do_PATCH(self):
        path = unquote(urlparse(self.path).path)

        def action():
            match = re.fullmatch(r"/api/work-orders/(\d+)", path)
            if not match:
                raise AppError(404, "Rota não encontrada.")
            self._send(200, self.service.update_work_order(int(match.group(1)), self._read_json()))

        self._handle(action)

    def _static(self, filename, content_type):
        try:
            content = (STATIC_DIR / filename).read_text(encoding="utf-8")
        except OSError:
            self._send(404, "Arquivo não encontrado.", "text/plain; charset=utf-8")
            return
        self._send(200, content, content_type)


def make_handler(service):
    return type("BoundRequestHandler", (RequestHandler,), {"service": service})