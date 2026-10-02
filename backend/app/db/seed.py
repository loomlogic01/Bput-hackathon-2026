"""
Database seeding script for the ESG/BRSR platform.
Seeds initial metadata, demo organization hierarchy, reporting period, BRSR framework structure, and system roles/permissions.
Safe to execute multiple times (idempotent / get-or-create pattern).
"""

from datetime import date
import logging

from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal
from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRIndicator,
    BRSRPrinciple,
    BRSRQuestion,
    BRSRSection,
    IndicatorType,
    QuestionResponseType,
)
from backend.app.db.models.organization import (
    BusinessUnit,
    Entity,
    Organization,
    Project,
)
from backend.app.db.models.reporting import ReportingBoundary, ReportingPeriod
from backend.app.db.models.user import Permission, Role, SystemRole, User
from backend.app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_db(db: Session) -> dict:
    """
    Seeds initial demonstration and metadata records into the database.
    Returns a dictionary summarizing records processed/created.
    """
    counts = {
        "organizations": 0,
        "entities": 0,
        "business_units": 0,
        "projects": 0,
        "reporting_periods": 0,
        "frameworks": 0,
        "sections": 0,
        "principles": 0,
        "indicators": 0,
        "questions": 0,
        "roles": 0,
        "permissions": 0,
        "users": 0,
    }

    # 1. Organization Hierarchy
    org = db.query(Organization).filter_by(code="MEIL").first()
    if not org:
        org = Organization(
            name="MEIL Group",
            code="MEIL",
            description="Megha Engineering & Infrastructures Limited Group",
        )
        db.add(org)
        db.flush()
        counts["organizations"] += 1
        logger.info("Created Organization: %s", org.name)

    entity = db.query(Entity).filter_by(code="MEIL-ENG", organization_id=org.id).first()
    if not entity:
        entity = Entity(
            name="MEIL Infrastructure Ltd",
            code="MEIL-ENG",
            organization_id=org.id,
        )
        db.add(entity)
        db.flush()
        counts["entities"] += 1
        logger.info("Created Entity: %s", entity.name)

    bu = db.query(BusinessUnit).filter_by(code="BU-ENERGY", entity_id=entity.id).first()
    if not bu:
        bu = BusinessUnit(
            name="Renewable Energy Division",
            code="BU-ENERGY",
            entity_id=entity.id,
        )
        db.add(bu)
        db.flush()
        counts["business_units"] += 1
        logger.info("Created Business Unit: %s", bu.name)

    project = db.query(Project).filter_by(code="PRJ-SOLAR-01", business_unit_id=bu.id).first()
    if not project:
        project = Project(
            name="Kurnool 500MW Solar Site",
            code="PRJ-SOLAR-01",
            location="Kurnool, Andhra Pradesh",
            business_unit_id=bu.id,
        )
        db.add(project)
        db.flush()
        counts["projects"] += 1
        logger.info("Created Project: %s", project.name)

    # 2. Reporting Period (FY 2025-26)
    rep_period = (
        db.query(ReportingPeriod)
        .filter_by(fiscal_year="FY 2025-26", organization_id=org.id)
        .first()
    )
    if not rep_period:
        rep_period = ReportingPeriod(
            fiscal_year="FY 2025-26",
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            boundary=ReportingBoundary.STANDALONE,
            description="Annual Reporting Period for FY 2025-26",
            organization_id=org.id,
        )
        db.add(rep_period)
        db.flush()
        counts["reporting_periods"] += 1
        logger.info("Created Reporting Period: %s", rep_period.fiscal_year)

    # 3. System Roles & Permissions
    # Base permissions
    perm_names = [
        ("submission:read", "Read access to BRSR submissions"),
        ("submission:create", "Create draft BRSR submissions"),
        ("submission:update", "Update BRSR submission values"),
        ("submission:submit", "Submit data for review"),
        ("submission:review", "Review submitted BRSR data"),
        ("submission:approve", "Approve reviewed BRSR data"),
        ("admin:all", "Full administrative access"),
    ]
    perm_dict = {}
    for p_name, p_desc in perm_names:
        perm = db.query(Permission).filter_by(name=p_name).first()
        if not perm:
            perm = Permission(name=p_name, description=p_desc)
            db.add(perm)
            db.flush()
            counts["permissions"] += 1
        perm_dict[p_name] = perm

    # Roles from SystemRole enum
    for role_enum in SystemRole:
        role = db.query(Role).filter_by(name=role_enum.value).first()
        if not role:
            role = Role(
                name=role_enum.value,
                description=f"System role for {role_enum.name.replace('_', ' ').title()}",
            )
            if role_enum == SystemRole.SUPER_ADMIN:
                role.permissions = list(perm_dict.values())
            elif role_enum == SystemRole.PROJECT_DATA_ENTRY:
                role.permissions = [
                    perm_dict["submission:read"],
                    perm_dict["submission:create"],
                    perm_dict["submission:update"],
                    perm_dict["submission:submit"],
                ]
            elif role_enum == SystemRole.REVIEWER:
                role.permissions = [
                    perm_dict["submission:read"],
                    perm_dict["submission:review"],
                ]
            elif role_enum == SystemRole.APPROVER:
                role.permissions = [
                    perm_dict["submission:read"],
                    perm_dict["submission:approve"],
                ]
            db.add(role)
            db.flush()
            counts["roles"] += 1
            logger.info("Created Role: %s", role.name)

    # 4. BRSR Framework Metadata Structure
    framework = (
        db.query(BRSRFramework)
        .filter_by(name="SEBI BRSR Core", version="2023-24")
        .first()
    )
    if not framework:
        framework = BRSRFramework(
            name="SEBI BRSR Core",
            version="2023-24",
            description="SEBI Business Responsibility and Sustainability Reporting Framework Core Indicators",
            is_active=True,
        )
        db.add(framework)
        db.flush()
        counts["frameworks"] += 1
        logger.info("Created BRSR Framework: %s v%s", framework.name, framework.version)

    # Section A - General Disclosures
    sec_a = (
        db.query(BRSRSection)
        .filter_by(code="SEC_A", framework_id=framework.id)
        .first()
    )
    if not sec_a:
        sec_a = BRSRSection(
            code="SEC_A",
            title="Section A: General Disclosures",
            description="Details of the listed entity, products/services, operations, employees, and subsidiary details.",
            order_index=1,
            framework_id=framework.id,
        )
        db.add(sec_a)
        db.flush()
        counts["sections"] += 1

    # Section A Indicator
    ind_gen = (
        db.query(BRSRIndicator)
        .filter_by(code="IND_GEN_01", section_id=sec_a.id)
        .first()
    )
    if not ind_gen:
        ind_gen = BRSRIndicator(
            code="IND_GEN_01",
            title="Entity Details & Operations Overview",
            indicator_type=IndicatorType.ESSENTIAL,
            order_index=1,
            section_id=sec_a.id,
        )
        db.add(ind_gen)
        db.flush()
        counts["indicators"] += 1

    # Section A Questions
    q_cin = (
        db.query(BRSRQuestion)
        .filter_by(code="Q_GEN_CIN", indicator_id=ind_gen.id)
        .first()
    )
    if not q_cin:
        q_cin = BRSRQuestion(
            code="Q_GEN_CIN",
            question_text="Corporate Identity Number (CIN) of the Entity",
            guidance="Provide valid 21-digit CIN.",
            response_type=QuestionResponseType.TEXT,
            is_mandatory=True,
            order_index=1,
            indicator_id=ind_gen.id,
        )
        db.add(q_cin)
        counts["questions"] += 1

    q_emp_count = (
        db.query(BRSRQuestion)
        .filter_by(code="Q_GEN_EMP_COUNT", indicator_id=ind_gen.id)
        .first()
    )
    if not q_emp_count:
        q_emp_count = BRSRQuestion(
            code="Q_GEN_EMP_COUNT",
            question_text="Total number of permanent employees",
            guidance="Count as of end of financial year.",
            response_type=QuestionResponseType.NUMBER,
            unit_of_measurement="Headcount",
            is_mandatory=True,
            order_index=2,
            indicator_id=ind_gen.id,
        )
        db.add(q_emp_count)
        counts["questions"] += 1

    # Section C - Principle-wise Performance
    sec_c = (
        db.query(BRSRSection)
        .filter_by(code="SEC_C", framework_id=framework.id)
        .first()
    )
    if not sec_c:
        sec_c = BRSRSection(
            code="SEC_C",
            title="Section C: Principle-wise Performance Disclosures",
            description="Essential and leadership indicators under NGRBC Principles 1 to 9.",
            order_index=3,
            framework_id=framework.id,
        )
        db.add(sec_c)
        db.flush()
        counts["sections"] += 1

    # Principle 6 - Environment
    p6 = (
        db.query(BRSRPrinciple)
        .filter_by(code="P6", section_id=sec_c.id)
        .first()
    )
    if not p6:
        p6 = BRSRPrinciple(
            principle_number=6,
            code="P6",
            title="Principle 6: Environmental Protection and Restoration",
            description="Businesses should respect and make efforts to protect and restore the environment.",
            order_index=6,
            section_id=sec_c.id,
        )
        db.add(p6)
        db.flush()
        counts["principles"] += 1

    # Principle 6 Essential Indicator
    ind_p6_energy = (
        db.query(BRSRIndicator)
        .filter_by(code="IND_P6_E1", section_id=sec_c.id)
        .first()
    )
    if not ind_p6_energy:
        ind_p6_energy = BRSRIndicator(
            code="IND_P6_E1",
            title="Energy Consumption & Intensity",
            indicator_type=IndicatorType.ESSENTIAL,
            order_index=1,
            section_id=sec_c.id,
            principle_id=p6.id,
        )
        db.add(ind_p6_energy)
        db.flush()
        counts["indicators"] += 1

    # Principle 6 Questions
    q_elec = (
        db.query(BRSRQuestion)
        .filter_by(code="Q_P6_ELEC_CONS", indicator_id=ind_p6_energy.id)
        .first()
    )
    if not q_elec:
        q_elec = BRSRQuestion(
            code="Q_P6_ELEC_CONS",
            question_text="Total electricity consumption (A)",
            guidance="Include grid electricity purchases in Gigajoules (GJ) or MWh.",
            response_type=QuestionResponseType.NUMBER,
            unit_of_measurement="MWh",
            is_mandatory=True,
            order_index=1,
            indicator_id=ind_p6_energy.id,
        )
        db.add(q_elec)
        counts["questions"] += 1

    q_renewable = (
        db.query(BRSRQuestion)
        .filter_by(code="Q_P6_RENEW_PCT", indicator_id=ind_p6_energy.id)
        .first()
    )
    if not q_renewable:
        q_renewable = BRSRQuestion(
            code="Q_P6_RENEW_PCT",
            question_text="Percentage of total energy consumption from renewable sources",
            guidance="Calculate as (Renewable Energy / Total Energy) * 100",
            response_type=QuestionResponseType.NUMBER,
            unit_of_measurement="%",
            is_mandatory=True,
            order_index=2,
            indicator_id=ind_p6_energy.id,
        )
        db.add(q_renewable)
        counts["questions"] += 1

    # 5. Demo Admin User
    demo_email = "admin@meil.com"
    demo_user = db.query(User).filter_by(email=demo_email).first()
    if not demo_user:
        demo_user = User(
            email=demo_email,
            hashed_password=get_password_hash("Admin@12345"),
            full_name="MEIL Admin",
            is_active=True,
        )
        db.add(demo_user)
        db.flush()
        counts["users"] += 1
        logger.info("Created demo admin user: %s", demo_email)
    else:
        logger.info("Demo admin user already exists: %s", demo_email)

    # Assign SUPER_ADMIN role if not already assigned
    super_admin_role = db.query(Role).filter_by(name=SystemRole.SUPER_ADMIN.value).first()
    if super_admin_role and super_admin_role not in demo_user.roles:
        demo_user.roles.append(super_admin_role)
        db.flush()
        logger.info("Assigned SUPER_ADMIN role to demo admin user")
    else:
        logger.info("SUPER_ADMIN role already assigned to demo admin user")

    # 5. Full BRSR framework (SEBI BRSR v2021) - separate from BRSR Core
    seed_full_brsr(db, counts)

    db.commit()
    logger.info("Database seeding completed successfully.")
    return counts


