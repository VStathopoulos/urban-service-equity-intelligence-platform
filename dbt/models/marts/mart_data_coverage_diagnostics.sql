{{ config(materialized='table') }}

with base as (

    select
        source_city,
        source_country,
        source_system,
        created_date,
        service_category_standardized,
        is_open,
        is_closed,
        has_geo,
        latitude,
        longitude
    from {{ ref('fact_service_requests') }}

),

city_coverage as (

    select
        source_city,
        source_country,
        source_system,

        min(created_date) as first_request_date,
        max(created_date) as last_request_date,
        count(*) as record_count,

        count(*) filter (
            where has_geo
        ) as records_with_geo,

        count(*) filter (
            where not has_geo
               or has_geo is null
        ) as records_missing_geo,

        count(*) filter (
            where latitude is not null
              and longitude is not null
              and latitude between -90 and 90
              and longitude between -180 and 180
        ) as records_with_valid_lat_lon,

        count(distinct service_category_standardized) as distinct_service_categories,

        count(*) filter (
            where is_open
        ) as open_record_count,

        count(*) filter (
            where is_closed
        ) as closed_record_count

    from base
    group by
        source_city,
        source_country,
        source_system

),

common_window as (

    select
        max(first_request_date) as common_window_start,
        min(last_request_date) as common_window_end
    from city_coverage

),

diagnostics as (

    select
        c.source_city,
        c.source_country,
        c.source_system,
        c.first_request_date,
        c.last_request_date,

        (c.last_request_date - c.first_request_date + 1) as available_days,

        round(
            ((c.last_request_date - c.first_request_date + 1) / 365.25)::numeric,
            2
        ) as available_years,

        c.record_count,
        c.records_with_geo,
        c.records_missing_geo,

        round(
            100.0 * c.records_with_geo / nullif(c.record_count, 0),
            2
        ) as usable_geospatial_share_pct,

        round(
            100.0 * c.records_missing_geo / nullif(c.record_count, 0),
            2
        ) as missing_geospatial_share_pct,

        c.records_with_valid_lat_lon,

        round(
            100.0 * c.records_with_valid_lat_lon / nullif(c.record_count, 0),
            2
        ) as valid_lat_lon_share_pct,

        c.distinct_service_categories,
        c.open_record_count,
        c.closed_record_count,

        w.common_window_start,
        w.common_window_end,

        case
            when w.common_window_start <= w.common_window_end then true
            else false
        end as has_valid_common_window,

        case
            when w.common_window_start <= w.common_window_end
                then (w.common_window_end - w.common_window_start + 1)
            else 0
        end as common_window_days,

        count(b.*) filter (
            where w.common_window_start <= w.common_window_end
              and b.created_date between w.common_window_start and w.common_window_end
        ) as inside_common_window_record_count,

        round(
            100.0 * count(b.*) filter (
                where w.common_window_start <= w.common_window_end
                  and b.created_date between w.common_window_start and w.common_window_end
            ) / nullif(c.record_count, 0),
            2
        ) as inside_common_window_share_pct,

        case
            when w.common_window_start > w.common_window_end
                then 'No overlapping observation window across cities; use city-specific diagnostics only.'
            when c.records_with_valid_lat_lon = 0
                then 'No valid latitude/longitude records available for geospatial analysis.'
            when c.records_with_valid_lat_lon < c.record_count
                then 'Partial geospatial coverage; map-based analysis uses only valid latitude/longitude records.'
            else 'Coverage supports geospatial analysis for this city within the available observation window.'
        end as coverage_diagnostic_note

    from city_coverage c
    cross join common_window w
    left join base b
        on c.source_city = b.source_city
       and c.source_country = b.source_country
       and c.source_system = b.source_system

    group by
        c.source_city,
        c.source_country,
        c.source_system,
        c.first_request_date,
        c.last_request_date,
        c.record_count,
        c.records_with_geo,
        c.records_missing_geo,
        c.records_with_valid_lat_lon,
        c.distinct_service_categories,
        c.open_record_count,
        c.closed_record_count,
        w.common_window_start,
        w.common_window_end

)

select *
from diagnostics
order by source_city
