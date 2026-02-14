"""Alertes email pour Calv-a-lot.

Envoie des notifications par email (SMTP OVH) pour les événements critiques :
- Agent passé en status DEAD
- Pas de signal reçu depuis 2 heures (Cash-a-lot down?)
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import Settings

logger = logging.getLogger("calvalot.notifier")

# Flag pour ne pas spammer (1 alerte par événement)
_alert_sent = {"agent_dead": False, "no_signal": False}


def _can_send():
    """Vérifie que la config SMTP est présente."""
    return all([Settings.SMTP_USER, Settings.SMTP_PASSWORD, Settings.ALERT_EMAIL_TO])


def _send_email(subject, html_body):
    """Envoie un email via SMTP SSL (OVH)."""
    if not _can_send():
        logger.debug("SMTP non configuré, alerte ignorée")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = Settings.SMTP_USER
    msg["To"] = Settings.ALERT_EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(Settings.SMTP_HOST, Settings.SMTP_PORT, context=context) as server:
            server.login(Settings.SMTP_USER, Settings.SMTP_PASSWORD)
            server.sendmail(Settings.SMTP_USER, Settings.ALERT_EMAIL_TO, msg.as_string())
        logger.info(f"Email envoyé: {subject}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi email: {e}")
        return False


def alert_agent_dead(total_eur, min_budget_eur):
    """Alerte quand l'agent Calv-a-lot passe en status DEAD."""
    if _alert_sent["agent_dead"]:
        return

    subject = f"Calv-a-lot: Agent DEAD ({total_eur:.2f}EUR < {min_budget_eur}EUR)"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #ef4444;">Agent Calv-a-lot arrêté</h2>
        <div style="background: #1f2937; color: #f3f4f6; padding: 20px; border-radius: 8px;">
            <p style="font-size: 20px; font-weight: bold; margin: 0;">
                Capital: {total_eur:.2f}EUR
            </p>
            <p style="color: #9ca3af; margin: 5px 0;">
                En dessous du seuil minimum de {min_budget_eur}EUR.
                L'agent a cessé de trader.
            </p>
        </div>
        <p style="color: #6b7280; font-size: 12px; margin-top: 20px;">
            Calv-a-lot (follower)
        </p>
    </div>
    """

    if _send_email(subject, html):
        _alert_sent["agent_dead"] = True


def alert_no_signal(hours_since_last):
    """Alerte quand aucun signal n'a été reçu depuis X heures."""
    if _alert_sent["no_signal"]:
        return

    subject = f"Calv-a-lot: Pas de signal depuis {hours_since_last:.1f}h"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Silence radio de Cash-a-lot</h2>
        <div style="background: #1f2937; color: #f3f4f6; padding: 20px; border-radius: 8px;">
            <p style="font-size: 18px; margin: 0;">
                Aucun nouveau signal reçu depuis <b>{hours_since_last:.1f} heures</b>.
            </p>
            <p style="color: #9ca3af; margin: 10px 0;">
                Cash-a-lot est peut-être down ou le réseau est coupé.
                Le poller continue de vérifier.
            </p>
        </div>
        <p style="color: #6b7280; font-size: 12px; margin-top: 20px;">
            Calv-a-lot (follower) |
            <a href="https://crypto.francony.fr" style="color: #3b82f6;">Cash-a-lot Dashboard</a>
        </p>
    </div>
    """

    if _send_email(subject, html):
        _alert_sent["no_signal"] = True


def reset_alert(alert_name):
    """Reset un flag d'alerte."""
    if alert_name in _alert_sent:
        _alert_sent[alert_name] = False