# ============================================================================
# Full BRSR framework ("SEBI BRSR" v2021)
# ============================================================================
# Source: support_materials/...Annexure1_p.pdf  ("Annexure I: Business
# Responsibility & Sustainability Reporting Format", SEBI circular 10-May-2021).
# Wording is verbatim; PDF page numbers are retained per row in `guidance`.
#
# This framework is SEPARATE from the existing "SEBI BRSR Core" 2023-24 rows,
# which are never read, modified or deleted by anything below.
BRSR_FULL_SECTIONS = [
    # code,   title,                                                        description,                              order
    ("SEC_A", "Section A: General Disclosures",
     "Details of the listed entity, products/services, operations, employees, holding/subsidiary/associate companies, CSR details and transparency and disclosures compliances.", 1),
    ("SEC_B", "Section B: Management and Process Disclosures",
     "Structures, policies and processes put in place towards adopting the NGRBC Principles and Core Elements.", 2),
    ("SEC_C", "Section C: Principle-wise Performance Disclosures",
     "Essential and Leadership indicators under NGRBC Principles 1 to 9.", 3),
]

BRSR_FULL_PRINCIPLES = [
    # number, code, title,                                             description
    (1, "P1", "Principle 1: Ethical, Transparent and Accountable Conduct",
     "Businesses should conduct and govern themselves with integrity, and in a manner that is Ethical, Transparent and Accountable."),
    (2, "P2", "Principle 2: Sustainable and Safe Products and Services",
     "Businesses should provide goods and services in a manner that is sustainable and safe."),
    (3, "P3", "Principle 3: Employee and Value Chain Well-being",
     "Businesses should respect and promote the well-being of all employees, including those in their value chains."),
    (4, "P4", "Principle 4: Responsiveness to Stakeholders",
     "Businesses should respect the interests of and be responsive to all its stakeholders."),
    (5, "P5", "Principle 5: Human Rights",
     "Businesses should respect and promote human rights."),
    (6, "P6", "Principle 6: Environmental Protection and Restoration",
     "Businesses should respect and make efforts to protect and restore the environment."),
    (7, "P7", "Principle 7: Responsible Public and Regulatory Policy Engagement",
     "Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent."),
    (8, "P8", "Principle 8: Inclusive Growth and Equitable Development",
     "Businesses should promote inclusive growth and equitable development."),
    (9, "P9", "Principle 9: Responsible Consumer Engagement",
     "Businesses should engage with and provide value to their consumers in a responsible manner."),
]

