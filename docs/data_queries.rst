.. index:: data queries

Data query examples
===================

Get network flows
-----------------
This example shows how to get the network flows for a given IP address::

    SELECT
    time as Time,
    application_category_name as Category,
    application_name as Application,
    risk as Risk,
    json_extract(enrichment, '$.geoip.country') as Country,
    json_extract(enrichment, '$.src_hostname') as "Src hostname",
    src_ip as Source,
    json_extract(enrichment, '$.dst_hostname') as "Dst hostname",
    dst_ip as Destination,
    requested_server_name as Request,
    bidirectional_bytes as "I/O"
    FROM network_dpi
    WHERE src_ip=="<client IP>" OR dst_ip=="<client IP>"
    ORDER BY timestamp DESC;



Get security alerts
------------------
This example shows how to get the security alerts for a given IP address::

    SELECT
    time as Time,
    category as Category,
    severity as Severity,
    json_extract(enrichment, '$.geoip.country') as Country,
    src_ip as Source,
    dst_ip as Destination,
    signature as Signature
    FROM network_alert
    WHERE src_ip=="<client IP>" OR dst_ip=="<client IP>"
    ORDER BY timestamp DESC;
