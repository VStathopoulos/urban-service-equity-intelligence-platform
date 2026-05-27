with source as (

    select *
    from {{ source('raw_nyc', 'nyc_311_requests') }}

),

renamed as (

    select
        unique_key::text as request_id,

        created_date::timestamptz as created_at,
        closed_date::timestamptz as closed_at,

        agency::text as agency,
        agency_name::text as agency_name,

        complaint_type::text as service_category_original,
        descriptor::text as service_subcategory_original,
        location_type::text as location_type,

        incident_zip::text as postal_code,
        incident_address::text as incident_address,
        street_name::text as street_name,
        cross_street_1::text as cross_street_1,
        cross_street_2::text as cross_street_2,
        address_type::text as address_type,

        city::text as city_name,
        borough::text as area_name,

        status::text as status,
        resolution_description::text as resolution_description,

        latitude::double precision as latitude,
        longitude::double precision as longitude,

        open_data_channel_type::text as open_data_channel_type,

        ingested_at_utc::timestamptz as ingested_at_utc,
        source_system::text as source_system,
        source_dataset_id::text as source_dataset_id,

        case
            when closed_date is not null
                then extract(epoch from (closed_date::timestamptz - created_date::timestamptz)) / 3600.0
            else null
        end as resolution_hours,

        case
            when closed_date is not null then true
            else false
        end as is_closed,

        case
            when closed_date is null then true
            else false
        end as is_open,

        case
            when latitude is not null and longitude is not null then true
            else false
        end as has_geo,

        'NYC'::text as source_city,
        'USA'::text as source_country

    from source

)

select *
from renamed
