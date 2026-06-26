CREATE TABLE IF NOT EXISTS dns_monitor.counter_diffs
(
    ts DateTime('UTC'),
    type LowCardinality(String),
    value Map(String, UInt64)
)
ENGINE = MergeTree
PARTITION BY toDate(ts)
PRIMARY KEY (ts, type)
ORDER BY (ts, type)
TTL ts + INTERVAL 31 DAY DELETE
SETTINGS
    min_age_to_force_merge_seconds = 86400,
    min_age_to_force_merge_on_partition_only = 1,
    ttl_only_drop_parts = 1