BRSR_FULL_INDICATORS = [
    # code,        section,  principle, title,                                                          indicator_type
    ("IND_A_I",    "SEC_A", None,      "I. Details of the listed entity",                            "ESSENTIAL"),
    ("IND_A_II",   "SEC_A", None,      "II. Products/services",                                      "ESSENTIAL"),
    ("IND_A_III",  "SEC_A", None,      "III. Operations",                                            "ESSENTIAL"),
    ("IND_A_IV",   "SEC_A", None,      "IV. Employees",                                              "ESSENTIAL"),
    ("IND_A_V",    "SEC_A", None,      "V. Holding, Subsidiary and Associate Companies",            "ESSENTIAL"),
    ("IND_A_VI",   "SEC_A", None,      "VI. CSR Details",                                             "ESSENTIAL"),
    ("IND_A_VII",  "SEC_A", None,      "VII. Transparency and Disclosures Compliances",              "ESSENTIAL"),
    ("IND_B_1",    "SEC_B", None,      "Policy and management processes",                           "ESSENTIAL"),
    ("IND_B_2",    "SEC_B", None,      "Governance, leadership and oversight",                       "ESSENTIAL"),
    ("IND_P1_E",   "SEC_C", "P1",     "Principle 1 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P1_L",   "SEC_C", "P1",     "Principle 1 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P2_E",   "SEC_C", "P2",     "Principle 2 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P2_L",   "SEC_C", "P2",     "Principle 2 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P3_E",   "SEC_C", "P3",     "Principle 3 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P3_L",   "SEC_C", "P3",     "Principle 3 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P4_E",   "SEC_C", "P4",     "Principle 4 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P4_L",   "SEC_C", "P4",     "Principle 4 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P5_E",   "SEC_C", "P5",     "Principle 5 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P5_L",   "SEC_C", "P5",     "Principle 5 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P6_E",   "SEC_C", "P6",     "Principle 6 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P6_L",   "SEC_C", "P6",     "Principle 6 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P7_E",   "SEC_C", "P7",     "Principle 7 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P7_L",   "SEC_C", "P7",     "Principle 7 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P8_E",   "SEC_C", "P8",     "Principle 8 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P8_L",   "SEC_C", "P8",     "Principle 8 - Leadership Indicators",                "LEADERSHIP"),
    ("IND_P9_E",   "SEC_C", "P9",     "Principle 9 - Essential Indicators",                 "ESSENTIAL"),
    ("IND_P9_L",   "SEC_C", "P9",     "Principle 9 - Leadership Indicators",                "LEADERSHIP"),
]


