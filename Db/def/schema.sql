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
        rsh_robot_id,
        rsh_user_id,
        rsh_status,
        rsh_timestamp
    )
    VALUES (
        NEW.r_id,
        NEW.r_user_id,
        NEW.r_status,
        NEW.r_timestamp
    );
    RETURN NEW; -- El valor de retorno se ignora en triggers AFTER, pero es buena práctica.
END;
$$;


--
-- Name: update_robot_status_timestamp_function(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_robot_status_timestamp_function() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   NEW.r_timestamp = NOW();
   RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: robot_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.robot_status_history (
    rsh_id integer NOT NULL,
    rsh_status character varying(255) NOT NULL,
    rsh_timestamp timestamp with time zone NOT NULL,
    rsh_robot_id integer NOT NULL,
    rsh_user_id integer
);


--
-- Name: robot_status_history_rsh_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.robot_status_history_rsh_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: robot_status_history_rsh_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.robot_status_history_rsh_id_seq OWNED BY public.robot_status_history.rsh_id;


--
-- Name: robots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.robots (
    r_id integer NOT NULL,
    r_name character varying(255) NOT NULL,
    r_description character varying(255),
    r_status character varying(255) NOT NULL,
    r_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    r_user_id integer
);


--
-- Name: robots_r_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.robots_r_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: robots_r_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.robots_r_id_seq OWNED BY public.robots.r_id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: seeds_schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seeds_schema_migrations (
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
-- Name: robot_status_history rsh_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history ALTER COLUMN rsh_id SET DEFAULT nextval('public.robot_status_history_rsh_id_seq'::regclass);


--
-- Name: robots r_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots ALTER COLUMN r_id SET DEFAULT nextval('public.robots_r_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: robot_status_history robot_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_pkey PRIMARY KEY (rsh_id);


--
-- Name: robots robots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_pkey PRIMARY KEY (r_id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: seeds_schema_migrations seeds_schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seeds_schema_migrations
    ADD CONSTRAINT seeds_schema_migrations_pkey PRIMARY KEY (version);


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
-- Name: robots update_robot_status_timestamp_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_robot_status_timestamp_trigger BEFORE UPDATE ON public.robots FOR EACH ROW EXECUTE FUNCTION public.update_robot_status_timestamp_function();


--
-- Name: robot_status_history robot_status_history_rsh_robot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_rsh_robot_id_fkey FOREIGN KEY (rsh_robot_id) REFERENCES public.robots(r_id) ON DELETE CASCADE;


--
-- Name: robot_status_history robot_status_history_rsh_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robot_status_history
    ADD CONSTRAINT robot_status_history_rsh_user_id_fkey FOREIGN KEY (rsh_user_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: robots robots_r_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_r_user_id_fkey FOREIGN KEY (r_user_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20250714193959'),
    ('20250829021010');
