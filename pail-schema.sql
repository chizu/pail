CREATE TABLE facts (id serial primary key, fact text not null, tidbit text not null, verb text default 'is', RE bool not null, protected bool not null, mood smallint default null, chance smallint default null, unique (fact, tidbit, verb));
CREATE INDEX facts_fact_lower ON facts (lower(fact));
