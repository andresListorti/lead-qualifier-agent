# Lead Qualifier Agent

[English](README.md) | **Español**

[![CI](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/andresListorti/lead-qualifier-agent/actions/workflows/ci.yml)

> **Proyecto de portfolio — solo DATOS DE DEMO — no es un sistema en producción.**

Un servicio chico hecho con FastAPI. Recibe leads de ventas (posibles clientes) y los califica
con un agente: un puntaje y una categoría, `hot` (caliente), `warm` (tibio) o `cold` (frío).
Los guarda en MySQL y los expone a través de una API protegida con Auth0 (JWT, RS256, RBAC).

Está hecho para mostrar un stack de backend realista de punta a punta: FastAPI, Pydantic v2,
SQLAlchemy 2, Alembic, MySQL, Auth0, GitHub Actions y empaquetado para AWS Lambda (listo, pero
sin desplegar, por decisión).

## Dos maneras de verlo

La misma API, mientras corre, ofrece dos vistas. Cada una tiene un enlace a la otra.

| Vista | Dirección | Para quién |
| --- | --- | --- |
| **Vista simple** | `http://127.0.0.1:8000/` | Cualquiera. Tiene un formulario y un resultado con colores. Trae pruebas de un clic (idempotencia, validación y login) y un registro "Lo técnico" con cada pedido HTTP real: headers, body y el equivalente en curl. Se puede pasar de español a inglés y de modo claro a oscuro. |
| **Vista técnica** | `http://127.0.0.1:8000/docs` | Perfiles técnicos. Es Swagger UI, generado a partir del esquema OpenAPI, y trae el botón `Authorize` para el token de Auth0. |

La vista simple (`web/index.html`) es una página sin dependencias que funciona como cliente de
los endpoints públicos. No agrega endpoints nuevos y no aparece en el esquema OpenAPI.

## Conceptos explicados

- **API:** un programa que no tiene pantalla propia; recibe pedidos y devuelve datos. Las dos
  vistas de arriba son maneras de hablarle.
- **Endpoint:** cada "puerta" de la API. Por ejemplo, `POST /leads` crea un lead y
  `GET /leads` los lista.
- **Métodos HTTP:** `GET` lee datos y `POST` crea datos nuevos.
- **Códigos de respuesta:** el número que devuelve la API.
  - `200`: OK.
  - `201`: creado.
  - `401`: no estás identificado.
  - `403`: estás identificado pero no tenés permiso.
  - `404`: no existe.
  - `422`: los datos que mandaste son inválidos.
  - `429`: mandaste demasiados pedidos seguidos.
  - `503`: un servicio del que depende la API no está disponible.
- **JSON:** el formato de texto en el que viajan los datos, por ejemplo `{"name": "Ana"}`.
- **Base de datos (MySQL):** donde quedan guardados los leads. Corre adentro de **Docker**, un
  programa que levanta servicios aislados sin instalarlos en Windows.
- **Migraciones (Alembic):** los pasos versionados que crean o cambian las tablas de la base.
- **Token / JWT:** una "credencial" firmada que emite **Auth0**, un servicio de login. La API
  verifica la firma y que el token traiga el permiso `read:leads`.
- **Idempotencia:** si llega dos veces el mismo pedido con la misma clave (`Idempotency-Key`),
  la API no crea un duplicado y devuelve el lead original. Sirve para dobles clics y reintentos.
- **Rate limit:** un límite de pedidos por minuto para cada IP, que frena abusos.
- **Tests y CI:** los tests son programas que verifican el código solos. CI (GitHub Actions) los
  corre en cada cambio que se sube a GitHub.

## Stack

| Área | Elección |
| --- | --- |
| API | Python 3.13, FastAPI, Pydantic v2 |
| Datos | MySQL 8 (Docker), SQLAlchemy 2, migraciones con Alembic |
| Login | Tokens de acceso de Auth0, RS256 validado contra el JWKS del tenant |
| Agente | Protocolo `LLMProvider`: proveedor de reglas fijas (por defecto) u opcional Gemini, plan gratuito |
| CI | GitHub Actions: ruff, pytest, migraciones y datos demo contra un MySQL de servicio |
| Tests | pytest, SQLite, 62 tests |

## Endpoints

| Método | Ruta | Login | Qué hace |
| --- | --- | --- | --- |
| GET | `/health` | público | Verifica que la API y la base respondan |
| POST | `/leads` | público | Crea y califica un lead (201). Con `Idempotency-Key`, un reenvío devuelve el original (200). Límite por IP (429) |
| GET | `/leads` | `read:leads` | Lista leads (`offset`, `limit` ≤ 100) |
| GET | `/leads/{id}` | `read:leads` | Trae un lead |

Con el servidor corriendo, la vista simple está en `/` y la documentación interactiva en `/docs`.

## Confiabilidad

`POST /leads` acepta un header opcional `Idempotency-Key`, de 1 a 100 caracteres: letras ASCII,
números, guiones bajos o guiones. Una clave inválida devuelve `422`.

- **Clave nueva:** crea el lead y devuelve `201`.
- **Clave ya usada:** devuelve el lead original con `200`, sin volver a llamar al agente, aunque
  los datos enviados hayan cambiado. Las claves son globales y se guardan junto con el lead, así
  que conviene usar una clave nueva para cada lead.
- **Sin clave:** cada pedido crea un lead nuevo.

La columna de la clave la agrega la migración `0002`, con un índice único: se aplica con
`alembic upgrade head`.

Ese índice único resuelve los envíos simultáneos: si hay conflicto al guardar, la sesión se
deshace y devuelve el registro ganador con `200`. Dos pedidos que se cruzan pueden calificar los
dos antes de guardar. Lo que se garantiza es un solo lead guardado por clave, no que el agente
corra una sola vez.

`RATE_LIMIT_PER_MINUTE` vale `30` por defecto; con `0` se desactiva. Es una ventana fija en
memoria, segura entre hilos, que limita los POST por IP.

- **Al superar el límite:** devuelve `429` con `Retry-After`, en segundos.
- **Qué cuenta:** los reenvíos y los pedidos rechazados también consumen el cupo. Los GET no se
  limitan.
- **Detrás de un proxy:** el límite usa la dirección del cliente ASGI, así que el proxy tiene que
  pasar la IP correcta. No se confía en headers reenviados.

**Solo por proceso:** al reiniciar se vacían los contadores, y varias instancias o Lambdas no los
comparten. En producción esto viviría en API Gateway o en Redis. Esta implementación de portfolio
no es un límite distribuido de producción.

## Diseño de seguridad

- Solo se acepta **RS256**. El algoritmo está fijo en el código y nunca se toma del header del
  token.
- La firma se verifica contra el JWKS de Auth0 (con caché). `iss`, `aud` y `exp` son
  obligatorios.
- El permiso se lee del claim RBAC `permissions` (o de `scope`). Un claim con tipo incorrecto no
  da ningún permiso.
- Sin token o con un token inválido → `401`. Token válido sin permiso → `403`. Auth0 sin
  configurar o caído → `503`: **falla cerrado**, nunca abierto.
- Los mensajes de error son genéricos: la API nunca dice por qué rechazó un token.
- Hay tests para estos ataques y errores:
  - confusión de algoritmo (HS256 firmado con la clave pública);
  - `alg=none`;
  - clave equivocada;
  - audience o issuer equivocados;
  - token vencido;
  - claims faltantes.
- No hay secretos en el repo: la configuración viene de variables de entorno (`.env.example`).

## El agente

`qualify_lead` le pide a un `LLMProvider` un resultado `{tier, score, reasons, suggested_reply}`
y lo valida: la categoría tiene que coincidir con el puntaje (hot ≥ 70, warm ≥ 40, si no cold).
Si falla, reintenta una vez. Si el proveedor sigue fallando o contesta algo incoherente, usa un
resultado seguro de respaldo.

- **`FixtureProvider` (por defecto):** reglas fijas, sin red y sin costo. Es el que usan los
  tests, CI y el demo.
  - Arranca en 20 puntos.
  - Suma 50 si el presupuesto es de 5000 USD o más, o 25 si es de 1000 USD o más.
  - Suma 20 si el mensaje tiene una palabra de interés o urgencia: urgent, urgente, demo, meeting
    o reunión.
- **`GeminiProvider` (opcional):** solo se activa con `GEMINI_API_KEY` **y**
  `GEMINI_FREE_TIER_CONFIRMED=true`, para que no pueda gastar plata por accidente.

## Correrlo en tu máquina

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install fastapi pydantic sqlalchemy alembic pymysql cryptography "pyjwt[crypto]" \
    uvicorn httpx python-dotenv pytest ruff
cp .env.example .env            # después, completá las contraseñas de MySQL
docker compose up -d            # MySQL 8 en 127.0.0.1:3306
alembic upgrade head
python -m api.app.seed          # 10 leads de DATOS DE DEMO (no duplica si ya están)
uvicorn api.app.main:app --reload
```

Después abrí `http://127.0.0.1:8000/` (vista simple) y `http://127.0.0.1:8000/docs`
(vista técnica).

Para correr los controles:

```bash
ruff check .
pytest -q
```

Para usar los endpoints protegidos:

1. Creá una API en Auth0 con el permiso `read:leads`.
2. Completá `AUTH0_DOMAIN` y `AUTH0_AUDIENCE` en `.env`.
3. Mandá el token como `Authorization: Bearer <token>`.

## AWS (serverless, listo pero sin desplegar)

`api/lambda_handler.py` envuelve la app de FastAPI con Mangum. `template.yaml` (AWS SAM) define
una función Lambda detrás de una HTTP API de API Gateway, sin RDS, EC2, NAT ni balanceador de
carga. `DATABASE_URL` apunta a un MySQL externo y se pasa como parámetro `NoEcho`.

El template se revisa con `cfn-lint` en CI, y el handler tiene tests. Este repo **no** se
desplegó en AWS: está preparado para hacerlo.

```bash
sam build
sam local start-api          # corre Lambda + API Gateway localmente en Docker
```

## Hoja de ruta

- [x] Fase 1: API, MySQL, migraciones, agente, tests
- [x] Fase 2: validación de JWT de Auth0 con RBAC
- [x] Fase 3: CI con GitHub Actions
- [x] Fase 4a: listo para AWS: handler de Lambda (Mangum) y template SAM (Lambda + HTTP API), revisados en CI. **Sin desplegar**, por decisión
- [x] Demo de confiabilidad: creación idempotente de leads y límite de pedidos por IP en cada proceso
- [x] Vista simple en `/`: cliente HTML de la API, bilingüe (ES / EN)
- [ ] Fase 4b: despliegue real en el plan gratuito de AWS, con GitHub OIDC (sin claves de larga duración)
- [ ] Opcional: frontend completo en Next.js

## Licencia

MIT
