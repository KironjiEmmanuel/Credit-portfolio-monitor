-- SQLite dialect of schema.sql. Same three tables, same columns, same keys - only the
-- DDL syntax differs (AUTOINCREMENT, no ENGINE/ENUM, index names unique per database).
-- Used for the bundled demo database.

CREATE TABLE IF NOT EXISTS loans_snapshot (
    snapshot_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_date        DATE NOT NULL,
    loaded_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    member_no              INTEGER NOT NULL,
    member_name            VARCHAR(255),
    loan_no                VARCHAR(50),
    phone_number           VARCHAR(30),
    car_registration_number VARCHAR(30),
    stage_name             VARCHAR(255),

    branch_code            VARCHAR(10),
    collection_champ_name  VARCHAR(255),
    collection_champion    VARCHAR(50),
    collection_troops      VARCHAR(50),
    collection_troops_name VARCHAR(255),

    loan_product_type      VARCHAR(50),
    loan_product_type_name VARCHAR(255),
    asset_type             VARCHAR(50),
    motor_bike_type        VARCHAR(255),

    application_date       DATE,
    disbursement_date      DATE,
    repayment_start_date   DATE,
    expected_completion_date DATE,
    last_pay_date          DATE,

    days_in_arrears        DECIMAL(10,2),
    performance_category   VARCHAR(30),
    par_band               VARCHAR(30),
    par_avg                DECIMAL(10,4),
    loss_severity          VARCHAR(20),
    watch_despite_good_standing BOOLEAN,

    approved_amount        DECIMAL(14,2),
    outstanding_balance    DECIMAL(14,2),
    total_outstanding_balance DECIMAL(14,2),
    amount_in_arrears      DECIMAL(14,2),
    net_balance            DECIMAL(14,2),
    schedule_net_balance   DECIMAL(14,2),
    security_amount        DECIMAL(14,2),
    savings_balance        DECIMAL(14,2),

    interest_due           DECIMAL(14,2),
    interest_paid          DECIMAL(14,2),
    total_amount_received  DECIMAL(14,2),
    total_scheduled_repayment DECIMAL(14,2),

    repo_fee_count         INTEGER,
    installments           INTEGER,

    collateral_coverage    DECIMAL(10,4),
    plan_deviation         DECIMAL(14,2),
    plan_deviation_material_flag BOOLEAN,
    days_since_last_pay    INTEGER,
    flag_cold              BOOLEAN,
    flag_escalate          BOOLEAN,
    collection_efficiency_pct DECIMAL(6,2),

    UNIQUE (loan_no, extraction_date)
);
CREATE INDEX IF NOT EXISTS idx_snap_extraction_date ON loans_snapshot (extraction_date);
CREATE INDEX IF NOT EXISTS idx_snap_member_loan     ON loans_snapshot (member_no, loan_no);
CREATE INDEX IF NOT EXISTS idx_snap_branch          ON loans_snapshot (branch_code);
CREATE INDEX IF NOT EXISTS idx_snap_par_band        ON loans_snapshot (par_band);

CREATE TABLE IF NOT EXISTS loans_current (
    snapshot_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_date        DATE NOT NULL,
    loaded_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    member_no              INTEGER NOT NULL,
    member_name            VARCHAR(255),
    loan_no                VARCHAR(50),
    phone_number           VARCHAR(30),
    car_registration_number VARCHAR(30),
    stage_name             VARCHAR(255),

    branch_code            VARCHAR(10),
    collection_champ_name  VARCHAR(255),
    collection_champion    VARCHAR(50),
    collection_troops      VARCHAR(50),
    collection_troops_name VARCHAR(255),

    loan_product_type      VARCHAR(50),
    loan_product_type_name VARCHAR(255),
    asset_type             VARCHAR(50),
    motor_bike_type        VARCHAR(255),

    application_date       DATE,
    disbursement_date      DATE,
    repayment_start_date   DATE,
    expected_completion_date DATE,
    last_pay_date          DATE,

    days_in_arrears        DECIMAL(10,2),
    performance_category   VARCHAR(30),
    par_band               VARCHAR(30),
    par_avg                DECIMAL(10,4),
    loss_severity          VARCHAR(20),
    watch_despite_good_standing BOOLEAN,

    approved_amount        DECIMAL(14,2),
    outstanding_balance    DECIMAL(14,2),
    total_outstanding_balance DECIMAL(14,2),
    amount_in_arrears      DECIMAL(14,2),
    net_balance            DECIMAL(14,2),
    schedule_net_balance   DECIMAL(14,2),
    security_amount        DECIMAL(14,2),
    savings_balance        DECIMAL(14,2),

    interest_due           DECIMAL(14,2),
    interest_paid          DECIMAL(14,2),
    total_amount_received  DECIMAL(14,2),
    total_scheduled_repayment DECIMAL(14,2),

    repo_fee_count         INTEGER,
    installments           INTEGER,

    collateral_coverage    DECIMAL(10,4),
    plan_deviation         DECIMAL(14,2),
    plan_deviation_material_flag BOOLEAN,
    days_since_last_pay    INTEGER,
    flag_cold              BOOLEAN,
    flag_escalate          BOOLEAN,
    collection_efficiency_pct DECIMAL(6,2),

    UNIQUE (loan_no)
);
CREATE INDEX IF NOT EXISTS idx_cur_extraction_date ON loans_current (extraction_date);
CREATE INDEX IF NOT EXISTS idx_cur_member_loan     ON loans_current (member_no, loan_no);
CREATE INDEX IF NOT EXISTS idx_cur_branch          ON loans_current (branch_code);
CREATE INDEX IF NOT EXISTS idx_cur_par_band        ON loans_current (par_band);

CREATE TABLE IF NOT EXISTS pipeline_run_log (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       DATETIME NOT NULL,
    finished_at      DATETIME,
    source_filename  VARCHAR(255),
    extraction_date  DATE,
    rows_loaded      INTEGER,
    status           TEXT DEFAULT 'success' CHECK (status IN ('success','failed')),
    error_message    TEXT
);
