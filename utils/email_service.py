"""Servicio de envío de correos usando Gmail SMTP."""
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv(override=False)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class EmailService:
    """Servicio para enviar correos electrónicos vía Gmail SMTP."""

    def __init__(self):
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

    def _connect(self) -> smtplib.SMTP_SSL:
        return smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        html_body: str,
    ) -> bool:
        """Enviar email HTML a uno o varios destinatarios.

        Args:
            to: Email destinatario o lista de destinatarios.
            subject: Asunto del correo.
            html_body: Contenido HTML del mensaje.

        Returns:
            True si el envío fue exitoso, False en caso contrario.
        """
        if not self.gmail_user or not self.gmail_app_password:
            print("⚠️ GMAIL_USER o GMAIL_APP_PASSWORD no configuradas.")
            return False

        recipients = [to] if isinstance(to, str) else to
        if not recipients:
            print("⚠️ No se proporcionaron destinatarios.")
            return False

        msg = EmailMessage()
        msg["From"] = self.gmail_user
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.add_alternative(html_body, subtype="html")

        try:
            with self._connect() as server:
                server.login(self.gmail_user, self.gmail_app_password)
                server.send_message(msg)
            print(f"✅ Correo enviado exitosamente a {', '.join(recipients)}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Error de autenticación SMTP: {e}")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ Error SMTP: {e}")
            return False
        except Exception as e:
            print(f"❌ Error inesperado al enviar correo: {e}")
            return False

    def send_temp_password(self, email: str, temp_password: str, nombre: str) -> bool:
        """Enviar correo con contraseña temporal."""
        html_body = f"""\
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #2563eb;">Hola {nombre},</h2>
    <p>Hemos recibido una solicitud para restablecer tu contraseña en AsisteGO.</p>
    <p>Tu contraseña temporal es:</p>
    <div style="background-color: #f3f4f6; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 2px; margin: 20px 0;">
        {temp_password}
    </div>
    <p>Esta contraseña expirará en 24 horas.</p>
    <p>Puedes usar esta contraseña para iniciar sesión y luego cambiarla por una nueva cuando lo desees.</p>
    <p style="color: #6b7280; font-size: 14px;">Si no solicitaste este cambio, ignora este correo.</p>
    <hr style="margin: 20px 0; border: none; border-top: 1px solid #e5e7eb;">
    <p style="color: #6b7280; font-size: 12px;">AsisteGO - Sistema de gestión para talleres mecánicos</p>
</div>
"""
        return self.send_email(
            to=email,
            subject="Tu contraseña temporal de AsisteGO",
            html_body=html_body,
        )


email_service = EmailService()
