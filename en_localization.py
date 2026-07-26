from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


def _norm_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


_QUESTION_CORE_EN_RAW = {
    "que tipo de sistema de riego utiliza actualmente en su unidad productiva?": "What type of irrigation system do you currently use in your production unit?",
    "como define los horarios y la duracion del riego en el campo?": "How do you define irrigation schedules and duration in the field?",
    "como gestiona actualmente los inventarios de insumos, herramientas o productos agricolas (inventarios)?": "How do you currently manage inventories of agricultural inputs, tools, or products?",
    "como realiza actualmente el control de insumos y productos en su campo (inventarios)?": "How do you currently control inputs and products in your field (inventory)?",
    "como mide o estima la cantidad de agua que utiliza para riego": "How do you measure or estimate the amount of water used for irrigation?",
    "como mide o estima la cantidad de agua que utiliza para riego?": "How do you measure or estimate the amount of water used for irrigation?",
    "como esta estructurado el sistema de distribucion de agua en el campo?": "How is the field water distribution system structured?",
    "como registra actualmente la cantidad de produccion generada diariamente en su campo?": "How do you currently record the amount of production generated daily in your field?",
    "como registra y analiza la produccion agricola diaria en su empresa?": "How do you record and analyze daily agricultural production in your company?",
    "como evalua el rendimiento de su produccion agricola?": "How do you evaluate your agricultural production performance?",
    "que nivel de conocimiento tiene sobre los requisitos de certificacion agricola?": "What is your level of knowledge of agricultural certification requirements?",
    "cual es el nivel de conocimiento y aplicacion de certificaciones en su empresa agricola?": "What is the level of knowledge and application of certifications in your agricultural company?",
    "cual es su nivel de conocimiento o experiencia con procesos de exportacion agricola?": "What is your level of knowledge or experience with agricultural export processes?",
    "cual es el nivel de conocimiento y participacion en procesos de exportacion de su empresa?": "What is your company's level of knowledge and participation in export processes?",
    "como realiza el control de calidad de sus productos agricolas antes de la venta?": "How do you perform quality control of your agricultural products before sale?",
    "como realiza actualmente los pagos de remuneraciones a sus trabajadores?": "How do you currently process payroll payments for your workers?",
    "ha postulado o adjudicado fondos publicos o privados para su actividad agricola en los ultimos tres anos?": "Have you applied for or been awarded public or private funding for your agricultural activity in the last three years?",
    "como gestiona actualmente la relacion con sus proveedores de insumos agricolas?": "How do you currently manage relationships with your agricultural input suppliers?",
    "como gestiona actualmente la relacion con sus proveedores de insumos?": "How do you currently manage relationships with your input suppliers?",
    "como realiza y controla los pagos a sus proveedores?": "How do you make and control payments to your suppliers?",
    "utiliza canales digitales para vender sus productos agricolas?": "Do you use digital channels to sell your agricultural products?",
    "utiliza canales digitales para vender sus productos?": "Do you use digital channels to sell your products?",
    "que medios de pago ofrece actualmente a sus clientes?": "What payment methods do you currently offer your customers?",
    "cual es el nivel de formacion del principal tomador de decisiones en su unidad productiva?": "What is the education level of the main decision-maker in your production unit?",
    "como estan distribuidas las responsabilidades en su empresa agricola?": "How are responsibilities distributed in your agricultural company?",
    "como estan definidos los roles dentro de su organizacion?": "How are roles defined within your organization?",
    "que uso hace de tecnologias en la nube (cloud) en su empresa agricola?": "How do you use cloud technologies in your agricultural company?",
    "utiliza algun sistema o software instalado localmente en sus equipos para apoyar la gestion agricola?": "Do you use any locally installed systems or software on your equipment to support agricultural management?",
    "que tipo de software utiliza en su empresa y como lo gestiona?": "What type of software do you use in your company and how do you manage it?",
    "participa usted o su equipo en instancias de capacitacion o formacion tecnica relacionadas con la actividad agricola?": "Do you or your team participate in technical training related to agricultural activity?",
    "cuenta con apoyo tecnico para mejorar la produccion o gestion de su empresa agricola?": "Do you have technical support to improve production or management in your agricultural company?",
}
_QUESTION_CORE_EN = {_norm_key(k): v for k, v in _QUESTION_CORE_EN_RAW.items()}


