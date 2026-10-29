from generator import CEDENTS, ENDORSEMENT, XL_LIMIT, XL_RATE, XL_RETENTION, build_treaties, month_of

LINE_KEYWORDS = {"PROPERTY": "daños", "MOTOR": "autos", "MARINE": "marítimo"}
CEDENT_KEYWORDS = {"CED01": "sierra", "CED02": "costa azul", "CED03": "meridiano"}
LINE_NAMES = {
    "PROPERTY": "daños a la propiedad",
    "MOTOR": "autos",
    "MARINE": "transporte marítimo de carga",
}
COVERS = {
    "PROPERTY": "incendio, inundación, sismo y robo de los bienes asegurados",
    "MOTOR": "choque, robo total o parcial e inundación de los vehículos asegurados",
    "MARINE": "avería de la carga, robo e incendio durante el trayecto, la carga y la descarga",
}
EXCLUSIONS = {
    "PROPERTY": "Se excluyen los daños por guerra, terrorismo o reacción nuclear y el deterioro gradual de los bienes.",
    "MOTOR": "Se excluyen los vehículos usados en competencias, los conducidos sin licencia vigente o bajo los "
             "efectos del alcohol, y el desgaste mecánico.",
    "MARINE": "Se excluyen la mercancía mal embalada por el asegurado, la demora en la entrega y el vicio propio "
              "de la carga.",
}


def usd(amount):
    return f"USD {amount:,.0f}"


def treaty_clauses(t):
    cedent = next(name for code, name, *_ in CEDENTS if code == t["cedent_code"])
    line = LINE_NAMES[t["line_of_business"]]
    year = t["underwriting_year"]
    if t["treaty_type"] == "QS":
        share = round(t["ceded_share"] * 100)
        kind = "cuota parte"
        cession = (f"La cedente cede el {share}% de cada riesgo de la cartera, y el reasegurador participa "
                   f"en esa misma proporción de las primas y de los siniestros.")
        premium = f"La cedente paga al reasegurador el {share}% de la prima de cada mes."
        notice = "La cedente avisa al reasegurador de todo siniestro mayor a USD 250,000 dentro de los 30 días siguientes."
    else:
        kind = "exceso de pérdida"
        cession = (f"El reasegurador paga la parte de cada siniestro que exceda la retención de {usd(XL_RETENTION)}, "
                   f"hasta un límite de {usd(XL_LIMIT)} por siniestro. La cedente retiene el primer {usd(XL_RETENTION)}.")
        premium = (f"La prima de reaseguro es fija: {usd(XL_RATE * XL_LIMIT)} al año, el {round(XL_RATE * 100)}% del "
                   f"límite, pagadera en doce mensualidades iguales.")
        notice = (f"La cedente avisa al reasegurador de todo siniestro cuyo incurrido supere {usd(XL_RETENTION / 2)} "
                  f"dentro de los 15 días siguientes.")
    clauses = [
        ("Objeto", f"Contrato de {kind} que protege la cartera de {line} de {cedent} suscrita del "
                   f"{t['inception_date']} al {t['expiry_date']}. Cubre {COVERS[t['line_of_business']]}."),
        ("Cesión", cession),
        ("Prima", premium),
        ("Exclusiones", EXCLUSIONS[t["line_of_business"]]),
        ("Aviso de siniestros", notice),
        ("Bordereaux", "La cedente envía cada mes un bordereau de primas y otro de siniestros, a más tardar el día 15 "
                       "del mes siguiente."),
    ]
    number, at, share = ENDORSEMENT
    if t["treaty_number"] == number:
        clauses.append(("Endoso 1", f"A partir del {month_of(at).isoformat()} el porcentaje cedido baja del "
                                    f"{round(t['ceded_share'] * 100)}% al {round(share * 100)}%. Los siniestros "
                                    f"ocurridos antes de esa fecha conservan el porcentaje anterior."))
    header = f"Contrato {t['treaty_number']}, {cedent}, {line}, {year}."
    return [{"treaty_number": t["treaty_number"], "clause_no": i, "title": title,
             "cedent_key": CEDENT_KEYWORDS[t["cedent_code"]], "line_key": LINE_KEYWORDS[t["line_of_business"]],
             "year": str(year), "chunk": f"{header} Cláusula {i}, {title}: {text}"}
            for i, (title, text) in enumerate(clauses, start=1)]


def all_clauses(seed=7, years=(2024, 2025)):
    return [c for y in years for t in build_treaties(seed, y) for c in treaty_clauses(t)]