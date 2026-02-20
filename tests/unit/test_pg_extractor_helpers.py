"""Unit tests for pg_reference_extractor helper functions.

Tests SSH key loading, GCS upload, secret retrieval, and retry logic.
All external dependencies are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestLoadSshKey:
    def test_loads_rsa_key(self):
        import paramiko

        from cloud_functions.pg_reference_extractor.main import load_ssh_key

        mock_key = MagicMock()
        with (
            patch(
                "cloud_functions.pg_reference_extractor.main.paramiko.Ed25519Key.from_private_key",
                side_effect=paramiko.SSHException,
            ),
            patch(
                "cloud_functions.pg_reference_extractor.main.paramiko.RSAKey.from_private_key",
                return_value=mock_key,
            ),
        ):
            result = load_ssh_key(
                "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
            )
            assert result is mock_key

    def test_loads_ed25519_key(self):
        from cloud_functions.pg_reference_extractor.main import load_ssh_key

        mock_key = MagicMock()
        with patch(
            "cloud_functions.pg_reference_extractor.main.paramiko.Ed25519Key.from_private_key",
            return_value=mock_key,
        ):
            result = load_ssh_key(
                "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
            )
            assert result is mock_key

    def test_unsupported_key_raises(self):
        import paramiko

        from cloud_functions.pg_reference_extractor.main import load_ssh_key

        with (
            patch(
                "cloud_functions.pg_reference_extractor.main.paramiko.Ed25519Key.from_private_key",
                side_effect=paramiko.SSHException,
            ),
            patch(
                "cloud_functions.pg_reference_extractor.main.paramiko.RSAKey.from_private_key",
                side_effect=paramiko.SSHException,
            ),
            patch(
                "cloud_functions.pg_reference_extractor.main.paramiko.ECDSAKey.from_private_key",
                side_effect=paramiko.SSHException,
            ),
            pytest.raises(ValueError, match="Unsupported SSH key type"),
        ):
            load_ssh_key("bad-key")


class TestUploadToGcs:
    def test_uploads_csv_with_correct_path(self):
        from cloud_functions.pg_reference_extractor.main import upload_to_gcs

        bucket = MagicMock()
        blob = MagicMock()
        bucket.blob.return_value = blob

        upload_to_gcs(bucket, "header\ndata\n", "produto.csv")

        bucket.blob.assert_called_once_with("raw/reference_data/produto.csv")
        blob.upload_from_string.assert_called_once_with(
            "header\ndata\n", content_type="text/csv; charset=utf-8"
        )


class TestCheckExistingFile:
    def test_returns_true_when_exists(self):
        from cloud_functions.pg_reference_extractor.main import check_existing_file

        bucket = MagicMock()
        blob = MagicMock()
        blob.exists.return_value = True
        bucket.blob.return_value = blob

        assert check_existing_file(bucket, "produto.csv") is True

    def test_returns_false_when_not_exists(self):
        from cloud_functions.pg_reference_extractor.main import check_existing_file

        bucket = MagicMock()
        blob = MagicMock()
        blob.exists.return_value = False
        bucket.blob.return_value = blob

        assert check_existing_file(bucket, "produto.csv") is False


class TestGetSecret:
    @patch("cloud_functions.pg_reference_extractor.main.PROJECT_ID", "test-project")
    def test_returns_decoded_secret(self):
        from cloud_functions.pg_reference_extractor.main import get_secret

        client = MagicMock()
        response = MagicMock()
        response.payload.data = b"secret-value"
        client.access_secret_version.return_value = response

        result = get_secret(client, "my-secret")

        assert result == "secret-value"
        client.access_secret_version.assert_called_once_with(
            request={"name": "projects/test-project/secrets/my-secret/versions/latest"}
        )


class TestGetAllSecrets:
    @patch("cloud_functions.pg_reference_extractor.main.get_secret")
    def test_returns_all_six_secrets(self, mock_get):
        from cloud_functions.pg_reference_extractor.main import get_all_secrets

        mock_get.side_effect = lambda c, s: f"val-{s}"
        client = MagicMock()

        result = get_all_secrets(client)

        assert result["ssh_host"] == "val-pg-host"
        assert result["ssh_user"] == "val-pg-ssh-user"
        assert result["ssh_key"] == "val-pg-ssh-private-key"
        assert result["pg_db"] == "val-pg-db-name"
        assert result["pg_user"] == "val-pg-db-user"
        assert result["pg_pass"] == "val-pg-db-password"
        assert mock_get.call_count == 6


class TestExtractReferenceData:
    @patch("cloud_functions.pg_reference_extractor.main.extract_with_retry")
    @patch("cloud_functions.pg_reference_extractor.main.get_all_secrets")
    @patch("cloud_functions.pg_reference_extractor.main.secretmanager.SecretManagerServiceClient")
    def test_returns_200_on_success(self, mock_sm_cls, mock_secrets, mock_extract):
        from cloud_functions.pg_reference_extractor.main import extract_reference_data

        mock_secrets.return_value = {}
        mock_extract.return_value = {
            "produto": {"status": "success", "rows": 30},
            "unidade": {"status": "success", "rows": 50},
        }

        body, status = extract_reference_data(MagicMock())

        assert status == 200
        assert '"success"' in body

    @patch("cloud_functions.pg_reference_extractor.main.get_all_secrets")
    @patch("cloud_functions.pg_reference_extractor.main.secretmanager.SecretManagerServiceClient")
    def test_returns_500_on_error(self, mock_sm_cls, mock_secrets):
        from cloud_functions.pg_reference_extractor.main import extract_reference_data

        mock_secrets.side_effect = Exception("Secret Manager unavailable")

        body, status = extract_reference_data(MagicMock())

        assert status == 500
        assert "Internal processing error" in body
