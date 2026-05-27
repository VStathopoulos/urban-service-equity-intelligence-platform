with fact as (

    select *
    from {{ ref('fact_service_requests') }}

),

aggregated as (

    select
        source_city,
        source_country,
        source_system,
        area_name,
        has_area,

        count(*) as total_requests,
        count(*) filter (where is_closed) as closed_requests,
        count(*) filter (where is_open) as open_requests,

        round(
            100.0 * count(*) filter (where is_open) / nullif(count(*), 0),
            2
        ) as open_backlog_rate_pct,

        count(*) filter (where has_geo) as geocoded_requests,

        round(
            100.0 * count(*) filter (where has_geo) / nullif(count(*), 0),
            2
        ) as geocoded_rate_pct,

        avg(latitude) filter (where has_geo) as area_centroid_latitude,
        avg(longitude) filter (where has_geo) as area_centroid_longitude,

        percentile_cont(0.5) within group (
            order by resolution_hours
        ) filter (where resolution_hours is not null) as median_resolution_hours,

        percentile_cont(0.9) within group (
            order by resolution_hours
        ) filter (where resolution_hours is not null) as p90_resolution_hours,

        count(*) filter (where is_sla_breach_72h) as sla_breach_72h_requests,

        round(
            100.0 * count(*) filter (where is_sla_breach_72h)
            / nullif(count(*) filter (where is_closed), 0),
            2
        ) as sla_breach_72h_rate_closed_pct,

        min(created_at) as first_created_at,
        max(created_at) as last_created_at,
        max(ingested_at_utc) as latest_ingested_at_utc

    from fact
    group by
        source_city,
        source_country,
        source_system,
        area_name,
        has_area

)

select *
from aggregated
