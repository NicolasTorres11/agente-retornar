# Documentacion Tecnica Del Codigo

## 1. Proposito

Este repositorio implementa un agente local de primera linea para mensajes de
WhatsApp de Clinica Retornar. El sistema:

- Recibe mensajes por simulacion HTTP, webhook Meta o bridge QR de WhatsApp.
- Clasifica el texto en cinco categorias.
- Detecta riesgo emocional antes de continuar flujos operativos.
- Solicita consentimiento para atencion automatizada en casos no criticos.
- Persiste mensajes, consentimientos y escalamientos en SQLite.
- Permite ejecutar una demostracion completamente local.

El alcance implementado es de desarrollo y demostracion. La conexion QR con
Baileys permite probar desde WhatsApp real, pero no representa el adaptador
productivo oficial recomendado.

Documentos relacionados:

- [ARQUITECTURA.md](ARQUITECTURA.md): vision objetivo y correspondencia con la implementacion local.
- [MODELO_DE_DATOS.md](MODELO_DE_DATOS.md): tablas, relaciones, cifrado y auditoria.

## 2. Arquitectura Local

El codigo sigue una separacion hexagonal simple: la logica de negocio no
depende directamente de FastAPI, SQLite ni WhatsApp.

```text
                       Entradas
       +------------------+------------------+
       |                  |                  |
  /dev/simulate     /ws/whatsapp       /webhook Meta
   (HTTP local)     (Baileys por QR)    (opcional)
       |                  |                  |
       +------------------+------------------+
                          |
                    FastAPI Adapter
                      src/api/app.py
                          |
                  ConversationService
             src/application/conversation_service.py
                   |                       |
             Classifier Port          Repository/Messenger Ports
             src/classifier/             src/ports/
                   |                       |
       Offline Rules / Azure OpenAI   SQLite / WhatsApp adapters
                                      src/adapters/
```

### Decisiones locales

| Decision | Motivo |
|---|---|
| FastAPI | Expone API y WebSocket en un servidor ligero local. |
| SQLite | Evita infraestructura externa y permite probar trazabilidad. |
| Fernet | Cifra contenido de mensajes y nombre antes de guardarlos. |
| Baileys | Permite demostrar WhatsApp mediante QR sin registrar Meta Cloud API. |
| Modo offline | Permite mostrar la demo aun sin credenciales Azure OpenAI. |
| Azure OpenAI opcional | Conserva la integracion LLM especificada para clasificacion real. |

## 3. Estructura De Carpetas

```text
.
|-- README.md                    Arranque rapido y comandos de demostracion
|-- docs/
|   `-- DOCUMENTACION_TECNICA.md Este documento
|-- src/
|   |-- api/                     Endpoints FastAPI y WebSocket
|   |-- application/             Orquestacion de la conversacion
|   |-- domain/                  Entidades y estados del dominio
|   |-- ports/                   Interfaces de persistencia y mensajeria
|   |-- adapters/
|   |   |-- sqlite/              Base local, cifrado y auditoria
|   |   `-- whatsapp/            Adaptador Meta Cloud API opcional
|   |-- classifier/              Pipeline de clasificacion y riesgo
|   `-- settings.py              Variables de configuracion de la aplicacion
|-- scripts/                     Ejecucion, inicializacion y demostraciones
|-- tests/                       Pruebas automaticas y dataset de demo
`-- wa_bridge/                   Bridge Node.js de WhatsApp QR a FastAPI
```

## 4. Modulos Y Responsabilidades

### 4.1. API: `src/api/`

Archivo principal: `src/api/app.py`.

Responsabilidades:

- Construye la aplicacion FastAPI.
- Inicializa el repositorio SQLite durante el arranque.
- Elige el mensajero de salida: consola local o Meta.
- Recibe mensajes por HTTP, WebSocket o webhook.
- Expone consultas de desarrollo para inspeccionar evidencia.

Endpoints:

