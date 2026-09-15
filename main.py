import os
import httpx
from fastapi import FastAPI, Request, Response, status
from huggingface_hub import InferenceClient

app = FastAPI()

# --- CONFIGURACIÓN DE CREDENCIALES ---
# NOTA: Si este token de prueba de 24 horas expira, cámbialo aquí o en las variables de entorno de Render.
TOKEN_DE_ACCESO = os.getenv("META_ACCESS_TOKEN", "EAAp1VOdWEY0BSf5BlDgMHhBhmuPI5eLNy7ypttZA7mIRa1Q5UXXFk2Eqn5fRniqgQH3vdMd10MWMvUqYGLKZA7ZAAR17uLCfO4dr4DwFtdDYx0A3bnaR3PqJB1hr5tW5ZB6jULtyUhZChfoPXmUXel1OxcWqHo0x819rd2BMW0GGoAzZCe31Yr9JSuC6t8Ud68z8jAOPIqioOljRe0ywYow24kJhaII7xyZAnk26Bqg9QavrdykMZBBTqyCPaSVOdZBKEgW8Cjs96DJeh1uWFAFkM")
TOKEN_VERIFICACION_WEBHOOK = "CHATBOT"
ID_TELEFONO_BUSINESS = "1069016372416229"

# --- CLIENTE DE INTELIGENCIA ARTIFICIAL (Llama 3.1) ---
HF_TOKEN = os.getenv("HF_TOKEN", "")
client = InferenceClient(token=HF_TOKEN)


@app.get("/webhook")
async def verificar_webhook(request: Request):
    """
    PASO 1: Validación obligatoria de Meta.
    """
    params = request.query_params
    
    # Captura las variantes de parámetros que Meta envía en su petición
    mode = params.get("hub.mode") or params.get("hub_mode")
    token = params.get("hub.verify_token") or params.get("hub_verify_token")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")

    if mode == "subscribe" and token == TOKEN_VERIFICACION_WEBHOOK:
        print(f"✅ Webhook verificado con éxito. Reto respondido: {challenge}")
        return Response(content=challenge, media_type="text/plain")
        
    print("❌ Error de verificación: Token o modo incorrectos.")
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@app.post("/webhook")
async def recibir_mensaje(request: Request):
    """
    PASO 2: Recibir los mensajes de los usuarios y responderles.
    """
    try:
        body = await request.json()

        # Extraemos de forma segura el mensaje de la estructura JSON de Meta
        entries = body.get("entry", [])
        if entries:
            changes = entries[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                
                if messages:
                    mensaje = messages[0]
                    telefono_cliente = mensaje.get("from")
                    
                    # Solo procesamos si el usuario envió un mensaje de texto
                    if mensaje.get("type") == "text":
                        texto_usuario = mensaje.get("text", {}).get("body", "")
                        print(f"💬 Mensaje de [{telefono_cliente}]: {texto_usuario}")

                        # 1. Preguntar a Llama 3.1
                        respuesta_ai = await consultar_llama(texto_usuario)
                        print(f"🤖 Llama responde: {respuesta_ai}")

                        # 2. Enviar respuesta por WhatsApp
                        await enviar_whatsapp(telefono_cliente, respuesta_ai)

    except Exception as e:
        print(f"❌ Error al procesar el mensaje: {str(e)}")
        
    # Siempre respondemos 200 OK a Meta inmediatamente para que no reintente enviar el mismo mensaje
    return Response(content="EVENT_RECEIVED", status_code=status.HTTP_200_OK)


async def consultar_llama(prompt_usuario: str) -> str:
    """
    Envía el texto a Hugging Face para obtener una respuesta de Llama 3.1.
    """
    try:
        messages = [
            {"role": "system", "content": "Eres un chatbot de WhatsApp amable y conciso. Responde en Español de forma breve."},
            {"role": "user", "content": prompt_usuario}
        ]
        
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Error en Hugging Face: {str(e)}")
        return "Lo siento, tuve un pequeño problema técnico. ¿Me repites la pregunta?"


async def enviar_whatsapp(telefono_destino: str, texto_respuesta: str):
    """
    Conexión asíncrona oficial con los servidores de Meta para mandar el mensaje.
    """
    url_api = f"https://facebook.com{ID_TELEFONO_BUSINESS}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN_DE_ACCESO}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono_destino,
        "type": "text",
        "text": {"preview_url": False, "body": texto_respuesta}
    }

    async with httpx.AsyncClient() as client_http:
        try:
            response = await client_http.post(url_api, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"🚀 Mensaje enviado con éxito a {telefono_destino}")
            else:
                print(f"❌ Meta rechazó el envío: {response.json()}")
        except Exception as e:
            print(f"❌ Error de red al conectar con Meta: {str(e)}")
