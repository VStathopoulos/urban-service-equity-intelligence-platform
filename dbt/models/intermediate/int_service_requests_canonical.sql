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

),

category_mapping as (

    select
        source_system,
        service_category_original,
        service_category_standardized
    from {{ ref('category_mapping') }}

)

select
    unioned.service_request_key,
    unioned.source_system,
    unioned.source_city,
    unioned.source_country,

    unioned.request_id,
    unioned.created_at,
    unioned.closed_at,
    unioned.created_date,
    unioned.created_month,

    unioned.status,
    unioned.is_closed,
    unioned.is_open,

    unioned.service_category_original,
    unioned.service_subcategory_original,
    unioned.request_type_original,
    unioned.service_detail_original,

    coalesce(category_mapping.service_category_standardized, 'Other / Unmapped') as service_category_standardized,
    category_mapping.service_category_standardized is not null as is_category_mapped,

    unioned.agency_or_department,

    case
        when unioned.area_name is not null and btrim(unioned.area_name) <> '' then true
        else false
    end as has_area,

    coalesce(nullif(btrim(unioned.area_name), ''), 'Unknown / Not reported') as area_name,

    unioned.city_name,
    unioned.postal_code,

    unioned.latitude,
    unioned.longitude,
    unioned.has_geo,

    unioned.resolution_hours,
    unioned.resolution_days,
    unioned.is_sla_breach_72h,

    unioned.intake_channel,
    unioned.ingested_at_utc

from unioned
left join category_mapping
    on unioned.source_system = category_mapping.source_system
   and unioned.service_category_original = category_mapping.service_category_original
