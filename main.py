import os
import httpx
from fastapi import FastAPI, Request, Response, status
# Cambiamos a AsyncInferenceClient para no bloquear FastAPI
from huggingface_hub import AsyncInferenceClient

app = FastAPI()

# --- CONFIGURACIÓN DE CREDENCIALES ---
TOKEN_DE_ACCESO = os.getenv("META_ACCESS_TOKEN", "TU_TOKEN_AQUÍ")
TOKEN_VERIFICACION_WEBHOOK = "CHATBOT"
ID_TELEFONO_BUSINESS = "1069016372416229"
#Phone Number ID:1302255416307642
# --- CLIENTE DE INTELIGENCIA ARTIFICIAL (Async) ---
HF_TOKEN = os.getenv("HF_TOKEN", "")
# Instanciamos el cliente asíncrono
client = AsyncInferenceClient(token=HF_TOKEN)


@app.get("/webhook")
async def verificar_webhook(request: Request):
    params = request.query_params
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
    try:
        body = await request.json()
        entries = body.get("entry", [])
        if entries:
            changes = entries[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                
                if messages:
                    mensaje = messages[0]
                    telefono_cliente = mensaje.get("from")
                    
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
        
    return Response(content="EVENT_RECEIVED", status_code=status.HTTP_200_OK)


async def consultar_llama(prompt_usuario: str) -> str:
    """
    Envía el texto a Hugging Face usando el cliente asíncrono.
    """
    try:
        messages = [
            {"role": "system", "content": "Eres un chatbot de WhatsApp amable y conciso. Responde en Español de forma breve."},
            {"role": "user", "content": prompt_usuario}
        ]
        
        # Ahora sí es un await real y eficiente
        completion = await client.chat.completions.create(
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
    Conexión corregida usando la URL oficial de Graph API v20.0
    """
    # CORRECCIÓN: URL corregida con graph.facebook.com y la versión v20.0
    url_api = f"https://graph.facebook.com/v25.0/{ID_TELEFONO_BUSINESS}/messages"
     #https://graph.facebook.com/v25.0/1302255416307642/messages `
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
                # Esto te dirá exactamente qué error tiene Meta si vuelve a fallar
                print(f"❌ Meta rechazó el envío (Código {response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Error de red al conectar con Meta: {str(e)}")
