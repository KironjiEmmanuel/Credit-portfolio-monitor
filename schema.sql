
-- Two-table design:
--   loans_snapshot  -> APPEND-ONLY. One row per loan per extraction_date.
--                      This is what powers trend/vintage/roll-rate analysis.
--   loans_current   -> REPLACED on every run. Latest state only.
--                      This is what most dashboard views query for "today".

CREATE DATABASE IF NOT EXISTS loan_portfolio
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE loan_portfolio;

-- ----------------------------------------------------------------------------
-- loans_snapshot: history table, append-only
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans_snapshot (
    snapshot_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    extraction_date         DATE NOT NULL,          -- derived from filename/mtime, see etl.py
    loaded_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- identifiers
    member_no                INT NOT NULL,
    member_name               VARCHAR(255),
    loan_no                    VARCHAR(50),
    phone_number               VARCHAR(30),
    car_registration_number    VARCHAR(30),
    stage_name                 VARCHAR(255),

    -- org / collections
    branch_code                 VARCHAR(10),
    collection_champ_name        VARCHAR(255),
    collection_champion            VARCHAR(50),   -- code e.g. COL/011
    collection_troops               VARCHAR(50),   -- team code e.g. TRP/006
    collection_troops_name           VARCHAR(255),

    -- product
    loan_product_type            VARCHAR(50),
    loan_product_type_name         VARCHAR(255),
    asset_type                       VARCHAR(50),
    motor_bike_type                    VARCHAR(255),

    -- dates
    application_date              DATE,
    disbursement_date               DATE,
    repayment_start_date              DATE,
    expected_completion_date            DATE,
    last_pay_date                         DATE,

    -- risk / status (kept close to the source system's own field names, see legend on dashboard)
    days_in_arrears               DECIMAL(10,2),
    performance_category            VARCHAR(30),   -- source system's native label: Perfoming/Watch/Substandard/Doubtful/Loss
    par_band                          VARCHAR(30),  -- engineered, mirrors performance_category
    par_avg                              DECIMAL(10,4),
    loss_severity                         VARCHAR(20),   -- Loss sub-band (4-30d/31-90d/91-180d/181-365d/365d+), NULL unless par_band='Loss'
    watch_despite_good_standing             BOOLEAN,      -- 0 DPD today but PAR AVG > this snapshot's own 75th pct
      
    -- amounts
    approved_amount                DECIMAL(14,2),
    outstanding_balance              DECIMAL(14,2),
    total_outstanding_balance          DECIMAL(14,2),
    amount_in_arrears                    DECIMAL(14,2),
    net_balance                            DECIMAL(14,2),
    schedule_net_balance                     DECIMAL(14,2),
    security_amount                            DECIMAL(14,2),
    savings_balance                              DECIMAL(14,2),

    interest_due                    DECIMAL(14,2),
    interest_paid                     DECIMAL(14,2),
    total_amount_received               DECIMAL(14,2),
    total_scheduled_repayment             DECIMAL(14,2),

    repo_fee_count                   INT,
    installments                       INT,

    -- engineered fields (recomputed each run, stored for query convenience)
    collateral_coverage               DECIMAL(10,4),
    plan_deviation                      DECIMAL(14,2),
    plan_deviation_material_flag          BOOLEAN,   -- material threshold applied, see etl.py
    days_since_last_pay                     INT,
    flag_cold                                 BOOLEAN,
    flag_escalate                               BOOLEAN,
    collection_efficiency_pct                     DECIMAL(6,2),

    INDEX idx_extraction_date (extraction_date),
    INDEX idx_member_loan (member_no, loan_no),
    INDEX idx_branch (branch_code),
    INDEX idx_par_band (par_band),
    UNIQUE KEY uq_loan_snapshot (loan_no, extraction_date)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- loans_current: latest state, truncated + reloaded each run
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans_current LIKE loans_snapshot;
ALTER TABLE loans_current DROP INDEX uq_loan_snapshot;
ALTER TABLE loans_current ADD UNIQUE KEY uq_loan_no (loan_no);

-- ----------------------------------------------------------------------------
-- pipeline_run_log: lightweight audit trail of each ETL execution
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    run_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    started_at         DATETIME NOT NULL,
    finished_at          DATETIME,
    source_filename        VARCHAR(255),
    extraction_date          DATE,
    rows_loaded                INT,
    status                        ENUM('success','failed') DEFAULT 'success',
    error_message                   TEXT
) ENGINE=InnoDB;