_SOLUTION_NAME_EN_RAW = {
    "agromet para monitoreo agroclimatico y alertas": "AGROMET for Agroclimatic Monitoring and Alerts",
    "alertas agromet de heladas y golpes de calor": "AGROMET Frost and Heatwave Alerts",
    "all in one hp i5 en pc factory": "All in One HP i5 at PC Factory",
    "all in one lenovo en pc factory": "All in One Lenovo at PC Factory",
    "aula virtual prochile": "ProChile Virtual Classroom",
    "concurso cnr ley 18.450 para tecnificacion de riego": "CNR Law 18,450 Irrigation Technification Grant Call",
    "cursos en linea sence": "SENCE Online Courses",
    "defontana emprendedor": "Defontana Entrepreneur",
    "defontana punto de venta inicio": "Defontana POS Starter",
    "defontana valor pyme": "Defontana SME Value",
    "diplomados sociedad digital sence": "SENCE Digital Society Diploma Programs",
    "doctorado en ciencias de la agricultura y la naturaleza uc": "UC Doctoral Program in Agricultural and Natural Sciences",
    "fia giras y eventos de innovacion": "FIA Innovation Tours and Events",
    "indap programa de desarrollo de inversiones": "INDAP Investment Development Program",
    "inia sav(b)ia para programacion autonoma del riego": "INIA Sav(b)IA for Autonomous Irrigation Scheduling",
    "jumpseller advanced": "Jumpseller Advanced",
    "jumpseller basic": "Jumpseller Basic",
    "jumpseller plus": "Jumpseller Plus",
    "jumpseller premium": "Jumpseller Premium",
    "magister en gestion de empresas agroalimentarias uc": "UC Master's in Agrifood Business Management",
    "manuales y pautas sag para inocuidad y buenas practicas": "SAG Manuals and Guidelines for Food Safety and Good Practices",
    "mercado pago link de pago": "Mercado Pago Payment Link",
    "mercado pago point smart 2": "Mercado Pago Point Smart 2",
    "nubox modulo basico 1,75 uf": "Nubox Basic Module 1.75 UF",
    "nubox plan 5,75 uf": "Nubox Plan 5.75 UF",
    "nubox plan 8,00 uf": "Nubox Plan 8.00 UF",
    "nubox plan avanzado 2,45 uf": "Nubox Advanced Plan 2.45 UF",
    "portal del usuario prochile": "ProChile User Portal",
    "programa inia la cruz de riego presurizado con energia fotovoltaica": "INIA La Cruz Program for Pressurized Irrigation with Photovoltaic Energy",
    "programador orbit b-hyve wifi en sodimac": "Orbit B-hyve WiFi Controller at Sodimac",
    "programador orbit pocket star en sodimac": "Orbit Pocket Star Controller at Sodimac",
    "renacer digital en el agro": "Digital Renewal in Agriculture",
    "temporizador de riego orbit en sodimac": "Orbit Irrigation Timer at Sodimac",
    "transbank link de pago": "Transbank Payment Link",
    "transbank pack emprende": "Transbank Entrepreneur Pack",
    "transbank smart pos + link de pago": "Transbank Smart POS + Payment Link",
    "transbank webpay plus": "Transbank Webpay Plus",
    "tuberia pvc 25 mm x 3 m en sodimac": "PVC Pipe 25 mm x 3 m at Sodimac",
    "tuberia pvc 25 mm x 6 m en sodimac": "PVC Pipe 25 mm x 6 m at Sodimac",
    "valvula orbit con control de flujo en sodimac": "Orbit Valve with Flow Control at Sodimac",
    "valvula solenoide 1 pulgada orbit en sodimac": "Orbit 1-inch Solenoid Valve at Sodimac",
}
_SOLUTION_NAME_EN = {_norm_key(k): v for k, v in _SOLUTION_NAME_EN_RAW.items()}


