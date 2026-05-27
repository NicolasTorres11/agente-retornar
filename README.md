# Clinica Retornar - Clasificador Local de Mensajes

Aplicacion local funcional para recibir mensajes, clasificarlos, aplicar el
flujo conversacional y validar la integracion de WhatsApp Cloud API.

Incluye clasificador, consentimiento, escalamiento por riesgo, persistencia
SQLite cifrada, webhook FastAPI con validacion HMAC, cliente saliente de Meta,
bridge opcional WhatsApp Web/Baileys por QR, modo de simulacion y pruebas
automaticas. El despliegue productivo queda fuera del alcance actual.

Documentacion detallada del codigo, carpetas y flujos:

- [Documentacion tecnica](docs/DOCUMENTACION_TECNICA.md)
- [Arquitectura y correspondencia local/productiva](docs/ARQUITECTURA.md)
- [Modelo de datos SQLite y seguridad](docs/MODELO_DE_DATOS.md)

## Requisitos

- Python `3.11` o `3.12` recomendado.
- Una cuenta Azure OpenAI con deployment `gpt-4o` solo si quieres usar el LLM.
- Para la demostracion offline no necesitas credenciales externas.

En esta maquina Python `3.11.9` esta instalado mediante `pyenv`, por lo que se
puede activar con `PYENV_VERSION=3.11.9`.

## Instalacion Local

```bash
PYENV_VERSION=3.11.9 python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python scripts/generate_key.py
# Pega el resultado en FIELD_ENCRYPTION_KEY dentro de .env
python scripts/init_db.py
```

El archivo `.env.example` trae `CLASSIFIER_OFFLINE_MODE=true`, suficiente para
probar todos los comandos sin llamar a Azure.

## Arquitectura Local

Se utiliza arquitectura hexagonal para mantener la logica testeable:

```text
src/domain/                 Entidades de mensajes y estados
src/ports/                  Contratos de persistencia y envio
src/application/            Flujo conversacional y reglas de handoff
src/classifier/             Clasificacion y detector local de riesgo
src/adapters/sqlite/        Persistencia cifrada y auditoria
src/adapters/whatsapp/      Firma webhook y envio Meta Cloud API
src/api/                    Endpoints FastAPI y simulador local
```

En desarrollo `WHATSAPP_SEND_MODE=console` guarda respuestas en SQLite sin
llamar a Meta. Cuando dispongas de un numero de prueba y token, cambia a
`WHATSAPP_SEND_MODE=meta`.

Para la demostracion sin configurar Meta, `wa_bridge/` implementa una segunda
entrada por QR usando Baileys. Es una integracion basada en WhatsApp Web,
util solo para desarrollo y video; no sustituye la API oficial en produccion.

## Demo Del Clasificador

Caso de cita:

```bash
python scripts/demo_classifier.py --offline "Necesito agendar cita con psiquiatria"
```

Caso administrativo:

```bash
python scripts/demo_classifier.py --offline "Cuales son los horarios de atencion los sabados"
```

Caso de riesgo:

```bash
python scripts/demo_classifier.py --offline "Me quiero matar, ya tengo las pastillas"
```

Ejecutar el lote de casos preparado para el video:

```bash
python scripts/demo_classifier.py --offline --batch tests/fixtures/mensajes_prueba.json
```

## Demo De La Aplicacion Completa

Arranca la API:

```bash
python scripts/run_local.py
```

En otra terminal prueba un flujo normal:

```bash
curl -s -X POST http://127.0.0.1:8000/dev/simulate \
  -H 'Content-Type: application/json' \
  -d '{"wa_id":"573001111111","text":"Quiero una cita"}'

curl -s -X POST http://127.0.0.1:8000/dev/simulate \
  -H 'Content-Type: application/json' \
  -d '{"wa_id":"573001111111","text":"SI AUTORIZO"}'

curl -s -X POST http://127.0.0.1:8000/dev/simulate \
  -H 'Content-Type: application/json' \
  -d '{"wa_id":"573001111111","text":"Necesito cita con psiquiatria"}'

curl -s http://127.0.0.1:8000/dev/messages/573001111111
```

Prueba que un primer mensaje critico se escala sin bloquearse por consentimiento:

```bash
curl -s -X POST http://127.0.0.1:8000/dev/simulate \
  -H 'Content-Type: application/json' \
  -d '{"wa_id":"573002222222","text":"Me quiero matar, tengo las pastillas"}'

curl -s http://127.0.0.1:8000/dev/escalations
```

