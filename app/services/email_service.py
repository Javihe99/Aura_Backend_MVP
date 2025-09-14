"""
Servicio para envío de emails de notificación de citas
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de emails de notificación de citas"""
    
    def __init__(self):
        # Configuración de email (puedes configurar estas variables en tu .env)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL", "javihe99@gmail.com")
        self.sender_password = os.getenv("SENDER_PASSWORD")  # App password para Gmail
        self.recipient_email = os.getenv("RECIPIENT_EMAIL", "javihe99@gmail.com")
        
        # Verificar configuración
        if not self.sender_password:
            logger.warning("SENDER_PASSWORD no configurado. El envío de emails no funcionará.")
    
    async def send_appointment_notification(self, appointment_data: Dict[str, Any]) -> bool:
        """
        Envía notificación de nueva cita por email
        
        Args:
            appointment_data: Datos de la cita
            
        Returns:
            True si el email se envió correctamente, False en caso contrario
        """
        try:
            if not self.sender_password:
                logger.error("No se puede enviar email: SENDER_PASSWORD no configurado")
                return False
            
            # Crear contenido del email
            subject = f"📅 Nueva Cita - {appointment_data.get('name', 'Cliente')}"
            body = self._create_email_body(appointment_data)
            
            # Crear mensaje
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = self.recipient_email
            
            # Crear versión HTML del email
            html_body = self._create_html_email_body(appointment_data)
            
            # Adjuntar versiones de texto y HTML
            text_part = MIMEText(body, "plain", "utf-8")
            html_part = MIMEText(html_body, "html", "utf-8")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Enviar email
            await self._send_email(message)
            
            logger.info(f"Email de notificación enviado exitosamente para cita {appointment_data.get('appointment_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de notificación: {str(e)}")
            return False
    
    def _create_email_body(self, appointment_data: Dict[str, Any]) -> str:
        """Crea el cuerpo del email en texto plano"""
        
        # Formatear fecha y hora
        appointment_time = appointment_data.get('appointment_time', '')
        try:
            if appointment_time:
                dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%d/%m/%Y a las %H:%M")
            else:
                formatted_time = "No especificada"
        except:
            formatted_time = appointment_time
        
        body = f"""
🏠 NUEVA CITA INMOBILIARIA

📋 INFORMACIÓN DE LA CITA:
• Cliente: {appointment_data.get('name', 'No especificado')}
• Email: {appointment_data.get('email', 'No especificado')}
• Teléfono: {appointment_data.get('phone', 'No especificado')}
• Fecha y Hora: {formatted_time}
• ID de Cita: {appointment_data.get('appointment_id', 'No disponible')}
• ID de Sesión: {appointment_data.get('session_id', 'No disponible')}

🏠 INFORMACIÓN DE LA PROPIEDAD:
• ID de Propiedad: {appointment_data.get('property_id', 'No especificada')}
• URL de Propiedad: {appointment_data.get('property_url', 'No especificada')}

💰 INFORMACIÓN FINANCIERA:
• Presupuesto Mínimo: {appointment_data.get('budget_min', 'No especificado')}€
• Presupuesto Máximo: {appointment_data.get('budget_max', 'No especificado')}€
• Necesita Financiación: {'Sí' if appointment_data.get('financing', False) else 'No'}

📍 UBICACIÓN:
• Ubicación del usuario Detectada: {appointment_data.get('user_location', 'No detectada')}

📝 RESUMEN DE LA CONVERSACIÓN:
{appointment_data.get('conversation_summary', 'No disponible')}

🔍 METADATOS DE PREFERENCIAS:
{self._format_preferences_metadata(appointment_data.get('preferences_metadata', {}))}

---
📅 Cita creada el: {datetime.now().strftime("%d/%m/%Y a las %H:%M")}
🤖 Generado automáticamente por Aura Backend MVP
        """
        
        return body.strip()
    
    def _create_html_email_body(self, appointment_data: Dict[str, Any]) -> str:
        """Crea el cuerpo del email en HTML"""
        
        # Formatear fecha y hora
        appointment_time = appointment_data.get('appointment_time', '')
        try:
            if appointment_time:
                dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%d/%m/%Y a las %H:%M")
            else:
                formatted_time = "No especificada"
        except:
            formatted_time = appointment_time
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
        .section {{ margin-bottom: 20px; padding: 15px; background: white; border-radius: 8px; border-left: 4px solid #667eea; }}
        .section h3 {{ margin-top: 0; color: #667eea; }}
        .info-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ color: #333; }}
        .highlight {{ background: #e8f4fd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠 Nueva Cita Inmobiliaria</h1>
        </div>
        
        <div class="content">
            <div class="section">
                <h3>📋 Información de la Cita</h3>
                <div class="info-row">
                    <span class="label">Cliente:</span>
                    <span class="value">{appointment_data.get('name', 'No especificado')}</span>
                </div>
                <div class="info-row">
                    <span class="label">Email:</span>
                    <span class="value">{appointment_data.get('email', 'No especificado')}</span>
                </div>
                <div class="info-row">
                    <span class="label">Teléfono:</span>
                    <span class="value">{appointment_data.get('phone', 'No especificado')}</span>
                </div>
                <div class="info-row">
                    <span class="label">Fecha y Hora:</span>
                    <span class="value">{formatted_time}</span>
                </div>
                <div class="info-row">
                    <span class="label">ID de Cita:</span>
                    <span class="value">{appointment_data.get('appointment_id', 'No disponible')}</span>
                </div>
            </div>
            
            <div class="section">
                <h3>🏠 Información de la Propiedad</h3>
                <div class="info-row">
                    <span class="label">ID de Propiedad:</span>
                    <span class="value">{appointment_data.get('property_id', 'No especificada')}</span>
                </div>
                <div class="info-row">
                    <span class="label">URL de Propiedad:</span>
                    <span class="value">
                        {f'<a href="{appointment_data.get("property_url")}" target="_blank">{appointment_data.get("property_url")}</a>' if appointment_data.get('property_url') else 'No especificada'}
                    </span>
                </div>
            </div>
            
            <div class="section">
                <h3>💰 Información Financiera</h3>
                <div class="info-row">
                    <span class="label">Presupuesto Mínimo:</span>
                    <span class="value">{appointment_data.get('budget_min', 'No especificado')}€</span>
                </div>
                <div class="info-row">
                    <span class="label">Presupuesto Máximo:</span>
                    <span class="value">{appointment_data.get('budget_max', 'No especificado')}€</span>
                </div>
                <div class="info-row">
                    <span class="label">Necesita Financiación:</span>
                    <span class="value">{'Sí' if appointment_data.get('financing', False) else 'No'}</span>
                </div>
            </div>
            
            <div class="section">
                <h3>📍 Ubicación</h3>
                <div class="info-row">
                    <span class="label">Ubicación Detectada:</span>
                    <span class="value">{appointment_data.get('user_location', 'No detectada')}</span>
                </div>
            </div>
            
            <div class="section">
                <h3>📝 Resumen de la Conversación</h3>
                <div class="highlight">
                    {appointment_data.get('conversation_summary', 'No disponible')}
                </div>
            </div>
            
            <div class="section">
                <h3>🔍 Metadatos de Preferencias</h3>
                <div class="highlight">
                    {self._format_preferences_metadata_html(appointment_data.get('preferences_metadata', {}))}
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>📅 Cita creada el: {datetime.now().strftime("%d/%m/%Y a las %H:%M")}</p>
            <p>🤖 Generado automáticamente por Aura Backend MVP</p>
        </div>
    </div>
</body>
</html>
        """
        
        return html_body
    
    def _format_preferences_metadata(self, metadata: Dict[str, Any]) -> str:
        """Formatea los metadatos de preferencias para texto plano"""
        if not metadata:
            return "No hay metadatos disponibles"
        
        formatted_items = []
        for key, value in metadata.items():
            if isinstance(value, list):
                formatted_items.append(f"• {key}: {', '.join(map(str, value))}")
            else:
                formatted_items.append(f"• {key}: {value}")
        
        return "\n".join(formatted_items) if formatted_items else "No hay metadatos disponibles"
    
    def _format_preferences_metadata_html(self, metadata: Dict[str, Any]) -> str:
        """Formatea los metadatos de preferencias para HTML"""
        if not metadata:
            return "No hay metadatos disponibles"
        
        formatted_items = []
        for key, value in metadata.items():
            if isinstance(value, list):
                formatted_items.append(f"<strong>{key}:</strong> {', '.join(map(str, value))}")
            else:
                formatted_items.append(f"<strong>{key}:</strong> {value}")
        
        return "<br>".join(formatted_items) if formatted_items else "No hay metadatos disponibles"
    
    async def _send_email(self, message: MIMEMultipart) -> None:
        """Envía el email usando SMTP"""
        try:
            # Crear contexto SSL
            context = ssl.create_default_context()
            
            # Conectar al servidor SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                
                # Enviar email
                text = message.as_string()
                server.sendmail(self.sender_email, self.recipient_email, text)
                
            logger.info("Email enviado exitosamente")
            
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            raise
