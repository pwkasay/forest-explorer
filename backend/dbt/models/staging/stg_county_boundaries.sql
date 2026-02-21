-- stg_county_boundaries.sql
-- Staging model: Census TIGER county boundaries with derived area fields.
-- 1:1 with raw.county_boundaries.

with source as (
    select * from {{ source('raw', 'county_boundaries') }}
),

renamed as (
    select
        geoid as county_fips,
        name as county_name,
        statecd as state_code,
        countycd as county_code,
        aland as land_area_sqm,
        awater as water_area_sqm,
        geom,

        -- Derived: area in acres (1 sq meter = 0.000247105 acres)
        round((aland * 0.000247105)::numeric, 0) as land_area_acres,
        round(((aland + coalesce(awater, 0)) * 0.000247105)::numeric, 0) as total_area_acres,

        ingested_at

    from source
)

select * from renamed
