import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import AppError, Service, make_handler


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = Service(Path(self.temp_dir.name) / "test.sqlite3")
        self.service.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_toner(self):
        return self.service.add_toner({"sku": "TN-1060", "name": "Toner preto", "min_stock": 1})

    def test_consumption_uses_oldest_lot_first_and_records_each_cost(self):
        toner = self.create_toner()
        self.service.receive_stock({"toner_id": toner["id"], "quantity": 5, "cost_per_unit": 10, "received_at": "2025-01-01"})
        self.service.receive_stock({"toner_id": toner["id"], "quantity": 5, "cost_per_unit": 15, "received_at": "2025-01-02"})

        self.service.consume_stock({"toner_id": toner["id"], "quantity": 6})

        stock = self.service.list_toners()[0]
        self.assertEqual(stock["quantity"], 4)
        with self.service._connect() as db:
            movements = db.execute(
                "SELECT quantity, unit_cost FROM stock_movements WHERE movement_type = 'OUT' ORDER BY id"
            ).fetchall()
        self.assertEqual([(row["quantity"], row["unit_cost"]) for row in movements], [(5, 10.0), (1, 15.0)])

    def test_insufficient_stock_does_not_partially_decrement_lots(self):
        toner = self.create_toner()
        self.service.receive_stock({"toner_id": toner["id"], "quantity": 3, "cost_per_unit": 8, "received_at": "2025-01-01"})

        with self.assertRaises(AppError) as error:
            self.service.consume_stock({"toner_id": toner["id"], "quantity": 4})

        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.service.list_toners()[0]["quantity"], 3)
        with self.service._connect() as db:
            outgoing = db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type = 'OUT'").fetchone()[0]
        self.assertEqual(outgoing, 0)

    def test_duplicate_csv_import_rolls_back_all_rows(self):
        self.create_toner()
        csv_text = "sku,name,min_stock\nNEW-1,Toner novo,2\nTN-1060,Duplicado,1\n"

        with self.assertRaises(AppError) as error:
            self.service.import_csv("toners", csv_text)

        self.assertEqual(error.exception.status, 409)
        self.assertEqual(len(self.service.list_toners()), 1)

    def test_assistant_reports_open_work_orders(self):
        client = self.service.add_client({"name": "Cliente Exemplo", "phone": "11999990000"})
        order = self.service.add_work_order({
            "client_id": client["id"],
            "equipment": "Impressora de teste",
            "issue": "Não imprime",
        })

        answer = self.service.answer_assistant("Quais OS estão abertas?")

        self.assertIn(f"OS #{order['id']}", answer["answer"])
        self.assertEqual(answer["work_orders"][0]["status"], "Aberta")

    def test_assistant_does_not_confuse_temos_with_work_order_keyword(self):
        self.create_toner()

        answer = self.service.answer_assistant("Quais toners temos?")

        self.assertIn("1 toner(s)", answer["answer"])

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        self.service.add_client({"name": "=1+1", "email": "teste@example.com"})

        exported = self.service.export_csv("clients")

        self.assertIn("'=1+1", exported)

    def test_http_server_serves_health_and_web_interface(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.service))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            connection.request("GET", "/api/health")
            health = connection.getresponse()
            self.assertEqual(health.status, 200)
            self.assertEqual(health.read(), b'{"status": "ok"}')

            connection.request("GET", "/")
            page = connection.getresponse()
            self.assertEqual(page.status, 200)
            self.assertIn("<html lang=\"pt-BR\">".encode(), page.read())

            for path, marker in (("/styles.css", b".app-shell"), ("/app.js", b"function refresh()")):
                connection.request("GET", path)
                asset = connection.getresponse()
                self.assertEqual(asset.status, 200)
                self.assertIn(marker, asset.read())
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()