# Full BRSR questions transcribed verbatim from
# support_materials/'...Annexure1_p.pdf' (SEBI BRSR reporting format, Annexure I).
# Tuple: (code, question_text, response_type, unit, source_page).
# response_type is an APPLICATION/UI inference (see docstring), not a SEBI-defined type.
BRSR_FULL_QUESTIONS = {
    "IND_A_I": [
        ("Q_A_01", "Corporate Identity Number (CIN) of the Listed Entity", "TEXT", None, 1),
        ("Q_A_02", "Name of the Listed Entity", "TEXT", None, 1),
        ("Q_A_03", "Year of incorporation", "NUMBER", None, 1),
        ("Q_A_04", "Registered office address", "TEXT", None, 1),
        ("Q_A_05", "Corporate address", "TEXT", None, 1),
        ("Q_A_06", "E-mail", "TEXT", None, 1),
        ("Q_A_07", "Telephone", "TEXT", None, 1),
        ("Q_A_08", "Website", "TEXT", None, 1),
        ("Q_A_09", "Financial year for which reporting is being done", "TEXT", None, 1),
        ("Q_A_10", "Name of the Stock Exchange(s) where shares are listed", "TEXT", None, 1),
        ("Q_A_11", "Paid-up Capital", "NUMBER", None, 1),
        ("Q_A_12", "Name and contact details (telephone, email address) of the person who may be contacted in case of any queries on the BRSR report", "TEXT", None, 1),
        ("Q_A_13", "Reporting boundary - Are the disclosures under this report made on a standalone basis (i.e. only for the entity) or on a consolidated basis (i.e. for the entity and all the entities which form a part of its consolidated financial statements, taken together). II. Products/services", "BOOLEAN", None, 1),
    ],
    "IND_A_II": [
        ("Q_A_14", "Details of business activities (accounting for 90% of the turnover): S. No. Description of Main Activity Description of Business Activity % of Turnover of the entity", "TABLE", None, 1),
        ("Q_A_15", "Products/Services sold by the entity (accounting for 90% of the entity’s Turnover): S. No. Product/Service NIC Code % of total Turnover contributed", "TABLE", None, 1),
    ],
    "IND_A_III": [
        ("Q_A_16", "Number of locations where plants and/or operations/offices of the entity are situated: Location Number of plants Number of offices Total National International", "TABLE", None, 2),
        ("Q_A_17", "Markets served by the entity: a. Number of locations Locations Number National (No. of States) International (No. of Countries) b. What is the contribution of exports as a percentage of the total turnover of the entity? c. A brief on types of customers IV. Employees", "TABLE", None, 2),
    ],
    "IND_A_IV": [
        ("Q_A_18", "Details as at the end of Financial Year: a. Employees and workers (including differently abled): S. No. Particulars Total (A) Male Female No. (B) % (B / A) No. (C) % (C / A) EMPLOYEES", "TABLE", None, 2),
        ("Q_A_19", "Participation/Inclusion/Representation of women Total (A) No. and percentage of Females No. (B) % (B / A) Board of Directors Key Management Personnel", "TABLE", None, 3),
        ("Q_A_20", "Turnover rate for permanent employees and workers (Disclose trends for the past 3 years) FY _____ (Turnover rate in current FY) FY _____ (Turnover rate in previous FY) FY _____ (Turnover rate in the year prior to the previous FY) Male Female Total Male Female Total Male Female Total Permanent Employees Permanent Workers", "TABLE", None, 3),
    ],
    "IND_A_V": [
        ("Q_A_21", "(a) Names of holding / subsidiary / associate companies / joint ventures S. No. Name of the holding / subsidiary / associate companies / joint ventures (A) Indicate whether holding/ Subsidiary/ Associate/ Joint Venture % of shares held by listed entity Does the entity indicated at column A, participate in the Business Responsibility initiatives of the listed entity? (Yes/No) VI. CSR Details", "TABLE", None, 4),
    ],
    "IND_A_VI": [
        ("Q_A_22", "(i) Whether CSR is applicable as per section 135 of Companies Act, 2013: (Yes/No) (ii) Turnover (in Rs.) (iii) Net worth (in Rs.) VII. Transparency and Disclosures Compliances", "BOOLEAN", None, 4),
    ],
    "IND_A_VII": [
        ("Q_A_23", "Complaints/Grievances on any of the principles (Principles 1 to 9) under the National Guidelines on Responsible Business Conduct: Stakeholder group from whom complaint is received Grievance Redressal Mechanism in Place (Yes/No) (If Yes, then provide web-link for grievance redress policy) FY _____ Current Financial Year FY _____ Previous Financial Year Number of complaints filed during the year Number of complaints pending resolution at close of the year Remarks Number of complaints filed during the year Number of complaints pending resolution at close of the year Remarks Communities Investors (other than shareholders)", "TABLE", None, 4),
        ("Q_A_24", "Overview of the entity’s material responsible business conduct issues Please indicate material responsible business conduct and sustainability issues pertaining to environmental and social matters that present a risk or an opportunity to your business, rationale for identifying the same, approach to adapt or mitigate the risk along-with its financial implications, as per the following format S. No. Material issue identified Indicate whether risk or opportunity (R/O) Rationale for identifying the risk / opportunity In case of risk, approach to adapt or mitigate Financial implications of the risk or opportunity (Indicate positive or negative implications)", "TABLE", None, 5),
    ],
    "IND_B_1": [
        ("Q_B_01", "a. Whether your entity’s policy/policies cover each principle and its core elements of the NGRBCs. (Yes/No) b. Has the policy been approved by the Board? (Yes/No) c. Web Link of the Policies, if available", "BOOLEAN", None, 6),
        ("Q_B_02", "Whether the entity has translated the policy into procedures. (Yes / No)", "BOOLEAN", None, 6),
        ("Q_B_03", "Do the enlisted policies extend to your value chain partners? (Yes/No)", "BOOLEAN", None, 6),
        ("Q_B_04", "Name of the national and international codes/certifications/labels/ standards (e.g. Forest Stewardship Council, Fairtrade, Rainforest Alliance, Trustea) standards (e.g. SA 8000, OHSAS, ISO, BIS) adopted by your entity and mapped to each principle.", "TABLE", None, 6),
        ("Q_B_05", "Specific commitments, goals and targets set by the entity with defined timelines, if any.", "TEXT", None, 6),
        ("Q_B_06", "Performance of the entity against the specific commitments, goals and targets along-with reasons in case the same are not met. Governance, leadership and oversight", "TEXT", None, 6),
    ],
    "IND_B_2": [
        ("Q_B_07", "Statement by director responsible for the business responsibility report, highlighting ESG related challenges, targets and achievements (listed entity has flexibility regarding the placement of this disclosure)", "TEXT", None, 6),
        ("Q_B_08", "Details of the highest authority responsible for implementation and oversight of the Business Responsibility policy (ies).", "TEXT", None, 6),
        ("Q_B_09", "Does the entity have a specified Committee of the Board/ Director responsible for decision making on sustainability related issues? (Yes / No). If yes, provide details.", "BOOLEAN", None, 6),
        ("Q_B_10", "Details of Review of NGRBCs by the Company: Subject for Review Indicate whether review was undertaken by Director / Committee of the Board/ Any other Committee Frequency (Annually/ Half yearly/ Quarterly/ Any other – please specify) P 1 P 2 P 3 P 4 P 5 P 6 P 7 P 8 P 9 P 1 P 2 P 3 P 4 P 5 P 6 P 7 P 8 P 9 Performance against above policies and follow up action Compliance with statutory requirements of relevance to the principles, and, rectification of any non-compliances", "TABLE", None, 7),
        ("Q_B_11", "Has the entity carried out independent assessment/ evaluation of the working of its policies by an external agency? (Yes/No). If yes, provide name of the agency. P 1 P 2 P 3 P 4 P 5 P 6 P 7 P 8 P 9", "BOOLEAN", None, 7),
        ("Q_B_12", "If answer to question (1) above is “No” i.e. not all Principles are covered by a policy, reasons to be stated: Questions P 1 P 2 P 3 P 4 P 5 P 6 P 7 P 8 P 9 The entity does not consider the Principles material to its business (Yes/No) The entity is not at a stage where it is in a position to formulate and implement the policies on specified principles (Yes/No) The entity does not have the financial or/human and technical resources available for the task (Yes/No) It is planned to be done in the next financial year (Yes/No) Any other reason (please specify)", "TABLE", None, 7),
    ],
    "IND_P1_E": [
        ("Q_P1_E01", "Percentage coverage by training and awareness programmes on any of the Principles during the financial year: Segment Total number of training and awareness programmes held Topics / principles covered under the training and its impact %age of persons in respective category covered by the awareness programmes Board of Directors Key Managerial Personnel Employees other than BoD and KMPs Workers", "TABLE", None, 8),
        ("Q_P1_E02", "Details of fines / penalties /punishment/ award/ compounding fees/ settlement amount paid in proceedings (by the entity or by directors / KMPs) with regulators/ law enforcement agencies/ judicial institutions, in the financial year, in the following format (Note: the entity shall make disclosures on the basis of materiality as specified in Regulation 30 of SEBI (Listing Obligations and Disclosure Obligations) Regulations, 2015 and as disclosed on the entity’s website): Monetary NGRBC Principle Name of the regulatory/ enforcement Amount (In INR) Brief of the Case Has an appeal been", "TABLE", 'INR', 8),
        ("Q_P1_E03", "Of the instances disclosed in Question 2 above, details of the Appeal/ Revision preferred in cases where monetary or non-monetary action has been appealed. Case Details Name of the regulatory/ enforcement agencies/ judicial institutions", "TABLE", None, 9),
        ("Q_P1_E04", "Does the entity have an anti-corruption or anti-bribery policy? If yes, provide details in brief and if available, provide a web-link to the policy.", "BOOLEAN", None, 9),
        ("Q_P1_E05", "Number of Directors/KMPs/employees/workers against whom disciplinary action was taken by any law enforcement agency for the charges of bribery/ corruption: FY _____ (Current Financial Year) FY _____ (Previous Financial Year) Directors KMPs Employees Workers", "NUMBER", None, 9),
        ("Q_P1_E06", "Details of complaints with regard to conflict of interest: FY _____ (Current Financial Year) FY _____ (Previous Financial Year)", "TABLE", None, 9),
        ("Q_P1_E07", "Provide details of any corrective action taken or underway on issues related to fines / penalties / action taken by regulators/ law enforcement agencies/ judicial institutions, on cases of corruption and conflicts of interest.", "TEXT", None, 10),
    ],
    "IND_P1_L": [
        ("Q_P1_L01", "Awareness programmes conducted for value chain partners on any of the Principles during the financial year: Total number of awareness programmes held Topics / principles covered under the training %age of value chain partners covered (by value of business done with such partners) under the awareness programmes", "TABLE", None, 10),
        ("Q_P1_L02", "Does the entity have processes in place to avoid/ manage conflict of interests involving members of the Board? (Yes/No) If Yes, provide details of the same.", "BOOLEAN", None, 10),
    ],
    "IND_P2_E": [
        ("Q_P2_E01", "Percentage of R&D and capital expenditure (capex) investments in specific technologies to improve the environmental and social impacts of product and processes to total R&D and capex investments made by the entity, respectively. Current Financial Year Previous Financial Year Details of improvements in environmental and social impacts R&D Capex", "NUMBER", None, 11),
        ("Q_P2_E02", "a. Does the entity have procedures in place for sustainable sourcing? (Yes/No) b. If yes, what percentage of inputs were sourced sustainably?", "BOOLEAN", None, 11),
        ("Q_P2_E03", "Describe the processes in place to safely reclaim your products for reusing, recycling and disposing at the end of life, for (a) Plastics (including packaging) (b) E-waste (c) Hazardous waste and (d) other waste.", "TEXT", None, 11),
        ("Q_P2_E04", "Whether Extended Producer Responsibility (EPR) is applicable to the entity’s activities (Yes / No). If yes, whether the waste collection plan is in line with the Extended Producer Responsibility (EPR) plan submitted to Pollution Control Boards? If not, provide steps taken to address the same.", "BOOLEAN", None, 11),
    ],
    "IND_P2_L": [
        ("Q_P2_L01", "Has the entity conducted Life Cycle Perspective / Assessments (LCA) for any of its products (for manufacturing industry) or for its services (for service industry)? If yes, provide details in the following format? NIC Code Name of Product /Service % of total Turnover contributed Boundary for which the Life Cycle Perspective / Assessment was conducted Whether conducted by independent external agency (Yes/No) Results communicated in public domain (Yes/No) If yes, provide the web-link.", "BOOLEAN", None, 11),
        ("Q_P2_L02", "If there are any significant social or environmental concerns and/or risks arising from production or disposal of your products / services, as identified in the Life Cycle Perspective / Assessments (LCA) or through any other means, briefly describe the same along-with action taken to mitigate the same. Name of Product / Service Description of the risk / concern Action Taken", "TEXT", None, 12),
        ("Q_P2_L03", "Percentage of recycled or reused input material to total material (by value) used in production (for manufacturing industry) or providing services (for service industry). Indicate input material Recycled or re-used input material to total material FY _____ Current Financial Year FY _____ Previous Financial Year", "NUMBER", None, 12),
        ("Q_P2_L04", "Of the products and packaging reclaimed at end of life of products, amount (in metric tonnes) reused, recycled, and safely disposed, as per the following format: FY _____ Current Financial Year FY _____ Previous Financial Year Re-Used Recycled Safely Disposed Re-Used Recycled Safely Disposed Plastics (including packaging) E-waste Hazardous waste Other waste", "NUMBER", 'metric tonnes', 12),
        ("Q_P2_L05", "Reclaimed products and their packaging materials (as percentage of products sold) for each product category. Indicate product category Reclaimed products and their packaging materials as % of total products sold in respective category", "TEXT", None, 12),
    ],
    "IND_P3_E": [
        ("Q_P3_E01", "a. Details of measures for the well-being of employees: Category % of employees covered by Total (A) Health insurance Accident insurance Maternity benefits Paternity Benefits Day Care facilities Number (B) % (B / A) Number (C) % (C / A) Number (D) % (D / A) Number (E) % (E / A) Number (F) % (F / A) Permanent employees Male Female Total Other than Permanent employees Male Female Total b. Details of measures for the well-being of workers: Category % of workers covered by Total (A) Health insurance Accident insurance Maternity benefits Paternity Benefits Day Care facilities Number (B) % (B / A) Number (C) % (C / A) Number (D) % (D / A) Number (E) % (E / A) Number (F) % (F / A) Permanent workers Male Female Total Other than Permanent workers Male Female Total", "TABLE", None, 13),
        ("Q_P3_E02", "Details of retirement benefits, for Current FY and Previous Financial Year. Benefits FY _____ Current Financial Year FY _____ Previous Financial Year No. of employees covered as a % of total employees No. of workers covered as a % of total workers Deducted and deposited with the authority (Y/N/N.A.) No. of employees covered as a % of total employees No. of workers covered as a % of total workers Deducted and deposited with the authority (Y/N/N.A.) PF", "TABLE", None, 13),
        ("Q_P3_E03", "Accessibility of workplaces Are the premises / offices of the entity accessible to differently abled employees and workers, as per the requirements of the Rights of Persons with Disabilities Act, 2016? If not, whether any steps are being taken by the entity in this regard.", "BOOLEAN", None, 14),
        ("Q_P3_E04", "Does the entity have an equal opportunity policy as per the Rights of Persons with Disabilities Act, 2016? If so, provide a web-link to the policy.", "BOOLEAN", None, 14),
        ("Q_P3_E05", "Return to work and Retention rates of permanent employees and workers that took parental leave. Permanent employees Permanent workers Gender Return to work rate Retention rate Return to work rate Retention rate Male Female Total", "NUMBER", None, 14),
        ("Q_P3_E06", "Is there a mechanism available to receive and redress grievances for the following categories of employees and worker? If yes, give details of the mechanism in brief. Yes/No (If Yes, then give details of the mechanism in brief) Permanent Workers Other than Permanent Workers Permanent Employees Other than Permanent Employees", "TABLE", None, 14),
        ("Q_P3_E07", "Membership of employees and worker in association(s) or Unions recognised by the listed entity: Category FY _____ (Current Financial Year) FY _____ (Previous Financial Year) Total employees / workers in respective category (A) No. of employees / workers in respective category, who are part of association(s) or Union (B) % (B / A) Total employees / workers in respective category (C) No. of employees / workers in respective category, who are part of association(s) or Union (D) % (D / C)", "TABLE", None, 14),
        ("Q_P3_E08", "Details of training given to employees and workers: Category FY _____ Current Financial Year FY _____ Previous Financial Year Total (A) On Health and safety measures On Skill upgradation Total (D) On Health and safety measures On Skill upgradation No. (B) % (B / A) No. (C) % (C / A) No. (E) % (E / D) No. (F) % (F / D) Employees Male Female Total Workers Male Female Total", "TABLE", None, 15),
        ("Q_P3_E09", "Details of performance and career development reviews of employees and worker: Category FY _____ Current Financial Year FY _____ Previous Financial Year Total (A) No. (B) % (B / A) Total (C) No. (D) % (D / C) Employees Male Female Total Workers Male Female Total", "TABLE", None, 15),
        ("Q_P3_E10", "Health and safety management system: a. Whether an occupational health and safety management system has been implemented by the entity? (Yes/ No). If yes, the coverage such system? b. What are the processes used to identify work-related hazards and assess risks on a routine and non-routine basis by the entity? c. Whether you have processes for workers to report the work related hazards and to remove themselves from such risks. (Y/N)", "TABLE", None, 15),
        ("Q_P3_E11", "Details of safety related incidents, in the following format: Safety Incident/Number Category FY _____ Current Financial Year FY _____ Previous Financial Year Lost Time Injury Frequency Rate (LTIFR) (per one million-person hours worked) Employees Workers Total recordable work-related injuries Employees Workers No. of fatalities Employees Workers High consequence work-related injury or ill-health (excluding fatalities) Employees Workers", "TABLE", None, 16),
        ("Q_P3_E12", "Describe the measures taken by the entity to ensure a safe and healthy work place.", "TEXT", None, 16),
        ("Q_P3_E13", "Number of Complaints on the following made by employees and workers: FY _____ (Current Financial Year) FY _____ (Previous Financial Year) Filed during the year Pending resolution at the end of year Remarks Filed during the year Pending resolution at the end of year Remarks Working Conditions Health & Safety", "NUMBER", None, 16),
        ("Q_P3_E14", "Assessments for the year: % of your plants and offices that were assessed (by entity or statutory authorities or third parties) Health and safety practices Working Conditions", "TABLE", None, 16),
        ("Q_P3_E15", "Provide details of any corrective action taken or underway to address safety-related incidents (if any) and on significant risks / concerns arising from assessments of health & safety practices and working conditions.", "TEXT", None, 16),
    ],
    "IND_P3_L": [
        ("Q_P3_L01", "Does the entity extend any life insurance or any compensatory package in the event of death of (A) Employees (Y/N) (B) Workers (Y/N).", "BOOLEAN", None, 17),
        ("Q_P3_L02", "Provide the measures undertaken by the entity to ensure that statutory dues have been deducted and deposited by the value chain partners.", "TEXT", None, 17),
        ("Q_P3_L03", "Provide the number of employees / workers having suffered high consequence work-related injury / ill-health / fatalities (as reported in Q11 of Essential Indicators above), who have been are rehabilitated and placed in suitable employment or whose family members have been placed in suitable employment: Total no. of affected employees/ workers No. of employees/workers that are rehabilitated and placed in suitable employment or whose family members have been placed in suitable employment FY _____ (Current Financial Year) FY _____ (Previous Financial Year) FY _____ (Current Financial Year) FY _____ (Previous Financial Year) Employees Workers", "TEXT", None, 17),
        ("Q_P3_L04", "Does the entity provide transition assistance programs to facilitate continued employability and the management of career endings resulting from retirement or termination of employment? (Yes/ No)", "BOOLEAN", None, 17),
        ("Q_P3_L05", "Details on assessment of value chain partners: % of value chain partners (by value of business done with such partners) that were assessed Health and safety practices Working Conditions", "TABLE", None, 17),
        ("Q_P3_L06", "Provide details of any corrective actions taken or underway to address significant risks / concerns arising from assessments of health and safety practices and working conditions of value chain partners.", "TABLE", None, 17),
    ],
    "IND_P4_E": [
        ("Q_P4_E01", "Describe the processes for identifying key stakeholder groups of the entity.", "TEXT", None, 18),
        ("Q_P4_E02", "List stakeholder groups identified as key for your entity and the frequency of engagement with each stakeholder group. Stakeholder Group Whether identified as Vulnerable & Marginalized Group (Yes/No) Channels of communication (Email, SMS, Newspaper, Pamphlets, Advertisement, Community Meetings, Notice Board, Website), Other Frequency of engagement (Annually/ Half yearly/ Quarterly / others – please specify) Purpose and scope of engagement including key topics and concerns raised during such engagement", "TABLE", None, 18),
    ],
    "IND_P4_L": [
        ("Q_P4_L01", "Provide the processes for consultation between stakeholders and the Board on economic, environmental, and social topics or if consultation is delegated, how is feedback from such consultations provided to the Board.", "TEXT", None, 18),
        ("Q_P4_L02", "Whether stakeholder consultation is used to support the identification and management of environmental, and social topics (Yes / No). If so, provide details of instances as to how the inputs received from stakeholders on these topics were incorporated into policies and activities of the entity.", "BOOLEAN", None, 18),
        ("Q_P4_L03", "Provide details of instances of engagement with, and actions taken to, address the concerns of vulnerable/ marginalized stakeholder groups.", "TABLE", None, 18),
    ],
    "IND_P5_E": [
        ("Q_P5_E01", "Employees and workers who have been provided training on human rights issues and policy(ies) of the entity, in the following format: Category FY _____ Current Financial Year FY _____ Previous Financial Year Total (A) No. of employees / workers covered (B) % (B / A) Total (C) No. of employees / workers covered (D) % (D / C) Employees Permanent Other than permanent Total Employees Workers Permanent Other than permanent Total Workers", "NUMBER", None, 19),
        ("Q_P5_E02", "Details of minimum wages paid to employees and workers, in the following format: Category FY _____ Current Financial Year FY _____ Previous Financial Year Total (A) Equal to Minimum Wage More than Minimum Wage Total (D) Equal to Minimum Wage More than Minimum Wage No. (B) % (B / A) No. (C) % (C / A) No. (E) % (E / D) No. (F) % (F / D) Employees Permanent Male Female Other than Permanent Male Female Workers Permanent Male Female Other than Permanent Male Female", "TABLE", None, 19),
        ("Q_P5_E03", "Details of remuneration/salary/wages, in the following format: Male Female Number Median remuneration/ salary/ wages of respective category Number Median remuneration/ salary/ wages of respective category Board of Directors (BoD) Key Managerial Personnel Employees other than BoD and KMP Workers", "TABLE", None, 20),
        ("Q_P5_E04", "Do you have a focal point (Individual/ Committee) responsible for addressing human rights impacts or issues caused or contributed to by the business? (Yes/No)", "BOOLEAN", None, 20),
        ("Q_P5_E05", "Describe the internal mechanisms in place to redress grievances related to human rights issues.", "TEXT", None, 20),
        ("Q_P5_E06", "Number of Complaints on the following made by employees and workers: FY _____ Current Financial Year FY _____ Previous Financial Year Filed during the year Pending resolution at the end of year Remarks Filed during the year Pending resolution at the end of year Remarks Sexual Harassment Discrimination at workplace Child Labour Forced Labour/Involuntary Labour Wages Other human rights related issues", "NUMBER", None, 20),
        ("Q_P5_E07", "Mechanisms to prevent adverse consequences to the complainant in discrimination and harassment cases.", "TEXT", None, 20),
        ("Q_P5_E08", "Do human rights requirements form part of your business agreements and contracts? (Yes/No)", "BOOLEAN", None, 20),
        ("Q_P5_E09", "Assessments for the year: % of your plants and offices that were assessed (by entity or statutory authorities or third parties) Child labour Forced/involuntary labour Sexual harassment Discrimination at workplace Wages Others – please specify", "TABLE", None, 21),
        ("Q_P5_E10", "Provide details of any corrective actions taken or underway to address significant risks / concerns arising from the assessments at Question 9 above.", "TABLE", None, 21),
    ],
    "IND_P5_L": [
        ("Q_P5_L01", "Details of a business process being modified / introduced as a result of addressing human rights grievances/complaints.", "TEXT", None, 21),
        ("Q_P5_L02", "Details of the scope and coverage of any Human rights due-diligence conducted.", "TEXT", None, 21),
        ("Q_P5_L03", "Is the premise/office of the entity accessible to differently abled visitors, as per the requirements of the Rights of Persons with Disabilities Act, 2016?", "BOOLEAN", None, 21),
        ("Q_P5_L04", "Details on assessment of value chain partners: % of value chain partners (by value of business done with such partners) that were assessed Sexual Harassment Discrimination at workplace Child Labour Forced Labour/Involuntary Labour Wages Others – please specify", "TABLE", None, 21),
        ("Q_P5_L05", "Provide details of any corrective actions taken or underway to address significant risks / concerns arising from the assessments at Question 4 above.", "TABLE", None, 21),
    ],
    "IND_P6_E": [
        ("Q_P6_E01", "Details of total energy consumption (in Joules or multiples) and energy intensity, in the following format: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Total electricity consumption (A) Total fuel consumption (B) Energy consumption through other sources (C) Total energy consumption (A+B+C) Energy intensity per rupee of turnover (Total energy consumption/ turnover in rupees) Energy intensity (optional) – the relevant metric may be selected by the entity Note: Indicate if any independent assessment/ evaluation/assurance has been carried out by an external agency? (Y/N) If yes, name of the external agency.", "TABLE", 'Joules or multiples', 22),
        ("Q_P6_E02", "Does the entity have any sites / facilities identified as designated consumers (DCs) under the Performance, Achieve and Trade (PAT) Scheme of the Government of India? (Y/N) If yes, disclose whether targets set under the PAT scheme have been achieved. In case targets have not been achieved, provide the remedial action taken, if any.", "BOOLEAN", None, 22),
        ("Q_P6_E03", "Provide details of the following disclosures related to water, in the following format: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Water withdrawal by source (in kilolitres)", "TABLE", 'kilolitres', 22),
        ("Q_P6_E04", "Has the entity implemented a mechanism for Zero Liquid Discharge? If yes, provide details of its coverage and implementation.", "BOOLEAN", None, 23),
        ("Q_P6_E05", "Please provide details of air emissions (other than GHG emissions) by the entity, in the following format: Parameter Please specify unit FY _____ (Current Financial Year) FY ______ (Previous Financial Year) NOx SOx Particulate matter (PM) Persistent organic pollutants (POP) Volatile organic compounds (VOC) Hazardous air pollutants (HAP) Others – please specify Note: Indicate if any independent assessment/ evaluation/assurance has been carried out by an external agency? (Y/N) If yes, name of the external agency.", "TABLE", None, 23),
        ("Q_P6_E06", "Provide details of greenhouse gas emissions (Scope 1 and Scope 2 emissions) & its intensity, in the following format: Parameter Unit FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Total Scope 1 emissions (Break-up of the GHG into CO2, CH4, N2O, HFCs, PFCs, SF6, NF3, if available) Metric tonnes of CO2 equivalent Total Scope 2 emissions (Break-up of the GHG into CO2, CH4, N2O, HFCs, PFCs, SF6, NF3, if available) Metric tonnes of CO2 equivalent Total Scope 1 and Scope 2 emissions per rupee of turnover Total Scope 1 and Scope 2 emission intensity (optional) – the relevant metric may be selected by the entity Note: Indicate if any independent assessment/ evaluation/assurance has been carried out by an external agency? (Y/N) If yes, name of the external agency.", "TABLE", None, 24),
        ("Q_P6_E07", "Does the entity have any project related to reducing Green House Gas emission? If Yes, then provide details.", "BOOLEAN", None, 24),
        ("Q_P6_E08", "Provide details related to waste management by the entity, in the following format: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Total Waste generated (in metric tonnes) Plastic waste (A) E-waste (B) Bio-medical waste (C) Construction and demolition waste (D) Battery waste (E) Radioactive waste (F)", "TABLE", 'metric tonnes', 24),
        ("Q_P6_E09", "Briefly describe the waste management practices adopted in your establishments. Describe the strategy adopted by your company to reduce usage of hazardous and toxic chemicals in your products and processes and the practices adopted to manage such wastes.", "TEXT", None, 25),
        ("Q_P6_E10", "If the entity has operations/offices in/around ecologically sensitive areas (such as national parks, wildlife sanctuaries, biosphere reserves, wetlands, biodiversity hotspots, forests, coastal regulation zones etc.) where environmental approvals / clearances are required, please specify details in the following format: S. No. Location of operations/offices Type of operations Whether the conditions of environmental approval / clearance are being complied with? (Y/N) If no, the reasons thereof and corrective action taken, if any.", "TABLE", None, 25),
        ("Q_P6_E11", "Details of environmental impact assessments of projects undertaken by the entity based on applicable laws, in the current financial year: Name and brief details of project EIA Notification No. Date Whether conducted by independent external agency (Yes / No) Results communicated in public domain (Yes / No) Relevant Web link", "TABLE", None, 26),
        ("Q_P6_E12", "Is the entity compliant with the applicable environmental law/ regulations/ guidelines in India; such as the Water (Prevention and Control of Pollution) Act, Air (Prevention and Control of Pollution) Act, Environment protection act and rules thereunder (Y/N). If not, provide details of all such non-compliances, in the following format: S. No. Specify the law / regulation / guidelines which was not complied with Provide details of the non-compliance Any fines / penalties / action taken by regulatory agencies such as pollution control boards or by courts Corrective action taken, if any", "BOOLEAN", None, 26),
    ],
    "IND_P6_L": [
        ("Q_P6_L01", "Provide break-up of the total energy consumed (in Joules or multiples) from renewable and non-renewable sources, in the following format: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) From renewable sources Total electricity consumption (A) Total fuel consumption (B) Energy consumption through other sources (C) Total energy consumed from renewable sources (A+B+C) From non-renewable sources", "TABLE", 'Joules or multiples', 26),
        ("Q_P6_L02", "Provide the following details related to water discharged: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Water discharge by destination and level of treatment (in kilolitres) (i) To Surface water - No treatment - With treatment – please specify level of treatment (ii) To Groundwater - No treatment - With treatment – please specify level of treatment (iii) To Seawater - No treatment - With treatment – please specify level of treatment (iv) Sent to third-parties - No treatment - With treatment – please specify level of treatment (v) Others - No treatment - With treatment – please specify level of treatment Total water discharged (in kilolitres) Note: Indicate if any independent assessment/ evaluation/assurance has been carried out by an external agency? (Y/N) If yes, name of the external agency.", "TABLE", 'kilolitres', 27),
        ("Q_P6_L03", "Water withdrawal, consumption and discharge in areas of water stress (in kilolitres): For each facility / plant located in areas of water stress, provide the following information: (i) Name of the area (ii) Nature of operations (iii) Water withdrawal, consumption and discharge in the following format: Parameter FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Water withdrawal by source (in kilolitres) (i) Surface water (ii) Groundwater (iii) Third party water (iv) Seawater / desalinated water (v) Others Total volume of water withdrawal (in kilolitres) Total volume of water consumption (in kilolitres) Water intensity per rupee of turnover (Water consumed / turnover) Water intensity (optional) – the relevant metric may be selected by the entity Water discharge by destination and level of treatment (in kilolitres) (i) Into Surface water - No treatment - With treatment – please specify level of treatment (ii) Into Groundwater - No treatment - With treatment – please specify level of treatment (iii) Into Seawater - No treatment - With treatment – please specify level of treatment (iv) Sent to third-parties", "TABLE", 'kilolitres', 28),
        ("Q_P6_L04", "Please provide details of total Scope 3 emissions & its intensity, in the following format: Parameter Unit FY _____ (Current Financial Year) FY ______ (Previous Financial Year) Total Scope 3 emissions (Break-up of the GHG into CO2, CH4, N2O, HFCs, PFCs, SF6, NF3, if available) Metric tonnes of CO2 equivalent Total Scope 3 emissions per rupee of turnover Total Scope 3 emission intensity (optional) – the relevant metric may be selected by the entity Note: Indicate if any independent assessment/ evaluation/assurance has been carried out by an external agency? (Y/N) If yes, name of the external agency.", "TABLE", None, 29),
        ("Q_P6_L05", "With respect to the ecologically sensitive areas reported at Question 10 of Essential Indicators above, provide details of significant direct & indirect impact of the entity on biodiversity in such areas along-with prevention and remediation activities.", "TABLE", None, 29),
        ("Q_P6_L06", "If the entity has undertaken any specific initiatives or used innovative technology or solutions to improve resource efficiency, or reduce impact due to emissions / effluent discharge / waste generated, please provide details of the same as well as outcome of such initiatives, as per the following format: Sr. No Initiative undertaken Details of the initiative (Web-link, if any, may be provided along-with summary) Outcome of the initiative", "TEXT", None, 29),
        ("Q_P6_L07", "Does the entity have a business continuity and disaster management plan? Give details in 100 words/ web link.", "BOOLEAN", None, 30),
        ("Q_P6_L08", "Disclose any significant adverse impact to the environment, arising from the value chain of the entity. What mitigation or adaptation measures have been taken by the entity in this regard.", "TEXT", None, 30),
        ("Q_P6_L09", "Percentage of value chain partners (by value of business done with such partners) that were assessed for environmental impacts.", "NUMBER", None, 30),
    ],
    "IND_P7_E": [
        ("Q_P7_E01", "a. Number of affiliations with trade and industry chambers/ associations. b. List the top 10 trade and industry chambers/ associations (determined based on the total members of such body) the entity is a member of/ affiliated to. S. No. Name of the trade and industry chambers/ associations Reach of trade and industry chambers/ associations (State/National) 1 2 3 4 5 6 7 8 9 10", "TEXT", None, 31),
        ("Q_P7_E02", "Provide details of corrective action taken or underway on any issues related to anti-competitive conduct by the entity, based on adverse orders from regulatory authorities. Name of authority Brief of the case Corrective action taken", "TABLE", None, 31),
    ],
    "IND_P7_L": [
        ("Q_P7_L01", "Details of public policy positions advocated by the entity: S. No. Public policy advocated Method resorted for such advocacy Whether information available in public domain? (Yes/No) Frequency of Review by Board (Annually/ Half yearly/ Quarterly / Others – please specify) Web Link, if available", "TABLE", None, 31),
    ],
    "IND_P8_E": [
        ("Q_P8_E01", "Details of Social Impact Assessments (SIA) of projects undertaken by the entity based on applicable laws, in the current financial year. Name and brief details of project SIA Notification No. Date of notification Whether conducted by independent external agency (Yes / No) Results communicated in public domain (Yes / No) Relevant Web link", "TABLE", None, 32),
        ("Q_P8_E02", "Provide information on project(s) for which ongoing Rehabilitation and Resettlement (R&R) is being undertaken by your entity, in the following format: S. No. Name of Project for which R&R is ongoing State District No. of Project Affected Families (PAFs) % of PAFs covered by R&R Amounts paid to PAFs in the FY (In INR)", "TABLE", 'INR', 32),
        ("Q_P8_E03", "Describe the mechanisms to receive and redress grievances of the community.", "TEXT", None, 32),
        ("Q_P8_E04", "Percentage of input material (inputs to total inputs by value) sourced from suppliers: FY _____ Current Financial Year FY _____ Previous Financial Year Directly sourced from MSMEs/ small producers Sourced directly from within the district and neighbouring districts", "NUMBER", None, 32),
    ],
    "IND_P8_L": [
        ("Q_P8_L01", "Provide details of actions taken to mitigate any negative social impacts identified in the Social Impact Assessments (Reference: Question 1 of Essential Indicators above): Details of negative social impact identified Corrective action taken", "TEXT", None, 32),
        ("Q_P8_L02", "Provide the following information on CSR projects undertaken by your entity in designated aspirational districts as identified by government bodies: S. No. State Aspirational District Amount spent (In INR)", "TABLE", 'INR', 33),
        ("Q_P8_L03", "(a) Do you have a preferential procurement policy where you give preference to purchase from suppliers comprising marginalized /vulnerable groups? (Yes/No) (b) From which marginalized /vulnerable groups do you procure? (c) What percentage of total procurement (by value) does it constitute?", "BOOLEAN", None, 33),
        ("Q_P8_L04", "Details of the benefits derived and shared from the intellectual properties owned or acquired by your entity (in the current financial year), based on traditional knowledge: S. No. Intellectual Property based on traditional knowledge Owned/ Acquired (Yes/No) Benefit shared (Yes / No) Basis of calculating benefit share", "TABLE", None, 33),
        ("Q_P8_L05", "Details of corrective actions taken or underway, based on any adverse order in intellectual property related disputes wherein usage of traditional knowledge is involved. Name of authority Brief of the Case Corrective action taken", "TABLE", None, 33),
        ("Q_P8_L06", "Details of beneficiaries of CSR Projects: S. No. CSR Project No. of persons benefitted from CSR Projects % of beneficiaries from vulnerable and marginalized groups", "TABLE", None, 33),
    ],
    "IND_P9_E": [
        ("Q_P9_E01", "Describe the mechanisms in place to receive and respond to consumer complaints and feedback.", "TEXT", None, 34),
        ("Q_P9_E02", "Turnover of products and/ services as a percentage of turnover from all products/service that carry information about: As a percentage to total turnover Environmental and social parameters relevant to the product Safe and responsible usage Recycling and/or safe disposal", "NUMBER", None, 34),
        ("Q_P9_E03", "Number of consumer complaints in respect of the following: FY _____ (Current Financial Year) Remarks FY _____ (Previous Financial Year) Remarks Received during the year Pending resolution at end of year Received during the year Pending resolution at end of year Data privacy Advertising Cyber-security Delivery of essential services Restrictive Trade Practices Unfair Trade Practices Other", "NUMBER", None, 34),
        ("Q_P9_E04", "Details of instances of product recalls on account of safety issues: Number Reasons for recall Voluntary recalls Forced recalls", "TABLE", None, 34),
        ("Q_P9_E05", "Does the entity have a framework/ policy on cyber security and risks related to data privacy? (Yes/No) If available, provide a web-link of the policy.", "BOOLEAN", None, 34),
        ("Q_P9_E06", "Provide details of any corrective actions taken or underway on issues relating to advertising, and delivery of essential services; cyber security and data privacy of customers; re-occurrence of instances of product recalls; penalty / action taken by regulatory authorities on safety of products / services.", "TEXT", None, 34),
    ],
    "IND_P9_L": [
        ("Q_P9_L01", "Channels / platforms where information on products and services of the entity can be accessed (provide web link, if available).", "TEXT", None, 35),
        ("Q_P9_L02", "Steps taken to inform and educate consumers about safe and responsible usage of products and/or services.", "TEXT", None, 35),
        ("Q_P9_L03", "Mechanisms in place to inform consumers of any risk of disruption/discontinuation of essential services.", "TEXT", None, 35),
        ("Q_P9_L04", "Does the entity display product information on the product over and above what is mandated as per local laws? (Yes/No/Not Applicable) If yes, provide details in brief. Did your entity carry out any survey with regard to consumer satisfaction relating to the major products / services of the entity, significant locations of operation of the entity or the entity as a whole? (Yes/No)", "BOOLEAN", None, 35),
        ("Q_P9_L05", "Provide the following information relating to data breaches: a. Number of instances of data breaches along-with impact b. Percentage of data breaches involving personally identifiable information of customers", "NUMBER", None, 35),
    ],
}


