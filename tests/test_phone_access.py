from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from phone_access import InfraiClient, InfraiError, PhoneAccessService, PhoneCodeVerification


def test_sms_otp_uses_required_to_field():
    class RecordingClient(InfraiClient):
        def request(self, method, path, payload):
            assert (method, path, payload) == ("POST", "/v1/sms/otp", {"to": "+15550100"})
            return {}

    RecordingClient("test-key").send_sms_otp("+15550100")


class VerifiedPhoneClient:
    def verify_phone(self, command):
        return {"user_id": "creator-47"}

    def create_session(self, command):
        assert command.user_id == "creator-47"
        return {"session_id": "session-9"}


class UnresolvedPhoneClient:
    def verify_phone(self, command):
        return {}

    def create_session(self, command):
        raise AssertionError("a session must not be created for an unresolved phone")


def test_verified_phone_creates_creator_session():
    service = PhoneAccessService(VerifiedPhoneClient())
    session = service.finish_login(PhoneCodeVerification(phone="+15550100", code="123456"))
    assert session == {"session_id": "session-9"}


def test_unresolved_phone_does_not_create_session():
    service = PhoneAccessService(UnresolvedPhoneClient())
    try:
        service.finish_login(PhoneCodeVerification(phone="+15550100", code="123456"))
    except InfraiError as error:
        assert error.code == "IDENTITY_NOT_RESOLVED"
    else:
        raise AssertionError("an unresolved identity must be rejected")
