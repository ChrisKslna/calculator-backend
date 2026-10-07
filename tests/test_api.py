"""Check the HTTP contract independently of the future browser interface."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import sqlite3

from src.app import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = str(Path(self.directory.name) / "test.db")
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_calculation_response(self):
        response = self.client.post(
            "/api/calculate", json={"expression": " (1+2)*3 "}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["expression"], "(1+2)*3")
        self.assertEqual(data["result"], "9")
        self.assertIsInstance(data["id"], int)
        self.assertIn("+00:00", data["created_at"])

    def test_backend_ignores_a_client_supplied_result(self):
        response = self.client.post(
            "/api/calculate", json={"expression": "2+3", "result": "999"}
        )
        self.assertEqual(response.get_json()["result"], "5")

    def test_decimal_result_remains_a_string(self):
        response = self.client.post(
            "/api/calculate", json={"expression": "0.1+0.2"}
        )
        self.assertEqual(response.get_json()["result"], "0.3")

    def test_division_by_zero_returns_a_client_error(self):
        response = self.client.post(
            "/api/calculate", json={"expression": "1/0"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
        self.assertEqual(response.get_json()["code"], "DIVISION_BY_ZERO")
        self.assertEqual(response.get_json()["position"], 2)

    def test_invalid_expression_returns_a_client_error(self):
        response = self.client.post(
            "/api/calculate", json={"expression": "2**3"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "INVALID_EXPRESSION")

    def test_invalid_expression_types(self):
        for value in (None, 123, True, [], {}):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/calculate", json={"expression": value}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["code"], "INVALID_INPUT")

    def test_missing_expression(self):
        response = self.client.post("/api/calculate", json={"result": 4})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    def test_json_body_must_be_an_object(self):
        for body in ("null", "[]", '"1+2"', "42"):
            with self.subTest(body=body):
                response = self.client.post(
                    "/api/calculate", data=body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["code"], "INVALID_INPUT")

    def test_malformed_json(self):
        response = self.client.post(
            "/api/calculate", data='{"expression":',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    def test_content_type_is_required(self):
        response = self.client.post("/api/calculate", data="1+2")
        self.assertEqual(response.status_code, 415)
        self.assertFalse(response.get_json()["success"])

    def test_oversized_request(self):
        response = self.client.post(
            "/api/calculate", json={"expression": "1" * 17000}
        )
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.get_json()["success"])

    def test_get_does_not_perform_calculation(self):
        response = self.client.get("/api/calculate")
        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response.headers["Allow"])
        self.assertFalse(response.get_json()["success"])

    def test_unknown_route_is_json(self):
        response = self.client.get("/api/missing")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.get_json()["success"])

    def test_history_is_persistent_across_new_app_instances(self):
        record = self.client.post(
            "/api/calculate", json={"expression": "5*8"}
        ).get_json()
        second_app = create_app({"TESTING": True, "DATABASE": self.db_path})
        history = second_app.test_client().get("/api/history").get_json()
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["id"], record["id"])
        self.assertEqual(history["items"][0]["result"], "40")

    def test_delete_removes_only_the_chosen_record_from_database(self):
        first = self.client.post(
            "/api/calculate", json={"expression": "2+3"}
        ).get_json()
        second = self.client.post(
            "/api/calculate", json={"expression": "6*7"}
        ).get_json()
        response = self.client.delete(f'/api/history/{first["id"]}')
        self.assertEqual(response.status_code, 200)
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT id FROM calculation_history"
            ).fetchall()
        connection.close()
        self.assertEqual(rows, [(second["id"],)])
        self.assertEqual(
            self.client.delete(f'/api/history/{first["id"]}').status_code, 404
        )

    def test_failed_calculations_are_not_saved(self):
        for expression in ("1/0", "1+", "abc"):
            self.client.post("/api/calculate", json={"expression": expression})
        self.assertEqual(self.client.get("/api/history").get_json()["total"], 0)

    def test_pagination_and_newest_first(self):
        for number in range(12):
            self.client.post(
                "/api/calculate", json={"expression": f"{number}+1"}
            )
        first = self.client.get("/api/history?page=1&page_size=8").get_json()
        second = self.client.get("/api/history?page=2&page_size=8").get_json()
        self.assertEqual((first["total"], first["pages"]), (12, 2))
        self.assertEqual(len(first["items"]), 8)
        self.assertEqual(first["items"][0]["expression"], "11+1")
        self.assertEqual(len(second["items"]), 4)

    def test_invalid_pagination(self):
        for query in ("page=0", "page=-1", "page=x", "page_size=101"):
            response = self.client.get(f"/api/history?{query}")
            self.assertEqual(response.status_code, 400)

    def test_empty_history_and_page_after_deletion(self):
        data = self.client.get("/api/history?page=9").get_json()
        self.assertEqual((data["page"], data["pages"], data["items"]), (1, 1, []))

    def test_separate_database_paths_do_not_share_history(self):
        self.client.post("/api/calculate", json={"expression": "1+2"})
        other_path = str(Path(self.directory.name) / "other.db")
        other_app = create_app({"TESTING": True, "DATABASE": other_path})
        other_history = other_app.test_client().get("/api/history").get_json()
        self.assertEqual(other_history["total"], 0)

    def test_persistence_failure_does_not_report_calculation_success(self):
        with patch("src.database.save_calculation", side_effect=sqlite3.Error):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.client.post(
                    "/api/calculate", json={"expression": "1+2"}
                )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
