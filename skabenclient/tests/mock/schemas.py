# sql schemas for testing

test = """

CREATE TABLE IF NOT EXISTS "test" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
  "uid" integer NOT NULL, 
  "sound" bool default 0 NOT NULL
);

"""