| Endpoint | Uso |
|---|---|
| `GET /health` | Verifica que el servicio este levantado. |
| `POST /dev/simulate` | Simula un mensaje sin WhatsApp. |
| `GET /dev/messages/{wa_id}` | Muestra la conversacion persistida localmente. |
| `GET /dev/escalations` | Muestra escalamientos registrados. |
| `WS /ws/whatsapp` | Recibe/envia mensajes del bridge Baileys. |
| `GET /webhook` | Handshake de WhatsApp Cloud API, opcional. |
| `POST /webhook` | Webhook firmado de Meta Cloud API, opcional. |

### 4.2. Aplicacion: `src/application/`

Archivo principal: `conversation_service.py`.

`ConversationService` ejecuta el caso de uso central:

1. Registra el mensaje entrante de manera idempotente.
2. Clasifica el mensaje.
3. Si existe riesgo de crisis, escala inmediatamente.
4. Si no hay crisis y falta consentimiento, solicita autorizacion.
5. Si ya hay consentimiento, decide respuesta o handoff por categoria.
6. Registra y envia la respuesta por el adaptador configurado.

Esta capa no conoce HTTP ni implementaciones concretas de base de datos. Solo
usa contratos definidos en `src/ports/`.

### 4.3. Dominio: `src/domain/`

Archivo: `models.py`.

Define objetos propios del problema:

| Modelo | Proposito |
|---|---|
| `InboundMessage` | Mensaje recibido con usuario, texto e identificador. |
| `OutboundMessage` | Mensaje de respuesta listo para enviar. |
| `ProcessOutcome` | Resultado del procesamiento de un turno. |
| `FlowState` | Estado de conversacion: nueva, consentimiento, handoff, crisis, etc. |
| `Priority` | Prioridad de escalamiento: normal, urgente o critica. |

### 4.4. Puertos: `src/ports/`

Los puertos definen lo que la aplicacion necesita sin acoplarla a tecnologia:

| Archivo | Contrato |
|---|---|
| `repository.py` | Guardar mensajes, consentimiento, estados y escalamientos. |
| `messaging.py` | Enviar una respuesta a un canal externo. |

Por esta separacion se puede sustituir SQLite o WhatsApp sin reescribir el
flujo conversacional.

### 4.5. Clasificador: `src/classifier/`

Entrada publica:

```python
from src.classifier import classify

result = classify("Necesito cita con psiquiatria")
```

Archivos:

| Archivo | Funcion |
|---|---|
| `models.py` | Categorias, acciones, riesgo y resultado Pydantic. |
| `preprocessor.py` | Normalizacion, truncamiento y deteccion de idioma. |
| `risk_detector.py` | Patrones deterministas para riesgo emocional. |
| `policy.py` | Politicas deterministas para matriz obligatoria y respuestas estables. |
| `classify.py` | Pipeline principal y reglas de seguridad. |
| `offline_client.py` | Reglas locales deterministicas para la demo. |
| `azure_client.py` | Integracion opcional con Azure OpenAI. |
| `prompts.py` | Instrucciones enviadas al modelo LLM. |
| `config.py` | Variables del clasificador. |

Categorias devueltas:

| Categoria | Uso |
|---|---|
| `solicitud_cita` | Agendar, reprogramar o cancelar cita. |
| `consulta_clinica` | Sintomas, medicacion o riesgo emocional. |
| `pqr` | Peticion, queja o reclamo. |
| `info_administrativa` | Horarios, sedes, convenios y tramites. |
| `no_relevante` | Saludo, prueba, vacio o contenido sin intencion clara. |

Regla prioritaria:

```text
Si el detector identifica riesgo medium, high o critical:
  categoria = consulta_clinica
  accion = escalar_crisis_emocional
  no se requiere respuesta del LLM
```

### 4.6. Persistencia: `src/adapters/sqlite/`

Archivos:

| Archivo | Funcion |
|---|---|
| `schema.sql` | Crea tablas e indices SQLite. |
| `repository.py` | Implementa las operaciones del puerto de persistencia. |
| `encryption.py` | Cifra/descifra campos sensibles con Fernet. |

Datos almacenados:

| Tabla | Contenido |
|---|---|
| `sessions` | Estado conversacional y consentimiento del usuario. |
| `messages` | Mensajes entrantes/salientes cifrados y clasificacion. |
| `escalations` | Casos enviados a atencion humana. |
| `consents` | Decisiones de autorizacion. |
| `audit_log` | Eventos relevantes con identificador hasheado. |

