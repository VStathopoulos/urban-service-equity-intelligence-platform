with source as (

    select *
    from {{ source('raw_barcelona', 'barcelona_iris_requests') }}

),

cleaned as (

    select
        nullif(btrim(replace(fitxa_id::text, '"', '')), '') as request_id,

        nullif(btrim(replace(tipus::text, '"', '')), '') as request_type_original,
        nullif(btrim(replace(area::text, '"', '')), '') as service_category_original,
        nullif(btrim(replace(element::text, '"', '')), '') as service_subcategory_original,
        nullif(btrim(replace(detall::text, '"', '')), '') as service_detail_original,

        nullif(btrim(replace(districte::text, '"', '')), '') as district_name,
        nullif(btrim(replace(barri::text, '"', '')), '') as neighbourhood_name,

        nullif(btrim(replace(suport::text, '"', '')), '') as support_channel,
        nullif(btrim(replace(canals_resposta::text, '"', '')), '') as response_channel,

        nullif(btrim(replace(dia_data_alta::text, '"', '')), '') as created_day,
        nullif(btrim(replace(mes_data_alta::text, '"', '')), '') as created_month,
        nullif(btrim(replace(any_data_alta::text, '"', '')), '') as created_year,

        nullif(btrim(replace(dia_data_tancament::text, '"', '')), '') as closed_day,
        nullif(btrim(replace(mes_data_tancament::text, '"', '')), '') as closed_month,
        nullif(btrim(replace(any_data_tancament::text, '"', '')), '') as closed_year,

        nullif(replace(btrim(replace(latitud::text, '"', '')), ',', '.'), '') as latitude_text,
        nullif(replace(btrim(replace(longitud::text, '"', '')), ',', '.'), '') as longitude_text,

        ingested_at_utc::timestamptz as ingested_at_utc,
        source_system::text as source_system,
        source_url::text as source_url

    from source

),

typed as (

    select
        request_id,

        case
            when created_year ~ '^[0-9]{4}$'
             and created_month ~ '^[0-9]{1,2}$'
             and created_day ~ '^[0-9]{1,2}$'
             and created_month::int between 1 and 12
             and created_day::int between 1 and 31
                then make_timestamptz(
                    created_year::int,
                    created_month::int,
                    created_day::int,
                    0, 0, 0,
                    'Europe/Madrid'
                )
            else null
        end as created_at,

        case
            when closed_year ~ '^[0-9]{4}$'
             and closed_month ~ '^[0-9]{1,2}$'
             and closed_day ~ '^[0-9]{1,2}$'
             and closed_month::int between 1 and 12
             and closed_day::int between 1 and 31
                then make_timestamptz(
                    closed_year::int,
                    closed_month::int,
                    closed_day::int,
                    0, 0, 0,
                    'Europe/Madrid'
                )
            else null
        end as closed_at,

        request_type_original,
        service_category_original,
        service_subcategory_original,
        service_detail_original,

        district_name,
        neighbourhood_name,
        coalesce(neighbourhood_name, district_name) as area_name,

        support_channel,
        response_channel,

        case
            when latitude_text ~ '^-?[0-9]+(\.[0-9]+)?$'
                then latitude_text::double precision
            else null
        end as latitude,

        case
            when longitude_text ~ '^-?[0-9]+(\.[0-9]+)?$'
                then longitude_text::double precision
            else null
        end as longitude,

        ingested_at_utc,
        source_system,
        source_url,

        'Barcelona'::text as source_city,
        'Spain'::text as source_country

    from cleaned

),

final as (

    select
        request_id,
        created_at,
        closed_at,

        case
            when closed_at is not null then 'Closed'
            else 'Open or unknown'
        end as status,

        request_type_original,
        service_category_original,
        service_subcategory_original,
        service_detail_original,

        district_name,
        neighbourhood_name,
        area_name,

        support_channel,
        response_channel,

        latitude,
        longitude,

        case
            when closed_at is not null and created_at is not null
                then extract(epoch from (closed_at - created_at)) / 3600.0
            else null
        end as resolution_hours,

        case
            when closed_at is not null then true
            else false
        end as is_closed,

        case
            when closed_at is null then true
            else false
        end as is_open,

        case
            when latitude is not null and longitude is not null then true
            else false
        end as has_geo,

        ingested_at_utc,
        source_system,
        source_url,
        source_city,
        source_country

    from typed

)

,
deduplicated as (

    select
        *,
        count(*) over (partition by request_id) as raw_duplicate_count,
        row_number() over (
            partition by request_id
            order by ingested_at_utc desc, created_at desc, closed_at desc
        ) as duplicate_rank
    from final

)

select
    request_id,
    created_at,
    closed_at,
    status,

    request_type_original,
    service_category_original,
    service_subcategory_original,
    service_detail_original,

    district_name,
    neighbourhood_name,
    area_name,

    support_channel,
    response_channel,

    latitude,
    longitude,

    resolution_hours,
    is_closed,
    is_open,
    has_geo,

    raw_duplicate_count,

    ingested_at_utc,
    source_system,
    source_url,
    source_city,
    source_country

from deduplicated
where duplicate_rank = 1
