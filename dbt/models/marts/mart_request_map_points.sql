with fact as (

    select *
    from {{ ref('fact_service_requests') }}

),

valid_geo as (

    select
        service_request_key as map_point_id,
        service_request_key,
        source_system,
        source_city,
        source_country,

        request_id,
        created_at,
        closed_at,
        created_date,
        created_week,
        created_month,
        created_year,
        created_month_number,
        created_day_of_week,

        status,
        is_closed,
        is_open,

        service_category_standardized,
        service_category_original,
        service_subcategory_original,
        request_type_original,
        service_detail_original,

        area_name,
        has_area,
        city_name,
        postal_code,

        latitude,
        longitude,
        has_geo,

        resolution_hours,
        resolution_days,
        resolution_time_bucket,
        is_sla_breach_72h,
        sla_72h_proxy_status,

        intake_channel,
        ingested_at_utc

    from fact
    where has_geo is true
      and latitude is not null
      and longitude is not null
      and latitude between -90 and 90
      and longitude between -180 and 180

)

select *
from valid_geo
