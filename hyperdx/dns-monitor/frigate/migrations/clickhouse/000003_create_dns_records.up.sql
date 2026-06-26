CREATE TABLE IF NOT EXISTS dns_monitor.dns_records
(
    ts DateTime('UTC'),
    type LowCardinality(String) DEFAULT '',
    class LowCardinality(String) DEFAULT '',
    device_id String DEFAULT '',
    qtype LowCardinality(String) DEFAULT '',
    domain String DEFAULT '',
    client_ip String DEFAULT '',
    display_name String DEFAULT '',
    status LowCardinality(String) DEFAULT '',
    correlation_status LowCardinality(String) DEFAULT '',
    enrichment_status LowCardinality(String) DEFAULT '',
    cache_status LowCardinality(String) DEFAULT '',
    rcode LowCardinality(String) DEFAULT '',
    forwarded_to String DEFAULT '',
    is_external Bool DEFAULT false,
    rtt_ms UInt32 DEFAULT 0,
    upstream_resolver String DEFAULT '',
    upstream_rtt_ms UInt32 DEFAULT 0,
    upstream_correlation_status LowCardinality(String) DEFAULT '',
    answer_ips Array(String) DEFAULT [],
    cnames Array(String) DEFAULT [],
    payload String DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toDate(ts)
PRIMARY KEY (type, class, device_id, ts)
ORDER BY (type, class, device_id, ts)
TTL ts + INTERVAL 14 DAY DELETE
SETTINGS
    min_age_to_force_merge_seconds = 86400,
    min_age_to_force_merge_on_partition_only = 1,
    ttl_only_drop_parts = 1