_SOLUTION_DESC_EN_RAW = {
    "usar la plataforma publica agromet y su sistema de monitoreo y alertas para programar labores y riegos con informacion agroclimatica de libre acceso.": "Use the public AGROMET platform and its monitoring and alert system to schedule field operations and irrigation with open agroclimatic information.",
    "activar el sistema de alertas de agromet para ajustar ventanas de riego, labores criticas y decisiones productivas ante eventos meteorologicos extremos.": "Activate AGROMET alerts to adjust irrigation windows, critical operations, and production decisions during extreme weather events.",
    "escalar el puesto local a un equipo mas robusto para software administrativo, reporteria y operacion multiventana.": "Upgrade the local workstation to more robust hardware for administrative software, reporting, and multi-window operations.",
    "montar un puesto local de administracion, inventario o ventas con un equipo disponible en retail chileno para operacion on premise.": "Set up a local administration, inventory, or sales workstation using hardware available in Chilean retail for on-premise operation.",
    "fortalecer habilidades exportadoras, logisticas, comerciales y digitales con la oferta formativa oficial de prochile.": "Strengthen export, logistics, commercial, and digital capabilities through ProChile's official training offer.",
    "postular a un concurso de la cnr para cofinanciar obras de tecnificacion, conduccion intrapredial o mejoras de eficiencia hidrica en predios de chile central.": "Apply to a CNR grant call to co-finance irrigation technification works, on-farm conveyance, or water-efficiency improvements in central Chile farms.",
    "capacitar al equipo en habilidades digitales y de gestion con cursos asincronicos gratuitos disponibles a nivel nacional.": "Train the team in digital and management skills using free asynchronous courses available nationwide.",
    "partir la digitalizacion administrativa y comercial con el erp gratuito de defontana para registro basico de compras, gastos, ventas y cuentas por cobrar/pagar.": "Start administrative and commercial digitalization with Defontana's free ERP for basic records of purchases, expenses, sales, and accounts receivable/payable.",
    "formalizar operaciones de venta, stock y documentos tributarios con un pos chileno integrado y soporte continuo.": "Formalize sales operations, inventory control, and tax documentation with an integrated Chilean POS and ongoing support.",
    "escalar la gestion de la pyme a un erp cloud chileno con reglas de cobro por facturacion y dte, util para ordenar inventario, clientes y proveedores.": "Scale SME management to a Chilean cloud ERP with billing and DTE charging rules, useful for organizing inventory, customers, and suppliers.",
    "desarrollar competencias mas avanzadas en emprendimiento, gestion digital y reconversion tecnologica con diplomados gratuitos.": "Develop advanced capabilities in entrepreneurship, digital management, and technological transition through free diploma programs.",
    "escalar a un nivel de especializacion avanzada para liderar innovacion, analisis y estrategia con alta base tecnica.": "Advance to an expert specialization level to lead innovation, analysis, and strategy with strong technical grounding.",
    "usar instrumentos fia para conocer soluciones innovadoras y acelerar adopcion tecnologica con foco territorial y sectorial.": "Use FIA instruments to identify innovative solutions and accelerate technology adoption with territorial and sector focus.",
    "acceder a cofinanciamiento no reembolsable para activos productivos y tecnologicos que cierren brechas de madurez de la pyme.": "Access non-reimbursable co-financing for productive and technological assets that close SME maturity gaps.",
    "adoptar como hoja de ruta la solucion sav(b)ia desarrollada por inia la cruz para automatizar la programacion del riego segun sensores, fenologia y capacidad de retencion del suelo.": "Adopt the INIA La Cruz Sav(b)IA solution as a roadmap to automate irrigation scheduling based on sensors, phenology, and soil water-holding capacity.",
    "llevar la operacion a un estandar de comercio electronico mas exigente con mayor soporte, mejor logistica y herramientas avanzadas.": "Raise operations to a more demanding e-commerce standard with stronger support, better logistics, and advanced tools.",
    "abrir un canal formal de venta digital con una plataforma chilena de e-commerce apta para pequenos catalogos y operacion inicial.": "Open a formal digital sales channel using a Chilean e-commerce platform suited to small catalogs and early-stage operation.",
    "profesionalizar la tienda online con mas herramientas de catalogo, diseno y gestion comercial para venta regional y nacional.": "Professionalize the online store with stronger catalog, design, and commercial management tools for regional and national sales.",
    "consolidar comercio digital con funcionalidades avanzadas de promocion, catalogos y administracion multicanal.": "Consolidate digital commerce with advanced promotion features, catalog management, and multichannel administration.",
    "fortalecer el nivel educacional del tomador de decisiones con formacion avanzada en gestion del sector agroalimentario.": "Strengthen the decision-maker's educational profile with advanced training in agrifood sector management.",
    "adoptar guias y pautas oficiales del sag como base documental para estandarizar manejo, inocuidad y control de calidad.": "Adopt official SAG guides and protocols as a documentary base to standardize handling, food safety, and quality control.",
    "cobrar online sin sitio propio y con costo fijo cero, compartiendo links por canales digitales de uso cotidiano.": "Collect online payments without a dedicated website and with zero fixed fee by sharing links through everyday digital channels.",
    "habilitar cobro con tarjeta y boleta desde una maquina autonoma de bajo despliegue operativo para venta presencial.": "Enable card payments and receipt issuance from a standalone terminal with low operational complexity for in-person sales.",
    "implementar un modulo cloud chileno de nubox para contabilidad, administracion comercial, existencias, gestion, remuneraciones o portal, segun la brecha prioritaria del kpi.": "Implement a Chilean Nubox cloud module for accounting, commercial administration, inventory, management, payroll, or portal features, according to the KPI priority gap.",
    "escalar a un volumen mayor de transacciones y documentos para profesionalizar la operacion administrativa y comercial de la pyme.": "Scale to higher transaction and document volume to professionalize the SME's administrative and commercial operation.",
    "adoptar una configuracion de mayor capacidad para procesos administrativos y comerciales mas complejos o con mas volumen documental.": "Adopt a higher-capacity setup for more complex administrative and commercial processes or greater document volume.",
    "subir a una capa intermedia de digitalizacion con mayor capacidad documental y operativa dentro del ecosistema nubox.": "Move to an intermediate digitalization layer with stronger document and operational capacity within the Nubox ecosystem.",
    "registrar la empresa en prochile para acceder a herramientas, convocatorias y acompanamiento institucional para internacionalizacion.": "Register the company with ProChile to access tools, calls, and institutional support for internationalization.",
    "tomar como referencia tecnica y de implementacion el modelo validado por inia la cruz para sistemas de riego presurizado alimentados con energia solar en zonas de alta escasez hidrica.": "Use the INIA La Cruz validated model as a technical and implementation reference for solar-powered pressurized irrigation systems in high water-scarcity areas.",
    "incorporar control remoto y mayor automatizacion para operar riego por estaciones con conectividad y mejor ajuste operativo.": "Incorporate remote control and greater automation to run station-based irrigation with connectivity and better operational tuning.",
    "escalar desde horarios fijos simples a un controlador por estaciones que ordena sectores y reduce dependencia de operacion manual.": "Scale from simple fixed schedules to a station-based controller that organizes sectors and reduces dependence on manual operation.",
    "cerrar brechas basicas de alfabetizacion digital en agricultores y equipos rurales mediante talleres presenciales adaptados al territorio.": "Close basic digital literacy gaps among farmers and rural teams through in-person workshops adapted to local context.",
    "instalar un temporizador basico para salir del riego manual y fijar frecuencias minimas estables en huertos, viveros o sectores demostrativos.": "Install a basic timer to move away from manual irrigation and establish stable minimum irrigation frequencies in orchards, nurseries, or demonstration sectors.",
    "cobrar por whatsapp, redes sociales o correo con una solucion chilena simple, sin mensualidad fija y apta para formalizacion rapida.": "Collect payments via WhatsApp, social media, or email with a simple Chilean solution, no fixed monthly fee, and fast formalization.",
    "incorporar una maquinita presencial y link de pago en una misma solucion para ventas en predio, ferias y redes sociales.": "Combine an in-person card terminal and payment link in one solution for on-farm, fair, and social media sales.",
    "escalar a un punto de venta inteligente con control de stock y ventas en local o packing primario.": "Scale to a smart point-of-sale setup with inventory and sales control for stores or primary packing facilities.",
    "integrar pagos online al sitio web o e-commerce de la pyme para profesionalizar cobros y reducir dependencia de transferencias.": "Integrate online payments into the SME website or e-commerce channel to professionalize collections and reduce dependence on transfers.",
    "construir o reemplazar tramos basicos de conduccion intrapredial con tuberia de presion disponible en el retail chileno.": "Build or replace basic on-farm conveyance sections with pressure-rated piping available in Chilean retail.",
    "ampliar la red de conduccion con tuberia de mayor longitud para consolidar sectores de riego mas estables y permanentes.": "Expand the conveyance network with longer piping to consolidate more stable and permanent irrigation sectors.",
    "mejorar el control hidraulico del sector incorporando regulacion de flujo para una operacion mas fina del riego presurizado.": "Improve hydraulic sector control by adding flow regulation for more precise pressurized irrigation operation.",
    "sectorizar la distribucion de agua con una valvula electrica basica que facilita el paso desde sistemas mixtos a redes mas ordenadas.": "Sectorize water distribution with a basic electric valve to support transition from mixed systems to more organized networks.",
}
_SOLUTION_DESC_EN = {_norm_key(k): v for k, v in _SOLUTION_DESC_EN_RAW.items()}


