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
    urls_servicio       jsonb             -- partyId → URL JSON-RPC (D-131)
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
