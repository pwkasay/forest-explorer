-- mart_plot_carbon_density.sql
-- Plot-level carbon summary with spatial coordinates.
-- Powers the map visualization: one point per plot with total carbon,
-- dominant species, stand characteristics, and ownership.

with plots as (
    select * from {{ ref('stg_fia_plots') }}
    where coord_quality = 'valid'
),

trees as (
    select * from {{ ref('stg_fia_trees') }}
    where tree_status = 'live'
),

conditions as (
    select * from {{ ref('stg_fia_conditions') }}
    where condition_id = 1  -- primary condition per plot
),

species_ref as (
    select * from {{ ref('species_ref') }}
),

plot_trees as (
    select
        t.plot_cn,
        sum(t.carbon_total_per_acre_lbs) as carbon_total_per_acre_lbs,
        sum(t.carbon_total_per_acre_lbs) / 2000.0 as carbon_total_per_acre_tons,
        sum(t.carbon_ag_per_acre_lbs) as carbon_ag_per_acre_lbs,
        sum(t.carbon_bg_per_acre_lbs) as carbon_bg_per_acre_lbs,
        sum(t.biomass_ag_lbs * t.trees_per_acre) as biomass_per_acre_lbs,
        count(*) as live_tree_count,
        count(distinct t.species_code) as species_richness,
        avg(t.diameter_inches) as avg_diameter_inches,
        avg(t.height_ft) as avg_height_ft,
        -- Dominant species by TPA contribution
        mode() within group (order by t.species_code) as dominant_species_code,
        -- Loblolly pine fraction
        sum(case when t.is_loblolly_pine then t.trees_per_acre else 0 end)
            / nullif(sum(t.trees_per_acre), 0) as loblolly_fraction
    from trees t
    group by t.plot_cn
)

select
    p.plot_cn,
    p.state_code,
    p.county_code,
    p.county_fips,
    p.inventory_year,
    p.latitude,
    p.longitude,
    p.elevation_ft,

    -- Carbon metrics
    pt.carbon_total_per_acre_tons,
    pt.carbon_ag_per_acre_lbs,
    pt.carbon_bg_per_acre_lbs,
    pt.biomass_per_acre_lbs,

    -- Forest structure
    pt.live_tree_count,
    pt.species_richness,
    pt.avg_diameter_inches,
    pt.avg_height_ft,
    pt.dominant_species_code,
    sr.common_name as dominant_species_name,
    pt.loblolly_fraction,

    -- Stand context
    c.stand_age_years,
    c.maturity_class,
    c.site_productivity,
    c.ownership_category,
    c.forest_type_code,
    c.slope_pct,

    -- Carbon density classification (for choropleth styling)
    case
        when pt.carbon_total_per_acre_tons >= 50 then 'very_high'
        when pt.carbon_total_per_acre_tons >= 30 then 'high'
        when pt.carbon_total_per_acre_tons >= 15 then 'medium'
        when pt.carbon_total_per_acre_tons >= 5 then 'low'
        else 'very_low'
    end as carbon_density_class

from plots p
inner join plot_trees pt on pt.plot_cn = p.plot_cn
left join conditions c on c.plot_cn = p.plot_cn
left join species_ref sr on sr.spcd = pt.dominant_species_code
