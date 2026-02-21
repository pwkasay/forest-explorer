-- stg_prism_normals.sql
-- Staging model: PRISM 30-year climate normals joined to FIA plot locations.
-- 1:1 with raw.prism_normals, adds derived climate classifications.

with source as (
    select * from {{ source('raw', 'prism_normals') }}
),

plots as (
    select * from {{ ref('stg_fia_plots') }}
),

enriched as (
    select
        s.plot_cn,
        p.state_code,
        p.county_code,
        p.latitude,
        p.longitude,
        s.annual_tmean_f,
        s.annual_ppt_in,
        s.jan_tmean_f,
        s.jul_tmean_f,
        s.growing_season_ppt_in,

        -- Derived: temperature range (continentality indicator)
        round((s.jul_tmean_f - s.jan_tmean_f)::numeric, 1) as temp_range_f,

        -- Derived: moisture classification
        case
            when s.annual_ppt_in >= 50 then 'wet'
            when s.annual_ppt_in >= 35 then 'moderate'
            else 'dry'
        end as moisture_class,

        s.ingested_at

    from source s
    inner join plots p on p.plot_cn = s.plot_cn
)

select * from enriched
