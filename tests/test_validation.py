"""Tests de validation.py: reglas de un control válido. No usan AWS ni HTTP."""

import sys
import unittest
from pathlib import Path

# Los módulos de la Lambda viven en backend/ y se importan sin paquete (como en el zip)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from validation import validate_control_id, validate_fields  # noqa: E402


def valid_body(**overrides):
    """Body mínimo válido para un POST; cada test cambia solo lo que le interesa."""
    body = {
        "code": "S3-001",
        "title": "S3 Block Public Access",
        "service": "S3",
        "category": "Data protection",
        "severity": "HIGH",
    }
    body.update(overrides)
    return body


class ValidateFieldsCreateTests(unittest.TestCase):
    """Modo POST (partial=False): obligatorios, defaults y todas las reglas."""

    def test_body_valido_aplica_default_de_status(self):
        cleaned, err = validate_fields(valid_body())
        self.assertIsNone(err)
        self.assertEqual(cleaned["status"], "REVIEW")

    def test_opcionales_ausentes_quedan_en_none(self):
        cleaned, _ = validate_fields(valid_body())
        self.assertIsNone(cleaned["description"])
        self.assertIsNone(cleaned["remediation"])

    def test_hace_strip_de_los_textos(self):
        cleaned, err = validate_fields(valid_body(code="  S3-001  "))
        self.assertIsNone(err)
        self.assertEqual(cleaned["code"], "S3-001")

    def test_falta_un_obligatorio(self):
        body = valid_body()
        del body["title"]
        cleaned, err = validate_fields(body)
        self.assertIsNone(cleaned)
        self.assertIn("'title'", err)

    def test_obligatorio_vacio_o_solo_espacios(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                _, err = validate_fields(valid_body(title=value))
                self.assertIsNotNone(err, "el POST aceptó un obligatorio vacío")
                self.assertIn("no puede estar vacío", err)

    def test_tipo_distinto_de_texto(self):
        for value in (123, ["HIGH"], {"a": 1}, True):
            with self.subTest(value=value):
                _, err = validate_fields(valid_body(severity=value))
                self.assertIn("debe ser un texto", err)

    def test_supera_el_largo_maximo(self):
        _, err = validate_fields(valid_body(code="X" * 21))
        self.assertIn("20 caracteres", err)

    def test_largo_maximo_exacto_es_valido(self):
        _, err = validate_fields(valid_body(code="X" * 20))
        self.assertIsNone(err)

    def test_enum_invalido(self):
        _, err = validate_fields(valid_body(severity="URGENTE"))
        self.assertIn("'severity' debe ser uno de", err)

    def test_enum_en_minusculas_se_rechaza(self):
        # Comportamiento actual (pregunta abierta en DECISIONS.md): no se normaliza con .upper()
        _, err = validate_fields(valid_body(severity="high"))
        self.assertIsNotNone(err)

    def test_allowlist_ignora_campos_desconocidos(self):
        cleaned, err = validate_fields(valid_body(id="hack", admin=True, created_at="2020-01-01"))
        self.assertIsNone(err)
        for field in ("id", "admin", "created_at"):
            self.assertNotIn(field, cleaned)


class ValidateFieldsPartialTests(unittest.TestCase):
    """Modo PATCH (partial=True): nada es obligatorio, sin defaults, solo lo que vino."""

    def test_devuelve_solo_los_campos_presentes(self):
        cleaned, err = validate_fields({"status": "FAIL"}, partial=True)
        self.assertIsNone(err)
        self.assertEqual(cleaned, {"status": "FAIL"})

    def test_no_aplica_el_default_de_status(self):
        cleaned, _ = validate_fields({"title": "Nuevo"}, partial=True)
        self.assertNotIn("status", cleaned)

    def test_body_vacio_no_tiene_campos_validos(self):
        _, err = validate_fields({}, partial=True)
        self.assertEqual(err, "No hay campos válidos para actualizar.")

    def test_solo_campos_desconocidos_no_tiene_campos_validos(self):
        for body in ({"admin": True}, {"created_at": "2020-01-01T00:00:00Z"}):
            with self.subTest(body=body):
                _, err = validate_fields(body, partial=True)
                self.assertEqual(err, "No hay campos válidos para actualizar.")

    def test_obligatorio_vacio_se_rechaza_tambien_en_patch(self):
        # Regresión del bug de la Etapa 6: el PATCH aceptaba {"title": ""}
        for value in ("", "   "):
            with self.subTest(value=value):
                _, err = validate_fields({"title": value}, partial=True)
                self.assertIsNotNone(err, "el PATCH aceptó un obligatorio vacío")
                self.assertIn("no puede estar vacío", err)

    def test_las_reglas_de_tipo_y_enum_siguen_aplicando(self):
        _, err = validate_fields({"severity": "URGENTE"}, partial=True)
        self.assertIn("debe ser uno de", err)


class CheckIdTests(unittest.TestCase):
    """check_id: solo checks que existen, o "" para un control manual (D92)."""

    def test_check_existente_es_valido(self):
        cleaned, err = validate_fields(valid_body(check_id="s3-account-public-access-block"))
        self.assertIsNone(err)
        self.assertEqual(cleaned["check_id"], "s3-account-public-access-block")

    def test_vacio_es_valido_y_significa_manual(self):
        cleaned, err = validate_fields({"check_id": ""}, partial=True)
        self.assertIsNone(err)
        self.assertEqual(cleaned, {"check_id": ""})

    def test_check_inexistente_se_rechaza_y_lista_los_validos(self):
        _, err = validate_fields(valid_body(check_id="s3-no-existe"))
        self.assertIn("check_id", err)
        self.assertIn("s3-account-public-access-block", err)
        self.assertIn('""', err)

    def test_ausente_queda_en_none(self):
        cleaned, _ = validate_fields(valid_body())
        self.assertIsNone(cleaned["check_id"])


class ValidateControlIdTests(unittest.TestCase):

    CANONICAL = "65f38383-241b-4e7b-aa38-72fc7d9edb6a"

    def test_uuid_canonico_es_valido(self):
        control_id, err = validate_control_id(self.CANONICAL)
        self.assertIsNone(err)
        self.assertEqual(control_id, self.CANONICAL)

    def test_normaliza_mayusculas_y_sin_guiones(self):
        for raw in (self.CANONICAL.upper(), self.CANONICAL.replace("-", "")):
            with self.subTest(raw=raw):
                control_id, err = validate_control_id(raw)
                self.assertIsNone(err)
                self.assertEqual(control_id, self.CANONICAL)

    def test_id_invalido(self):
        _, err = validate_control_id("abc")
        self.assertIn("UUID válido", err)

    def test_id_ausente(self):
        for raw in (None, ""):
            with self.subTest(raw=raw):
                _, err = validate_control_id(raw)
                self.assertIn("requerido", err)


if __name__ == "__main__":
    unittest.main()
