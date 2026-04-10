--
-- PostgreSQL database dump
--

\restrict mdx6wVAtOUlFzft8CJ2v5hUJLsOgVKi5Aj0AqrHQ6cIdkfTcuTWOjhBmcwAjV3s

-- Dumped from database version 15.17 (Debian 15.17-1.pgdg13+1)
-- Dumped by pg_dump version 15.17 (Debian 15.17-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: book_files; Type: TABLE; Schema: public; Owner: vera
--

CREATE TABLE public.book_files (
    id integer NOT NULL,
    book_id integer NOT NULL,
    original_filename character varying(255) NOT NULL,
    stored_path character varying(500) NOT NULL,
    volume_number integer,
    editor character varying(255),
    translator character varying(255),
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.book_files OWNER TO vera;

--
-- Name: book_files_id_seq; Type: SEQUENCE; Schema: public; Owner: vera
--

CREATE SEQUENCE public.book_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.book_files_id_seq OWNER TO vera;

--
-- Name: book_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vera
--

ALTER SEQUENCE public.book_files_id_seq OWNED BY public.book_files.id;


--
-- Name: books; Type: TABLE; Schema: public; Owner: vera
--

CREATE TABLE public.books (
    id integer NOT NULL,
    collection character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    author character varying(255) NOT NULL,
    language character varying(50) NOT NULL,
    edition_label character varying(255) NOT NULL,
    source_label character varying(255) NOT NULL,
    is_primary_source boolean NOT NULL
);


ALTER TABLE public.books OWNER TO vera;

--
-- Name: books_id_seq; Type: SEQUENCE; Schema: public; Owner: vera
--

CREATE SEQUENCE public.books_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.books_id_seq OWNER TO vera;

--
-- Name: books_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vera
--

ALTER SEQUENCE public.books_id_seq OWNED BY public.books.id;


--
-- Name: chunks; Type: TABLE; Schema: public; Owner: vera
--

CREATE TABLE public.chunks (
    id integer NOT NULL,
    book_id integer NOT NULL,
    book_file_id integer,
    chapter_or_section character varying(255) NOT NULL,
    text text NOT NULL,
    sequence_index integer,
    volume integer,
    column_start integer,
    column_end integer,
    pdf_page integer,
    char_offset_start integer,
    char_offset_end integer,
    visual_anchor character varying(100) NOT NULL
);


ALTER TABLE public.chunks OWNER TO vera;

--
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: public; Owner: vera
--

CREATE SEQUENCE public.chunks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.chunks_id_seq OWNER TO vera;

--
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vera
--

ALTER SEQUENCE public.chunks_id_seq OWNED BY public.chunks.id;


--
-- Name: translations; Type: TABLE; Schema: public; Owner: vera
--

CREATE TABLE public.translations (
    id integer NOT NULL,
    chunk_id integer NOT NULL,
    language character varying(10) NOT NULL,
    text text NOT NULL,
    translator character varying(255),
    edition_label character varying(255)
);


ALTER TABLE public.translations OWNER TO vera;

--
-- Name: translations_id_seq; Type: SEQUENCE; Schema: public; Owner: vera
--

CREATE SEQUENCE public.translations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.translations_id_seq OWNER TO vera;

--
-- Name: translations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: vera
--

ALTER SEQUENCE public.translations_id_seq OWNED BY public.translations.id;


--
-- Name: book_files id; Type: DEFAULT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.book_files ALTER COLUMN id SET DEFAULT nextval('public.book_files_id_seq'::regclass);


--
-- Name: books id; Type: DEFAULT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.books ALTER COLUMN id SET DEFAULT nextval('public.books_id_seq'::regclass);


--
-- Name: chunks id; Type: DEFAULT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.chunks ALTER COLUMN id SET DEFAULT nextval('public.chunks_id_seq'::regclass);


--
-- Name: translations id; Type: DEFAULT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.translations ALTER COLUMN id SET DEFAULT nextval('public.translations_id_seq'::regclass);


--
-- Data for Name: book_files; Type: TABLE DATA; Schema: public; Owner: vera
--

COPY public.book_files (id, book_id, original_filename, stored_path, volume_number, editor, translator, created_at) FROM stdin;
1	1	migne_pl_vol4.pdf	pdfs/migne_pl_vol4.pdf	4	\N	\N	2026-04-10 23:24:39.31782
\.


--
-- Data for Name: books; Type: TABLE DATA; Schema: public; Owner: vera
--

COPY public.books (id, collection, title, author, language, edition_label, source_label, is_primary_source) FROM stdin;
1	PL	De Unitate Ecclesiae	São Cipriano de Cartago	Latim	Migne PL — edição 1844	Archive.org	t
\.


--
-- Data for Name: chunks; Type: TABLE DATA; Schema: public; Owner: vera
--

COPY public.chunks (id, book_id, book_file_id, chapter_or_section, text, sequence_index, volume, column_start, column_end, pdf_page, char_offset_start, char_offset_end, visual_anchor) FROM stdin;
1	1	1	Cap. 6	Habere jam non potest Deum patrem, qui Ecclesiam non habet matrem. Si potuit evadere quisquam qui extra arcam Noe fuit, et qui extra Ecclesiam foris fuerit evadit.	0	4	503	503	256	0	120	col503
\.


--
-- Data for Name: translations; Type: TABLE DATA; Schema: public; Owner: vera
--

COPY public.translations (id, chunk_id, language, text, translator, edition_label) FROM stdin;
1	1	pt	Não pode já ter Deus por Pai quem não tem a Igreja por Mãe. Se pôde escapar quem estava fora da arca de Noé, escapará também quem estiver fora da Igreja.	Anônimo	Tradução litúrgica tradicional
\.


--
-- Name: book_files_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vera
--

SELECT pg_catalog.setval('public.book_files_id_seq', 1, true);


--
-- Name: books_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vera
--

SELECT pg_catalog.setval('public.books_id_seq', 1, true);


--
-- Name: chunks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vera
--

SELECT pg_catalog.setval('public.chunks_id_seq', 1, true);


--
-- Name: translations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: vera
--

SELECT pg_catalog.setval('public.translations_id_seq', 1, true);


--
-- Name: book_files book_files_pkey; Type: CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.book_files
    ADD CONSTRAINT book_files_pkey PRIMARY KEY (id);


--
-- Name: books books_pkey; Type: CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.books
    ADD CONSTRAINT books_pkey PRIMARY KEY (id);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: translations translations_pkey; Type: CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.translations
    ADD CONSTRAINT translations_pkey PRIMARY KEY (id);


--
-- Name: book_files book_files_book_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.book_files
    ADD CONSTRAINT book_files_book_id_fkey FOREIGN KEY (book_id) REFERENCES public.books(id);


--
-- Name: chunks chunks_book_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_book_file_id_fkey FOREIGN KEY (book_file_id) REFERENCES public.book_files(id);


--
-- Name: chunks chunks_book_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.chunks
    ADD CONSTRAINT chunks_book_id_fkey FOREIGN KEY (book_id) REFERENCES public.books(id);


--
-- Name: translations translations_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vera
--

ALTER TABLE ONLY public.translations
    ADD CONSTRAINT translations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.chunks(id);


--
-- PostgreSQL database dump complete
--

\unrestrict mdx6wVAtOUlFzft8CJ2v5hUJLsOgVKi5Aj0AqrHQ6cIdkfTcuTWOjhBmcwAjV3s

