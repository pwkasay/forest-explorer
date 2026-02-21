-- mart_carbon_by_species.sql
-- Business-ready: carbon storage metrics by tree species.
-- This is the model that powers the dashboard's species comparison charts.
-- Aggregates from staging trees + species reference seed.

with trees as (
    select * from {{ ref('stg_fia_trees') }}
    where tree_status = 'live'
),

species_ref as (
    select * from {{ ref('species_ref') }}
),

species_carbon as (
    select
        t.species_code,
        sr.common_name as species_name,
        sr.genus,
        sr.family,
        t.state_code,

        count(*) as tree_count,
        count(distinct t.plot_cn) as plot_count,

        -- Per-acre carbon metrics (the numbers that matter)
        avg(t.carbon_total_per_acre_lbs) as avg_carbon_per_acre_lbs,
        avg(t.carbon_total_per_acre_lbs) / 2000.0 as avg_carbon_per_acre_tons,
        avg(t.carbon_ag_per_acre_lbs) as avg_carbon_ag_per_acre_lbs,
        avg(t.carbon_bg_per_acre_lbs) as avg_carbon_bg_per_acre_lbs,

        -- Tree size metrics
        avg(t.diameter_inches) as avg_diameter_inches,
        avg(t.height_ft) as avg_height_ft,
        max(t.diameter_inches) as max_diameter_inches,

        -- Biomass
        avg(t.biomass_ag_lbs * t.trees_per_acre) as avg_biomass_per_acre_lbs,

        -- Loblolly flag for Funga-relevant filtering
        bool_or(t.is_loblolly_pine) as includes_loblolly

    from trees t
    left join species_ref sr on sr.spcd = t.species_code
    group by t.species_code, sr.common_name, sr.genus, sr.family, t.state_code
    having count(distinct t.plot_cn) >= 3  -- minimum sample size
)

select
    *,
    -- Rank within state by carbon density
    row_number() over (
        partition by state_code
        order by avg_carbon_per_acre_tons desc
    ) as carbon_rank

from species_carbon
