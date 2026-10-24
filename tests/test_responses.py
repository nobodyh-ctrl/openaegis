"""Tests de responses.py: formato de entrada y salida de API Gateway (payload 2.0)."""

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from responses import build_response, error_response, parse_json_body, user_sub  # noqa: E402


class BuildResponseTests(unittest.TestCase):

    def test_formato_de_api_gateway(self):
        response = build_response(200, {"ok": True})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"], {"Content-Type": "application/json"})
        self.assertIsInstance(response["body"], str)  # API Gateway espera el body como string
        self.assertEqual(json.loads(response["body"]), {"ok": True})

    def test_decimal_entero_se_serializa_como_int(self):
        # boto3.resource devuelve los números de DynamoDB como Decimal
        body = json.loads(build_response(200, {"n": Decimal("3")})["body"])
        self.assertEqual(body["n"], 3)
        self.assertIsInstance(body["n"], int)

    def test_decimal_con_decimales_se_serializa_como_float(self):
        body = json.loads(build_response(200, {"n": Decimal("2.5")})["body"])
        self.assertEqual(body["n"], 2.5)

    def test_tipo_no_serializable_falla(self):
        with self.assertRaises(TypeError):
            build_response(200, {"x": object()})

    def test_error_response(self):
        response = error_response(404, "Control no encontrado.")
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"]), {"error": "Control no encontrado."})


class ParseJsonBodyTests(unittest.TestCase):

    def assert_400(self, event, expected_message):
        body, err_response = parse_json_body(event)
        self.assertIsNone(body)
        self.assertEqual(err_response["statusCode"], 400)
        self.assertEqual(json.loads(err_response["body"])["error"], expected_message)

    def test_body_ausente_o_vacio(self):
        for event in ({}, {"body": None}, {"body": ""}):
            with self.subTest(event=event):
                self.assert_400(event, "El cuerpo de la solicitud está vacío.")

    def test_json_invalido(self):
        for raw in ("hola", '{"name" = "x"}'):
            with self.subTest(raw=raw):
                self.assert_400({"body": raw}, "JSON inválido.")

    def test_json_valido_que_no_es_objeto(self):
        # Regresión de la Etapa 5: [] provocaba un AttributeError y un 500
        for raw in ("[]", "123", '"hola"'):
            with self.subTest(raw=raw):
                self.assert_400({"body": raw}, "El body debe ser un objeto JSON.")

    def test_objeto_valido(self):
        body, err_response = parse_json_body({"body": '{"status": "FAIL"}'})
        self.assertIsNone(err_response)
        self.assertEqual(body, {"status": "FAIL"})



class UserSubTests(unittest.TestCase):

    def test_devuelve_el_sub_del_authorizer(self):
        event = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "abc-123"}}}}}
        self.assertEqual(user_sub(event), "abc-123")

    def test_sin_authorizer_devuelve_none(self):
        # Por ejemplo, una prueba desde la consola de Lambda: el evento no trae claims
        self.assertIsNone(user_sub({}))
        self.assertIsNone(user_sub({"requestContext": {"requestId": "x"}}))


if __name__ == "__main__":
    unittest.main()