_PRICE_DISPLAY_EN_RAW = {
    "31072 clp/month desde el mes 4; promocion de 14990 clp/month durante los primeros 3 meses": "CLP 31,072/month from month 4; promotional CLP 14,990/month for the first 3 months",
    "piloto o convenio; sin precio publico vigente clp": "Pilot or agreement; no current public price (CLP)",
    "postulacion o proyecto cofinanciado; sin precio publico unico clp": "Application or co-funded project; no single public price (CLP)",
    "sin precio publico unico; costo variable segun diametro, longitud, mano de obra y diseno hidraulico; requiere cotizacion clp": "No single public price; cost varies by diameter, length, labor, and hydraulic design; quotation required (CLP)",
    "sin precio publico unico; costo variable segun diametro, longitud, accesorios, mano de obra y superficie; requiere cotizacion clp": "No single public price; cost varies by diameter, length, accessories, labor, and coverage area; quotation required (CLP)",
    "sin precio publico vigente para el modelo especifico; requiere cotizacion de un equipo equivalente clp": "No current public price for the specific model; quotation for an equivalent device is required (CLP)",
    "11000000 clp total programa": "CLP 11,000,000 total program",
    "16720000 clp total programa": "CLP 16,720,000 total program",
}
_PRICE_DISPLAY_EN = {_norm_key(k): v for k, v in _PRICE_DISPLAY_EN_RAW.items()}


