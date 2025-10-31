-- Sociétés
create table if not exists company (
  id serial primary key,
  country text not null default 'FR',
  siren text unique,
  name text not null,
  naf text,
  headcount_band text,
  website text,
  phone_public text,
  last_filed_accounts_date date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Signaux normalisés
create table if not exists signal (
  id serial primary key,
  company_id int references company(id) on delete cascade,
  source text not null, -- 'BODACC' | 'BALO' | 'SIRENE' | 'PRESSE'
  type text not null,   -- 'PROC_COLLECTIVE' | 'SALE_OF_BUSINESS' | ...
  event_date date not null,
  url text not null,
  excerpt text not null,
  weight int not null,
  confidence numeric not null check (confidence between 0 and 1),
  created_at timestamptz default now()
);
create index if not exists idx_signal_company_date on signal (company_id, event_date);
create index if not exists idx_signal_type_date on signal (type, event_date);

-- Score journalier
create table if not exists company_score_daily (
  company_id int references company(id) on delete cascade,
  score_date date not null,
  score_total numeric not null,
  top_signal_type text,
  explanation text,
  primary key (company_id, score_date)
);

-- Clients
create table if not exists client (
  id serial primary key,
  name text not null,
  sector_focus text,
  email_primary text not null,
  alert_threshold int default 75,
  is_active boolean default true,
  created_at timestamptz default now()
);

-- Utilisateurs client
create table if not exists client_user (
  id serial primary key,
  client_id int references client(id) on delete cascade,
  full_name text not null,
  email text not null unique,
  password_hash text not null,
  role text default 'member',
  created_at timestamptz default now()
);

-- Secteurs suivis par client (préfixe NAF)
create table if not exists client_sector (
  client_id int references client(id) on delete cascade,
  naf_prefix text not null,
  primary key (client_id, naf_prefix)
);

-- PDFs générés
create table if not exists document_pdf (
  id serial primary key,
  client_id int references client(id) on delete cascade,
  company_id int references company(id) on delete set null,
  kind text not null, -- 'daily_brief' | 'weekly_digest'
  path text not null,
  published_at timestamptz not null,
  score numeric,
  top_signal_type text,
  sector_tag text,
  week_label text,
  created_at timestamptz default now()
);
create index if not exists idx_docpdf_client_kind_date on document_pdf (client_id, kind, published_at);
create index if not exists idx_docpdf_client_sector on document_pdf (client_id, sector_tag);
create index if not exists idx_docpdf_client_week on document_pdf (client_id, week_label);

-- Sociétés
create table if not exists company (
  id serial primary key,
  country text not null default 'FR',
  siren text unique,
  name text not null,
  naf text,
  headcount_band text,
  website text,
  phone_public text,
  last_filed_accounts_date date,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Signaux normalisés
create table if not exists signal (
  id serial primary key,
  company_id int references company(id) on delete cascade,
  source text not null, -- 'BODACC' | 'BALO' | 'SIRENE' | 'PRESSE'
  type text not null,   -- 'PROC_COLLECTIVE' | 'SALE_OF_BUSINESS' | ...
  event_date date not null,
  url text not null,
  excerpt text not null,
  weight int not null,
  confidence numeric not null check (confidence between 0 and 1),
  created_at timestamptz default now()
);
create index if not exists idx_signal_company_date on signal (company_id, event_date);
create index if not exists idx_signal_type_date on signal (type, event_date);

-- Score journalier
create table if not exists company_score_daily (
  company_id int references company(id) on delete cascade,
  score_date date not null,
  score_total numeric not null,
  top_signal_type text,
  explanation text,
  primary key (company_id, score_date)
);

-- Clients
create table if not exists client (
  id serial primary key,
  name text not null,
  sector_focus text,
  email_primary text not null,
  alert_threshold int default 75,
  is_active boolean default true,
  created_at timestamptz default now()
);

-- Utilisateurs client
create table if not exists client_user (
  id serial primary key,
  client_id int references client(id) on delete cascade,
  full_name text not null,
  email text not null unique,
  password_hash text not null,
  role text default 'member',
  created_at timestamptz default now()
);

-- Secteurs suivis par client (préfixe NAF)
create table if not exists client_sector (
  client_id int references client(id) on delete cascade,
  naf_prefix text not null,
  primary key (client_id, naf_prefix)
);

-- PDFs générés
create table if not exists document_pdf (
  id serial primary key,
  client_id int references client(id) on delete cascade,
  company_id int references company(id) on delete set null,
  kind text not null, -- 'daily_brief' | 'weekly_digest'
  path text not null,
  published_at timestamptz not null,
  score numeric,
  top_signal_type text,
  sector_tag text,
  week_label text,
  created_at timestamptz default now()
);
create index if not exists idx_docpdf_client_kind_date on document_pdf (client_id, kind, published_at);
create index if not exists idx_docpdf_client_sector on document_pdf (client_id, sector_tag);
create index if not exists idx_docpdf_client_week on document_pdf (client_id, week_label);
