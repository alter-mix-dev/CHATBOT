import os
import requests
from fastapi import FastAPI, Request, Response, status
from huggingface_hub import InferenceClient

app = FastAPI()

# 1. CONFIGURACIÓN DE TU CUENTA DE META
TOKEN_DE_ACCESO = "EAAp1VOdWEY0BSXqvu8K3nZB3UfgL36JkZCnqxkn9iJWFlKiAh0t8ZCjdH0SlWQJXTN8bZA5lZAIwZCZCXC3uTNaNAS1XLOeB5WZCQ55KXruliHeWfzqu5dqeLwZCyZB3iQYnyMnnvhTmDwnjh6YSsE14pHmMAcY8OmY2RHUAlyiA5lmxeimVPBN3UVzdTZCfN14q6OOouHIDDQZCnC0rFFW6OsYSBi1pUY9tGMMEZCuIHy7dwhis1gZCPKOhpXleG6cZCdZAEZAoWTHnAm3mlGJChT4vAEXMXLAZDZD"
TOKEN_VERIFICACION_WEBHOOK = "CHATBOT"
ID_TELEFONO_BUSINESS = "1302255416307642"

# 2. CONFIGURACIÓN DE HUGGING FACE (Llama 3.1)
# Extrae tu token de Hugging Face de las variables de entorno de Render
HF_TOKEN = os.getenv("HF_TOKEN", "")

# Inicializamos el cliente oficial de Inferencia de Hugging Face
# Si no hay token, funcionará con cuotas muy limitadas de prueba pública
client = InferenceClient(token=HF_TOKEN)

#@app.get("/")
@app.get("/webhook")
async def verificar_webhook(request: Request):
    """
    PASO 1: Validación obligatoria del Webhook requerida por Meta.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == TOKEN_VERIFICACION_WEBHOOK:
            print("✅ Webhook verificado correctamente con Meta.")
            return Response(content=challenge, media_type="text/plain")
        
    return Response(status_code=status.HTTP_403_FORBIDDEN)

#@app.post("/")
@app.post("/webhook")
async def recibir_mensaje(request: Request):
    """
    PASO 2: Recepción y procesamiento de mensajes entrantes de WhatsApp.
    """
    try:
        body = await request.json()

        # Validación estructural del JSON entrante de Meta
        if body.get("object") == "whatsapp_business_account":
            entry = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if messages:
                mensaje_original = messages[0]
                telefono_cliente = mensaje_original.get("from")
                tipo_mensaje = mensaje_original.get("type")

                if tipo_mensaje == "text":
                    texto_usuario = mensaje_original.get("text", {}).get("body", "")
                    print(f"💬 Mensaje recibido de [{telefono_cliente}]: {texto_usuario}")

                    # Consultar a Llama 3.1 en Hugging Face de forma gratuita
                    respuesta_bot = await consultar_llama(texto_usuario)
                    print(f"🤖 Llama respondió: {respuesta_bot}")

                    # Reenviar la respuesta al usuario mediante WhatsApp
                    await enviar_whatsapp(telefono_cliente, respuesta_bot)

    except Exception as e:
        print(f"❌ Error procesando el Webhook: {str(e)}")
        
    # Siempre responder 200 OK a Meta de inmediato para evitar reintentos duplicados
    return Response(content="EVENT_RECEIVED", status_code=status.HTTP_200_OK)


async def consultar_llama(prompt_usuario: str) -> str:
    """
    Se conecta a la infraestructura gratuita de Hugging Face para despertar a Llama.
    """
    try:
        # Usamos Llama 3.1 8B Instruct (ligero, veloz y gratuito)
        messages = [
            {
                "role": "system", 
                "content": "Eres un chatbot de WhatsApp inteligente, conciso y amable. Responde siempre en Español de manera breve ya que tus usuarios leen desde el móvil."
            },
            {
                "role": "user", 
                "content": prompt_usuario
            }
        ]
        
        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct",
            messages=messages,
            max_tokens=250,
            temperature=0.7
        )
        
        return completion.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"⚠️ Error consultando Llama en Hugging Face: {str(e)}")
        return "Lo siento, mi cerebro de IA está un poco saturado en este momento. ¿Me repites la pregunta?"


async def enviar_whatsapp(telefono_destino: str, texto_respuesta: str):
    """
    Despacha el mensaje de vuelta a WhatsApp a través de los servidores de Meta.
    """
    url_api = f"https://graph.facebook.com{ID_TELEFONO_BUSINESS}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN_DE_ACCESO}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono_destino,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": texto_respuesta
        }
    }

    try:
        response = requests.post(url_api, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"🚀 Respuesta enviada con éxito a [{telefono_destino}]")
        else:
            print(f"❌ Meta rechazó la petición: {response.json()}")
    except Exception as e:
        print(f"❌ Error de conexión al enviar WhatsApp: {str(e)}")
