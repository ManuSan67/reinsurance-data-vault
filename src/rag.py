EMBEDDING_MODEL = "databricks-gte-large-en"
CHAT_MODEL = "databricks-meta-llama-3-3-70b-instruct"

PROMPT = ("Eres analista de una reaseguradora. Responde en español usando solo las cláusulas de abajo y cita "
          "el contrato y el número de cláusula. Si la respuesta no está en las cláusulas, di que no la encuentras "
          "en los contratos.")


def load_sql(kb, view):
    return f"""CREATE OR REPLACE TABLE {kb}.treaty_clauses AS
SELECT *, ai_query('{EMBEDDING_MODEL}', chunk) AS embedding FROM {view}"""


def search_sql(kb, top_k):
    return f"""WITH q AS (SELECT ai_query('{EMBEDDING_MODEL}', :question) AS v)
SELECT c.treaty_number, c.clause_no, c.title, c.chunk,
       aggregate(zip_with(c.embedding, q.v, (a, b) -> a * b), 0D, (acc, x) -> acc + x)
       / sqrt(aggregate(c.embedding, 0D, (acc, x) -> acc + x * x) * aggregate(q.v, 0D, (acc, x) -> acc + x * x))
         AS similarity,
       (CASE WHEN instr(lower(:question), c.cedent_key) > 0 THEN 1 ELSE 0 END
        + CASE WHEN instr(lower(:question), c.line_key) > 0 THEN 1 ELSE 0 END
        + CASE WHEN instr(:question, c.year) > 0 THEN 1 ELSE 0 END) AS metadata_matches,
       size(array_intersect(
         filter(split(regexp_replace(lower(:question), '[^a-z0-9áéíóúñü]+', ' '), ' '), w -> length(w) > 4),
         split(regexp_replace(lower(c.chunk), '[^a-z0-9áéíóúñü]+', ' '), ' '))) AS keyword_matches
FROM {kb}.treaty_clauses c CROSS JOIN q
ORDER BY metadata_matches DESC, keyword_matches DESC, similarity DESC
LIMIT {top_k}"""


def answer_sql(kb, top_k):
    return f"""WITH hits AS ({search_sql(kb, top_k)}),
context AS (
  SELECT concat_ws(char(10), collect_list(chunk)) AS clauses,
         collect_list(concat(treaty_number, ' cláusula ', clause_no)) AS sources
  FROM hits
)
SELECT ai_query('{CHAT_MODEL}',
                concat('{PROMPT}', char(10), char(10), clauses, char(10), char(10), 'Pregunta: ', :question)) AS answer,
       sources
FROM context"""