_DOMAIN_EN_RAW = {
    "agricultura y sostenibilidad hidrica": "Agriculture and Water Sustainability",
    "inventarios y sostenibilidad hidrica": "Agriculture and Water Sustainability",
    "gestion financiera": "Financial Management",
    "gestion de capacidades": "Capability Management",
    "gestion de la produccion y certificacion para la exportacion": "Production Management and Export Certification",
}
_DOMAIN_EN = {_norm_key(k): v for k, v in _DOMAIN_EN_RAW.items()}


_KDA_EN_RAW = {
    "agua para riego": "Irrigation Water",
    "certificacion": "Certification",
    "exportacion": "Export",
    "gestion comercial": "Commercial Management",
    "gestion de estrategias": "Strategy Management",
    "infraestructura ti": "IT Infrastructure",
    "manejo del agua": "Water Management",
    "manejo del riego": "Irrigation Management",
    "produccion": "Production",
    "productos de campo": "Field Products",
    "proveedores": "Suppliers",
    "recursos humanos": "Human Resources",
    "recursos financieros": "Financial Resources",
}
_KDA_EN = {_norm_key(k): v for k, v in _KDA_EN_RAW.items()}


_KPI_EN_RAW = {
    "cantidad de agua": "Water Quantity",
    "comprension de los estandares de certificacion": "Understanding of Certification Standards",
    "cumplimiento de roles": "Role Compliance",
    "estandares de control de calidad": "Quality Control Standards",
    "fondos concursables": "Competitive Funding Access",
    "formacion exportadora": "Export Training",
    "gestion de inventarios": "Inventory Management",
    "gestion de proveedores": "Supplier Management",
    "iniciativas de formacion": "Training Initiatives",
    "nivel educacional": "Education Level",
    "pago de proveedores": "Supplier Payments",
    "produccion diaria": "Daily Production",
    "programacion de riego": "Irrigation Scheduling",
    "remuneraciones": "Payroll",
    "rendimiento": "Performance",
    "sistema de riego": "Irrigation System",
    "sistemas de distribucion": "Distribution Systems",
    "sistemas de pago": "Payment Systems",
    "soporte tecnico": "Technical Support",
    "tecnologia cloud": "Cloud Technology",
    "tecnologia on premise": "On-premise Technology",
    "ventas online": "Online Sales",
}
_KPI_EN = {_norm_key(k): v for k, v in _KPI_EN_RAW.items()}