Prueba un webhook con firma como lo entrega WhatsApp:

```bash
python scripts/send_webhook_demo.py "Hola, necesito una cita"
```

## Conectar Azure OpenAI

Edita `.env` y establece:

```dotenv
CLASSIFIER_OFFLINE_MODE=false
AZURE_OPENAI_ENDPOINT=https://<tu-recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=<tu-api-key>
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Luego ejecuta el mismo comando, sin `--offline`:

```bash
python scripts/demo_classifier.py "Necesito agendar cita con psiquiatria"
```

`offline_rules_v1` es un modo deterministico para desarrollo y video, no un
reemplazo del modelo LLM. El detector de riesgo se ejecuta localmente antes
del LLM en ambos modos.

## Conectar WhatsApp Cloud API

Para usar una app/numeracion de prueba de Meta, edita `.env`:

```dotenv
WHATSAPP_SEND_MODE=meta
WHATSAPP_VERIFY_TOKEN=<token-que-configuraras-en-meta>
WHATSAPP_APP_SECRET=<app-secret-de-meta>
WHATSAPP_ACCESS_TOKEN=<access-token-de-meta>
WHATSAPP_PHONE_NUMBER_ID=<phone-number-id>
WHATSAPP_API_VERSION=<version-activa-en-tu-panel-meta>
```

Expone temporalmente `http://127.0.0.1:8000/webhook` mediante un tunel HTTPS
de desarrollo y registra la URL publica en Meta. La API soporta:

- `GET /webhook`: handshake de verificacion.
- `POST /webhook`: firma `X-Hub-Signature-256`, mensajes de texto y statuses.
- Envio saliente por `/{PHONE_NUMBER_ID}/messages` cuando `SEND_MODE=meta`.

Usa la version de Graph API que aparezca disponible en la configuracion de
tu app de Meta al momento de la prueba.

## Probar Desde WhatsApp Con QR (Baileys)

Esta opcion evita crear la app en Meta para la demostracion local. Necesitas
Node.js 20 o superior y, preferiblemente, un numero de WhatsApp dedicado a
pruebas.

Instala el bridge una sola vez:

```bash
cd wa_bridge
npm install
cd ..
```

En `.env` conserva:

```dotenv
CLASSIFIER_OFFLINE_MODE=true
WHATSAPP_SEND_MODE=console
PYTHON_WS_URL=ws://127.0.0.1:8000/ws/whatsapp
WA_BRIDGE_ALLOW_FROM_ME=false
```

Levanta dos terminales:

```bash
# Terminal 1 - aplicacion Python
source .venv/bin/activate
python scripts/run_local.py
```

```bash
# Terminal 2 - conexion WhatsApp por QR
cd wa_bridge
PYTHON_WS_URL=ws://127.0.0.1:8000/ws/whatsapp npm start
```

La primera vez aparece un QR en la segunda terminal. Desde el telefono que
sera el bot abre:

```text
WhatsApp > Dispositivos vinculados > Vincular dispositivo
```

Escanea el QR. Luego escribe al numero conectado desde otro WhatsApp:

```text
Quiero una cita
SI AUTORIZO
Necesito cita con psiquiatria
```

Para mostrar el protocolo de crisis durante la demo:

```text
Me quiero matar, tengo las pastillas
```

La sesion QR se almacena localmente en `wa_bridge/auth_info/`, que esta
excluida de git. No compartas ni subas esa carpeta: permite acceso a la
sesion vinculada. Para desvincularla, elimina el dispositivo desde WhatsApp
y borra `wa_bridge/auth_info/`.

Si solo cuentas con un telefono, puedes establecer
`WA_BRIDGE_ALLOW_FROM_ME=true` y escribir en el chat "Mensaje a ti mismo" de
la cuenta vinculada; para la grabacion es mas confiable usar dos numeros.

## Tests

```bash
pytest
ruff check src scripts tests
```

## Estructura

```text
docs/                           Documentacion tecnica del codigo y procesos
img-architectures/              Diagramas visuales usados en arquitectura
src/                            Aplicacion hexagonal local
scripts/demo_classifier.py      Demo aislada del clasificador
scripts/run_local.py            Servidor FastAPI local
scripts/send_webhook_demo.py    POST webhook firmado para demostracion
wa_bridge/                      Conexion QR WhatsApp Web/Baileys para demo
tests/                          Pruebas unitarias y end-to-end
.env.example                    Configuracion de ejemplo
requirements-dev.txt            Dependencias para instalar y probar
```
