SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: user_action; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_action AS ENUM (
    'Girar',
    'Pinzar',
    'Reverencia'
);


--
-- Name: user_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_status AS ENUM (
    'profe',
    'alumno'
);


--
-- Name: log_robot_status_change_function(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.log_robot_status_change_function() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO robot_status_history (
        robot_id,
        user_id,
        status,
        timestamp
    )
    VALUES (
        NEW.id,
        NEW.user_id,
        NEW.status,
        NOW()
    );
    RETURN NEW; -- El valor de retorno se ignora en triggers AFTER, pero es buena práctica.
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: robot_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.robot_status_history (
    id integer NOT NULL,
    status character varying(255) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    robot_id uuid NOT NULL,
    user_id integer
);


--
-- Name: robot_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.robot_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: robot_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.robot_status_history_id_seq OWNED BY public.robot_status_history.id;


--
-- Name: robots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.robots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    external_identifier character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(255),
    psw character varying(255) NOT NULL,
    status character varying(255) NOT NULL,
    user_id integer
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nombrecompleto character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    usr_name character varying(255) NOT NULL,
    usr_psw character varying(255) NOT NULL,
    statuss public.user_status,
    usr_pronouns character varying(255),
    accion public.user_action
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: robot_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history ALTER COLUMN id SET DEFAULT nextval('public.robot_status_history_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: robot_status_history robot_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_pkey PRIMARY KEY (id);


--
-- Name: robots robots_external_identifier_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_external_identifier_key UNIQUE (external_identifier);


--
-- Name: robots robots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_usr_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_usr_name_key UNIQUE (usr_name);


--
-- Name: robots log_robot_status_change_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER log_robot_status_change_trigger AFTER INSERT OR UPDATE ON public.robots FOR EACH ROW EXECUTE FUNCTION public.log_robot_status_change_function();


--
-- Name: robot_status_history robot_status_history_robot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_robot_id_fkey FOREIGN KEY (robot_id) REFERENCES public.robots(id) ON DELETE CASCADE;


--
-- Name: robot_status_history robot_status_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: robots robots_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20250714193959'),
    ('20250829021010');
