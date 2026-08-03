"""
Backend de e-mail Django que envia mensagens através da Microsoft Graph API,
usando um App Registration do Azure AD (fluxo OAuth2 client-credentials).

Ativado quando EMAIL_SEND_METHOD=graph no .env (ver fidc_gestao/settings.py).
Requer no .env: DEFAULT_FROM_EMAIL, AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET.
"""
import logging

import msal
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


class GraphEmailBackend(BaseEmailBackend):
    """
    Envia django.core.mail.EmailMessage (e EmailMultiAlternatives, usando a
    primeira alternativa text/html se houver) via Microsoft Graph API.
    """

    def _get_access_token(self):
        app = msal.ConfidentialClientApplication(
            client_id=settings.AZURE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}",
            client_credential=settings.AZURE_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                "Falha ao obter token do Azure AD para envio de e-mail via Graph: "
                f"{result.get('error')}: {result.get('error_description')}"
            )
        return result["access_token"]

    def _build_payload(self, message):
        content_type = "Text"
        body = message.body

        # EmailMultiAlternatives pode trazer uma versão HTML como alternativa
        alternatives = getattr(message, "alternatives", None) or []
        for alt_body, alt_mimetype in alternatives:
            if alt_mimetype == "text/html":
                body = alt_body
                content_type = "HTML"
                break

        return {
            "message": {
                "subject": message.subject,
                "body": {"contentType": content_type, "content": body},
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in message.to
                ],
                "ccRecipients": [
                    {"emailAddress": {"address": addr}} for addr in message.cc
                ],
                "bccRecipients": [
                    {"emailAddress": {"address": addr}} for addr in message.bcc
                ],
            },
            "saveToSentItems": "false",
        }

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            access_token = self._get_access_token()
        except Exception:
            logger.exception("Não foi possível autenticar no Microsoft Graph.")
            if self.fail_silently:
                return 0
            raise

        sender = settings.DEFAULT_FROM_EMAIL
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = GRAPH_SEND_MAIL_URL.format(sender=sender)

        sent_count = 0
        for message in email_messages:
            payload = self._build_payload(message)
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status()
                sent_count += 1
            except requests.RequestException:
                logger.exception(
                    "Falha ao enviar e-mail via Microsoft Graph para %s.", message.to
                )
                if not self.fail_silently:
                    raise

        return sent_count
