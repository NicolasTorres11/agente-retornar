# Arquitectura Del Agente Conversacional

## 1. Vision General

El agente de Clinica Retornar atiende la primera interaccion recibida por
WhatsApp, clasifica la necesidad del usuario y decide si puede orientar el
flujo operativo o si requiere intervencion humana.

Objetivos principales:

- Atender solicitudes frecuentes de manera ordenada.
- Detectar riesgo emocional con prioridad sobre cualquier automatizacion.
- Evitar que el bot entregue recomendaciones clinicas.
- Mantener trazabilidad de mensajes, consentimiento y escalamientos.
- Permitir evolucionar de una demostracion local a una integracion oficial.

## 2. Capacidades Funcionales

| Capacidad | Descripcion |
|---|---|
| Clasificacion | Identifica una de cinco categorias a partir del mensaje. |
| Riesgo emocional | Detecta indicadores de crisis y fuerza escalamiento critico. |
| Consentimiento | Solicita autorizacion antes del flujo normal automatizado. |
| Handoff | Registra casos que deben pasar a una persona. |
| Persistencia | Guarda sesiones, mensajes, consentimientos y auditoria. |
| Canal WhatsApp | Funciona localmente con QR; dispone de adaptador Meta opcional. |

## 3. Categorias De Clasificacion

| Categoria | Ejemplo | Decision esperada |
|---|---|---|
| `solicitud_cita` | "Necesito una cita con psiquiatria" | Solicitar datos o continuar agendamiento. |
| `consulta_clinica` | "Olvide tomar mi medicamento" | Escalar a equipo humano. |
| `pqr` | "Quiero poner una queja" | Escalar y registrar solicitud. |
| `info_administrativa` | "Cuales son los horarios" | Responder u orientar. |
| `no_relevante` | "Hola" o mensaje vacio | Saludar o ignorar. |

## 4. Arquitectura Objetivo Descrita En El Diseno

La vision de produccion plantea una arquitectura desacoplada y auditable:

```text
Usuario WhatsApp
       |
WhatsApp Business Cloud API (Meta)
       |
Webhook HTTPS / validacion de firma
       |
Cola durable de mensajes
       |
Agente conversacional / clasificador
       |                         |
Persistencia y auditoria      Handoff humano
       |                         |
Sistemas institucionales      Equipo clinico/operativo
```

Componentes esperados para una operacion productiva:

| Capa | Responsabilidad |
|---|---|
| Canal | Recepcion y envio mediante WhatsApp Business Cloud API oficial. |
| Ingreso | Webhook HTTPS, validacion de firma y respuesta rapida al canal. |
| Procesamiento | Clasificacion, reglas de riesgo, decisiones y flujos. |
| Persistencia | Estado conversacional, mensajes, consentimiento y auditoria. |
| Handoff | Transferencia de casos clinicos, PQR o crisis a personal humano. |
| Integracion | Consulta futura de sistemas como Compuconta o SIH por adaptadores. |
| Observabilidad | Metricas, eventos y alertas sin exponer texto sensible. |

Esta arquitectura corresponde a la solucion institucional futura. Para el
entregable se implementa un prototipo local que preserva las reglas y los
limites del dominio sin requerir infraestructura de nube.

## 5. Arquitectura Implementada Para Desarrollo Local

```text
             +-----------------------------+
             |  Entrada de mensajes        |
             |-----------------------------|
             | HTTP /dev/simulate          |
             | WhatsApp QR con Baileys     |
             | Webhook Meta opcional       |
             +-------------+---------------+
                           |
                           v
             +-----------------------------+
             | FastAPI                     |
             | src/api/app.py              |
             +-------------+---------------+
                           |
                           v
             +-----------------------------+
             | ConversationService         |
             | reglas de flujo y handoff   |
             +------+------+---------------+
                    |      |
             +------+      +------------------+
             v                                v
   +-------------------+          +-----------------------+
   | Clasificador      |          | Puertos de salida     |
   | offline / Azure   |          | repositorio/mensajes  |
   +-------------------+          +-----------+-----------+
                                              |
                          +-------------------+-------------------+
                          v                                       v
                 +-------------------+                  +----------------+
                 | SQLite cifrado    |                  | Baileys / Meta |
                 +-------------------+                  +----------------+
```

### Correspondencia entre vision y prototipo

