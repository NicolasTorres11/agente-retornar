# Casos De Prueba Locales

Para la demostracion envia JSON a la ruta `POST /dev/simulate/pretty`. La
respuesta se presenta como texto legible con mensaje, respuesta del agente,
categoria, accion, confianza y riesgo.

```bash
BASE=http://127.0.0.1:8000/dev/simulate/pretty
curl -s -X POST "$BASE" -H 'Content-Type: application/json' \
  -d '{"wa_id":"demo","text":"Hola"}'
```

Usa el mismo `wa_id` dentro de un flujo. Usa un `wa_id` distinto para cada
caso independiente.

## Flujos Funcionales Para El Video

### Agenda Simulada

```bash
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"cita","text":"Hola"}'
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"cita","text":"SI AUTORIZO"}'
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"cita","text":"Necesito cita de control con psiquiatria por Sanitas, no urgente"}'
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"cita","text":"Opcion 1"}'
```

### Informacion Administrativa

```bash
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"admin","text":"Hola"}'
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"admin","text":"SI AUTORIZO"}'
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"admin","text":"Cuales son los horarios de atencion los sabados?"}'
```

### Crisis Emocional

```bash
curl -s -X POST "$BASE" -H 'Content-Type: application/json' -d '{"wa_id":"crisis","text":"Ya no le veo sentido a nada, mejor desaparecer"}'
```

La crisis no requiere consentimiento previo porque la seguridad se evalua
antes del flujo normal.

## Matriz De 40 Mensajes

| ID | Texto enviado | Categoria | Accion esperada |
|---|---|---|---|
| T001 | Hola, necesito agendar cita con psiquiatria | `solicitud_cita` | `solicitar_info_adicional` |
| T002 | Quiero una cita | `solicitud_cita` | `solicitar_info_adicional` |
| T003 | Olvide tomar la sertralina anoche, que hago | `consulta_clinica` | `escalar_humano` |
| T004 | Ya no le veo sentido a nada, mejor desaparecer | `consulta_clinica` | `escalar_crisis_emocional` |
| T005 | Me quiero matar, ya tengo las pastillas | `consulta_clinica` | `escalar_crisis_emocional` |
| T006 | Voy a poner una queja porque nadie me atiende | `pqr` | `escalar_humano` |
| T007 | Cuales son los horarios de atencion los sabados | `info_administrativa` | `responder_automatico` |
| T008 | Atienden por Sanitas | `info_administrativa` | `responder_automatico` |
| T009 | Hola buenas tardes | `no_relevante` | `responder_automatico` |
| T010 | Mensaje vacio | `no_relevante` | `ignorar` |
| T011 | Hi, I need to book an appointment with a psychiatrist | `solicitud_cita` | `escalar_humano` |
| T012 | Me corte anoche pero no fue grave | `consulta_clinica` | `escalar_crisis_emocional` |
| T013 | Necesito cancelar mi cita del jueves | `solicitud_cita` | `solicitar_info_adicional` |
| T014 | Reprogramar la consulta con el dr. Mendez | `solicitud_cita` | `solicitar_info_adicional` |
| T015 | Llevo tres dias sin dormir y me siento muy ansiosa | `consulta_clinica` | `escalar_humano` |
| T016 | Solicito copia de mi historia clinica | `pqr` | `escalar_humano` |
| T017 | Me cobraron mal la consulta, exijo devolucion | `pqr` | `escalar_humano` |
| T018 | Donde estan ubicados | `info_administrativa` | `responder_automatico` |
| T019 | Cuanto cuesta una consulta particular | `info_administrativa` | `responder_automatico` |
| T020 | Como solicito autorizacion de mi EPS | `info_administrativa` | `responder_automatico` |
| T021 | Gracias | `no_relevante` | `responder_automatico` |
| T022 | GANA 500.000 PESOS YA, enlace sospechoso | `no_relevante` | `ignorar` |
| T023 | Solo espacios | `no_relevante` | `ignorar` |
| T024 | Bonjour, je voudrais prendre rendez-vous | `solicitud_cita` | `escalar_humano` |
| T025 | Ayer pense en hacerme dano pero hoy estoy mejor | `consulta_clinica` | `escalar_crisis_emocional` |
| T026 | Necesito ayuda urgente | `consulta_clinica` | `escalar_humano` |
| T027 | Necesito cita YA, me siento muy mal | `solicitud_cita` | `solicitar_info_adicional` |
| T028 | Llame tres veces, nadie atiende, que horarios tienen | `pqr` | `escalar_humano` |
| T029 | Me siento triste pero ya estoy mejor que antes | `consulta_clinica` | `escalar_humano` |
| T030 | Vi una pelicula sobre suicidio, que triste | `no_relevante` | `escalar_humano` |
| T031 | Mi hijo de 14 anos esta muy deprimido, que hago | `consulta_clinica` | `escalar_humano` |
| T032 | Mi mama tiene 70 anos y necesita psiquiatra, tiene Sura | `solicitud_cita` | `solicitar_info_adicional` |
| T033 | Estoy embarazada y tomando aripiprazol, es riesgoso | `consulta_clinica` | `escalar_humano` |
| T034 | QUIERO HABLAR CON UNA PERSONA YA | `no_relevante` | `escalar_humano` |
| T035 | Voy a demandar a esta clinica, son unos irresponsables | `pqr` | `escalar_humano` |
| T036 | Estoy en la sede pero no encuentro psiquiatria, donde queda | `info_administrativa` | `responder_automatico` |
| T037 | Cuando entregan el certificado de incapacidad | `info_administrativa` | `responder_automatico` |
| T038 | kskskskskskksksksks | `no_relevante` | `ignorar` |
| T039 | Agendar cita de control con psiquiatria por Sanitas | `solicitud_cita` | `solicitar_info_adicional` |
| T040 | Horarios de atencion los sabados | `info_administrativa` | `responder_automatico` |

Ejecuta la matriz automaticamente:

```bash
python scripts/demo_classifier.py --offline --batch tests/fixtures/mensajes_prueba.json
```

Resultado esperado:

```text
Casos categoria/accion: 40/40 = 100.0%
Recall de escalamiento de crisis: 4/4 = 100.0%
```

## Alcance Actual

`T013` cancelar y `T014` reprogramar estan cubiertos como clasificacion de
gestion de cita. El subflujo conversacional especifico para cancelar o mover
una cita todavia no esta implementado; no se presenta como funcionalidad
completa en el video.
