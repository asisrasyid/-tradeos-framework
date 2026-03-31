-- Fix numeric overflow on bic_score in hmm_models
-- BIC values for large datasets (e.g. 11813 M15 bars) can exceed 1 billion
-- Change from NUMERIC(precision,scale) to DOUBLE PRECISION to handle any float value

ALTER TABLE hmm_models
    ALTER COLUMN bic_score TYPE DOUBLE PRECISION
    USING bic_score::DOUBLE PRECISION;