Campos sensibles guardados cifrados:

- Contenido del mensaje.
- Nombre recibido del usuario.

El archivo local se genera en `data/retornar_agent.db` y esta excluido de Git.

### 4.7. WhatsApp Oficial Opcional: `src/adapters/whatsapp/`

Este adaptador se mantiene como extension disponible:

| Archivo | Funcion |
|---|---|
| `webhook.py` | Verifica firma HMAC y convierte payload Meta a mensajes internos. |
| `client.py` | Envia texto con Graph API o simula envio local. |

No es necesario para la demostracion QR.

### 4.8. Bridge QR: `wa_bridge/`

El bridge es un proceso Node.js independiente:

```text
WhatsApp telefono
       |
   Baileys QR
       |
wa_bridge/index.js
       |
WebSocket /ws/whatsapp
       |
Aplicacion Python
```

Proceso:

1. `npm start` inicia Baileys.
2. Si no existe sesion, imprime un QR.
3. El usuario vincula WhatsApp como dispositivo.
4. Cuando recibe un texto, lo manda por WebSocket a FastAPI.
5. FastAPI procesa y devuelve una respuesta.
6. Baileys envia la respuesta al chat original.

Seguridad local:

- `wa_bridge/auth_info/` contiene la sesion vinculada y no se versiona.
- El bridge no imprime el contenido de los mensajes en consola.
- Los mensajes enviados por el bot se excluyen por ID y texto esperado para
  evitar bucles, incluido el modo "Mensaje a ti mismo".

## 5. Flujo De Un Mensaje

### 5.1. Flujo normal con consentimiento

```text
Usuario: "Quiero una cita"
  -> Bridge/API recibe texto
  -> SQLite registra mensaje entrante
  -> Clasificador: solicitud_cita
  -> No existe consentimiento
  -> Bot solicita "SI AUTORIZO"

Usuario: "SI AUTORIZO"
  -> Registra consentimiento
  -> Bot confirma autorizacion

Usuario: "Quisiera agendar una cita"
  -> Clasificador: solicitud_cita
  -> Consentimiento existente
  -> Bot solicita tipo de cita, especialidad, EPS y urgencia

Usuario: "Psiquiatria. Compensar y no es de control."
  -> SQLite guarda especialidad, EPS y tipo de cita cifrados
  -> Bot solicita solo urgencia faltante

Usuario: "No urgente"
  -> SQLite completa la solicitud de cita
  -> Bot muestra tres horarios de agenda simulada local

Usuario: "Opcion 1"
  -> Bot confirma la cita seleccionada
  -> Aclara que el agendamiento es simulado para la prueba local
```

### 5.2. Flujo administrativo directo

```text
Usuario autorizado: "Cuales son los horarios de atencion los sabados?"
  -> Clasificador: info_administrativa
  -> Bot responde lunes a viernes 7:00 a.m. a 7:00 p.m.,
     sabados 8:00 a.m. a 1:00 p.m. y urgencias 24/7
```

### 5.3. Flujo de crisis

```text
Usuario: "Me quiero matar, tengo las pastillas"
  -> Mensaje se persiste cifrado
  -> Detector local identifica riesgo critical
  -> Se omite solicitud de consentimiento en ese turno
  -> Sesion pasa a crisis_active
  -> Se crea escalation con prioridad critical
  -> Bot entrega mensaje inmediato de orientacion urgente
```

La deteccion de crisis ocurre antes del consentimiento para no bloquear una
respuesta urgente de seguridad.

### 5.4. Flujo de consulta clinica no critica

```text
Usuario autorizado: "Olvide tomar mi medicamento"
  -> Clasificador: consulta_clinica
  -> Se registra escalation urgent
  -> Bot informa que el caso sera revisado por un humano
```

## 6. Modos De Ejecucion

### 6.1. Clasificador offline

No necesita API externas. Usa `offline_rules_v1`:

```bash
python scripts/demo_classifier.py --offline "Necesito una cita"
```

### 6.2. Clasificador con Azure OpenAI

