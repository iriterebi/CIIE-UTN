import uuid
import pytest

from src.robot.utils.crockford_base32 import uuid_to_crockford_base32, _CROCKFORD_ALPHABET


class TestUuidToCrockfordBase32:
    def test_uuid_cero(self):
        zero_uuid = uuid.UUID(int=0)
        assert uuid_to_crockford_base32(zero_uuid) == '0'

    def test_resultado_solo_usa_caracteres_del_alfabeto(self):
        test_uuid = uuid.uuid4()
        result = uuid_to_crockford_base32(test_uuid)
        for char in result:
            assert char in _CROCKFORD_ALPHABET

    def test_no_contiene_caracteres_excluidos(self):
        """Crockford Base32 excluye I, L, O, U."""
        for _ in range(20):
            result = uuid_to_crockford_base32(uuid.uuid4())
            for excluded in ['I', 'L', 'O', 'U']:
                assert excluded not in result

    def test_acepta_string(self):
        test_uuid = uuid.uuid4()
        result_str = uuid_to_crockford_base32(str(test_uuid))
        result_uuid = uuid_to_crockford_base32(test_uuid)
        assert result_str == result_uuid

    def test_determinista(self):
        test_uuid = uuid.uuid4()
        assert uuid_to_crockford_base32(test_uuid) == uuid_to_crockford_base32(test_uuid)

    def test_uuids_distintos_dan_resultados_distintos(self):
        uuid1 = uuid.uuid4()
        uuid2 = uuid.uuid4()
        assert uuid_to_crockford_base32(uuid1) != uuid_to_crockford_base32(uuid2)

    def test_uuid_conocido(self):
        # Verificar que un UUID conocido produce un resultado consistente
        known_uuid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        result = uuid_to_crockford_base32(known_uuid)
        assert isinstance(result, str)
        assert len(result) > 0
        # Ejecutar dos veces para confirmar determinismo
        assert result == uuid_to_crockford_base32(known_uuid)

    def test_string_invalido_lanza_error(self):
        with pytest.raises(ValueError):
            uuid_to_crockford_base32("no-es-un-uuid")
