with nyc as (

    select
        'nyc_311'::text as source_system,
        source_city,
        source_country,

        request_id,
        concat('nyc_311:', request_id) as service_request_key,

        created_at,
        closed_at,
        created_at::date as created_date,
        date_trunc('month', created_at)::date as created_month,

        status,
        is_closed,
        is_open,

        service_category_original,
        service_subcategory_original,
        null::text as request_type_original,
        null::text as service_detail_original,

        agency as agency_or_department,
        area_name,
        city_name,
        postal_code,

        latitude,
        longitude,
        has_geo,

        resolution_hours,
        resolution_hours / 24.0 as resolution_days,

        case
            when resolution_hours is not null and resolution_hours > 72 then true
            when resolution_hours is not null then false
            else null
        end as is_sla_breach_72h,

        open_data_channel_type as intake_channel,

        ingested_at_utc

    from {{ ref('stg_nyc_311_requests') }}

),

barcelona as (

    select
        'barcelona_iris'::text as source_system,
        source_city,
        source_country,

        request_id,
        concat('barcelona_iris:', request_id) as service_request_key,

        created_at,
        closed_at,
        created_at::date as created_date,
        date_trunc('month', created_at)::date as created_month,

        status,
        is_closed,
        is_open,

        service_category_original,
        service_subcategory_original,
        request_type_original,
        service_detail_original,

        null::text as agency_or_department,
        area_name,
        'Barcelona'::text as city_name,
        null::text as postal_code,

        latitude,
        longitude,
        has_geo,

        resolution_hours,
        resolution_hours / 24.0 as resolution_days,

        case
            when resolution_hours is not null and resolution_hours > 72 then true
            when resolution_hours is not null then false
            else null
        end as is_sla_breach_72h,

        support_channel as intake_channel,

        ingested_at_utc

    from {{ ref('stg_barcelona_iris_requests') }}

),

unioned as (

    select * from nyc
    union all
    select * from barcelona

)

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

    status,
    is_closed,
    is_open,

    service_category_original,
    service_subcategory_original,
    request_type_original,
    service_detail_original,

    null::text as service_category_standardized,
    false as is_category_mapped,

    agency_or_department,

    case
        when area_name is not null and btrim(area_name) <> '' then true
        else false
    end as has_area,

    coalesce(nullif(btrim(area_name), ''), 'Unknown / Not reported') as area_name,

    city_name,
    postal_code,

    latitude,
    longitude,
    has_geo,

    resolution_hours,
    resolution_days,
    is_sla_breach_72h,

    intake_channel,
    ingested_at_utc

from unioned
