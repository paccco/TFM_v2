-- Estado externalizado (D-04, D-69, `maquina-estados.md` §3). Solo las columnas que usa cada rama;
-- las siguientes lo amplían mientras no haya datos que conservar.

CREATE TABLE IF NOT EXISTS peticiones (
    request_id uuid PRIMARY KEY,          -- creación condicional (D-67, D-83)
    comprador  text NOT NULL,
    version    integer NOT NULL,          -- escritura condicional (D-63, D-101)
    rondas     jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS sesiones (
    session_id          uuid PRIMARY KEY, -- creación condicional (D-67)
    request_id          uuid NOT NULL REFERENCES peticiones,
    ronda               integer NOT NULL,
    item_id             text NOT NULL,
    config              jsonb NOT NULL,   -- valores efectivos (D-91)
    version             integer NOT NULL, -- D-63
    instancia           text,             -- arrendamiento (D-63, D-65)
    arrendamiento_hasta timestamptz,
    estado              text NOT NULL,
    subestado           text,
    turn                integer,
    attempt             integer,
    message_id          text,             -- D-66
    failed_party_id     text,             -- D-99
    urls_servicio       jsonb,            -- partyId → URL JSON-RPC (D-131)
    context_ids         jsonb NOT NULL DEFAULT '{}', -- partyId → contextId (D-20)
    task_id             text,             -- intento en curso, solo en AWAITING_TASK (D-58)
    inicio_intento      timestamptz,      -- D-52, D-65
    oferta_vigente      jsonb,
    emisor_oferta       text,
    oferta_acordada     jsonb,            -- HELD (D-42, D-84)
    held_until          timestamptz,      -- D-86
    envios_agreement    jsonb,            -- partyId → PENDIENTE (D-85)
    resultado           jsonb,            -- desde CLOSING (D-53, D-82)
    envios_close        jsonb             -- partyId → PENDIENTE (D-64)
);

-- Registros de solo añadir (`maquina-estados.md` §3), con el reloj de la base de datos (D-69).
CREATE TABLE IF NOT EXISTS actos_aceptados (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sesiones,
    turn       integer NOT NULL,
    emisor     text NOT NULL,
    tipo       text NOT NULL,
    oferta     jsonb,
    reason     text,
    task_id    text NOT NULL,
    instante   timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS fallos (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sesiones,
    turn       integer NOT NULL,
    attempt    integer NOT NULL,
    task_id    text,
    code       text NOT NULL,
    field      text NOT NULL,
    instante   timestamptz NOT NULL
);

-- Sin uso en v0.1.0, que solo admite STRICT (D-11): lo llena feature/autocorreccion.
CREATE TABLE IF NOT EXISTS coerciones (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES sesiones,
    turn       integer NOT NULL,
    attempt    integer NOT NULL,
    task_id    text NOT NULL,
    code       text NOT NULL,
    field      text NOT NULL,
    original   jsonb,
    corregido  jsonb,
    decision   text NOT NULL,                -- R-xx (D-123)
    instante   timestamptz NOT NULL
);

-- Tasks de las peticiones del comprador (D-97, D-127), con la identidad que las creó (D-128).
CREATE TABLE IF NOT EXISTS tareas (
    task_id   uuid PRIMARY KEY,
    identidad text NOT NULL,
    datos     jsonb NOT NULL
);

-- Registro de solo añadir de las peticiones del comprador (D-89, D-98, D-103, D-128).
CREATE TABLE IF NOT EXISTS registro_peticiones (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo       text,
    request_id uuid,
    ronda      integer,
    sender     text,
    identidad  text NOT NULL,
    message_id text NOT NULL,
    task_id    uuid NOT NULL,
    resultado  text NOT NULL,
    codigos    text[] NOT NULL,
    instante   timestamptz NOT NULL DEFAULT clock_timestamp() -- reloj único (D-69)
);

-- D-98, D-128: un sender suplantado no cuenta para la unicidad.
CREATE UNIQUE INDEX IF NOT EXISTS registro_peticiones_unica
    ON registro_peticiones (sender, message_id)
    WHERE sender = identidad;

-- Registro de envíos de control (D-70, D-85): uno por envío de AGREEMENT_HELD o SESSION_CLOSE.
CREATE TABLE IF NOT EXISTS envios_control (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  uuid NOT NULL REFERENCES sesiones,
    tipo        text NOT NULL,
    parte       text NOT NULL,
    turn        integer NOT NULL,
    instante    timestamptz NOT NULL,   -- el de la escritura de la marca (D-69)
    resultado   text NOT NULL,          -- ENVIADO o FALLIDO
    task_id     text,
    estado_task text,
    con_message boolean NOT NULL,
    code        text                    -- AGENT_UNREACHABLE, TURN_TIMEOUT o AGENT_ERROR
);
