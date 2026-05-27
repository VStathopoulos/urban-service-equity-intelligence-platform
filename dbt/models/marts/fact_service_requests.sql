with source as (

    select *
    from {{ ref('int_service_requests_canonical') }}

),

final as (

    select
        service_request_key,
        source_system,
        source_city,
        source_country,

        request_id,
        created_at,
        closed_at,
        created_date,
        created_month,

        date_trunc('week', created_at)::date as created_week,
        extract(year from created_at)::int as created_year,
        extract(month from created_at)::int as created_month_number,
        extract(dow from created_at)::int as created_day_of_week,

        status,
        is_closed,
        is_open,

        service_category_original,
        service_subcategory_original,
        service_category_standardized,
        is_category_mapped,

        request_type_original,
        service_detail_original,

        agency_or_department,
        has_area,
        area_name,
        city_name,
        postal_code,

        latitude,
        longitude,
        has_geo,

        resolution_hours,
        resolution_days,

        case
            when resolution_hours is null then 'No closed timestamp'
            when resolution_hours < 24 then '< 24 hours'
            when resolution_hours < 72 then '24–72 hours'
            when resolution_hours < 168 then '3–7 days'
            else '7+ days'
        end as resolution_time_bucket,

        is_sla_breach_72h,

        case
            when is_sla_breach_72h is true then 'Breached 72h proxy'
            when is_sla_breach_72h is false then 'Within 72h proxy'
            else 'Not closed / unknown'
        end as sla_72h_proxy_status,

        intake_channel,
        ingested_at_utc

    from source

)

select *
from final
