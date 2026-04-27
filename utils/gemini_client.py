"""Cliente para la API de Google Gemini (IA de texto)."""
import os
import requests
from typing import List, Dict, Optional


class GeminiClient:
    """Cliente HTTP para interactuar con la API de Google Gemini."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    SYSTEM_PROMPT_CHAT = """Eres un asistente virtual profesional de Asistego, un taller mecánico de emergencias vehiculares en Santa Cruz, Bolivia.

Tu objetivo es ayudar a clientes con:
- Información sobre servicios de emergencia (grúa, mecánico a domicilio, diagnóstico)
- Tiempos estimados de respuesta (generalmente 15-30 minutos)
- Precios aproximados de servicios comunes
- Estados de sus solicitudes de servicio
- Consejos básicos de seguridad vehicular
- Información general sobre el taller

Directrices:
- Sé amable, profesional y empático (los clientes están en situaciones de estrés)
- Responde en español de manera clara y concisa
- Si no tienes información específica, indica que un representante del taller se comunicará
- Para emergencias graves, sugiere llamar directamente al taller
- No hagas diagnósticos médicos ni de seguridad críticos sin verificación humana

Servicios disponibles:
- Asistencia mecánica a domicilio
- Servicio de grúa
- Diagnóstico de problemas
- Cambio de batería, neumáticos, aceite
- Reparaciones eléctricas y mecánicas
- Venta de repuestos

Contacto del taller:
- Teléfono: +591 7123 4567
- Horario: 24/7 para emergencias"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Inicializar cliente con API key y modelo."""
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        masked_key = f"{self.api_key[:10]}...{self.api_key[-5:]}"
        print(f"🚀 [Gemini] Cliente inicializado. Modelo: {self.model}, Key: {masked_key}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500,
        system_prompt: Optional[str] = None,
    ) -> Dict:
        """
        Enviar solicitud de chat completion a Gemini.

        Args:
            messages: Lista de mensajes [{"role": "user", "content": "..."}]
            temperature: Creatividad de la respuesta (0-1)
            max_tokens: Máximo de tokens en respuesta
            system_prompt: Prompt de sistema personalizado

        Returns:
            Dict con respuesta de la API o error
        """
        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"

        combined_text = ""
        if system_prompt:
            combined_text += system_prompt + "\n\n"

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                combined_text += content + "\n\n"
            else:
                combined_text += f"{role}: {content}\n"

        payload = {
            "contents": [
                {
                    "parts": [{"text": combined_text.strip()}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            candidates = data.get("candidates", [])
            if candidates and len(candidates) > 0:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts and len(parts) > 0:
                    respuesta_texto = parts[0].get("text", "")
                    usage = data.get("usageMetadata", {})
                    return {
                        "success": True,
                        "respuesta": respuesta_texto,
                        "modelo_usado": self.model,
                        "tokens_usados": usage.get("totalTokenCount", 0),
                    }

            return {
                "success": False,
                "error": "Respuesta inesperada de la API",
                "detalle": data,
            }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout al conectar con Gemini",
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Error de conexión: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error inesperado: {str(e)}",
            }

    def generar_diagnostico(
        self,
        descripcion_problema: str,
        vehiculo_info: Optional[Dict] = None,
    ) -> Dict:
        """
        Generar diagnóstico IA basado en descripción textual.

        Args:
            descripcion_problema: Descripción del problema por el cliente
            vehiculo_info: Información opcional del vehículo

        Returns:
            Dict con diagnóstico estructurado o error
        """
        system_prompt = """Eres un asistente de diagnóstico mecánico de Asistego. Analiza descripciones de problemas vehiculares y proporciona evaluaciones preliminares.

Responde SIEMPRE en formato JSON con esta estructura:
{
    "diagnostico": "Descripción detallada del problema probable",
    "gravedad": "baja|media|alta|critica",
    "causas_probables": ["Causa 1", "Causa 2", "Causa 3"],
    "repuestos_sugeridos": ["Repuesto 1", "Repuesto 2"],
    "tiempo_estimado_minutos": 45,
    "recomendaciones": "Acciones sugeridas para el cliente",
    "requiere_grua": true|false,
    "notas_tecnico": "Información útil para el mecánico asignado"
}

Consideraciones:
- Gravedad "critica": Problema de seguridad, no debe conducirse
- Gravedad "alta": Avería importante, requiere atención inmediata
- Gravedad "media": Problema que debe resolverse pronto
- Gravedad "baja": Mantenimiento o problema menor

Sé conservador en las estimaciones de tiempo. Es mejor superar expectativas."""

        prompt = f"Descripción del problema: {descripcion_problema}\n\n"

        if vehiculo_info:
            prompt += "Información del vehículo:\n"
            prompt += f"- Marca: {vehiculo_info.get('marca', 'No especificada')}\n"
            prompt += f"- Modelo: {vehiculo_info.get('modelo', 'No especificado')}\n"
            prompt += f"- Año: {vehiculo_info.get('anio', 'No especificado')}\n"
            prompt += f"- Tipo: {vehiculo_info.get('tipo', 'No especificado')}\n\n"

        prompt += "Proporciona el diagnóstico en formato JSON especificado."

        messages = [{"role": "user", "content": prompt}]

        resultado = self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=800,
        )

        if resultado["success"]:
            try:
                import json
                contenido = resultado["respuesta"]
                if "```json" in contenido:
                    contenido = contenido.split("```json")[1].split("```")[0]
                elif "```" in contenido:
                    contenido = contenido.split("```")[1].split("```")[0]

                diagnostico_json = json.loads(contenido.strip())
                return {
                    "success": True,
                    "diagnostico": diagnostico_json,
                    "modelo_usado": resultado.get("modelo_usado"),
                    "tokens_usados": resultado.get("tokens_usados"),
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "No se pudo parsear el diagnóstico",
                    "respuesta_raw": resultado["respuesta"],
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error procesando diagnóstico: {str(e)}",
                }

        return resultado

    def consultar_chat(
        self,
        mensaje_usuario: str,
        contexto_solicitud: Optional[Dict] = None,
    ) -> Dict:
        """
        Consulta al asistente de chat para clientes.

        Args:
            mensaje_usuario: Mensaje del cliente
            contexto_solicitud: Datos opcionales de la solicitud activa

        Returns:
            Dict con respuesta del asistente
        """
        contexto = ""
        if contexto_solicitud:
            contexto = f"\nContexto de solicitud activa:\n"
            if "problema" in contexto_solicitud:
                contexto += f"- Problema reportado: {contexto_solicitud['problema']}\n"
            if "estado" in contexto_solicitud:
                contexto += f"- Estado actual: {contexto_solicitud['estado']}\n"
            if "vehiculo" in contexto_solicitud:
                v = contexto_solicitud["vehiculo"]
                contexto += f"- Vehículo: {v.get('marca', 'N/A')} {v.get('modelo', 'N/A')}\n"

        messages = [
            {"role": "user", "content": mensaje_usuario + contexto}
        ]

        return self.chat_completion(
            messages=messages,
            system_prompt=self.SYSTEM_PROMPT_CHAT,
            temperature=0.7,
            max_tokens=400,
        )


_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Obtener instancia singleton del cliente Gemini."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
