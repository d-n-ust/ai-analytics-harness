-- Preset: the warehouse as a team has it before anyone has invested in it.
--
-- The generator's own tables, under the generator's own names, with nothing describing any of them.
-- `evt` mixes three event kinds behind an integer; `u.internal` is 0, 1 or NULL; `subs.st` is a
-- status code. Every trap in study 05 lives in this file's six lines.
--
-- SOURCES ARE QUALIFIED, and must stay that way. A view's references resolve in the READER's
-- search_path, and an arm's agent has only its own schema in scope — an unqualified `FROM evt`
-- here fails the moment the arm reads the view.

CREATE VIEW u     AS SELECT * FROM _source.u;
CREATE VIEW hab   AS SELECT * FROM _source.hab;
CREATE VIEW evt   AS SELECT * FROM _source.evt;
CREATE VIEW subs  AS SELECT * FROM _source.subs;
CREATE VIEW spend AS SELECT * FROM _source.spend;
CREATE VIEW ref   AS SELECT * FROM _source.ref;
