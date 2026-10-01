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

    db.commit()
    logger.info("Database seeding completed successfully.")
    return counts


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