def _load_json_map(rel_path: str) -> dict[str, str]:
    path = Path(__file__).resolve().parent / rel_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


_OPTION_EN_FILE_MAP = _load_json_map("assets/localization/options_en.json")
_OPTION_EN = {_norm_key(k): v for k, v in _OPTION_EN_FILE_MAP.items()}


def localize_question_prompt(prompt: str, qnum: int | None = None, language: str = "en") -> str:
    raw = str(prompt or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    number = qnum
    core = raw
    match = re.match(r"^\s*(?:Pregunta|Question)\s*(\d+)\s*:\s*(.+)$", raw, flags=re.IGNORECASE)
    if match:
        number = int(match.group(1))
        core = match.group(2).strip()
    translated = _QUESTION_CORE_EN.get(_norm_key(core))
    if translated is None:
        translated = core
    if number is not None:
        return f"Question {int(number)}: {translated}"
    return translated


def localize_option_text(option: str, language: str = "en") -> str:
    raw = str(option or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _OPTION_EN.get(_norm_key(raw), raw)


def localize_solution_name(name: str, language: str = "en") -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _SOLUTION_NAME_EN.get(_norm_key(raw), raw)


def localize_solution_description(description: str, language: str = "en") -> str:
    raw = str(description or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _SOLUTION_DESC_EN.get(_norm_key(raw), raw)


def localize_price_display(price: str, language: str = "en") -> str:
    raw = str(price or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _PRICE_DISPLAY_EN.get(_norm_key(raw), raw)


def localize_domain(domain: str, language: str = "en") -> str:
    raw = str(domain or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _DOMAIN_EN.get(_norm_key(raw), raw)


def localize_kda(kda: str, language: str = "en") -> str:
    raw = str(kda or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _KDA_EN.get(_norm_key(raw), raw)


def localize_kpi(kpi: str, language: str = "en") -> str:
    raw = str(kpi or "").strip()
    if not raw:
        return ""
    if str(language).lower() != "en":
        return raw
    return _KPI_EN.get(_norm_key(raw), raw)