Usa las credenciales configuradas en `.env`:

```dotenv
CLASSIFIER_OFFLINE_MODE=false
AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### 6.3. API sin WhatsApp

Permite probar todo el flujo desde terminal:

```bash
python scripts/run_local.py
curl -X POST http://127.0.0.1:8000/dev/simulate \
  -H 'Content-Type: application/json' \
  -d '{"wa_id":"573001111111","text":"Quiero una cita"}'
```

### 6.4. WhatsApp real mediante QR

Procesos requeridos:

```bash
# Terminal 1
source .venv/bin/activate
python scripts/run_local.py

# Terminal 2
cd wa_bridge
npm start
```

Despues de escanear el QR, una segunda cuenta de WhatsApp puede escribir al
numero vinculado.

## 7. Scripts

| Script | Uso |
|---|---|
| `scripts/generate_key.py` | Genera clave Fernet para cifrado local. |
| `scripts/init_db.py` | Inicializa SQLite usando la configuracion `.env`. |
| `scripts/run_local.py` | Levanta FastAPI en `127.0.0.1:8000`. |
| `scripts/demo_classifier.py` | Clasifica un texto o ejecuta el batch de demo. |
| `scripts/send_webhook_demo.py` | Simula webhook firmado del adaptador Meta opcional. |

## 8. Variables De Entorno

| Variable | Funcion | Necesaria en demo QR |
|---|---|---:|
| `CLASSIFIER_OFFLINE_MODE` | Usa reglas locales o Azure OpenAI. | Si |
| `DB_PATH` | Ubicacion del archivo SQLite. | Si |
| `FIELD_ENCRYPTION_KEY` | Clave Fernet para cifrar datos. | Si |
| `APP_ENV` | Activa endpoints locales de desarrollo. | Si |
| `PYTHON_WS_URL` | URL WebSocket para el bridge Node. | Si |
| `WA_BRIDGE_ALLOW_FROM_ME` | Permite prueba con mensajes propios. | Opcional |
| `AZURE_OPENAI_*` | Configuracion del LLM real. | No |
| `WHATSAPP_*` | Configuracion Meta Cloud API. | No |

## 9. Pruebas Automaticas

La suite valida:

| Archivo | Cobertura funcional |
|---|---|
| `test_preprocessor.py` | Texto vacio, truncamiento, normalizacion e idioma. |
| `test_risk_detector.py` | Riesgo bajo, medio, alto y critico. |
| `test_classifier.py` | Pipeline, fallbacks, idioma y modo offline. |
| `test_api_e2e.py` | Consentimiento, crisis, webhook y WebSocket Baileys. |
| `test_whatsapp_client.py` | Construccion de llamada Meta opcional. |

Comandos:

```bash
pytest
ruff check src scripts tests
python scripts/demo_classifier.py --offline --batch tests/fixtures/mensajes_prueba.json
```

Resultados verificados durante desarrollo:

```text
21 tests aprobados
95% de cobertura del clasificador
12/12 categorias correctas en batch local
3/3 casos de crisis escalados
```

## 10. Alcance Y Limitaciones

Implementado:

- Clasificacion funcional con contrato validado.
- Deteccion local conservadora de riesgo.
- Consentimiento y handoff basicos.
- Persistencia cifrada local.
- API de simulacion.
- Prueba por WhatsApp mediante QR.
- Adaptador Meta opcional.

Fuera del alcance actual:

- Panel real para que un humano atienda el handoff.
- Integracion con sistemas clinicos o agendamiento.
- Despliegue cloud.
- Operacion productiva certificada de WhatsApp.
- Validacion clinica formal de los mensajes de crisis.

## 11. Recomendacion Para La Sustentacion

En el video se puede explicar:

1. La logica esta separada en capas para reemplazar adaptadores sin alterar el dominio.
2. Se prueba por QR para demostrar el flujo local sin depender del alta comercial de Meta.
3. La solucion productiva migraria el canal al adaptador oficial Meta disponible en el codigo.
4. En riesgo emocional, la respuesta segura ocurre antes de solicitar consentimiento.
5. Cada mensaje y escalamiento queda trazable localmente y el contenido se cifra en disco.