| Arquitectura objetivo | Implementacion local actual |
|---|---|
| WhatsApp Cloud API oficial | Baileys por QR para demo; adaptador Meta conservado como opcion. |
| Webhook publico | FastAPI local con endpoint webhook y WebSocket. |
| Cola durable cloud | Ejecucion directa local con mensajes persistidos en SQLite. |
| Orquestacion de agente | `ConversationService`. |
| Clasificador GPT-4o | Azure OpenAI opcional; reglas offline para pruebas. |
| Base gestionada / auditoria | SQLite local con cifrado Fernet. |
| Handoff humano integrado | Registro de escalamiento; interfaz humana no incluida. |
| Dashboard/monitoreo | Endpoints de inspeccion local para evidencia. |

## 6. Arquitectura Hexagonal Del Codigo

La implementacion local separa decisiones de negocio de detalles tecnicos:

```text
                    Adaptadores de entrada
           FastAPI HTTP | WebSocket QR | Webhook Meta
                            |
                            v
                 +---------------------+
                 | Capa de aplicacion  |
                 | ConversationService |
                 +---------+-----------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
        Dominio                      Puertos
 mensajes/estados          repositorio y mensajeria
                                         |
                    +--------------------+-------------------+
                    v                                        v
              SQLite/Fernet                        Baileys o Meta API
              Adaptadores externos/salida
```

Beneficios:

- El clasificador puede probarse sin WhatsApp.
- El canal WhatsApp puede cambiar sin modificar reglas de crisis.
- SQLite puede sustituirse por una base productiva manteniendo los puertos.
- La suite automatica cubre el negocio sin depender de servicios externos.

## 7. Flujo Principal

### 7.1. Mensaje operativo

```text
Mensaje recibido
 -> registrar en base cifrada
 -> clasificar texto
 -> detectar ausencia de consentimiento
 -> solicitar autorizacion
 -> registrar consentimiento
 -> procesar siguiente solicitud
 -> responder o escalar
```

### 7.2. Mensaje con riesgo

```text
Mensaje recibido
 -> registrar en base cifrada
 -> ejecutar detector local de riesgo
 -> forzar categoria consulta_clinica
 -> forzar accion escalar_crisis_emocional
 -> registrar escalamiento critical
 -> responder con orientacion inmediata
```

El riesgo se evalua antes de exigir consentimiento para evitar retrasar la
atencion de un usuario potencialmente vulnerable.

## 8. Human-In-The-Loop

Casos que el diseño deriva a humano:

| Situacion | Prioridad local |
|---|---|
| Riesgo emocional medio/alto/critico | `critical` en el prototipo. |
| Consulta clinica no critica | `urgent`. |
| PQR | `normal`. |
| Error de clasificacion automatica | `normal`. |
| Idioma diferente al espanol | Escalamiento humano. |

Implementado actualmente:

- Registro de `escalations` en SQLite.
- Estado `handoff` o `crisis_active` en la sesion.
- Consulta del registro por `GET /dev/escalations`.

No implementado aun:

- Panel del funcionario que toma el caso.
- Asignacion a profesionales.
- Respuesta humana enviada por el mismo canal.

## 9. Seguridad Y Privacidad En El Prototipo

| Control | Implementacion |
|---|---|
| Secretos fuera del codigo | `.env`, excluido de Git. |
| Cifrado de mensajes | Fernet antes de almacenar contenido en SQLite. |
| Cifrado de nombre | Fernet para el nombre recibido del canal. |
| Auditoria | Eventos con identificador de usuario hasheado. |
| Sesion WhatsApp QR | `wa_bridge/auth_info/`, excluida de Git. |
| Logs del bridge | No imprimen contenido completo del mensaje. |
| Idempotencia | `message_id_meta` evita procesar dos veces un mensaje entrante. |

## 10. Que Se Presenta Como Demo Y Que Como Futuro

| Funcionalidad | Estado de presentacion |
|---|---|
| Clasificador y riesgo | Implementado y probado. |
| API local | Implementada y probada. |
| SQLite cifrado | Implementado y probado dentro de flujos. |
| WhatsApp por QR | Implementado para demo local. |
| Azure OpenAI | Adaptador implementado; uso real requiere credenciales. |
| Meta Cloud API | Adaptador implementado; no requerido para la demo QR. |
| Integracion Compuconta/SIH | Arquitectura futura, no implementada. |
| Handoff con panel/Teams | Arquitectura futura, no implementada. |

