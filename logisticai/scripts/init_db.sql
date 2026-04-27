-- LogisticAI local development database schema
-- Mirrors the Spanner schema for local dev without GCP

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    tier        VARCHAR(20) DEFAULT 'starter',
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id             VARCHAR(36) PRIMARY KEY,
    tenant_id               VARCHAR(36) NOT NULL REFERENCES tenants(tenant_id),
    carrier_id              VARCHAR(64),
    status                  VARCHAR(20) DEFAULT 'on_track',
    current_hub             VARCHAR(32),
    destination             VARCHAR(32),
    current_route           JSONB DEFAULT '[]',
    current_route_cost      DECIMAL(10,2) DEFAULT 0,
    risk_score              DECIMAL(5,4) DEFAULT 0,
    delay_prediction_minutes INTEGER DEFAULT 0,
    lat                     DECIMAL(9,6),
    lon                     DECIMAL(9,6),
    optimization_weights    JSONB DEFAULT '{"cost":0.33,"time":0.34,"risk":0.33}',
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shipments_tenant_risk
    ON shipments (tenant_id, risk_score DESC)
    WHERE status != 'delivered';

CREATE TABLE IF NOT EXISTS reroute_audit_log (
    audit_id            VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    shipment_id         VARCHAR(36) NOT NULL REFERENCES shipments(shipment_id),
    old_route           JSONB,
    new_route           JSONB,
    cost_delta_usd      DECIMAL(10,2),
    risk_delta          DECIMAL(5,4),
    autonomy_level      VARCHAR(20),
    confidence          DECIMAL(5,4),
    disruption_event_id VARCHAR(36),
    reroute_reason      VARCHAR(128),
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS disruptions (
    disruption_id   VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    tenant_id       VARCHAR(36),
    type            VARCHAR(32) NOT NULL,
    severity        DECIMAL(3,2) NOT NULL,
    affected_nodes  JSONB DEFAULT '[]',
    duration_hours  INTEGER DEFAULT 6,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Seed demo tenant
INSERT INTO tenants (tenant_id, name, tier)
VALUES ('demo-tenant', 'LogisticAI Demo', 'enterprise')
ON CONFLICT DO NOTHING;
