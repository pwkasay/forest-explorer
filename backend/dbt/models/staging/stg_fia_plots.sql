-- stg_fia_plots.sql
-- Staging model: clean raw FIA plot data with validated coordinates.
-- 1:1 with raw.fia_plot, adds computed fields and filters.

with source as (
    select * from {{ source('raw', 'fia_plot') }}
),

validated as (
    select
        cn as plot_cn,
        statecd as state_code,
        unitcd as unit_code,
        countycd as county_code,
        plot as plot_number,
        invyr as inventory_year,
        lat as latitude,
        lon as longitude,
        elev as elevation_ft,
        ecosubcd as ecological_subsection,
        geom,

        -- Derived: FIPS code for county joins
        lpad(statecd::text, 2, '0') || lpad(countycd::text, 3, '0') as county_fips,

        -- Data quality flags
        case
            when lat is null or lon is null then 'missing_coords'
            when lat < 24.0 or lat > 50.0 or lon < -125.0 or lon > -66.0 then 'out_of_bounds'
            else 'valid'
        end as coord_quality,

        ingested_at

    from source
    where lat is not null
      and lon is not null
)

select * from validated