def seed_full_brsr(db: Session, counts: dict) -> None:
    """Seed the Full BRSR framework ("SEBI BRSR" v2021).

    Source
    ------
    support_materials/...Annexure1_p.pdf - "Annexure I: Business Responsibility &
    Sustainability Reporting Format" (SEBI circular 10-May-2021).  Question wording
    is transcribed verbatim; source PDF page numbers are retained on each row.

    Application-level decisions (NOT source-defined by SEBI)
    -------------------------------------------------------
    * ``response_type`` is inferred for the UI.  SEBI does not publish data types:
        TABLE  - the source prescribes a reporting table
        NUMBER - percentage / number / total / rate / quantity
        BOOLEAN- Yes/No, "Whether", "Does the entity ..."
        TEXT   - Describe / Provide details / Brief on / narrative
    * Sections A and B have no SEBI Essential/Leadership labelling, so their
      sub-headings are stored as indicators typed ESSENTIAL purely as an
      application-level classification.
    * Section A/B questions are marked mandatory as an application-level rule.
    * ``unit_of_measurement`` is populated ONLY where the source states a unit
      explicitly.  It is never inferred.
    * The 9 NGRBC principles, their titles and the Essential/Leadership split ARE
      source-defined.

    Idempotent
    ----------
    Every lookup is scoped by its parent foreign key, so re-running is safe and
    the existing "SEBI BRSR Core" 2023-24 framework is never read or modified.
    """
    framework = (
        db.query(BRSRFramework)
        .filter_by(name="SEBI BRSR", version="2021")
        .first()
    )
    if not framework:
        framework = BRSRFramework(
            name="SEBI BRSR",
            version="2021",
            description="Business Responsibility and Sustainability Reporting Format",
            is_active=True,
        )
        db.add(framework)
        db.flush()
        counts["frameworks"] += 1
        logger.info("Created BRSR Framework: SEBI BRSR v2021")

    # --- Sections (scoped by framework_id) ---
    sections = {}
    for code, title, description, order_index in BRSR_FULL_SECTIONS:
        section = (
            db.query(BRSRSection)
            .filter_by(code=code, framework_id=framework.id)
            .first()
        )
        if not section:
            section = BRSRSection(
                code=code,
                title=title,
                description=description,
                order_index=order_index,
                framework_id=framework.id,
            )
            db.add(section)
            db.flush()
            counts["sections"] += 1
            logger.info("Created BRSR Section: %s (%s)", code, title)
        sections[code] = section

    # --- Principles (scoped by section_id) ---
    principles = {}
    for number, code, title, description in BRSR_FULL_PRINCIPLES:
        principle = (
            db.query(BRSRPrinciple)
            .filter_by(code=code, section_id=sections["SEC_C"].id)
            .first()
        )
        if not principle:
            principle = BRSRPrinciple(
                principle_number=number,
                code=code,
                title=title,
                description=description,
                order_index=number,
                section_id=sections["SEC_C"].id,
            )
            db.add(principle)
            db.flush()
            counts["principles"] += 1
            logger.info("Created BRSR Principle: %s", title)
        principles[code] = principle

    # --- Indicators and questions (scoped by section_id / indicator_id) ---
    for ind_index, (code, section_code, principle_code, title, itype) in enumerate(
        BRSR_FULL_INDICATORS, start=1
    ):
        indicator_type = IndicatorType(itype)
        indicator = (
            db.query(BRSRIndicator)
            .filter_by(code=code, section_id=sections[section_code].id)
            .first()
        )
        if not indicator:
            indicator = BRSRIndicator(
                code=code,
                title=title,
                indicator_type=indicator_type,
                order_index=ind_index,
                section_id=sections[section_code].id,
                principle_id=principles[principle_code].id if principle_code else None,
            )
            db.add(indicator)
            db.flush()
            counts["indicators"] += 1
            logger.info("Created BRSR Indicator: %s - %s", code, title)

        # Section A/B are application-level mandatory; Section C follows the
        # source: Essential expected from every mandated filer, Leadership voluntary.
        section_a_or_b = principle_code is None

        for order_index, (q_code, text, rtype, unit, page) in enumerate(
            BRSR_FULL_QUESTIONS[code], start=1
        ):
            question = (
                db.query(BRSRQuestion)
                .filter_by(code=q_code, indicator_id=indicator.id)
                .first()
            )
            if not question:
                question = BRSRQuestion(
                    code=q_code,
                    question_text=text,
                    guidance=f"Source: SEBI BRSR Annexure I (2021), page {page}.",
                    response_type=QuestionResponseType(rtype),
                    unit_of_measurement=unit,
                    is_mandatory=True if section_a_or_b else (indicator_type == IndicatorType.ESSENTIAL),
                    order_index=order_index,
                    indicator_id=indicator.id,
                )
                db.add(question)
                counts["questions"] += 1

    logger.info(
        "Seeded Full BRSR (SEBI BRSR v2021): %d questions across %d indicators",
        sum(len(v) for v in BRSR_FULL_QUESTIONS.values()),
        len(BRSR_FULL_INDICATORS),
    )


def main() -> None:
    db = SessionLocal()
    try:
        results = seed_db(db)
        print("Seed Execution Finished.")
        print("Created records summary:", results)
    finally:
        db.close()


if __name__ == "__main__":
    main()
